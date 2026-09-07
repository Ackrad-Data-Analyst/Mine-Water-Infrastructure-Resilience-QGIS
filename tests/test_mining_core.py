import unittest

from mine_resilience_qgis.mining_core import (
    risk_band, runoff_screening_volume, validate_score, weighted_risk_score,
)


class MiningCoreTests(unittest.TestCase):
    def test_weighted_score_and_band(self):
        self.assertEqual(weighted_risk_score(5, 3, 4), 86.0)
        self.assertEqual(risk_band(86), "CRITICAL")
        self.assertEqual(risk_band(60), "HIGH")
        self.assertEqual(risk_band(40), "MODERATE")
        self.assertEqual(risk_band(39.99), "LOW")

    def test_screening_volume(self):
        self.assertEqual(runoff_screening_volume(2, 50, 0.5), 500.0)

    def test_invalid_values_fail(self):
        with self.assertRaises(ValueError): validate_score(6)
        with self.assertRaises(ValueError): weighted_risk_score(1, 2, 3, 0, 0, 0)
        with self.assertRaises(ValueError): runoff_screening_volume(1, 10, 1.2)


if __name__ == "__main__":
    unittest.main()
