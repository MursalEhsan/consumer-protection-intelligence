import unittest

import pandas as pd

from src.cfpb_narrative_model import (
    OTHER_LABEL,
    map_issue_labels,
    normalize_narrative,
    remove_duplicate_leakage,
    remove_near_duplicate_leakage,
    sample_quotas,
    sample_rank,
    select_training_taxonomy,
    split_for_date,
)


class CFPBNarrativeModelTests(unittest.TestCase):
    def test_chronological_split_boundaries(self):
        self.assertEqual(split_for_date(pd.Timestamp("2024-10-31")), None)
        self.assertEqual(split_for_date(pd.Timestamp("2024-11-01")), "train")
        self.assertEqual(split_for_date(pd.Timestamp("2025-11-01")), "validation")
        self.assertEqual(split_for_date(pd.Timestamp("2026-08-14")), "test")
        self.assertEqual(split_for_date(pd.Timestamp("2026-08-15")), None)

    def test_sample_quotas_respect_cap_and_sum(self):
        quotas = sample_quotas(100_000)
        self.assertEqual(quotas, {"train": 60_000, "validation": 20_000, "test": 20_000})
        self.assertEqual(sum(sample_quotas(997).values()), 997)
        with self.assertRaises(ValueError):
            sample_quotas(100_001)

    def test_sample_rank_is_deterministic(self):
        self.assertEqual(sample_rank("12345"), sample_rank("12345"))
        self.assertNotEqual(sample_rank("12345"), sample_rank("54321"))

    def test_taxonomy_uses_training_labels_and_maps_others(self):
        labels = pd.Series(["Alpha"] * 10 + ["Beta"] * 5 + ["Rare"] * 2)
        taxonomy = select_training_taxonomy(labels, top_k=2, minimum_support=3)
        self.assertEqual(taxonomy["selected_issue_labels"], ["Alpha", "Beta"])
        mapped = map_issue_labels(pd.Series(["Alpha", "Novel"]), taxonomy["selected_issue_labels"])
        self.assertEqual(mapped.tolist(), ["Alpha", OTHER_LABEL])

    def test_duplicate_complaint_and_exact_text_leakage_is_removed(self):
        sample = pd.DataFrame(
            [
                {
                    "Date received": "2017-01-01",
                    "Issue": "Fees",
                    "Consumer complaint narrative": "Same complaint text",
                    "split": "train",
                    "source_archive": "old.zip",
                    "Complaint ID": "1",
                },
                {
                    "Date received": "2025-11-01",
                    "Issue": "Fees",
                    "Consumer complaint narrative": "same   complaint TEXT",
                    "split": "validation",
                    "source_archive": "recent.zip",
                    "Complaint ID": "2",
                },
                {
                    "Date received": "2026-01-01",
                    "Issue": "Fraud",
                    "Consumer complaint narrative": "Different complaint text",
                    "split": "test",
                    "source_archive": "test.zip",
                    "Complaint ID": "1",
                },
            ]
        )
        deduplicated, stats = remove_duplicate_leakage(sample)
        self.assertEqual(len(deduplicated), 1)
        self.assertEqual(deduplicated.iloc[0]["split"], "train")
        self.assertEqual(stats["complaint_ids_crossing_temporal_splits_before_removal"], 1)
        self.assertEqual(stats["exact_duplicate_text_groups_crossing_splits_before_removal"], 1)
        self.assertEqual(stats["exact_duplicate_text_groups_crossing_splits_after_removal"], 0)
        self.assertNotIn("Complaint ID", deduplicated.columns)

    def test_text_normalization_only_folds_case_and_whitespace(self):
        self.assertEqual(
            normalize_narrative(" A  complaint\nTEXT "),
            "a complaint text",
        )

    def test_near_duplicate_check_prevents_cross_split_template_leakage(self):
        first = (
            "There is a persistent problem with my bank payment that has not been solved "
            "despite repeated contact with customer service."
        )
        near_duplicate = (
            "There is a persistent problem with my bank payment, that has not been solved "
            "despite repeated contact with customer service."
        )
        sample = pd.DataFrame(
            [
                {
                    "Date received": "2024-12-01",
                    "Issue": "Fees",
                    "Consumer complaint narrative": first,
                    "split": "train",
                    "source_archive": "train.zip",
                },
                {
                    "Date received": "2025-11-01",
                    "Issue": "Fees",
                    "Consumer complaint narrative": near_duplicate,
                    "split": "validation",
                    "source_archive": "validation.zip",
                },
            ]
        )
        filtered, stats = remove_near_duplicate_leakage(sample)
        self.assertEqual(len(filtered), 1)
        self.assertEqual(stats["near_duplicate_pairs_across_splits_removed"], 1)
        self.assertEqual(filtered.iloc[0]["split"], "train")


if __name__ == "__main__":
    unittest.main()
