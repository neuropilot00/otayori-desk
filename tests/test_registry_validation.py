from __future__ import annotations

import json
import tempfile
import unittest
from itertools import product
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from sakurano_line_notifier.web_catalog import (
    CatalogError, CatalogNotice, CatalogResult, CatalogService, _parse_source, load_sources,
)


REGISTRY = Path(__file__).resolve().parents[1] / "sources.json"


def source(source_id="school", **changes):
    return {
        "id": source_id, "name": source_id, "ward": "武蔵野市", "level": "小学校",
        "page_url": f"https://example.test/{source_id}", **changes,
    }


def cached_notice(source, grade, refresh, results):
    """Exercise real selection and audience filtering without crawling websites."""
    notice = CatalogNotice(
        id=source.id, source_id=source.id, source_name=source.name, ward=source.ward,
        level=source.level, grade=grade or source.default_grade, title="公開のお知らせ",
        kind=source.content_kind, url=source.page_url, text="公式の資料です。",
        content_hash="a" * 64, date_label="2026/10/03", published_label="2026/10/03",
        source_group=source.source_group, feed_group=source.feed_group,
        coverage_kind=source.coverage_kind,
    )
    results[source.id] = CatalogResult(source, notice.grade, "2026-10-03T00:00:00+00:00", (notice,))
    return True


class RegistryValidationTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.path = Path(directory.name) / "sources.json"

    def load(self, *entries):
        self.path.write_text(json.dumps({"sources": list(entries)}, ensure_ascii=False), encoding="utf-8")
        return load_sources(self.path)

    def test_optional_defaults_and_normalization_remain_compatible(self):
        parsed = self.load(source())[0]
        self.assertEqual((parsed.collection_id, parsed.collection_root, parsed.enabled), ("school", True, True))
        self.assertEqual((parsed.shared_with_ward, parsed.related_collections), (False, ()))
        self.assertEqual((parsed.source_group, parsed.feed_group, parsed.mode), ("school", "notices", "pdf"))
        parsed = _parse_source(source(mode=" PDF ", source_group=" SCHOOL ", feed_group=" NOTICES ", default_grade="１学年"), 0)
        self.assertEqual((parsed.mode, parsed.source_group, parsed.feed_group, parsed.default_grade), ("pdf", "school", "notices", "1年生"))

    def test_boolean_fields_do_not_coerce_strings_numbers_or_null(self):
        for field, value in product(
            ("enabled", "collection_root", "shared_with_ward"),
            ("false", "true", "0", "", 0, 1, None, [], {}),
        ):
            with self.subTest(field=field, value=value), self.assertRaisesRegex(CatalogError, field):
                self.load(source(**{field: value}))

    def test_static_information_cannot_be_registered_as_live_notices(self):
        with self.assertRaisesRegex(CatalogError, "static sources must be reference"):
            self.load(source(mode="static", static_text="施設の説明", coverage_kind="notices"))

    def test_explicit_boolean_values_are_preserved(self):
        parsed = self.load(source(), source("child", collection_id="school", collection_root=False, enabled=False))[1]
        self.assertFalse(parsed.enabled)
        self.assertFalse(parsed.collection_root)
        self.assertFalse(parsed.shared_with_ward)

    def test_enum_fields_reject_blank_null_and_non_strings(self):
        for field, value in product(
            ("level", "mode", "source_group", "feed_group", "content_kind", "coverage_kind", "collection_driver"),
            ("", "  ", None, False, 1, [], {}),
        ):
            with self.subTest(field=field, value=value), self.assertRaisesRegex(CatalogError, field):
                self.load(source(**{field: value}))

    def test_bounded_enumerations_reject_unknown_values(self):
        for field in ("level", "mode", "source_group", "feed_group", "content_kind", "coverage_kind", "collection_driver"):
            with self.subTest(field=field), self.assertRaisesRegex(CatalogError, field):
                self.load(source(**{field: "unknown"}))

    def test_identity_and_ward_fields_cannot_be_coerced_or_used_as_wildcards(self):
        for field, value in product(("id", "collection_id", "ward", "name"), (None, False, 1, [], {}, "", "  ")):
            with self.subTest(field=field, value=value), self.assertRaisesRegex(CatalogError, field):
                self.load(source(**{field: value}))
        for field, value in product(("id", "collection_id"), ("all", "*", "a/b", "a b", "a" * 101)):
            with self.subTest(field=field, value=value), self.assertRaisesRegex(CatalogError, field):
                self.load(source(**{field: value}))

    def test_duplicate_source_ids_and_collection_roots_fail(self):
        with self.assertRaisesRegex(CatalogError, "source ids must be unique.*school"):
            self.load(source(), source())
        for enabled in (True, False):
            with self.subTest(enabled=enabled), self.assertRaisesRegex(CatalogError, "duplicate roots.*school.*other"):
                self.load(source(), source("other", collection_id="school", enabled=enabled))

    def test_children_require_a_root_not_another_child(self):
        cases = (
            [source("child", collection_id="missing", collection_root=False)],
            [source(), source("child", collection_id="school", collection_root=False),
             source("grandchild", collection_id="child", collection_root=False)],
            [source(collection_root=False)],
        )
        for entries in cases:
            with self.subTest(entries=entries), self.assertRaisesRegex(CatalogError, "collection_id.*has no root"):
                self.load(*entries)

    def test_enabled_children_and_related_sources_cannot_depend_on_disabled_roots(self):
        with self.assertRaisesRegex(CatalogError, "enabled source.*child.*disabled.*school"):
            self.load(source(enabled=False), source("child", collection_id="school", collection_root=False))
        with self.assertRaisesRegex(CatalogError, "related_collections.*school.*disabled"):
            self.load(source(enabled=False), source("club", source_group="after_school", related_collections=["school"]))
        self.assertEqual(len(self.load(source(enabled=False),
                                       source("child", collection_id="school", collection_root=False, enabled=False))), 2)

    def test_children_cannot_cross_municipalities_even_when_disabled_or_shared(self):
        for group, enabled in product(("school", "municipality", "after_school"), (True, False)):
            with self.subTest(group=group, enabled=enabled), self.assertRaisesRegex(CatalogError, "child.*ward.*school"):
                self.load(source(), source("child", collection_id="school", collection_root=False,
                                          source_group=group, ward="港区", enabled=enabled,
                                          shared_with_ward=group == "municipality"))

    def test_school_and_club_children_must_match_parent_level(self):
        for group, level in product(("school", "after_school"), ("中学校", "高等学校")):
            with self.subTest(group=group, level=level), self.assertRaisesRegex(CatalogError, "child.*level.*school"):
                self.load(source(), source("child", collection_id="school", collection_root=False,
                                          source_group=group, level=level))

    def test_school_children_require_a_school_parent(self):
        for group in ("municipality", "after_school"):
            with self.subTest(group=group), self.assertRaisesRegex(CatalogError, "school collection root"):
                self.load(source("parent", source_group=group),
                          source("child", collection_id="parent", collection_root=False))

    def test_school_and_facility_specific_sources_cannot_share_with_whole_ward(self):
        entries = [source(shared_with_ward=True)]
        entries.extend(source(source_group="after_school", shared_with_ward=True, content_kind=kind,
                              coverage_kind="reference" if kind == "gakudo_facility" else "notices")
                       for kind in ("gakudo_facility", "asobee_letter", "gakudo_daily", "document"))
        for entry in entries:
            with self.subTest(entry=entry), self.assertRaisesRegex(CatalogError, "shared_with_ward"):
                self.load(entry)

    def test_shared_municipality_and_common_after_school_references_are_valid(self):
        entries = [source(), source("city", collection_id="school", collection_root=False,
                                   source_group="municipality", shared_with_ward=True, level="中学校")]
        entries.extend(source(kind, collection_id="school", collection_root=False, source_group="after_school",
                              content_kind=kind, coverage_kind="reference", shared_with_ward=True)
                       for kind in ("gakudo_admissions", "asobee_reference"))
        self.assertEqual(len(self.load(*entries)), 4)

    def test_related_targets_must_exist_as_collection_roots(self):
        with self.assertRaisesRegex(CatalogError, "related_collections.*unknown.*missing"):
            self.load(source(related_collections=["missing"]))
        with self.assertRaisesRegex(CatalogError, "related_collections.*unknown.*child"):
            self.load(source(related_collections=["child"]),
                      source("child", collection_id="school", collection_root=False))
        for value in ("school", None, [None], [1], ["*"], ["a/b"]):
            with self.subTest(value=value), self.assertRaisesRegex(CatalogError, "related_collections"):
                self.load(source(related_collections=value))

    def test_related_links_cannot_cross_wards_for_any_source_group(self):
        for group, enabled in product(("school", "after_school", "municipality"), (True, False)):
            with self.subTest(group=group, enabled=enabled), self.assertRaisesRegex(CatalogError, "related_collections.*same ward"):
                self.load(source(), source("other", source_group=group, enabled=enabled,
                                          ward="港区", related_collections=["school"]))

    def test_children_can_precede_roots_and_root_id_need_not_equal_collection_id(self):
        entries = self.load(source("child", collection_id="collection", collection_root=False),
                            source("root", collection_id="collection"),
                            source("related", source_group="after_school", related_collections=["collection"]))
        self.assertEqual([entry.id for entry in entries], ["child", "root", "related"])

    def test_school_news_cannot_join_another_school_or_municipality_even_in_same_ward(self):
        for group, child in product(("school", "municipality"), (True, False)):
            entries = [source(), source("other", source_group=group)]
            if child:
                entries.append(source("letter", collection_id="school", collection_root=False, related_collections=["other"]))
            else:
                entries[0]["related_collections"] = ["other"]
            with self.subTest(group=group, child=child), self.assertRaisesRegex(CatalogError, "related_collections.*another school"):
                self.load(*entries)
        self.assertEqual(self.load(source(related_collections=["school"]))[0].related_collections, ("school",))
        with self.assertRaisesRegex(CatalogError, "related_collections.*another school"):
            self.load(source(), source("other"),
                      source("letter", source_group="after_school", collection_id="school",
                             collection_root=False, related_collections=["other"]))

    def test_school_and_club_related_links_require_the_same_level(self):
        for origin, target in (("school", "after_school"), ("after_school", "school"), ("after_school", "after_school")):
            with self.subTest(origin=origin, target=target), self.assertRaisesRegex(CatalogError, "related_collections.*same level"):
                self.load(source(source_group=origin, related_collections=["other"]),
                          source("other", source_group=target, level="中学校"))
        self.assertEqual(len(self.load(source(level="中学校"),
                                       source("city", source_group="municipality", related_collections=["school"]))), 2)

    def test_same_ward_school_and_club_links_are_directed_and_do_not_expand_transitively(self):
        self.load(
            source(related_collections=["school", "school"]),
            source("club", source_group="after_school", related_collections=["school"]),
            source("letter", collection_id="school", collection_root=False, related_collections=["club"]),
            source("unrelated", related_collections=["club"]),
            source("city", source_group="municipality", shared_with_ward=True),
            source("other_city", ward="港区", source_group="municipality", shared_with_ward=True),
            source("disabled", enabled=False, source_group="after_school", related_collections=["school"]),
        )
        with patch.dict("os.environ", {"WEB_SCHEDULED_COLLECTION": "false"}):
            catalog = CatalogService(SimpleNamespace(), self.path)
        self.addCleanup(catalog.close)
        catalog._cached_result = cached_notice
        catalog._submit_source = Mock(side_effect=AssertionError("unexpected scan"))
        expected = {
            "school": {"school", "club", "letter", "city"},
            "club": {"club", "letter", "unrelated", "city"},
            "unrelated": {"unrelated", "city"},
            "letter": {"letter"},
        }
        for requested, ids in expected.items():
            with self.subTest(requested=requested):
                results = catalog.get_many(source_id=requested)
                self.assertEqual({result.source.id for result in results}, ids)
                self.assertEqual({notice.source_id for result in results for notice in result.notices}, ids)
        self.assertEqual(catalog.sources[0].related_collections, ("school",))


class ProductionRegistryScopeTests(unittest.TestCase):
    # Reviewed existing municipal sources and school/club pairings. Expectations
    # intentionally do not derive sharing permission from related_collections.
    COMMON = {
        "sakurano_musashino_events", "musashino_public_program_news", "musashino_education_notices",
        "musashino_sakurazutsumi_events", "musashino_gakudo_notices", "musashino_food_family_events",
        "musashino_family_sports_events", "musashino_asobee_reference", "musashino_school_lunch_parent",
        "musashino_school_health_parent", "musashino_school_safety_parent",
    }
    PAIRED_SCHOOLS = (
        "dai1", "dai2", "dai3", "dai4", "dai5", "oonoden", "kyounan", "honjuku",
        "senkawa", "inokashira", "sekimaeminami",
    )

    def setUp(self):
        with patch.dict("os.environ", {"WEB_SCHEDULED_COLLECTION": "false"}):
            self.catalog = CatalogService(SimpleNamespace(), REGISTRY)
        self.addCleanup(self.catalog.close)
        self.catalog._cached_result = cached_notice
        self.catalog._submit_source = Mock(side_effect=AssertionError("unexpected scan"))
        self.sources = {entry.id: entry for entry in self.catalog.sources}

    def expected_ids(self, requested):
        if requested in (None, "all", "*"):
            return {entry.id for entry in self.sources.values() if entry.enabled}
        entry = self.sources[requested]
        if not entry.enabled:
            return set()
        if not entry.collection_root:
            return {requested}
        expected = {item.id for item in self.sources.values() if item.collection_id == entry.collection_id}
        for school in self.PAIRED_SCHOOLS:
            if requested == f"musashino_{school}_es":
                expected.add(f"musashino_{school}_gakudo")
            if requested == f"musashino_{school}_gakudo":
                expected.add(f"musashino_{school}_es_asobee_public_letters")
        if entry.ward == "武蔵野市":
            expected.update(self.COMMON)
        return {item for item in expected if self.sources[item].enabled}

    def assert_scope(self, expected, **filters):
        if not expected:
            with self.assertRaisesRegex(CatalogError, "no enabled source"):
                self.catalog.get_many(**filters)
            return
        results = self.catalog.get_many(**filters)
        self.assertEqual({result.source.id for result in results}, expected)
        self.assertEqual({notice.source_id for result in results for notice in result.notices}, expected)

    def test_all_sources_grades_feed_and_group_scopes_exclude_unrelated_collections(self):
        for requested in self.sources:
            expected = self.expected_ids(requested)
            for grade, feed, group in product(
                (None, *self.sources[requested].grades),
                (None, "all", "*", "notices", "events"),
                (None, "all", "*", "school", "municipality", "after_school"),
            ):
                matching = {item for item in expected
                            if (feed in (None, "all", "*") or self.sources[item].feed_group == feed)
                            and (group in (None, "all", "*") or self.sources[item].source_group == group)}
                filters = dict(source_id=requested, grade=grade, feed_group=feed, source_group=group)
                with self.subTest(**filters):
                    self.assert_scope(matching, **filters)

    def test_all_sources_and_wildcards_respect_ward_and_level_filters(self):
        for requested, ward, level in product(
            (*self.sources, None, "all", "*"),
            (None, "all", "*", *sorted({entry.ward for entry in self.sources.values()}), "未登録市"),
            (None, "all", "*", "小学校", "中学校", "高等学校", "未登録校種"),
        ):
            matching = {item for item in self.expected_ids(requested)
                        if (ward in (None, "all", "*") or self.sources[item].ward == ward)
                        and (level in (None, "all", "*") or self.sources[item].level == level)}
            with self.subTest(source=requested, ward=ward, level=level):
                self.assert_scope(matching, source_id=requested, ward=ward, level=level)

    def test_global_feed_group_scopes_and_unknown_source_do_not_expand(self):
        for requested, feed, group in product((None, "all", "*"), ("notices", "events"),
                                              ("all", "school", "municipality", "after_school")):
            matching = {item for item in self.expected_ids(requested)
                        if self.sources[item].feed_group == feed
                        and (group == "all" or self.sources[item].source_group == group)}
            with self.subTest(source=requested, feed=feed, group=group):
                self.assert_scope(matching, source_id=requested, feed_group=feed, source_group=group)
        self.assert_scope(set(), source_id="unregistered_source")
        for field in ("feed_group", "source_group"):
            with self.subTest(field=field), self.assertRaises(CatalogError):
                self.catalog.get_many(source_id="sakurano", **{field: "invalid"})


if __name__ == "__main__":
    unittest.main()
