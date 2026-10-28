import unittest
from scripts.smoke_test import run


class SmokeTests(unittest.TestCase):
    def test_synthetic_core_smoke(self):
        result = run()
        self.assertEqual(result['core'], 'PASS')
        self.assertEqual(result['embedding'], 'NOT_RUN')
        self.assertEqual(result['llm'], 'NOT_IMPLEMENTED')

    def test_reranker_requires_explicit_model_path(self):
        with self.assertRaises(ValueError):
            run(reranker=True)


if __name__ == '__main__':
    unittest.main()
