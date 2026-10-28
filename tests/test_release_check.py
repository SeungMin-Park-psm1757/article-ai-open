import unittest
from scripts.check_release import MAX_BLOB, scan_blob


class ReleaseCheckTests(unittest.TestCase):
    def test_sensitive_and_binary_patterns(self):
        self.assertFalse(scan_blob(b'public example'))
        self.assertTrue(scan_blob(b'content\x00binary'))
        self.assertTrue(scan_blob(b'x' * (MAX_BLOB + 1)))
        self.assertTrue(scan_blob((b'gh' + b'p_' + b'a' * 24)))
        self.assertTrue(scan_blob(b'C:\\Users\\example\\secret'))


if __name__ == '__main__':
    unittest.main()
