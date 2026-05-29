import time
import unittest

from brain import run_with_timeout


class RunWithTimeoutTests(unittest.TestCase):
    def test_returns_result_before_timeout(self):
        result = run_with_timeout(lambda: "ok", timeout_seconds=0.5)
        self.assertEqual(result, "ok")

    def test_raises_timeout_error(self):
        with self.assertRaises(TimeoutError):
            run_with_timeout(lambda: time.sleep(0.2), timeout_seconds=0.05)


if __name__ == "__main__":
    unittest.main()
