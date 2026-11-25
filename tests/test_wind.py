import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from fsxwl.wind import components  # noqa: E402


class TestWind(unittest.TestCase):
    def test_lers_runway_07_with_280_wind_is_tail_and_left(self):
        rel, head, cross = components(70, 280, 18)
        self.assertAlmostEqual(rel, 210)
        self.assertAlmostEqual(head, -15.6, places=1)   # tailwind
        self.assertAlmostEqual(cross, -9.0, places=1)   # from the left

    def test_runway_25_same_wind_is_head_and_right(self):
        _, head, cross = components(250, 280, 18)
        self.assertAlmostEqual(head, 15.6, places=1)
        self.assertAlmostEqual(cross, 9.0, places=1)

    def test_pure_headwind_and_wraparound(self):
        rel, head, cross = components(355, 5, 10)
        self.assertAlmostEqual(rel, 10)
        self.assertGreater(head, 9.8)
        self.assertGreater(cross, 0)


if __name__ == "__main__":
    unittest.main()
