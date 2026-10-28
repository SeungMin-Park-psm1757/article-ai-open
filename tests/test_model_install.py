import hashlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts import install_models


class Response(io.BytesIO):
    status = 206
    headers = {'Content-Range': 'bytes 3-5/6'}


class ModelInstallTests(unittest.TestCase):
    @staticmethod
    def mark(staging, model):
        (staging / '.article-ai-download.json').write_text(
            json.dumps({'repo': model['repo'], 'revision': model['revision']}), encoding='utf-8')

    def test_resume_verifies_before_publishing(self):
        data = b'abcdef'
        entry = {'path': 'sub/model.bin', 'size': len(data), 'algorithm': 'sha256',
                 'digest': hashlib.sha256(data).hexdigest()}
        model = {'repo': 'example/model', 'revision': 'a' * 40, 'role': 'embedding', 'files': [entry]}
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            staging = root / 'example--model.partial' / 'sub'
            staging.mkdir(parents=True)
            self.mark(staging.parent, model)
            (staging / 'model.bin.part').write_bytes(data[:3])
            with patch.object(install_models.urllib.request, 'urlopen', return_value=Response(data[3:])) as request:
                result = install_models.install(model, root)
            self.assertEqual(request.call_args.args[0].get_header('Range'), 'bytes=3-')
            self.assertEqual((result / entry['path']).read_bytes(), data)
            with self.assertRaises(FileExistsError):
                install_models.install(model, root)

    def test_corrupt_file_does_not_publish(self):
        model = {'repo': 'example/model', 'revision': 'b' * 40, 'role': 'llm',
                 'files': [{'path': 'data', 'size': 3, 'algorithm': 'sha256', 'digest': '0' * 64}]}
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            staging = root / 'example--model.partial'
            staging.mkdir()
            self.mark(staging, model)
            (staging / 'data.part').write_bytes(b'bad')
            with self.assertRaises(ValueError):
                install_models.install(model, root)
            self.assertFalse((root / 'example--model').exists())
            self.assertEqual((staging / 'data.part').read_bytes(), b'bad')

    def test_resume_requires_matching_range(self):
        data = b'abcdef'
        entry = {'path': 'data', 'size': len(data), 'algorithm': 'sha256',
                 'digest': hashlib.sha256(data).hexdigest()}
        model = {'repo': 'example/model', 'revision': 'a' * 40, 'role': 'llm', 'files': [entry]}
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            staging = root / 'example--model.partial'
            staging.mkdir()
            self.mark(staging, model)
            (staging / 'data.part').write_bytes(data[:3])
            bad_response = Response(data)
            bad_response.status = 200
            with patch.object(install_models.urllib.request, 'urlopen', return_value=bad_response):
                with self.assertRaises(ValueError):
                    install_models.install(model, root)
            self.assertEqual((staging / 'data.part').read_bytes(), data[:3])

    def test_unowned_staging_is_not_modified(self):
        model = {'repo': 'example/model', 'revision': 'a' * 40, 'role': 'llm', 'files': []}
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            staging = root / 'example--model.partial'
            staging.mkdir()
            with self.assertRaises(ValueError):
                install_models.install(model, root)
            self.assertEqual(list(staging.iterdir()), [])

    def test_lock_and_path_validation(self):
        lock = json.loads(install_models.LOCK.read_text(encoding='utf-8'))
        self.assertEqual({m['role'] for m in lock['models']}, {'llm', 'embedding', 'reranker'})
        for model in lock['models']:
            self.assertTrue(model['files'])
            for entry in model['files']:
                install_models.safe_file(Path('root'), entry['path'])
                self.assertEqual(len(entry['digest']), 64 if entry['algorithm'] == 'sha256' else 40)
        with self.assertRaises(ValueError):
            install_models.safe_file(Path('root'), '../outside')


if __name__ == '__main__':
    unittest.main()
