"""Isolated CPU semantic index with page-offset provenance."""
import hashlib
import json
from pathlib import Path

import numpy as np

from scripts.install_models import LOCK, safe_file, verified

DIMENSIONS = 1024
CHUNK_SIZE = 1000
OVERLAP = 200
MAX_CHUNKS = 2000
INDEX_VERSION = 'page-window-v1'


def model_spec(role='embedding'):
    return next(model for model in json.loads(LOCK.read_text(encoding='utf-8'))['models'] if model['role'] == role)


def _verified_model_path(root, role):
    spec = model_spec(role)
    path = Path(root) / spec['repo'].replace('/', '--')
    if not path.is_dir() or path.is_symlink():
        raise ValueError(f'고정된 {role} 모델 폴더를 찾을 수 없습니다.')
    for entry in spec['files']:
        file = safe_file(path, entry['path'])
        if not verified(file, entry):
            raise ValueError(f"{role} 모델 파일 검증 실패: {entry['path']}")
    return path


def load_model(root):
    path = _verified_model_path(root, 'embedding')
    try:
        from sentence_transformers import SentenceTransformer
    except ImportError as exc:
        raise ValueError('의미 검색용 의존성이 설치되지 않았습니다.') from exc
    return SentenceTransformer(str(path), device='cpu', local_files_only=True, trust_remote_code=False)


def load_reranker(root):
    path = _verified_model_path(root, 'reranker')
    try:
        from sentence_transformers import CrossEncoder
    except ImportError as exc:
        raise ValueError('리랭커용 의존성이 설치되지 않았습니다.') from exc
    return CrossEncoder(str(path), device='cpu', local_files_only=True, trust_remote_code=False)


def _snapshot(db):
    rows = db.execute('''SELECT d.id,d.sha256,p.page,p.text FROM pages p
        JOIN documents d ON d.id=p.document_id ORDER BY d.id,p.page''').fetchall()
    digest = hashlib.sha256()
    for doc_id, sha, page, text in rows:
        digest.update(json.dumps([doc_id, sha, page, text], ensure_ascii=False, separators=(',', ':')).encode('utf-8'))
        digest.update(b'\n')
    return rows, digest.hexdigest()


def _windows(rows):
    chunks = []
    for doc_id, sha, page, text in rows:
        for start in range(0, len(text), CHUNK_SIZE - OVERLAP):
            end = min(start + CHUNK_SIZE, len(text))
            passage = text[start:end]
            if passage.strip():
                chunks.append((doc_id, sha, page, start, end, passage))
            if end == len(text):
                break
            if len(chunks) > MAX_CHUNKS:
                raise ValueError('실험 색인은 최대 2,000개 구간까지 지원합니다.')
    if len(chunks) > MAX_CHUNKS:
        raise ValueError('실험 색인은 최대 2,000개 구간까지 지원합니다.')
    return chunks


def _vectors(model, texts, query=False):
    kwargs = {'prompt_name': 'query'} if query else {}
    vectors = np.asarray(model.encode(texts, batch_size=4, **kwargs), dtype=np.float32)
    if vectors.shape != (len(texts), DIMENSIONS) or not np.isfinite(vectors).all():
        raise ValueError('임베딩 차원 또는 값이 올바르지 않습니다.')
    norms = np.linalg.norm(vectors, axis=1)
    if not np.isfinite(norms).all() or np.any(norms <= 0):
        raise ValueError('임베딩 벡터의 크기가 올바르지 않습니다.')
    vectors = vectors / norms[:, None]
    return vectors


def rebuild(db, model):
    rows, fingerprint = _snapshot(db)
    chunks = _windows(rows)
    if not chunks:
        raise ValueError('색인할 텍스트가 없습니다. 문헌을 먼저 등록하세요.')
    vectors = _vectors(model, [chunk[-1] for chunk in chunks])
    revision = model_spec()['revision']
    with db:
        db.execute('BEGIN IMMEDIATE')
        if _snapshot(db)[1] != fingerprint:
            raise ValueError('색인 중 문헌이 변경되었습니다. 다시 시도하세요.')
        db.execute('CREATE TABLE IF NOT EXISTS semantic_meta (fingerprint TEXT NOT NULL, revision TEXT NOT NULL, version TEXT NOT NULL, chunk_count INTEGER NOT NULL)')
        db.execute('''CREATE TABLE IF NOT EXISTS semantic_chunks (
            document_id INTEGER NOT NULL, document_sha256 TEXT NOT NULL, page INTEGER NOT NULL,
            start INTEGER NOT NULL, end INTEGER NOT NULL, vector BLOB NOT NULL,
            PRIMARY KEY(document_id,page,start),
            FOREIGN KEY(document_id,page) REFERENCES pages(document_id,page) ON DELETE CASCADE)''')
        db.execute('DELETE FROM semantic_chunks')
        db.execute('DELETE FROM semantic_meta')
        db.executemany('INSERT INTO semantic_chunks VALUES(?,?,?,?,?,?)',
                       [(doc_id, sha, page, start, end, vector.astype('<f4').tobytes())
                        for (doc_id, sha, page, start, end, _), vector in zip(chunks, vectors)])
        db.execute('INSERT INTO semantic_meta VALUES(?,?,?,?)', (fingerprint, revision, INDEX_VERSION, len(chunks)))
    return len(chunks)


def search(db, model, query, limit=10):
    if not query.strip() or len(query) > 500:
        raise ValueError('검색어는 1~500자여야 합니다.')
    if not 1 <= limit <= 100:
        raise ValueError('결과 개수는 1~100이어야 합니다.')
    has_meta = db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='semantic_meta'").fetchone()
    if not has_meta:
        raise ValueError('의미 색인을 먼저 생성하세요.')
    meta = db.execute('SELECT fingerprint,revision,version,chunk_count FROM semantic_meta').fetchone()
    if not meta or meta[:3] != (_snapshot(db)[1], model_spec()['revision'], INDEX_VERSION):
        raise ValueError('문헌 또는 모델이 변경되어 색인을 다시 만들어야 합니다.')
    query_vector = _vectors(model, [query.strip()], query=True)[0]
    rows = db.execute('''SELECT c.document_id,d.title,c.page,c.start,c.end,p.text,c.vector
        FROM semantic_chunks c JOIN documents d ON d.id=c.document_id
        JOIN pages p ON p.document_id=c.document_id AND p.page=c.page''').fetchall()
    if len(rows) != meta[3] or _snapshot(db)[1] != meta[0]:
        raise ValueError('색인이 손상되었거나 문헌이 변경되었습니다. 다시 생성하세요.')
    found = []
    for doc_id, title, page, start, end, text, raw in rows:
        if len(raw) != DIMENSIONS * 4 or not (0 <= start < end <= len(text)):
            raise ValueError('색인이 손상되었습니다. 다시 생성하세요.')
        vector = np.frombuffer(raw, dtype='<f4')
        if not np.isfinite(vector).all() or not np.isclose(np.linalg.norm(vector), 1, atol=1e-4):
            raise ValueError('색인 벡터가 손상되었습니다. 다시 생성하세요.')
        found.append((float(np.dot(query_vector, vector)), doc_id, title, page, start, end, text[start:end]))
    return sorted(found, key=lambda item: (-item[0], item[1], item[3], item[4]))[:limit]


def _verify_sources(db, candidates):
    for _, doc_id, title, page, start, end, passage in candidates:
        row = db.execute('''SELECT d.title,p.text FROM pages p JOIN documents d ON d.id=p.document_id
            WHERE p.document_id=? AND p.page=?''', (doc_id, page)).fetchone()
        if not row or row[0] != title or not (0 <= start < end <= len(row[1])) or row[1][start:end] != passage:
            raise ValueError('후보의 원문 출처가 변경되었거나 일치하지 않습니다.')


def rerank(db, model, query, candidates):
    if not query.strip() or len(query) > 500 or len(candidates) > 100:
        raise ValueError('검색어나 후보의 크기가 허용 범위를 벗어났습니다.')
    if not candidates:
        return []
    meta = db.execute('SELECT fingerprint,revision,version FROM semantic_meta').fetchone()
    before = _snapshot(db)[1]
    if not meta or meta != (before, model_spec()['revision'], INDEX_VERSION):
        raise ValueError('문헌 또는 모델이 변경되어 색인을 다시 만들어야 합니다.')
    _verify_sources(db, candidates)
    scores = np.asarray(model.predict([(query.strip(), item[-1]) for item in candidates], batch_size=2), dtype=np.float32).reshape(-1)
    if scores.shape != (len(candidates),) or not np.isfinite(scores).all():
        raise ValueError('리랭커 점수가 올바르지 않습니다.')
    if _snapshot(db)[1] != before:
        raise ValueError('리랭킹 중 문헌이 변경되었습니다. 다시 검색하세요.')
    _verify_sources(db, candidates)
    return sorted(zip((float(score) for score in scores), candidates), key=lambda item: -item[0])
