import io
import sqlite3
import tempfile
import unittest
from pathlib import Path

from pypdf import PdfWriter

import core
import ontology


class OntologyTests(unittest.TestCase):
    def test_existing_document_store_gains_empty_concept_schema(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'legacy.sqlite3'
            old = sqlite3.connect(path)
            old.execute('CREATE TABLE documents (id INTEGER PRIMARY KEY, sha256 TEXT NOT NULL UNIQUE, title TEXT NOT NULL, pdf BLOB NOT NULL)')
            old.execute('INSERT INTO documents(sha256,title,pdf) VALUES(?,?,?)', ('example', 'Existing', b'original'))
            old.commit()
            old.close()
            upgraded = core.connect(path)
            self.assertEqual(upgraded.execute('SELECT title,pdf FROM documents').fetchone(), ('Existing', b'original'))
            self.assertEqual(upgraded.execute('SELECT version FROM ontology_schema').fetchone()[0], 1)
            self.assertEqual(upgraded.execute('SELECT COUNT(*) FROM ontology_concepts').fetchone()[0], 0)
            upgraded.close()

    def test_empty_concepts_links_history_and_backup(self):
        with tempfile.TemporaryDirectory() as directory:
            db = core.connect(Path(directory) / 'data.sqlite3')
            self.assertEqual(db.execute('SELECT COUNT(*) FROM ontology_concepts').fetchone()[0], 0)
            writer = PdfWriter()
            writer.add_blank_page(width=100, height=100)
            output = io.BytesIO()
            writer.write(output)
            document_id, _ = core.add_pdf(db, 'Synthetic', output.getvalue())
            concept_id = ontology.add_concept(db, 'Research  Method')
            with self.assertRaises(ValueError):
                ontology.add_concept(db, 'research method')
            ontology.rename_concept(db, concept_id, 'Research design')
            ontology.link_document(db, concept_id, document_id)
            with self.assertRaises(ValueError):
                ontology.link_document(db, concept_id, document_id)
            backup = sqlite3.connect(Path(directory) / 'backup.sqlite3')
            db.backup(backup)
            self.assertEqual(backup.execute('SELECT COUNT(*) FROM ontology_document_links').fetchone()[0], 1)
            self.assertEqual(backup.execute('PRAGMA integrity_check').fetchone()[0], 'ok')
            backup.close()
            core.delete_document(db, document_id)
            self.assertEqual(db.execute('SELECT COUNT(*) FROM ontology_document_links').fetchone()[0], 0)
            self.assertEqual(db.execute("SELECT COUNT(*) FROM ontology_history WHERE action='document_deleted'").fetchone()[0], 1)
            ontology.deactivate_concept(db, concept_id)
            with self.assertRaises(ValueError):
                ontology.rename_concept(db, concept_id, 'Inactive')
            ontology.reactivate_concept(db, concept_id)
            self.assertEqual(db.execute('SELECT active FROM ontology_concepts').fetchone()[0], 1)
            db.close()
            restored = core.connect(Path(directory) / 'backup.sqlite3')
            self.assertEqual(restored.execute('SELECT label FROM ontology_concepts').fetchone()[0], 'Research design')
            self.assertEqual(restored.execute('PRAGMA foreign_key_check').fetchall(), [])
            restored.close()

    def test_newer_schema_is_rejected_without_changes(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'data.sqlite3'
            db = core.connect(path)
            with db:
                db.execute('UPDATE ontology_schema SET version=999')
            db.close()
            with self.assertRaises(RuntimeError):
                core.connect(path)
            db = sqlite3.connect(path)
            self.assertEqual(db.execute('SELECT version FROM ontology_schema').fetchone()[0], 999)
            db.close()


if __name__ == '__main__':
    unittest.main()
