import sqlite3
import tempfile
import unittest
from pathlib import Path

import numpy as np

import core
import semantic


class FakeEncoder:
    def encode(self, texts, **kwargs):
        self.last_kwargs = kwargs
        vectors = np.zeros((len(texts), semantic.DIMENSIONS), dtype=np.float32)
        for index, text in enumerate(texts):
            vectors[index, 0 if 'plants' in text else 1] = 2
        return vectors


class SemanticTests(unittest.TestCase):
    def test_offsets_stale_index_and_failed_rebuild(self):
        with tempfile.TemporaryDirectory() as directory:
            db = core.connect(Path(directory) / 'data.sqlite3')
            with db:
                db.execute("INSERT INTO documents(id,sha256,title,pdf) VALUES(1,'synthetic','Example',X'00')")
                db.execute('INSERT INTO pages VALUES(?,?,?)', (1, 1, 'plants grow in light ' * 90))
            model = FakeEncoder()
            count = semantic.rebuild(db, model)
            self.assertGreater(count, 1)
            results = semantic.search(db, model, 'plants')
            self.assertEqual(model.last_kwargs['prompt_name'], 'query')
            for _, doc_id, _, page, start, end, passage in results:
                original = db.execute('SELECT text FROM pages WHERE document_id=? AND page=?', (doc_id, page)).fetchone()[0]
                self.assertEqual(passage, original[start:end])
            class InvalidEncoder:
                def encode(self, texts, **kwargs):
                    return np.zeros((len(texts), semantic.DIMENSIONS))
            with self.assertRaises(ValueError):
                semantic.rebuild(db, InvalidEncoder())
            self.assertEqual(db.execute('SELECT COUNT(*) FROM semantic_chunks').fetchone()[0], count)
            with db:
                db.execute('UPDATE pages SET text=? WHERE document_id=1 AND page=1', ('changed text',))
            with self.assertRaisesRegex(ValueError, '다시'):
                semantic.search(db, model, 'plants')
            db.close()

    def test_corrupt_index_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            db = core.connect(Path(directory) / 'data.sqlite3')
            with db:
                db.execute("INSERT INTO documents(id,sha256,title,pdf) VALUES(1,'s','Example',X'00')")
                db.execute("INSERT INTO pages VALUES(1,1,'plants')")
            model = FakeEncoder()
            semantic.rebuild(db, model)
            with db:
                db.execute("UPDATE semantic_chunks SET vector=X'00'")
            with self.assertRaisesRegex(ValueError, '손상'):
                semantic.search(db, model, 'plants')
            db.close()

    def test_document_change_during_rebuild_keeps_existing_index(self):
        with tempfile.TemporaryDirectory() as directory:
            db = core.connect(Path(directory) / 'data.sqlite3')
            with db:
                db.execute("INSERT INTO documents(id,sha256,title,pdf) VALUES(1,'s','Example',X'00')")
                db.execute("INSERT INTO pages VALUES(1,1,'plants')")
            semantic.rebuild(db, FakeEncoder())
            old_meta = db.execute('SELECT * FROM semantic_meta').fetchone()

            class ChangingEncoder(FakeEncoder):
                def encode(self, texts, **kwargs):
                    with db:
                        db.execute("UPDATE pages SET text='changed' WHERE document_id=1 AND page=1")
                    return super().encode(texts, **kwargs)

            with self.assertRaisesRegex(ValueError, '변경'):
                semantic.rebuild(db, ChangingEncoder())
            self.assertEqual(db.execute('SELECT * FROM semantic_meta').fetchone(), old_meta)
            with self.assertRaisesRegex(ValueError, '다시'):
                semantic.search(db, FakeEncoder(), 'plants')
            db.close()

    def test_reranking_preserves_evidence_and_rejects_invalid_scores(self):
        with tempfile.TemporaryDirectory() as directory:
            db = core.connect(Path(directory) / 'data.sqlite3')
            with db:
                db.execute("INSERT INTO documents(id,sha256,title,pdf) VALUES(1,'s','Example',X'00')")
                db.execute("INSERT INTO pages VALUES(1,1,'plants')")
                db.execute("INSERT INTO pages VALUES(1,2,'other')")
            encoder = FakeEncoder()
            semantic.rebuild(db, encoder)
            candidates = semantic.search(db, encoder, 'plants')

            class Reranker:
                def predict(self, pairs, **kwargs):
                    return np.array([-2.0, 3.0])

            ranked = semantic.rerank(db, Reranker(), 'plants', candidates)
            self.assertEqual(ranked[0][1], candidates[1])
            self.assertEqual(ranked[1][1], candidates[0])

            class InvalidReranker:
                def predict(self, pairs, **kwargs):
                    return np.array([float('nan'), 0.0])

            with self.assertRaisesRegex(ValueError, '점수'):
                semantic.rerank(db, InvalidReranker(), 'plants', candidates)
            altered = [(*candidates[0][:-1], 'invented')]
            with self.assertRaisesRegex(ValueError, '출처'):
                semantic.rerank(db, Reranker(), 'plants', altered)
            class RenamingReranker(Reranker):
                def predict(self, pairs, **kwargs):
                    core.rename_document(db, 1, 'Renamed')
                    return super().predict(pairs, **kwargs)
            with self.assertRaisesRegex(ValueError, '출처'):
                semantic.rerank(db, RenamingReranker(), 'plants', candidates)
            db.close()


if __name__ == '__main__':
    unittest.main()
