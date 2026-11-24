"""Unit and isolated SQLite integration tests for the monitoring engine."""

import sqlite3
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

import database
from monitoring_rules import evaluate_visit


def visit(**overrides):
    data = {
        "visit_id": 100,
        "patient_id": 7,
        "visit_date": "2026-01-10",
        "gestational_age_weeks": 28,
        "systolic_bp": 120,
        "diastolic_bp": 80,
        "urine_protein": "Negative",
        "maternal_warning_signs": [],
        "other_symptoms": None,
    }
    data.update(overrides)
    return data


def rule_ids(data, previous_visits=None):
    return {alert["rule_id"] for alert in evaluate_visit(data, previous_visits)["alerts"]}


class BloodPressureRuleTests(unittest.TestCase):
    def test_below_threshold_is_informational_not_clearance(self):
        result = evaluate_visit(visit())
        self.assertIn("BP001", {alert["rule_id"] for alert in result["alerts"]})
        self.assertIn("does not", result["summary"])

    def test_systolic_and_diastolic_rules_are_independent(self):
        self.assertIn("BP002", rule_ids(visit(systolic_bp=145, diastolic_bp=85)))
        self.assertNotIn("BP003", rule_ids(visit(systolic_bp=145, diastolic_bp=85)))
        self.assertIn("BP003", rule_ids(visit(systolic_bp=130, diastolic_bp=95)))
        self.assertIn("BP006", rule_ids(visit(systolic_bp=165, diastolic_bp=80)))
        self.assertIn("BP007", rule_ids(visit(systolic_bp=130, diastolic_bp=115)))

    def test_moderate_values_and_combined_finding(self):
        result = evaluate_visit(visit(systolic_bp=155, diastolic_bp=105))
        found = {alert["rule_id"] for alert in result["alerts"]}
        self.assertTrue({"BP004", "BP005", "BP008"}.issubset(found))
        self.assertEqual(result["overall_severity"], "WARNING")

    def test_exact_bp_boundaries(self):
        cases = [
            (139, 89, "BP001"),
            (140, 89, "BP002"),
            (149, 89, "BP002"),
            (150, 89, "BP004"),
            (159, 89, "BP004"),
            (160, 89, "BP006"),
            (139, 90, "BP003"),
            (139, 99, "BP003"),
            (139, 100, "BP005"),
            (139, 109, "BP005"),
            (139, 110, "BP007"),
        ]
        for systolic, diastolic, expected in cases:
            with self.subTest(systolic=systolic, diastolic=diastolic):
                self.assertIn(expected, rule_ids(visit(systolic_bp=systolic, diastolic_bp=diastolic)))

    def test_severe_bp_has_urgent_overall_level_and_below_band_is_not_flagged(self):
        for values in ((160, 80), (120, 110)):
            with self.subTest(values=values):
                result = evaluate_visit(
                    visit(systolic_bp=values[0], diastolic_bp=values[1])
                )
                self.assertEqual(result["overall_severity"], "URGENT")
        self.assertNotIn("BP002", rule_ids(visit(systolic_bp=139)))
        self.assertNotIn("BP003", rule_ids(visit(diastolic_bp=89)))

    def test_missing_and_invalid_bp_are_not_treated_as_normal(self):
        for data in (
            visit(systolic_bp=None, diastolic_bp=None),
            visit(systolic_bp="", diastolic_bp="invalid"),
            visit(systolic_bp=120.5, diastolic_bp=80),
        ):
            ids = rule_ids(data)
            self.assertIn("BP010", ids)
            self.assertNotIn("BP001", ids)

    def test_repeated_elevated_visits_are_flagged_without_confirmation_claim(self):
        result = evaluate_visit(
            visit(systolic_bp=145),
            previous_visits=[{"visit_id": 10, "systolic_bp": 142, "diastolic_bp": 82}],
        )
        bp009 = next(alert for alert in result["alerts"] if alert["rule_id"] == "BP009")
        self.assertIn("timing", bp009["explanation"])
        self.assertIn("does not establish diagnostic confirmation", bp009["explanation"])


class UrineAndGestationalRuleTests(unittest.TestCase):
    def test_each_urine_option(self):
        cases = [
            ("Negative", "UR001"),
            ("Trace", "UR002"),
            ("+1", "UR003"),
            ("+2", "UR004"),
            ("+3", "UR005"),
            ("+4", "UR006"),
            ("Not tested", "UR007"),
            (None, "UR007"),
        ]
        for protein, expected in cases:
            with self.subTest(protein=protein):
                self.assertIn(expected, rule_ids(visit(urine_protein=protein)))

    def test_invalid_urine_and_protein_boundaries(self):
        self.assertIn("UR007", rule_ids(visit(urine_protein="unknown")))
        self.assertNotIn("UR003", rule_ids(visit(urine_protein="unknown")))
        self.assertNotIn(
            "GA003",
            rule_ids(
                visit(
                    gestational_age_weeks=20,
                    systolic_bp=140,
                    urine_protein="Trace",
                )
            ),
        )

    def test_positive_protein_with_normal_bp_and_raised_bp(self):
        self.assertIn(
            "GA004",
            rule_ids(visit(systolic_bp=120, diastolic_bp=80, urine_protein="+1")),
        )
        self.assertIn(
            "GA003",
            rule_ids(visit(gestational_age_weeks=28, systolic_bp=140, urine_protein="+1")),
        )

    def test_gestational_age_before_twenty_at_twenty_and_after(self):
        self.assertIn(
            "GA001", rule_ids(visit(gestational_age_weeks=19, systolic_bp=140))
        )
        self.assertIn(
            "GA002", rule_ids(visit(gestational_age_weeks=20, systolic_bp=140))
        )
        self.assertIn(
            "GA002", rule_ids(visit(gestational_age_weeks=21, diastolic_bp=90))
        )

    def test_invalid_or_missing_gestational_age(self):
        self.assertIn("GA005", rule_ids(visit(gestational_age_weeks=None)))
        self.assertIn("GA005", rule_ids(visit(gestational_age_weeks=46)))


class SymptomAndCombinedRuleTests(unittest.TestCase):
    def test_each_symptom_rule_and_emergency_override(self):
        cases = [
            ("headache", "SYM001", "WARNING"),
            ("visual_disturbance", "SYM002", "URGENT"),
            ("epigastric_pain", "SYM003", "URGENT"),
            ("difficulty_breathing", "SYM004", "URGENT"),
            ("reduced_urine_output", "SYM005", "WARNING"),
            ("nausea_vomiting", "SYM006", "CAUTION"),
            ("seizure", "SYM007", "EMERGENCY"),
        ]
        for symptom, expected_rule, expected_level in cases:
            with self.subTest(symptom=symptom):
                result = evaluate_visit(visit(maternal_warning_signs=[symptom]))
                finding = next(a for a in result["alerts"] if a["rule_id"] == expected_rule)
                self.assertEqual(finding["severity"], expected_level)
                if symptom == "seizure":
                    self.assertEqual(result["overall_severity"], "EMERGENCY")

    def test_other_symptoms_are_recorded_for_review(self):
        self.assertIn("SYM008", rule_ids(visit(other_symptoms="Other reported symptom")))

    def test_combined_bp_symptom_rules(self):
        cases = [
            ("headache", "COM001"),
            ("visual_disturbance", "COM002"),
            ("epigastric_pain", "COM003"),
            ("difficulty_breathing", "COM004"),
        ]
        for symptom, expected in cases:
            with self.subTest(symptom=symptom):
                self.assertIn(
                    expected,
                    rule_ids(visit(systolic_bp=145, maternal_warning_signs=[symptom])),
                )
        self.assertIn(
            "COM005",
            rule_ids(visit(urine_protein="+1", maternal_warning_signs=["headache"])),
        )


class LaboratoryRuleTests(unittest.TestCase):
    def test_supported_laboratory_thresholds(self):
        cases = [
            ({"platelet_count": 149999}, "LAB001"),
            ({"serum_creatinine": 90}, "LAB002"),
            ({"alt_value": 71}, "LAB003"),
            ({"alt_value": 60, "alt_upper_limit": 29}, "LAB003"),
            ({"ast_value": 42, "ast_upper_limit": 40}, "LAB004"),
            ({"urine_protein_creatinine_ratio": 30}, "LAB005"),
            ({"urine_albumin_creatinine_ratio": 8}, "LAB006"),
        ]
        for values, expected in cases:
            with self.subTest(rule=expected):
                self.assertIn(expected, rule_ids(visit(**values)))

    def test_lab_cutoffs_and_alt_uses_strict_greater_than(self):
        self.assertNotIn("LAB001", rule_ids(visit(platelet_count=150000)))
        self.assertNotIn("LAB002", rule_ids(visit(serum_creatinine=89.9)))
        self.assertNotIn("LAB003", rule_ids(visit(alt_value=70)))
        self.assertNotIn(
            "LAB003",
            rule_ids(visit(alt_value=60, alt_upper_limit=30)),
        )
        self.assertNotIn("LAB004", rule_ids(visit(ast_value=40, ast_upper_limit=40)))
        self.assertNotIn(
            "LAB005", rule_ids(visit(urine_protein_creatinine_ratio=29.9))
        )
        self.assertNotIn(
            "LAB006", rule_ids(visit(urine_albumin_creatinine_ratio=7.9))
        )

    def test_optional_missing_values_are_skipped_and_ast_needs_lab_limit(self):
        ids = rule_ids(visit())
        self.assertFalse(any(rule_id.startswith("LAB00") for rule_id in ids))
        ids_with_ast = rule_ids(visit(ast_value=45))
        self.assertIn("LAB008", ids_with_ast)
        self.assertNotIn("LAB004", ids_with_ast)

    def test_invalid_optional_lab_value_is_reported(self):
        self.assertIn("LAB007", rule_ids(visit(platelet_count=-1)))


class DatabaseMonitoringTests(unittest.TestCase):
    def setUp(self):
        self.original_path = database.DATABASE_PATH
        self.temporary_directory = tempfile.TemporaryDirectory()
        database.DATABASE_PATH = Path(self.temporary_directory.name) / "test.db"
        database.initialize_database()
        self.patient_id = database.add_patient("Unit Test Patient", 30)

    def tearDown(self):
        database.DATABASE_PATH = self.original_path
        self.temporary_directory.cleanup()

    def test_visit_and_alerts_are_saved_and_repeat_evaluation_does_not_duplicate(self):
        visit_id = database.add_antenatal_visit(
            self.patient_id,
            date.today(),
            28,
            120,
            80,
            "Negative",
            maternal_warning_signs=["seizure"],
        )
        first = database.get_visit_monitoring(visit_id)
        self.assertEqual(first["overall_severity"], "EMERGENCY")
        first_rule_ids = {alert["rule_id"] for alert in first["alerts"]}
        self.assertIn("SYM007", first_rule_ids)

        second = database.reevaluate_visit_monitoring(visit_id)
        second_rule_ids = {alert["rule_id"] for alert in second["alerts"]}
        self.assertEqual(first_rule_ids, second_rule_ids)
        self.assertEqual(len(first["alerts"]), len(second["alerts"]))
        saved_alerts = database.get_patient_visits(self.patient_id)[0]["alerts"]
        self.assertEqual(
            [
                (alert["rule_id"], alert["severity"], alert["rule_version"])
                for alert in saved_alerts
            ],
            [
                (alert["rule_id"], alert["severity"], alert["rule_version"])
                for alert in second["alerts"]
            ],
        )

    def test_dashboard_alert_counts_use_distinct_visits(self):
        database.add_antenatal_visit(
            self.patient_id, date.today(), 28, 165, 112, "Negative",
            maternal_warning_signs=["seizure"],
        )
        overview = database.get_dashboard_data()["monitoring_overview"]
        self.assertEqual(overview["evaluated_visits"], 1)
        self.assertEqual(overview["emergency_visits"], 1)
        self.assertEqual(overview["urgent_visits"], 1)

    def test_unknown_patient_is_rejected_and_no_visit_is_written(self):
        with self.assertRaises(ValueError):
            database.add_antenatal_visit(
                999999, date.today(), 28, 120, 80, "Negative"
            )
        self.assertEqual(database.get_patient_visits(999999), [])

    def test_optional_fields_must_be_valid_and_write_is_atomic(self):
        with self.assertRaises(ValueError):
            database.add_antenatal_visit(
                self.patient_id,
                date.today(),
                28,
                120,
                80,
                "Negative",
                urine_output_ml=300,
            )
        self.assertEqual(database.get_patient_visits(self.patient_id), [])

    def test_rule_engine_failure_rolls_back_visit_insert(self):
        with patch(
            "monitoring_rules.evaluate_visit",
            side_effect=RuntimeError("isolated rule test failure"),
        ):
            with self.assertRaises(RuntimeError):
                database.add_antenatal_visit(
                    self.patient_id, date.today(), 28, 120, 80, "Negative"
                )
        self.assertEqual(database.get_patient_visits(self.patient_id), [])


class MigrationPreservationTests(unittest.TestCase):
    def test_legacy_records_survive_safe_optional_column_migration(self):
        original_path = database.DATABASE_PATH
        with tempfile.TemporaryDirectory() as temporary_directory:
            path = Path(temporary_directory) / "legacy.db"
            connection = sqlite3.connect(path)
            try:
                connection.executescript(
                    """
                    CREATE TABLE patients (
                        patient_id INTEGER PRIMARY KEY AUTOINCREMENT,
                        full_name TEXT NOT NULL,
                        age INTEGER,
                        contact_number TEXT,
                        registration_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    );
                    CREATE TABLE antenatal_visits (
                        visit_id INTEGER PRIMARY KEY AUTOINCREMENT,
                        patient_id INTEGER NOT NULL,
                        visit_date DATE NOT NULL,
                        gestational_age_weeks INTEGER NOT NULL,
                        systolic_bp INTEGER NOT NULL,
                        diastolic_bp INTEGER NOT NULL,
                        urine_protein TEXT NOT NULL,
                        notes TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (patient_id) REFERENCES patients(patient_id)
                    );
                    INSERT INTO patients (patient_id, full_name, age, registration_date)
                    VALUES (41, 'Legacy Patient', 32, '2024-01-02 03:04:05');
                    INSERT INTO antenatal_visits
                        (visit_id, patient_id, visit_date, gestational_age_weeks,
                         systolic_bp, diastolic_bp, urine_protein, notes)
                    VALUES (91, 41, '2024-02-03', 28, 120, 80, 'Negative', 'legacy note');
                    """
                )
                connection.commit()
            finally:
                connection.close()

            database.DATABASE_PATH = path
            try:
                database.initialize_database()
                patient = database.get_patient_by_id(41)
                saved_visits = database.get_patient_visits(41)
                self.assertEqual(patient["registration_date"], "2024-01-02 03:04:05")
                self.assertEqual(len(saved_visits), 1)
                self.assertEqual(saved_visits[0]["visit_id"], 91)
                self.assertEqual(saved_visits[0]["notes"], "legacy note")
                self.assertIsNone(saved_visits[0]["monitoring_evaluated_at"])
                self.assertEqual(saved_visits[0]["platelet_count"], None)
                self.assertIsNone(saved_visits[0]["assessment_snapshot"])
                self.assertIsNone(saved_visits[0]["assessment"])
                self.assertIsNone(database.get_visit_monitoring(91))
            finally:
                database.DATABASE_PATH = original_path


if __name__ == "__main__":
    unittest.main()
