"""SQLite helpers for patient and antenatal visit records."""

import sqlite3
import json
import math
from contextlib import contextmanager
from datetime import date, datetime
from pathlib import Path


DATABASE_PATH = Path(__file__).resolve().parent / "preeclampsia.db"
URINE_PROTEIN_VALUES = ("Negative", "Trace", "+1", "+2", "+3", "+4", "Not tested")
MATERNAL_WARNING_SIGN_CODES = {
    "headache",
    "visual_disturbance",
    "epigastric_pain",
    "nausea_vomiting",
    "difficulty_breathing",
    "reduced_urine_output",
    "seizure",
    "other_symptoms",
}

MONITORING_VISIT_COLUMNS = {
    "maternal_warning_signs": "TEXT",
    "other_symptoms": "TEXT",
    "platelet_count": "INTEGER",
    "serum_creatinine": "REAL",
    "alt_value": "REAL",
    "alt_upper_limit": "REAL",
    "ast_value": "REAL",
    "ast_upper_limit": "REAL",
    "urine_protein_creatinine_ratio": "REAL",
    "urine_albumin_creatinine_ratio": "REAL",
    "urine_output_ml": "REAL",
    "urine_output_period_hours": "REAL",
    "overall_severity": "TEXT",
    "monitoring_summary": "TEXT",
    "monitoring_evaluated_at": "TIMESTAMP",
    "monitoring_rule_version": "TEXT",
    "assessment_snapshot": "TEXT",
    "assessment_version": "TEXT",
    "assessment_saved_at": "TIMESTAMP",
}


@contextmanager
def _connection():
    """Open a database connection, enable foreign keys, then always close it."""
    connection = sqlite3.connect(DATABASE_PATH)
    connection.row_factory = sqlite3.Row
    try:
        connection.execute("PRAGMA foreign_keys = ON")
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def initialize_database():
    """Create the database tables if needed and turn on foreign key checks."""
    try:
        with _connection() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS patients (
                    patient_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    full_name TEXT NOT NULL,
                    age INTEGER,
                    contact_number TEXT,
                    registration_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS antenatal_visits (
                    visit_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    patient_id INTEGER NOT NULL,
                    visit_date DATE NOT NULL,
                    gestational_age_weeks INTEGER NOT NULL,
                    systolic_bp INTEGER NOT NULL,
                    diastolic_bp INTEGER NOT NULL,
                    urine_protein TEXT NOT NULL CHECK (
                        urine_protein IN ('Negative', 'Trace', '+1', '+2', '+3', '+4', 'Not tested')
                    ),
                    notes TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (patient_id) REFERENCES patients(patient_id)
                );
                """
            )
            connection.execute("BEGIN")
            existing_columns = {
                row["name"]
                for row in connection.execute("PRAGMA table_info(antenatal_visits)")
            }
            for column_name, column_type in MONITORING_VISIT_COLUMNS.items():
                if column_name not in existing_columns:
                    connection.execute(
                        f"ALTER TABLE antenatal_visits ADD COLUMN {column_name} {column_type}"
                    )
            connection.execute(
                """CREATE TABLE IF NOT EXISTS visit_alerts (
                    alert_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    visit_id INTEGER NOT NULL,
                    rule_id TEXT NOT NULL,
                    rule_name TEXT NOT NULL,
                    severity TEXT NOT NULL,
                    measurement TEXT NOT NULL,
                    explanation TEXT NOT NULL,
                    suggested_action TEXT NOT NULL,
                    guideline_source TEXT NOT NULL,
                    rule_version TEXT NOT NULL,
                    generated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (visit_id) REFERENCES antenatal_visits(visit_id)
                        ON DELETE CASCADE,
                    UNIQUE (visit_id, rule_id)
                )"""
            )
    except sqlite3.Error as error:
        raise RuntimeError(f"Could not initialize the database: {error}") from error


def _required_text(value, field_name, *, max_length=None):
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} is required.")
    cleaned = value.strip()
    if max_length is not None and len(cleaned) > max_length:
        raise ValueError(f"{field_name} must be {max_length} characters or fewer.")
    return cleaned


def add_patient(full_name, age=None, contact_number=None):
    """Add a patient and return the new patient's ID."""
    name = _required_text(full_name, "Full name", max_length=150)
    if age is not None and (
        isinstance(age, bool) or not isinstance(age, int) or not 1 <= age <= 120
    ):
        raise ValueError("Age must be a whole number from 1 to 120 or None.")
    if contact_number is not None:
        if not isinstance(contact_number, str):
            raise ValueError("Contact number must be text or None.")
        contact_number = contact_number.strip() or None
        if contact_number is not None and len(contact_number) > 30:
            raise ValueError("Contact number must be 30 characters or fewer.")
    try:
        with _connection() as connection:
            cursor = connection.execute(
                "INSERT INTO patients (full_name, age, contact_number) VALUES (?, ?, ?)",
                (name, age, contact_number),
            )
            return cursor.lastrowid
    except sqlite3.Error as error:
        raise RuntimeError(f"Could not add patient: {error}") from error


def get_all_patients():
    """Return all patients as dictionaries, newest registration first."""
    try:
        with _connection() as connection:
            rows = connection.execute(
                "SELECT * FROM patients ORDER BY registration_date DESC, patient_id DESC"
            ).fetchall()
            return [dict(row) for row in rows]
    except sqlite3.Error as error:
        raise RuntimeError(f"Could not retrieve patients: {error}") from error


def get_patient_by_id(patient_id):
    """Return one patient as a dictionary, or None if the ID is not found."""
    try:
        with _connection() as connection:
            row = connection.execute(
                "SELECT * FROM patients WHERE patient_id = ?", (patient_id,)
            ).fetchone()
            return dict(row) if row else None
    except sqlite3.Error as error:
        raise RuntimeError(f"Could not retrieve patient: {error}") from error


def update_patient(patient_id, full_name, age, contact_number=None):
    """Update a patient's name, age, and contact number; return whether found."""
    if isinstance(patient_id, bool) or not isinstance(patient_id, int) or patient_id <= 0:
        raise ValueError("Patient ID must be a positive whole number.")
    name = _required_text(full_name, "Full name", max_length=150)
    if isinstance(age, bool) or not isinstance(age, int) or not 1 <= age <= 120:
        raise ValueError("Age must be a whole number from 1 to 120.")
    if contact_number is not None:
        if not isinstance(contact_number, str):
            raise ValueError("Contact number must be text or None.")
        contact_number = contact_number.strip() or None
        if contact_number is not None and len(contact_number) > 30:
            raise ValueError("Contact number must be 30 characters or fewer.")

    try:
        with _connection() as connection:
            cursor = connection.execute(
                """UPDATE patients
                SET full_name = ?, age = ?, contact_number = ?
                WHERE patient_id = ?""",
                (name, age, contact_number, patient_id),
            )
            return cursor.rowcount == 1
    except sqlite3.Error as error:
        raise RuntimeError(f"Could not update patient: {error}") from error


def _optional_measurement(value, label, *, whole_number=False, positive=False):
    if value is None or (isinstance(value, str) and not value.strip()):
        return None
    if isinstance(value, bool):
        raise ValueError(f"{label} must be a number.")
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError) as error:
        raise ValueError(f"{label} must be a number.") from error
    if not math.isfinite(number) or number < 0 or (positive and number <= 0):
        raise ValueError(f"{label} must be a valid {'positive ' if positive else 'non-negative '}number.")
    if whole_number and not number.is_integer():
        raise ValueError(f"{label} must be a whole number.")
    return int(number) if whole_number else number


def _save_monitoring_evaluation(connection, visit_id, evaluation):
    """Replace a visit's alert set and persist its evaluation in the same transaction."""
    from assessment_engine import build_overall_assessment

    assessment = build_overall_assessment(evaluation)
    assessment_snapshot = json.dumps(
        assessment, ensure_ascii=False, sort_keys=True
    )
    connection.execute("DELETE FROM visit_alerts WHERE visit_id = ?", (visit_id,))
    for alert in evaluation["alerts"]:
        connection.execute(
            """INSERT INTO visit_alerts
            (visit_id, rule_id, rule_name, severity, measurement, explanation,
             suggested_action, guideline_source, rule_version)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                visit_id,
                alert["rule_id"],
                alert["rule_name"],
                alert["severity"],
                alert["measurement"],
                alert["explanation"],
                alert["suggested_action"],
                alert["guideline_source"],
                alert["rule_version"],
            ),
        )
    connection.execute(
        """UPDATE antenatal_visits
        SET overall_severity = ?, monitoring_summary = ?,
            monitoring_evaluated_at = CURRENT_TIMESTAMP,
            monitoring_rule_version = ?, assessment_snapshot = ?,
            assessment_version = ?, assessment_saved_at = CURRENT_TIMESTAMP
        WHERE visit_id = ?""",
        (
            evaluation["overall_severity"],
            evaluation["summary"],
            evaluation["rule_version"],
            assessment_snapshot,
            assessment["assessment_version"],
            visit_id,
        ),
    )
    return assessment


def add_antenatal_visit(
    patient_id, visit_date, gestational_age_weeks, systolic_bp,
    diastolic_bp, urine_protein, notes=None, *, maternal_warning_signs=None,
    other_symptoms=None, platelet_count=None, serum_creatinine=None,
    alt_value=None, alt_upper_limit=None, ast_value=None, ast_upper_limit=None,
    urine_protein_creatinine_ratio=None, urine_albumin_creatinine_ratio=None,
    urine_output_ml=None, urine_output_period_hours=None
):
    """Save and evaluate a visit atomically; return its generated visit ID."""
    if isinstance(patient_id, bool) or not isinstance(patient_id, int) or patient_id <= 0:
        raise ValueError("Patient ID must be a positive whole number.")
    if isinstance(gestational_age_weeks, bool) or not isinstance(gestational_age_weeks, int) or not 1 <= gestational_age_weeks <= 45:
        raise ValueError("Gestational age must be a whole number from 1 to 45 weeks.")
    for value, label in ((systolic_bp, "Systolic blood pressure"), (diastolic_bp, "Diastolic blood pressure")):
        if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
            raise ValueError(f"{label} must be a positive whole number.")
    if systolic_bp <= diastolic_bp:
        raise ValueError("Systolic blood pressure must be greater than diastolic blood pressure.")
    if urine_protein not in URINE_PROTEIN_VALUES:
        raise ValueError(f"Urine protein must be one of: {', '.join(URINE_PROTEIN_VALUES)}.")
    if notes is not None and not isinstance(notes, str):
        raise ValueError("Notes must be text or None.")
    if notes is not None and len(notes) > 2000:
        raise ValueError("Notes must be 2000 characters or fewer.")
    if other_symptoms is not None and not isinstance(other_symptoms, str):
        raise ValueError("Other symptoms must be text or None.")
    if other_symptoms is not None and len(other_symptoms) > 500:
        raise ValueError("Other symptoms must be 500 characters or fewer.")
    if maternal_warning_signs is None:
        maternal_warning_signs = []
    if not isinstance(maternal_warning_signs, (list, tuple, set)):
        raise ValueError("Maternal warning signs must be supplied as a list of selected options.")
    if any(not isinstance(symptom, str) for symptom in maternal_warning_signs):
        raise ValueError("Maternal warning signs must contain text values.")
    invalid_symptoms = set(maternal_warning_signs) - MATERNAL_WARNING_SIGN_CODES
    if invalid_symptoms:
        raise ValueError("Select only the supported maternal warning sign options.")
    if "other_symptoms" in maternal_warning_signs and not (
        other_symptoms and other_symptoms.strip()
    ):
        raise ValueError("Describe the other symptoms you selected.")

    optional_values = {
        "platelet_count": _optional_measurement(
            platelet_count, "Platelet count", whole_number=True, positive=True
        ),
        "serum_creatinine": _optional_measurement(serum_creatinine, "Serum creatinine"),
        "alt_value": _optional_measurement(alt_value, "ALT"),
        "alt_upper_limit": _optional_measurement(
            alt_upper_limit, "ALT laboratory upper limit", positive=True
        ),
        "ast_value": _optional_measurement(ast_value, "AST"),
        "ast_upper_limit": _optional_measurement(
            ast_upper_limit, "AST laboratory upper limit", positive=True
        ),
        "urine_protein_creatinine_ratio": _optional_measurement(
            urine_protein_creatinine_ratio, "Urine protein-to-creatinine ratio"
        ),
        "urine_albumin_creatinine_ratio": _optional_measurement(
            urine_albumin_creatinine_ratio, "Urine albumin-to-creatinine ratio"
        ),
        "urine_output_ml": _optional_measurement(urine_output_ml, "Urine output"),
        "urine_output_period_hours": _optional_measurement(
            urine_output_period_hours, "Urine output measurement period", positive=True
        ),
    }
    if (optional_values["urine_output_ml"] is None) != (
        optional_values["urine_output_period_hours"] is None
    ):
        raise ValueError("Urine output and its measurement period must be provided together.")
    if other_symptoms is not None:
        other_symptoms = other_symptoms.strip() or None
    symptoms_json = json.dumps(sorted(set(maternal_warning_signs)))
    if isinstance(visit_date, datetime):
        raise ValueError("Visit date must be a date without a time.")
    if isinstance(visit_date, date):
        parsed_visit_date = visit_date
    elif isinstance(visit_date, str):
        try:
            parsed_visit_date = date.fromisoformat(visit_date.strip())
        except ValueError as error:
            raise ValueError("Visit date must be a valid date in YYYY-MM-DD format.") from error
    else:
        raise ValueError("Visit date must be a date or YYYY-MM-DD text.")
    if parsed_visit_date > date.today():
        raise ValueError("Visit date cannot be in the future.")
    visit_date = parsed_visit_date.isoformat()
    try:
        from monitoring_rules import evaluate_visit

        with _connection() as connection:
            previous_rows = connection.execute(
                """SELECT visit_id, systolic_bp, diastolic_bp
                FROM antenatal_visits WHERE patient_id = ?
                ORDER BY visit_date, visit_id""",
                (patient_id,),
            ).fetchall()
            cursor = connection.execute(
                """INSERT INTO antenatal_visits
                (patient_id, visit_date, gestational_age_weeks, systolic_bp,
                 diastolic_bp, urine_protein, notes, maternal_warning_signs,
                 other_symptoms, platelet_count, serum_creatinine, alt_value,
                 alt_upper_limit, ast_value, ast_upper_limit,
                 urine_protein_creatinine_ratio, urine_albumin_creatinine_ratio,
                 urine_output_ml, urine_output_period_hours)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    patient_id, visit_date, gestational_age_weeks, systolic_bp,
                    diastolic_bp, urine_protein, notes, symptoms_json,
                    other_symptoms,
                    optional_values["platelet_count"],
                    optional_values["serum_creatinine"],
                    optional_values["alt_value"],
                    optional_values["alt_upper_limit"],
                    optional_values["ast_value"],
                    optional_values["ast_upper_limit"],
                    optional_values["urine_protein_creatinine_ratio"],
                    optional_values["urine_albumin_creatinine_ratio"],
                    optional_values["urine_output_ml"],
                    optional_values["urine_output_period_hours"],
                ),
            )
            visit_id = cursor.lastrowid
            visit_data = {
                "visit_id": visit_id,
                "patient_id": patient_id,
                "visit_date": visit_date,
                "gestational_age_weeks": gestational_age_weeks,
                "systolic_bp": systolic_bp,
                "diastolic_bp": diastolic_bp,
                "urine_protein": urine_protein,
                "maternal_warning_signs": symptoms_json,
                "other_symptoms": other_symptoms,
                **optional_values,
            }
            evaluation = evaluate_visit(
                visit_data, previous_visits=[dict(row) for row in previous_rows]
            )
            _save_monitoring_evaluation(connection, visit_id, evaluation)
            return visit_id
    except sqlite3.IntegrityError as error:
        raise ValueError(
            "The visit could not be saved because the selected patient or one of "
            "the recorded fields is no longer valid. Please check and try again."
        ) from error
    except OverflowError as error:
        raise ValueError(
            "A numeric value is too large to store. Please check the measurements."
        ) from error
    except sqlite3.Error as error:
        raise RuntimeError(f"Could not add antenatal visit: {error}") from error


def get_patient_visits(patient_id):
    """Return a patient's visits, with the most recent visit date first."""
    try:
        with _connection() as connection:
            rows = connection.execute(
                """SELECT * FROM antenatal_visits WHERE patient_id = ?
                ORDER BY visit_date DESC, visit_id DESC""",
                (patient_id,),
            ).fetchall()
            visits = [dict(row) for row in rows]
            for visit in visits:
                alert_rows = connection.execute(
                    """SELECT rule_id, rule_name, severity, measurement, explanation,
                              suggested_action, guideline_source, rule_version,
                              generated_at
                    FROM visit_alerts WHERE visit_id = ?
                    ORDER BY alert_id""",
                    (visit["visit_id"],),
                ).fetchall()
                visit["alerts"] = [dict(alert) for alert in alert_rows]
                try:
                    visit["assessment"] = (
                        json.loads(visit["assessment_snapshot"])
                        if visit.get("assessment_snapshot")
                        else None
                    )
                except (json.JSONDecodeError, TypeError):
                    visit["assessment"] = None
            return visits
    except sqlite3.Error as error:
        raise RuntimeError(f"Could not retrieve antenatal visits: {error}") from error


def reevaluate_visit_monitoring(visit_id):
    """Re-evaluate one saved visit, replacing its saved alerts without duplication."""
    try:
        from monitoring_rules import evaluate_visit

        with _connection() as connection:
            row = connection.execute(
                "SELECT * FROM antenatal_visits WHERE visit_id = ?", (visit_id,)
            ).fetchone()
            if row is None:
                return None
            visit = dict(row)
            previous_rows = connection.execute(
                """SELECT visit_id, systolic_bp, diastolic_bp
                FROM antenatal_visits
                WHERE patient_id = ? AND visit_id <> ?
                ORDER BY visit_date, visit_id""",
                (visit["patient_id"], visit_id),
            ).fetchall()
            evaluation = evaluate_visit(
                visit, previous_visits=[dict(previous) for previous in previous_rows]
            )
            assessment = _save_monitoring_evaluation(connection, visit_id, evaluation)
            evaluation["assessment"] = assessment
            return evaluation
    except sqlite3.Error as error:
        raise RuntimeError(f"Could not evaluate visit monitoring: {error}") from error


def get_visit_monitoring(visit_id):
    """Return a saved visit evaluation, or None if the visit is not evaluated."""
    try:
        with _connection() as connection:
            row = connection.execute(
                """SELECT overall_severity, monitoring_summary,
                          monitoring_evaluated_at, monitoring_rule_version,
                          assessment_snapshot, assessment_version,
                          assessment_saved_at
                FROM antenatal_visits WHERE visit_id = ?""",
                (visit_id,),
            ).fetchone()
            if row is None or row["monitoring_evaluated_at"] is None:
                return None
            alerts = connection.execute(
                """SELECT rule_id, rule_name, severity, measurement, explanation,
                          suggested_action, guideline_source, rule_version, generated_at
                FROM visit_alerts WHERE visit_id = ? ORDER BY alert_id""",
                (visit_id,),
            ).fetchall()
            evaluation = dict(row)
            evaluation["alerts"] = [dict(alert) for alert in alerts]
            try:
                evaluation["assessment"] = (
                    json.loads(evaluation["assessment_snapshot"])
                    if evaluation["assessment_snapshot"]
                    else None
                )
            except (json.JSONDecodeError, TypeError):
                evaluation["assessment"] = None
            return evaluation
    except sqlite3.Error as error:
        raise RuntimeError(f"Could not retrieve visit monitoring: {error}") from error


def get_dashboard_data():
    """Return live dashboard summaries, recent activity, and chart records."""
    today = date.today()
    month_start = today.replace(day=1)
    if month_start.month == 12:
        next_month_start = date(month_start.year + 1, 1, 1)
    else:
        next_month_start = date(month_start.year, month_start.month + 1, 1)

    try:
        with _connection() as connection:
            summary = connection.execute(
                """SELECT
                    (SELECT COUNT(*) FROM patients) AS total_patients,
                    (SELECT COUNT(*) FROM antenatal_visits) AS total_visits,
                    (SELECT COUNT(*) FROM antenatal_visits
                     WHERE visit_date >= ? AND visit_date < ?) AS visits_this_month,
                    (SELECT COUNT(DISTINCT patient_id) FROM antenatal_visits)
                        AS patients_with_visits,
                    (SELECT MIN(gestational_age_weeks) FROM antenatal_visits)
                        AS minimum_gestational_age,
                    (SELECT MAX(gestational_age_weeks) FROM antenatal_visits)
                        AS maximum_gestational_age
                """,
                (month_start.isoformat(), next_month_start.isoformat()),
            ).fetchone()

            recent_visits = connection.execute(
                """SELECT
                    visits.visit_id,
                    patients.patient_id,
                    patients.full_name,
                    visits.visit_date,
                    visits.gestational_age_weeks,
                    visits.systolic_bp,
                    visits.diastolic_bp,
                    visits.urine_protein
                FROM antenatal_visits AS visits
                JOIN patients ON patients.patient_id = visits.patient_id
                ORDER BY visits.visit_date DESC, visits.visit_id DESC
                LIMIT 10
                """
            ).fetchall()

            recent_patients = connection.execute(
                """SELECT patient_id, full_name, age, registration_date
                FROM patients
                ORDER BY registration_date DESC, patient_id DESC
                LIMIT 10
                """
            ).fetchall()

            urine_protein_counts = connection.execute(
                """SELECT urine_protein, COUNT(*) AS visit_count
                FROM antenatal_visits
                GROUP BY urine_protein
                """
            ).fetchall()
            urine_protein_summary = {
                result: 0 for result in URINE_PROTEIN_VALUES
            }
            for row in urine_protein_counts:
                urine_protein_summary[row["urine_protein"]] = row["visit_count"]

            monthly_visits = connection.execute(
                """SELECT substr(visit_date, 1, 7) AS visit_month,
                          COUNT(*) AS visit_count
                FROM antenatal_visits
                GROUP BY substr(visit_date, 1, 7)
                ORDER BY visit_month
                """
            ).fetchall()

            gestational_age_distribution = connection.execute(
                """SELECT gestational_age_weeks, COUNT(*) AS visit_count
                FROM antenatal_visits
                GROUP BY gestational_age_weeks
                ORDER BY gestational_age_weeks
                """
            ).fetchall()

            blood_pressure_trends = connection.execute(
                """SELECT patient_id, visit_id, visit_date,
                          systolic_bp, diastolic_bp
                FROM antenatal_visits
                ORDER BY visit_date, visit_id
                """
            ).fetchall()

            patient_overview = connection.execute(
                """SELECT
                    patients.patient_id,
                    patients.full_name,
                    patients.age,
                    patients.registration_date,
                    COUNT(visits.visit_id) AS visit_count
                FROM patients
                LEFT JOIN antenatal_visits AS visits
                    ON visits.patient_id = patients.patient_id
                GROUP BY patients.patient_id
                ORDER BY patients.registration_date DESC, patients.patient_id DESC
                """
            ).fetchall()

            monitoring_counts = connection.execute(
                """SELECT
                    (SELECT COUNT(*) FROM antenatal_visits
                     WHERE monitoring_evaluated_at IS NOT NULL) AS evaluated_visits,
                    (SELECT COUNT(DISTINCT visit_id) FROM visit_alerts
                     WHERE severity = 'CAUTION') AS caution_visits,
                    (SELECT COUNT(DISTINCT visit_id) FROM visit_alerts
                     WHERE severity = 'WARNING') AS warning_visits,
                    (SELECT COUNT(DISTINCT visit_id) FROM visit_alerts
                     WHERE severity = 'URGENT') AS urgent_visits,
                    (SELECT COUNT(DISTINCT visit_id) FROM visit_alerts
                     WHERE severity = 'EMERGENCY') AS emergency_visits
                """
            ).fetchone()

            assessment_counts = connection.execute(
                """SELECT
                    COUNT(DISTINCT CASE WHEN overall_severity = 'INFORMATION'
                        THEN visit_id END) AS no_alert_visits,
                    COUNT(DISTINCT CASE WHEN overall_severity = 'CAUTION'
                        THEN visit_id END) AS monitoring_required_visits,
                    COUNT(DISTINCT CASE WHEN overall_severity = 'WARNING'
                        THEN visit_id END) AS concerning_visits,
                    COUNT(DISTINCT CASE WHEN overall_severity = 'URGENT'
                        THEN visit_id END) AS urgent_visits,
                    COUNT(DISTINCT CASE WHEN overall_severity = 'EMERGENCY'
                        THEN visit_id END) AS emergency_visits
                FROM antenatal_visits
                WHERE assessment_snapshot IS NOT NULL"""
            ).fetchone()

            recent_assessments = connection.execute(
                """SELECT visits.visit_id, visits.patient_id, patients.full_name,
                          visits.visit_date, visits.overall_severity,
                          visits.assessment_snapshot
                FROM antenatal_visits AS visits
                JOIN patients ON patients.patient_id = visits.patient_id
                WHERE visits.assessment_snapshot IS NOT NULL
                ORDER BY visits.visit_date DESC, visits.visit_id DESC
                LIMIT 10"""
            ).fetchall()
            decoded_recent_assessments = []
            for row in recent_assessments:
                record = dict(row)
                try:
                    record["assessment"] = json.loads(record.pop("assessment_snapshot"))
                except (json.JSONDecodeError, TypeError):
                    record["assessment"] = None
                    record.pop("assessment_snapshot", None)
                decoded_recent_assessments.append(record)

            return {
                "summary": dict(summary),
                "recent_patients": [dict(row) for row in recent_patients],
                "recent_visits": [dict(row) for row in recent_visits],
                "urine_protein_summary": urine_protein_summary,
                "monthly_visits": [dict(row) for row in monthly_visits],
                "gestational_age_distribution": [
                    dict(row) for row in gestational_age_distribution
                ],
                "blood_pressure_trends": [
                    dict(row) for row in blood_pressure_trends
                ],
                "patient_overview": [dict(row) for row in patient_overview],
                "monitoring_overview": dict(monitoring_counts),
                "assessment_overview": dict(assessment_counts),
                "recent_assessments": decoded_recent_assessments,
            }
    except sqlite3.Error as error:
        raise RuntimeError(f"Could not load dashboard data: {error}") from error
