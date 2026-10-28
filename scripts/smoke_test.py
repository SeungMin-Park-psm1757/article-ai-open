"""Run a local-only smoke check with a newly generated synthetic PDF."""
import argparse
import io
import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import core

SENTENCE = 'Synthetic research documents can be searched locally.'


def synthetic_pdf():
    text = f'BT /F1 12 Tf 72 720 Td ({SENTENCE}) Tj ET\n'.encode('ascii')
    objects = [
        b'<< /Type /Catalog /Pages 2 0 R >>',
        b'<< /Type /Pages /Kids [3 0 R] /Count 1 >>',
        b'<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 5 0 R >> >> /Contents 4 0 R >>',
        b'<< /Length ' + str(len(text)).encode('ascii') + b' >>\nstream\n' + text + b'endstream',
        b'<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>',
    ]
    output = io.BytesIO()
    output.write(b'%PDF-1.4\n')
    offsets = [0]
    for number, obj in enumerate(objects, 1):
        offsets.append(output.tell())
        output.write(f'{number} 0 obj\n'.encode('ascii') + obj + b'\nendobj\n')
    xref = output.tell()
    output.write(f'xref\n0 {len(offsets)}\n'.encode('ascii'))
    output.write(b'0000000000 65535 f \n')
    for offset in offsets[1:]:
        output.write(f'{offset:010d} 00000 n \n'.encode('ascii'))
    output.write(f'trailer\n<< /Size {len(offsets)} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n'.encode('ascii'))
    return output.getvalue()


def run(model_root=None, reranker=False):
    result = {'fixture': 'synthetic', 'core': 'NOT_RUN', 'embedding': 'NOT_RUN',
              'reranker': 'NOT_RUN', 'llm': 'NOT_IMPLEMENTED', 'gpu_profile': 'NOT_VERIFIED'}
    if reranker and model_root is None:
        raise ValueError('--reranker requires --model-root')
    with tempfile.TemporaryDirectory(prefix='article-ai-smoke-') as folder:
        db = core.connect(Path(folder) / 'documents.sqlite3')
        try:
            if db.execute('SELECT COUNT(*) FROM documents').fetchone()[0] != 0:
                raise RuntimeError('Synthetic database is not empty')
            data = synthetic_pdf()
            document_id, extracted = core.add_pdf(db, 'Synthetic example', data)
            matches = core.search(db, 'Synthetic research')
            inspected = core.inspect(db, SENTENCE)
            if extracted != 1 or len(matches) != 1 or matches[0][2] != 1 or len(inspected) != 1:
                raise RuntimeError('Synthetic extraction, search, or inspection failed')
            if db.execute('SELECT pdf FROM documents WHERE id=?', (document_id,)).fetchone()[0] != data:
                raise RuntimeError('Stored PDF does not match the original')
            report_id = core.save_report(db, 'Synthetic report')
            if db.execute('SELECT content FROM reports WHERE id=?', (report_id,)).fetchone()[0] != 'Synthetic report':
                raise RuntimeError('Report persistence check failed')
            result['core'] = 'PASS'
            if model_root is not None:
                import semantic
                model = semantic.load_model(model_root)
                semantic.rebuild(db, model)
                candidates = semantic.search(db, model, 'synthetic research')
                if not candidates or candidates[0][3] != 1 or SENTENCE not in candidates[0][-1]:
                    raise RuntimeError('Semantic result or source page check failed')
                result['embedding'] = 'PASS'
                if reranker:
                    rerank_model = semantic.load_reranker(model_root)
                    ranked = semantic.rerank(db, rerank_model, 'synthetic research', candidates)
                    if not ranked or ranked[0][1][3] != 1 or SENTENCE not in ranked[0][1][-1]:
                        raise RuntimeError('Reranking source check failed')
                    result['reranker'] = 'PASS'
        finally:
            db.close()
    return result


def main():
    parser = argparse.ArgumentParser(description='Test only a temporary synthetic corpus, never your documents.')
    parser.add_argument('--model-root', type=Path)
    parser.add_argument('--reranker', action='store_true')
    args = parser.parse_args()
    try:
        print(json.dumps(run(args.model_root, args.reranker), ensure_ascii=False))
    except (OSError, ValueError, RuntimeError) as exc:
        print(f'Smoke test failed: {exc}', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
