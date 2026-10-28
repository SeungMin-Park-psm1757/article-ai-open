import io
import tempfile
import unittest
from pathlib import Path
from pypdf import PdfWriter
import core


class StoreTests(unittest.TestCase):
    def test_empty_import_duplicate_delete(self):
        with tempfile.TemporaryDirectory() as folder:
            db = core.connect(Path(folder) / 'data.sqlite3')
            self.assertEqual(core.search(db, 'anything'), [])
            writer = PdfWriter()
            writer.add_blank_page(width=100, height=100)
            output = io.BytesIO()
            writer.write(output)
            doc_id, count = core.add_pdf(db, 'Synthetic', output.getvalue())
            self.assertEqual(count, 0)
            with self.assertRaises(ValueError):
                core.add_pdf(db, 'duplicate', output.getvalue())
            with db:
                db.execute('INSERT INTO pages VALUES(?,?,?)', (doc_id, 2, 'This is a synthetic research sentence for testing.'))
            self.assertEqual(len(core.search(db, 'synthetic')), 1)
            self.assertEqual(len(core.inspect(db, 'This is a synthetic research sentence for testing.')), 1)
            long_sentence = 'synthetic ' * 30
            with db:
                db.execute('UPDATE pages SET text=? WHERE document_id=? AND page=2', (long_sentence, doc_id))
            self.assertEqual(len(core.inspect(db, long_sentence)), 1)
            core.rename_document(db, doc_id, 'Updated')
            self.assertEqual(core.search(db, 'synthetic')[0][1], 'Updated')
            report_id = core.save_report(db, 'Synthetic report')
            core.delete_document(db, doc_id)
            self.assertEqual(core.search(db, 'synthetic'), [])
            db.close()
            db = core.connect(Path(folder) / 'data.sqlite3')
            self.assertEqual(db.execute('SELECT content FROM reports WHERE id=?', (report_id,)).fetchone()[0], 'Synthetic report')
            db.close()


if __name__ == '__main__':
    unittest.main()
