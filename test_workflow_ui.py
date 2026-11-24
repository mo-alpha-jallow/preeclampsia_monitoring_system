"""Streamlit workflow smoke tests against temporary SQLite databases."""

import tempfile
import unittest
import json
from datetime import date, datetime, timedelta
from pathlib import Path

import database
from streamlit.testing.v1 import AppTest


APP_FILE = Path(__file__).with_name("app.py")


class StreamlitWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.original_database_path = database.DATABASE_PATH
        self.temp_directory = tempfile.TemporaryDirectory()
        database.DATABASE_PATH = Path(self.temp_directory.name) / "workflow.db"
        database.initialize_database()

    def tearDown(self):
        database.DATABASE_PATH = self.original_database_path
        self.temp_directory.cleanup()

    def new_app(self):
        app = AppTest.from_file(str(APP_FILE), default_timeout=40).run()
        self.assertFalse(app.exception, [str(item.value) for item in app.exception])
        return app

    def test_empty_database_and_all_navigation_pages_render(self):
        app = self.new_app()
        self.assertEqual(database.get_all_patients(), [])
        for page in (
            "Patient Registration",
            "Patient Records",
            "Antenatal Visits",
            "Patient Visit History",
            "Dashboard",
        ):
            app.sidebar.radio[0].set_value(page).run()
            self.assertFalse(
                app.exception, f"{page}: {[str(item.value) for item in app.exception]}"
            )

    def test_database_initialization_error_is_user_friendly(self):
        blocked_path = Path(self.temp_directory.name) / "not-a-database-file"
        blocked_path.mkdir()
        database.DATABASE_PATH = blocked_path
        app = AppTest.from_file(str(APP_FILE), default_timeout=40).run()
        self.assertFalse(app.exception, [str(item.value) for item in app.exception])
        self.assertTrue(
            any("database could not be opened or initialized" in str(item.value).casefold()
                for item in app.error)
        )

    def test_registration_resets_after_save_and_does_not_repeat_old_values(self):
        app = self.new_app()
        app.sidebar.radio[0].set_value("Patient Registration").run()
        app.text_input(key="registration_name_0").set_value("Temporary Workflow Patient")
        app.number_input(key="registration_age_0").set_value(32)
        app.form_submit_button[0].click().run()

        patients = database.get_all_patients()
        self.assertEqual(len(patients), 1)
        patient_id = patients[0]["patient_id"]
        self.assertTrue(
            any(f"Patient ID: {patient_id}" in str(item.value) for item in app.success)
        )
        self.assertEqual(app.text_input(key="registration_name_1").value, "")

        app.form_submit_button[0].click().run()
        self.assertEqual(len(database.get_all_patients()), 1)
        self.assertTrue(app.error)

    def test_patient_search_edit_cancel_and_save_preserve_identity_and_date(self):
        patient_id = database.add_patient("Searchable Test Patient", 31)
        before = database.get_patient_by_id(patient_id)
        app = self.new_app()
        app.sidebar.radio[0].set_value("Patient Records").run()
        app.text_input[0].set_value("searchable").run()
        self.assertFalse(app.exception)
        self.assertTrue(app.dataframe)
        app.text_input[0].set_value(str(patient_id)).run()
        self.assertFalse(app.exception)

        app.button(key=f"toggle_patient_edit_{patient_id}").click().run()
        app.text_input(key=f"edit_name_{patient_id}_0").set_value("Unsaved Name")
        next(item for item in app.form_submit_button if item.label == "Cancel").click().run()
        self.assertEqual(database.get_patient_by_id(patient_id)["full_name"], before["full_name"])

        app.button(key=f"toggle_patient_edit_{patient_id}").click().run()
        app.text_input(key=f"edit_name_{patient_id}_1").set_value("Updated Searchable Patient")
        app.number_input(key=f"edit_age_{patient_id}_1").set_value(36)
        app.text_input(key=f"edit_contact_{patient_id}_1").set_value("555-0102")
        next(item for item in app.form_submit_button if item.label == "Save Changes").click().run()
        after = database.get_patient_by_id(patient_id)
        self.assertEqual(after["patient_id"], before["patient_id"])
        self.assertEqual(after["registration_date"], before["registration_date"])
        self.assertEqual(after["full_name"], "Updated Searchable Patient")
        self.assertEqual(after["age"], 36)
        self.assertEqual(after["contact_number"], "555-0102")
        self.assertFalse(app.exception)

    def test_history_keeps_assessments_attached_to_the_correct_visit_and_patient(self):
        patient_one = database.add_patient("History Patient One", 28)
        patient_two = database.add_patient("History Patient Two", 33)
        emergency_visit = database.add_antenatal_visit(
            patient_one,
            date.today(),
            28,
            120,
            80,
            "Negative",
            maternal_warning_signs=["seizure"],
        )
        monitoring_visit = database.add_antenatal_visit(
            patient_two, date.today(), 29, 120, 80, "Trace"
        )
        app = self.new_app()
        app.sidebar.radio[0].set_value("Patient Visit History").run()

        app.selectbox(key="history_patient_id").set_value(patient_one).run()
        app.selectbox(key=f"history_visit_id_{patient_one}").set_value(emergency_visit).run()
        self.assertTrue(
            any("Seizure/convulsion recorded" in str(item.value) for item in app.error)
        )
        self.assertFalse(app.exception)

        app.selectbox(key="history_patient_id").set_value(patient_two).run()
        app.selectbox(key=f"history_visit_id_{patient_two}").set_value(monitoring_visit).run()
        self.assertTrue(any("MONITORING REQUIRED" in str(item.value) for item in app.info))
        self.assertFalse(
            any("Seizure/convulsion recorded" in str(item.value) for item in app.error)
        )
        self.assertFalse(app.exception)

    def test_antenatal_form_saves_assessment_and_clears_for_next_visit(self):
        patient_id = database.add_patient("Temporary Visit Workflow Patient", 30)
        app = self.new_app()
        app.sidebar.radio[0].set_value("Antenatal Visits").run()
        app.number_input(key=f"visit_gestational_age_{patient_id}_0").set_value(28)
        # No artificial upper entry ceiling: an unusual positive reading is
        # passed to the existing rule engine for review.
        app.number_input(key=f"visit_systolic_{patient_id}_0").set_value(300)
        app.number_input(key=f"visit_diastolic_{patient_id}_0").set_value(80)
        app.number_input(key=f"platelets_{patient_id}_0").set_value(140000)
        app.number_input(key=f"creatinine_{patient_id}_0").set_value(90.0)
        app.checkbox(key=f"symptom_headache_{patient_id}_0").set_value(True)
        app.form_submit_button[0].click().run()

        visits = database.get_patient_visits(patient_id)
        self.assertEqual(len(visits), 1)
        self.assertEqual(visits[0]["systolic_bp"], 300)
        self.assertEqual(visits[0]["platelet_count"], 140000)
        self.assertEqual(visits[0]["serum_creatinine"], 90)
        self.assertIn("headache", visits[0]["maternal_warning_signs"])
        self.assertEqual(
            visits[0]["assessment"]["overall_category"],
            "URGENT CLINICAL ASSESSMENT REQUIRED",
        )
        self.assertTrue(visits[0]["assessment"]["possible_preeclampsia_concern"])
        self.assertTrue(
            any("Visit saved successfully" in str(item.value) for item in app.success)
        )
        self.assertFalse(app.exception)

        # The form key changes after save, so a repeat click cannot resubmit the
        # previous visit values under the new form.
        self.assertIsNone(
            app.number_input(key=f"visit_systolic_{patient_id}_1").value
        )
        app.form_submit_button[0].click().run()
        self.assertEqual(len(database.get_patient_visits(patient_id)), 1)
        self.assertTrue(app.error)

    def test_future_datetime_invalid_bp_and_invalid_optional_values_are_rejected(self):
        patient_id = database.add_patient("Temporary Validation Patient", 27)
        with self.assertRaises(ValueError):
            database.add_antenatal_visit(
                patient_id, "not-a-date", 28, 120, 80, "Negative"
            )
        with self.assertRaises(ValueError):
            database.add_antenatal_visit(
                patient_id, datetime.now(), 28, 120, 80, "Negative"
            )
        with self.assertRaises(ValueError):
            database.add_antenatal_visit(
                patient_id, date.today() + timedelta(days=1), 28, 120, 80, "Negative"
            )
        with self.assertRaises(ValueError):
            database.add_antenatal_visit(
                patient_id, date.today(), 28, -120, 80, "Negative"
            )
        with self.assertRaises(ValueError):
            database.add_antenatal_visit(
                patient_id,
                date.today(),
                28,
                120,
                80,
                "Negative",
                urine_output_ml=10,
            )
        with self.assertRaises(ValueError):
            database.add_antenatal_visit(
                patient_id,
                date.today(),
                28,
                120,
                80,
                "Negative",
                maternal_warning_signs=["unrecognized_symptom"],
            )
        with self.assertRaises(ValueError):
            database.add_antenatal_visit(
                patient_id,
                date.today(),
                28,
                120,
                80,
                "Negative",
                maternal_warning_signs=["other_symptoms"],
            )
        with self.assertRaises(ValueError):
            database.add_patient("Age Validation Patient", 121)
        with self.assertRaises(ValueError):
            database.add_patient("Long Contact Patient", 30, "1" * 31)
        self.assertEqual(database.get_patient_visits(patient_id), [])

    def test_dashboard_charts_render_with_light_background_and_actual_counts(self):
        patient_id = database.add_patient("Temporary Chart Patient", 30)
        database.add_antenatal_visit(patient_id, date.today(), 28, 125, 82, "Trace")
        database.add_antenatal_visit(patient_id, date.today(), 29, 127, 83, "+1")
        app = self.new_app()

        self.assertEqual(len(app.get("vega_lite_chart")), 5)
        for chart_element in app.get("vega_lite_chart"):
            spec = json.loads(chart_element.proto.spec)
            config = spec["config"]
            self.assertEqual(config["background"], "#FFFFFF")
            self.assertEqual(config["view"]["fill"], "#FFFFFF")
            self.assertEqual(config["axis"]["labelColor"], "#334155")
        dashboard = database.get_dashboard_data()
        self.assertEqual(dashboard["summary"]["total_patients"], 1)
        self.assertEqual(dashboard["summary"]["total_visits"], 2)


if __name__ == "__main__":
    unittest.main()
