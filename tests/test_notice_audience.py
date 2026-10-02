from __future__ import annotations

import unittest
from dataclasses import replace

from sakurano_line_notifier.notice_audience import matches_audience
from tests import test_after_school_scope as scope_tests


class AudienceTitleTests(unittest.TestCase):
    def test_middle_admission_is_not_elementary_first_grade(self):
        for title in (
            "【中学校・入学】市立中学校への入学手続き",
            "【中学校・入学】中学新1年生の保護者説明会",
            "中学新１年生 入学説明会",
        ):
            for grade in range(1, 6):
                self.assertFalse(matches_audience(title, "小学校", str(grade)))
            self.assertTrue(matches_audience(title, "小学校", "6年生"))
            self.assertTrue(matches_audience(title, "小学校", "全学年"))

    def test_middle_only_notices_are_not_sixth_grade_admission(self):
        self.assertFalse(matches_audience("中学校の給食費", "小学校", "6年生"))
        self.assertTrue(matches_audience("中学校の給食費", "中学校", "1年生"))

    def test_incoming_pupil_procedures_are_not_current_first_grade(self):
        for title in ("【小学校・入学】市立小学校への入学手続き", "新小学1年生の入学準備金(就学援助費制度)", "【小中学校・入学】新入学児童生徒の就学学校の変更申請受付"):
            self.assertFalse(matches_audience(title, "小学校", "1年生"))
            self.assertTrue(matches_audience(title, "小学校", "全学年"))
        self.assertTrue(matches_audience("小学校の入学式日程変更", "小学校", "1年生"))
        self.assertTrue(matches_audience("【小中学校・入学】新入学の手続き", "小学校", "6年生"))

    def test_joint_safety_and_support_notices_are_preserved(self):
        for title in (
            "市立小・中学校における非常変災時の臨時休業等の判断基準について",
            "小中学校の就学援助", "小学生・中学生の相談窓口",
            "小学1年生から中学3年生までのイベント", "就学相談",
        ):
            self.assertTrue(matches_audience(title, "小学校", "1年生"), title)
            self.assertTrue(matches_audience(title, "小学校", "2年生"), title)

    def test_explicit_grade_range_and_list(self):
        for title, allowed in (("小学校２年生対象の体験", {2}), ("小学1〜3年生の体験", {1, 2, 3}), ("小学1・3年生の体験", {1, 3})):
            for grade in range(1, 7):
                self.assertEqual(matches_audience(title, "小学校", str(grade)), grade in allowed, (title, grade))
            self.assertTrue(matches_audience(title, "小学校", "全学年"))

    def test_high_school_entry_targets_middle_third_not_elementary(self):
        self.assertFalse(matches_audience("高等学校入学説明会", "小学校", "1年生"))
        self.assertFalse(matches_audience("高校入学説明会", "中学校", "1年生"))
        self.assertTrue(matches_audience("高校入学説明会", "中学校", "3年生"))

    def test_unknown_stage_or_ambiguous_title_is_not_silently_excluded(self):
        self.assertTrue(matches_audience("中学校入学説明会", None, "1年生"))
        self.assertTrue(matches_audience("親子の体験講座 2026年度", "小学校", "1年生"))
        self.assertTrue(matches_audience("小学3〜1年生", "小学校", "4年生"))


class AudienceCatalogTests(unittest.TestCase):
    setUp = scope_tests.AfterSchoolScopeTests.setUp
    tearDown = scope_tests.AfterSchoolScopeTests.tearDown
    result = staticmethod(scope_tests.AfterSchoolScopeTests.result)
    payload = scope_tests.AfterSchoolScopeTests.payload

    def test_filter_is_response_only_shared_cache_and_other_families_survive(self):
        def scan(source, grade):
            result = self.result(source, grade)
            if source.id == "musashino_education_notices":
                base = result.notices[0]
                return replace(result, notices=(
                    replace(base, id="middle", title="【中学校・入学】中学新1年生の保護者説明会"),
                    replace(base, id="common", title="小・中学校の就学援助"),
                ))
            return result
        self.catalog._scan_source.side_effect = scan
        for _ in range(2):
            first = self.catalog.get_many(source_id="sakurano", grade="1年生", source_group="municipality")
            source = next(r for r in first if r.source.id == "musashino_education_notices")
            self.assertEqual([n.id for n in source.notices], ["common"])
            self.assertEqual(source.coverage()["audience_excluded_count"], 1)
            sixth = self.catalog.get_many(source_id="sakurano", grade="6年生", source_group="municipality")
            self.assertEqual([n.id for r in sixth if r.source.id == source.source.id for n in r.notices], ["middle", "common"])
        stored = self.catalog.get_source("musashino_education_notices", "全学年")
        self.assertEqual([n.id for n in stored.notices], ["middle", "common"])
        self.assertIsNone(self.catalog.find_notice("middle", source_id="sakurano", grade="1年生"))
        self.assertIsNotNone(self.catalog.find_notice("middle", source_id="sakurano", grade="6年生"))

    def test_all_excluded_is_not_a_collection_failure(self):
        self.catalog._scan_source.side_effect = lambda source, grade: replace(self.result(source, grade), notices=(replace(self.result(source, grade).notices[0], title="【中学校・入学】入学手続き"),))
        response = self.payload(group="municipality")
        self.assertEqual(response["notices"], [])
        self.assertGreater(response["audience_excluded_count"], 0)
        self.assertTrue(response["complete"])
        self.assertTrue(all("unavailable" not in c["issue_codes"] for c in response["coverage"]))
