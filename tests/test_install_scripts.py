import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path


@unittest.skipUnless(shutil.which('pwsh') and shutil.which('py'), 'Windows PowerShell and Python launcher required')
class InstallScriptTests(unittest.TestCase):
    def test_unowned_environment_is_not_modified(self):
        source = Path(__file__).resolve().parents[1] / 'scripts' / 'install.ps1'
        with tempfile.TemporaryDirectory(prefix='article-ai-install-test-') as folder:
            root = Path(folder)
            (root / 'scripts').mkdir()
            shutil.copyfile(source, root / 'scripts' / 'install.ps1')
            existing = root / '.venv'
            existing.mkdir()
            sentinel = existing / 'do-not-touch.txt'
            sentinel.write_text('untouched', encoding='utf-8')
            result = subprocess.run(['pwsh', '-NoProfile', '-NonInteractive', '-File', str(root / 'scripts' / 'install.ps1')],
                                    cwd=root, capture_output=True, timeout=30)
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(sentinel.read_text(encoding='utf-8'), 'untouched')
            self.assertFalse((existing / 'article-ai-owner.txt').exists())


if __name__ == '__main__':
    unittest.main()
