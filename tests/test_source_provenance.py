from copy import deepcopy
import json
from pathlib import Path
import unittest

from sakurano_line_notifier.source_provenance import registry_fingerprint, validate_provenance


ROOT = Path(__file__).resolve().parents[1]


class SourceProvenanceTests(unittest.TestCase):
    def setUp(self):
        self.registry = json.loads((ROOT / "sources.json").read_text())
        self.review = json.loads((ROOT / "research/tokyo-source-provenance-20261003.json").read_text())

    def test_production_registry_has_matching_review_records_and_verified_school_roots(self):
        validate_provenance(self.registry, self.review)

    def test_inventory_add_remove_or_duplicate_cannot_silently_pass(self):
        for kind in ("add", "remove", "duplicate"):
            registry = deepcopy(self.registry)
            if kind == "add":
                registry["sources"].append({**registry["sources"][0], "id": "new-school"})
            elif kind == "remove":
                registry["sources"].pop()
            else:
                registry["sources"].append(registry["sources"][0])
            with self.subTest(kind=kind), self.assertRaises(ValueError):
                validate_provenance(registry, self.review)

    def test_changed_scope_url_or_filter_requires_updated_review(self):
        for key, value in (("ward", "港区"), ("level", "中学校"), ("shared_with_ward", True),
                           ("include_patterns", [".*"]), ("page_url", "https://other.example/")):
            registry = deepcopy(self.registry)
            registry["sources"][0][key] = value
            with self.subTest(key=key), self.assertRaisesRegex(ValueError, "fingerprint"):
                validate_provenance(registry, self.review)

    def test_review_cannot_silently_weaken_school_identity(self):
        for key, value in (("status", "unverified"), ("municipality", "港区"),
                           ("school_type", "中学校"), ("evidence_ids", ["missing"])):
            review = deepcopy(self.review)
            review["sources"][0]["identity"][key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                validate_provenance(self.registry, review)

    def test_source_order_is_not_part_of_per_source_fingerprint(self):
        self.registry["sources"].reverse()
        validate_provenance(self.registry, self.review)
        source = self.registry["sources"][0]
        self.assertEqual(registry_fingerprint(source), registry_fingerprint(dict(reversed(list(source.items())))))

    def test_unverified_endpoints_are_not_promoted_to_verified(self):
        original = deepcopy(self.review)
        self.assertTrue(any(endpoint["reachability"]["status"] == "unverified"
                            for row in self.review["sources"] for endpoint in row["endpoints"]))
        validate_provenance(self.registry, self.review)
        self.assertEqual(original, self.review)

    def test_empty_or_invalid_evidence_cannot_support_verified_school(self):
        for value in (None, {}, {"verification_status": "verified"}):
            review = deepcopy(self.review)
            review["evidence"] = {key: value for key in review["evidence"]}
            with self.assertRaisesRegex(ValueError, "supporting evidence"):
                validate_provenance(self.registry, review)
        review = deepcopy(self.review)
        for item in review["evidence"].values():
            item["verification_status"] = "unverified"
        with self.assertRaisesRegex(ValueError, "verified supporting evidence"):
            validate_provenance(self.registry, review)


if __name__ == "__main__":
    unittest.main()
