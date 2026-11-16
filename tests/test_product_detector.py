from pathlib import Path
import sys
import unittest
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "scripts"), str(ROOT / "src")]
from detector import aggregate, replay  # noqa: E402
from fixtures import generate  # noqa: E402


class ProductDetectorTests(unittest.TestCase):
    def test_golden_view(self):
        df = pd.read_parquet(ROOT / "tests/fixtures/monthly.parquet")
        pd.testing.assert_frame_equal(df, generate())
        rows = aggregate(df).query("month=='2019-01' and Product=='Demo credit'")
        self.assertEqual(
            rows[["issue_key", "issue_count", "product_count", "issue_share"]].values.tolist(),
            [["Demo access", 15, 25, 0.6], ["Demo billing", 10, 25, 0.4]],
        )

    def test_two_spikes(self):
        scored = (
            replay(generate()).query("issue=='Demo access' and product=='Demo credit'").set_index("month")
        )
        self.assertFalse(scored.loc["2023-11", "glm"])
        self.assertTrue(scored.loc["2023-12", "glm"])
