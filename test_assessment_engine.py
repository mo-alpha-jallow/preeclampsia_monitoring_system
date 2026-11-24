"""Assessment and visit-linked persistence tests using isolated SQLite files."""

import json
import sqlite3
import tempfile
import unittest
from datetime import date
from pathlib import Path

import database
from assessment_engine import (
    ASSESSMENT_VERSION,
    EMERGENCY_MESSAGE,
    NO_ALERT_EXPLANATION,
    NO_ALERT_SUMMARY,
    PREECLAMPSIA_DISCLAIMER,
    PREECLAMPSIA_MESSAGE,
    SEIZURE_MESSAGE,
    build_overall_assessment,
)
from monitoring_rules import evaluate_visit


def make_visit(**overrides):
    values = {
        "visit_id": 15,
        "patient_id": 4,
        "visit_date": "2026-03-01",
        "gestational_age_weeks": 28,
        "systolic_bp": 120,
        "diastolic_bp": 80,
        "urine_protein": "Negative",
        "maternal_warning_signs": [],
        "other_symptoms": None,
    }
    values.update(overrides)
    return values


def assess(**overrides):
    return build_overall_assessment(evaluate_visit(make_visit(**overrides)))


class OverallAssessmentTests(unittest.TestCase):
    def test_no_actionable_alerts_use_exact_non_reassuring_summary(self):
        assessment = build_overall_assessment(
            {"overall_severity": "INFORMATION", "alerts": []}
        )
        self.assertEqual(
            assessment["overall_category"], "NO PREDEFINED ALERT RULES TRIGGERED"
        )
        self.assertEqual(assessment["summary"], NO_ALERT_SUMMARY)
        self.assertEqual(assessment["explanation"], NO_ALERT_EXPLANATION)
        self.assertFalse(assessment["possible_preeclampsia_concern"])

    def test_informational_only_existing_findings_remain_no_alert_category(self):
        assessment = assess()
        self.assertEqual(
            assessment["overall_category"], "NO PREDEFINED ALERT RULES TRIGGERED"
        )
        self.assertEqual(assessment["triggered_rule_count"], 2)
        self.assertEqual(
            assessment["summary"], NO_ALERT_SUMMARY
        )

    def test_monitoring_required_for_caution(self):
        assessment = assess(urine_protein="Trace")
        self.assertEqual(assessment["overall_category"], "MONITORING REQUIRED")
        self.assertEqual(assessment["overall_severity"], "CAUTION")
        self.assertTrue(assessment["combined_recommendations"])

    def test_concerning_result_from_existing_warning(self):
        assessment = assess(systolic_bp=145)
        self.assertEqual(assessment["overall_category"], "CONCERNING FINDINGS")
        self.assertEqual(assessment["overall_severity"], "WARNING")

    def test_urgent_result_from_severe_range_bp(self):
        assessment = assess(systolic_bp=160)
        self.assertEqual(
            assessment["overall_category"], "URGENT CLINICAL ASSESSMENT REQUIRED"
        )
        self.assertEqual(assessment["overall_severity"], "URGENT")

    def test_emergency_and_seizure_message_are_never_downgraded(self):
        assessment = assess(
            systolic_bp=120,
            diastolic_bp=80,
            urine_protein="Negative",
            gestational_age_weeks=10,
            maternal_warning_signs=["seizure"],
        )
        self.assertEqual(assessment["overall_category"], "EMERGENCY")
        self.assertTrue(assessment["emergency"])
        self.assertEqual(assessment["emergency_message"], SEIZURE_MESSAGE)
        self.assertIn("cannot diagnose eclampsia", assessment["emergency_message"])
        self.assertEqual(assessment["combined_recommendations"][0]["priority"], "EMERGENCY")
        with_severe_bp = assess(
            systolic_bp=160,
            diastolic_bp=112,
            urine_protein="+1",
            maternal_warning_signs=["seizure"],
        )
        self.assertEqual(with_severe_bp["overall_severity"], "EMERGENCY")
        self.assertEqual(with_severe_bp["overall_category"], "EMERGENCY")

    def test_generic_emergency_severity_is_preserved(self):
        assessment = build_overall_assessment(
            {
                "overall_severity": "EMERGENCY",
                "alerts": [
                    {
                        "rule_id": "X001",
                        "rule_name": "Emergency finding",
                        "severity": "EMERGENCY",
                        "suggested_action": "Seek immediate assistance.",
                    }
                ],
            }
        )
        self.assertEqual(assessment["overall_category"], "EMERGENCY")
        self.assertEqual(assessment["emergency_message"], EMERGENCY_MESSAGE)

    def test_bp_plus_positive_protein_after_20_weeks_flags_possible_concern(self):
        assessment = assess(systolic_bp=140, urine_protein="+1")
        self.assertTrue(assessment["possible_preeclampsia_concern"])
        self.assertEqual(
            assessment["possible_preeclampsia_message"], PREECLAMPSIA_MESSAGE
        )
        self.assertEqual(
            assessment["possible_preeclampsia_disclaimer"],
            PREECLAMPSIA_DISCLAIMER,
        )

    def test_bp_plus_documented_organ_lab_flag_is_possible_concern(self):
        assessment = assess(systolic_bp=140, serum_creatinine=90)
        self.assertTrue(assessment["possible_preeclampsia_concern"])
        self.assertIn("LAB002", {item["rule_id"] for item in assessment["triggered_findings"]})

    def test_protein_alone_does_not_create_possible_concern_or_diagnosis(self):
        assessment = assess(urine_protein="+1")
        self.assertFalse(assessment["possible_preeclampsia_concern"])
        self.assertIn("not a diagnosis", assessment["summary"].casefold())

    def test_before_20_weeks_uses_existing_rule_without_preeclampsia_flag(self):
        assessment = assess(
            gestational_age_weeks=19,
            systolic_bp=145,
            urine_protein="+1",
        )
        rule_ids = {finding["rule_id"] for finding in assessment["triggered_findings"]}
        self.assertIn("GA001", rule_ids)
        self.assertNotIn("GA003", rule_ids)
        self.assertFalse(assessment["possible_preeclampsia_concern"])

    def test_laboratory_recommendations_are_relevant(self):
        assessment = assess(platelet_count=140000)
        recommendation_text = " ".join(
            item["recommendation"] for item in assessment["individual_recommendations"]
        ).casefold()
        self.assertIn("professional assessment", recommendation_text)
        self.assertIn("LAB001", {item["rule_id"] for item in assessment["individual_recommendations"]})

    def test_highest_severity_wins_and_findings_are_all_retained(self):
        assessment = assess(
            systolic_bp=160,
            urine_protein="+1",
            maternal_warning_signs=["headache"],
        )
        self.assertEqual(assessment["overall_severity"], "URGENT")
        self.assertEqual(
            assessment["overall_category"], "URGENT CLINICAL ASSESSMENT REQUIRED"
        )
        self.assertGreaterEqual(assessment["triggered_rule_count"], 4)

    def test_duplicate_recommendations_are_combined_and_keep_all_reasons(self):
        alerts = [
            {
                "rule_id": "A1",
                "rule_name": "First finding",
                "severity": "WARNING",
                "suggested_action": " Arrange professional assessment. ",
            },
            {
                "rule_id": "A2",
                "rule_name": "Second finding",
                "severity": "URGENT",
                "suggested_action": "Arrange professional assessment",
            },
        ]
        assessment = build_overall_assessment(
            {"overall_severity": "URGENT", "alerts": alerts}
        )
        self.assertEqual(len(assessment["combined_recommendations"]), 1)
        recommendation = assessment["combined_recommendations"][0]
        self.assertEqual(recommendation["priority"], "URGENT")
        self.assertEqual(recommendation["rule_ids"], ["A2", "A1"])
        self.assertEqual(len(recommendation["reasons"]), 2)

    def test_emergency_recommendations_precede_less_urgent_recommendations(self):
        assessment = assess(
            systolic_bp=145,
            maternal_warning_signs=["seizure"],
        )
        priorities = [
            item["priority"] for item in assessment["combined_recommendations"]
        ]
        self.assertEqual(priorities[0], "EMERGENCY")
        self.assertEqual(
            priorities,
            sorted(priorities, key=lambda level: -{
                "INFORMATION": 0,
                "CAUTION": 1,
                "WARNING": 2,
                "URGENT": 3,
                "EMERGENCY": 4,
            }[level]),
        )

    def test_missing_measurements_remain_monitoring_flags_not_reassurance(self):
        result = evaluate_visit(
            make_visit(systolic_bp=None, diastolic_bp=None, urine_protein=None)
        )
        assessment = build_overall_assessment(result)
        self.assertEqual(assessment["overall_category"], "MONITORING REQUIRED")
        self.assertIn("BP010", {finding["rule_id"] for finding in assessment["triggered_findings"]})
        self.assertIn("not treated as normal", assessment["explanation"])

    def test_identical_input_is_reproducible(self):
        evaluation = evaluate_visit(make_visit(systolic_bp=150, urine_protein="+2"))
        self.assertEqual(
            build_overall_assessment(evaluation), build_overall_assessment(evaluation)
        )
        self.assertEqual(build_overall_assessment(evaluation)["assessment_version"], ASSESSMENT_VERSION)


class AssessmentPersistenceTests(unittest.TestCase):
    def setUp(self):
        self.original_database_path = database.DATABASE_PATH
        self.temp_directory = tempfile.TemporaryDirectory()
        database.DATABASE_PATH = Path(self.temp_directory.name) / "assessment-tests.db"
        database.initialize_database()
        self.patient_id = database.add_patient("Assessment Test Patient", 30)

    def tearDown(self):
        database.DATABASE_PATH = self.original_database_path
        self.temp_directory.cleanup()

    def test_re_evaluation_updates_one_snapshot_and_history_stays_visit_specific(self):
        emergency_visit_id = database.add_antenatal_visit(
            self.patient_id,
            date.today(),
            28,
            120,
            80,
            "Negative",
            maternal_warning_signs=["seizure"],
        )
        monitoring_visit_id = database.add_antenatal_visit(
            self.patient_id,
            date.today(),
            29,
            120,
            80,
            "Trace",
        )
        first_emergency = database.get_visit_monitoring(emergency_visit_id)
        self.assertEqual(first_emergency["assessment"]["overall_category"], "EMERGENCY")
        self.assertEqual(
            first_emergency["assessment"]["emergency_message"], SEIZURE_MESSAGE
        )
        self.assertEqual(
            database.get_visit_monitoring(monitoring_visit_id)["assessment"]["overall_category"],
            "MONITORING REQUIRED",
        )

        database.reevaluate_visit_monitoring(emergency_visit_id)
        visits = database.get_patient_visits(self.patient_id)
        by_id = {visit["visit_id"]: visit for visit in visits}
        self.assertEqual(
            by_id[emergency_visit_id]["assessment"]["overall_category"], "EMERGENCY"
        )
        self.assertEqual(
            by_id[monitoring_visit_id]["assessment"]["overall_category"],
            "MONITORING REQUIRED",
        )
        connection = sqlite3.connect(database.DATABASE_PATH)
        try:
            saved_count = connection.execute(
                "SELECT COUNT(*) FROM antenatal_visits WHERE assessment_snapshot IS NOT NULL"
            ).fetchone()[0]
            self.assertEqual(saved_count, 2)
            snapshot = json.loads(
                connection.execute(
                    "SELECT assessment_snapshot FROM antenatal_visits WHERE visit_id = ?",
                    (emergency_visit_id,),
                ).fetchone()[0]
            )
            self.assertEqual(snapshot["assessment_version"], ASSESSMENT_VERSION)
        finally:
            connection.close()

    def test_dashboard_assessment_totals_count_visits_once_by_overall_level(self):
        database.add_antenatal_visit(
            self.patient_id, date.today(), 28, 120, 80, "Negative"
        )
        database.add_antenatal_visit(
            self.patient_id, date.today(), 29, 120, 80, "Trace"
        )
        database.add_antenatal_visit(
            self.patient_id,
            date.today(),
            30,
            120,
            80,
            "Negative",
            maternal_warning_signs=["seizure"],
        )
        data = database.get_dashboard_data()
        counts = data["assessment_overview"]
        self.assertEqual(counts["no_alert_visits"], 1)
        self.assertEqual(counts["monitoring_required_visits"], 1)
        self.assertEqual(counts["emergency_visits"], 1)
        self.assertEqual(len(data["recent_assessments"]), 3)


if __name__ == "__main__":
    unittest.main()
