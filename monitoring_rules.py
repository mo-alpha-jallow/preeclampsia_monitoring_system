"""Explainable educational monitoring rules for antenatal visit records.

These rules generate review flags only. They do not diagnose a condition,
predict outcomes, or replace assessment by a qualified health professional.
"""

from math import isfinite


RULE_VERSION = "1.0"

SEVERITY_ORDER = {
    "INFORMATION": 0,
    "CAUTION": 1,
    "WARNING": 2,
    "URGENT": 3,
    "EMERGENCY": 4,
}

MOH_BP_SOURCE = "Malaysian MOH Perinatal Care Manual, 4th ed. (2020), §5.2.1"
NICE_SOURCE = "NICE NG133, recommendations 1.2.1–1.2.7 and 1.5.2"
SYMPTOM_SOURCE = "NICE NG133, recommendation 1.5.2 and severe pre-eclampsia terms"
EDUCATIONAL_SOURCE = "Educational completeness or combined-review rule; not a diagnostic criterion"


def _value(data, key, default=None):
    if data is None:
        return default
    if hasattr(data, "get"):
        return data.get(key, default)
    try:
        return data[key]
    except (KeyError, IndexError, TypeError):
        return default


def _number(value, *, whole_number=False, positive=False):
    """Convert a usable numeric input, rejecting booleans and non-finite values."""
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, str):
        value = value.strip()
        if not value:
            return None
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    if not isfinite(number) or (positive and number <= 0):
        return None
    if whole_number and not number.is_integer():
        return None
    return int(number) if whole_number else number


def _missing(value):
    return value is None or (isinstance(value, str) and not value.strip())


def _normalize_protein(value):
    if _missing(value):
        return None
    normalized = str(value).strip().casefold().replace(" ", "")
    aliases = {
        "negative": "Negative",
        "trace": "Trace",
        "+1": "+1",
        "1+": "+1",
        "+2": "+2",
        "2+": "+2",
        "+3": "+3",
        "3+": "+3",
        "+4": "+4",
        "4+": "+4",
        "nottested": "Not tested",
    }
    return aliases.get(normalized)


def _symptom_set(value):
    if isinstance(value, str):
        import json

        try:
            value = json.loads(value)
        except (json.JSONDecodeError, TypeError):
            value = [value]
    if isinstance(value, dict):
        return {str(key) for key, selected in value.items() if selected}
    if isinstance(value, (list, tuple, set)):
        return {str(item) for item in value if item}
    return set()


def _alert(rule_id, name, severity, measurement, explanation, action, source):
    return {
        "rule_id": rule_id,
        "rule_name": name,
        "severity": severity,
        "measurement": str(measurement),
        "explanation": explanation,
        "suggested_action": action,
        "guideline_source": source,
        "rule_version": RULE_VERSION,
    }


def evaluate_visit(visit_data, previous_visits=None):
    """Evaluate all supported rules and return alerts plus an overall summary."""
    previous_visits = previous_visits or []
    alerts = []
    emitted_rules = set()

    def add(rule_id, *details):
        if rule_id not in emitted_rules:
            alerts.append(_alert(rule_id, *details))
            emitted_rules.add(rule_id)

    raw_systolic = _value(visit_data, "systolic_bp")
    raw_diastolic = _value(visit_data, "diastolic_bp")
    systolic = _number(raw_systolic, whole_number=True, positive=True)
    diastolic = _number(raw_diastolic, whole_number=True, positive=True)
    invalid_bp = []
    if systolic is None:
        status = "missing" if _missing(raw_systolic) else "invalid"
        invalid_bp.append(f"systolic BP is {status}")
    if diastolic is None:
        status = "missing" if _missing(raw_diastolic) else "invalid"
        invalid_bp.append(f"diastolic BP is {status}")
    if invalid_bp:
        add(
            "BP010",
            "Missing or invalid blood pressure",
            "CAUTION",
            "; ".join(invalid_bp),
            "Blood pressure information is incomplete or invalid. Missing values are not treated as normal.",
            "Record valid systolic and diastolic measurements and have the record reviewed.",
            EDUCATIONAL_SOURCE,
        )

    bp_alert_severities = []
    if systolic is not None:
        if systolic >= 160:
            severity = "URGENT"
            add(
                "BP006", "Severe systolic elevation", severity,
                f"Systolic BP {systolic} mmHg",
                "The systolic value is at least 160 mmHg, within the requested severe-range monitoring band.",
                "Seek urgent professional clinical assessment. Do not wait for another measurement.",
                f"{MOH_BP_SOURCE}; {NICE_SOURCE}",
            )
            bp_alert_severities.append(severity)
        elif 150 <= systolic <= 159:
            severity = "WARNING"
            add(
                "BP004", "Moderate systolic elevation", severity,
                f"Systolic BP {systolic} mmHg",
                "The systolic value is in the 150–159 mmHg educational moderate band.",
                "Arrange professional review in the appropriate clinical context.",
                MOH_BP_SOURCE,
            )
            bp_alert_severities.append(severity)
        elif 140 <= systolic <= 149:
            severity = "CAUTION"
            add(
                "BP002", "Mild systolic elevation", severity,
                f"Systolic BP {systolic} mmHg",
                "The systolic value is in the 140–149 mmHg educational mild band.",
                "Review the measurement with a qualified health professional.",
                MOH_BP_SOURCE,
            )
            bp_alert_severities.append(severity)

    if diastolic is not None:
        if diastolic >= 110:
            severity = "URGENT"
            add(
                "BP007", "Severe diastolic elevation", severity,
                f"Diastolic BP {diastolic} mmHg",
                "The diastolic value is at least 110 mmHg, within the requested severe-range monitoring band.",
                "Seek urgent professional clinical assessment. Do not wait for another measurement.",
                f"{MOH_BP_SOURCE}; {NICE_SOURCE}",
            )
            bp_alert_severities.append(severity)
        elif 100 <= diastolic <= 109:
            severity = "WARNING"
            add(
                "BP005", "Moderate diastolic elevation", severity,
                f"Diastolic BP {diastolic} mmHg",
                "The diastolic value is in the 100–109 mmHg educational moderate band.",
                "Arrange professional review in the appropriate clinical context.",
                MOH_BP_SOURCE,
            )
            bp_alert_severities.append(severity)
        elif 90 <= diastolic <= 99:
            severity = "CAUTION"
            add(
                "BP003", "Mild diastolic elevation", severity,
                f"Diastolic BP {diastolic} mmHg",
                "The diastolic value is in the 90–99 mmHg educational mild band.",
                "Review the measurement with a qualified health professional.",
                MOH_BP_SOURCE,
            )
            bp_alert_severities.append(severity)

    raised_systolic = systolic is not None and systolic >= 140
    raised_diastolic = diastolic is not None and diastolic >= 90
    raised_bp = raised_systolic or raised_diastolic
    if systolic is not None and diastolic is not None:
        if not raised_systolic and not raised_diastolic:
            add(
                "BP001", "Below configured hypertension threshold", "INFORMATION",
                f"{systolic}/{diastolic} mmHg",
                "Neither recorded value reaches the configured 140/90 mmHg review threshold. This does not establish that a patient is healthy or free from pre-eclampsia.",
                "Continue assessment based on the full clinical context and applicable care guidance.",
                f"{MOH_BP_SOURCE}; {NICE_SOURCE}",
            )
        if raised_systolic and raised_diastolic:
            combined_severity = max(
                bp_alert_severities or ["CAUTION"],
                key=lambda value: SEVERITY_ORDER[value],
            )
            add(
                "BP008", "Both blood pressure measurements elevated", combined_severity,
                f"{systolic}/{diastolic} mmHg",
                "Both systolic (at least 140 mmHg) and diastolic (at least 90 mmHg) values meet the configured review threshold.",
                "Arrange professional assessment. This combined finding is not a diagnosis.",
                f"{MOH_BP_SOURCE}; {NICE_SOURCE}",
            )

    # The database does not capture time or measurement conditions, so this is
    # a repeated-reading flag, not confirmation under a diagnostic protocol.
    elevated_visit_keys = set()
    for index, prior in enumerate(previous_visits):
        prior_sys = _number(_value(prior, "systolic_bp"), whole_number=True, positive=True)
        prior_dia = _number(_value(prior, "diastolic_bp"), whole_number=True, positive=True)
        if ((prior_sys is not None and prior_sys >= 140)
                or (prior_dia is not None and prior_dia >= 90)):
            visit_key = _value(prior, "visit_id", f"previous-{index}")
            if visit_key is None:
                visit_key = f"previous-{index}"
            elevated_visit_keys.add(visit_key)
    if raised_bp:
        current_visit_key = _value(visit_data, "visit_id", "current-visit")
        if current_visit_key is None:
            current_visit_key = "current-visit"
        elevated_visit_keys.add(current_visit_key)
    if len(elevated_visit_keys) >= 2:
        add(
            "BP009", "Repeated elevated readings across visits", "WARNING",
            f"Elevated readings on {len(elevated_visit_keys)} separate visit records",
            "At least two separate visit records contain an elevated systolic or diastolic value. Their timing and measurement conditions are not recorded, so this does not establish diagnostic confirmation.",
            "Arrange professional review. Confirmatory assessment must follow the applicable clinical protocol.",
            f"{MOH_BP_SOURCE}; educational repeated-visit flag",
        )

    raw_protein = _value(visit_data, "urine_protein")
    protein = _normalize_protein(raw_protein)
    if protein is None or protein == "Not tested":
        reason = "missing" if _missing(raw_protein) else "not tested or invalid"
        add(
            "UR007", "Missing urine protein result", "CAUTION",
            f"Urine protein: {reason}",
            "A usable urine protein result is not recorded. Missing or untested results are not treated as negative.",
            "Record a valid result when available and interpret it with the full clinical assessment.",
            EDUCATIONAL_SOURCE,
        )
    elif protein == "Negative":
        add(
            "UR001", "Negative recorded dipstick screen", "INFORMATION",
            "Urine protein: Negative",
            "The recorded dipstick screening result is negative. This result alone does not exclude pre-eclampsia or other concerns.",
            "Interpret with symptoms, blood pressure, other investigations, and professional assessment.",
            NICE_SOURCE,
        )
    elif protein == "Trace":
        add(
            "UR002", "Trace urine protein", "CAUTION",
            "Urine protein: Trace",
            "Trace protein is a screening observation and is not a standalone diagnosis.",
            "Monitor and interpret alongside blood pressure, symptoms, and the clinical context.",
            NICE_SOURCE,
        )
    else:
        protein_rules = {
            "+1": ("UR003", "1+ urine protein screening result", "WARNING", "A dipstick result of 1+ or more is a positive screening result; it is not a standalone diagnosis.", "Arrange professional assessment and appropriate quantitative urine protein testing."),
            "+2": ("UR004", "2+ urine protein screening result", "WARNING", "A 2+ dipstick result is a stronger positive screening finding, but does not diagnose pre-eclampsia by itself.", "Arrange professional assessment and appropriate quantitative urine protein testing."),
            "+3": ("UR005", "3+ urine protein screening result", "URGENT", "A 3+ dipstick result is a positive screening finding requiring prompt clinical review.", "Seek prompt assessment by a qualified health professional."),
            "+4": ("UR006", "4+ urine protein screening result", "URGENT", "A 4+ dipstick result is a strong positive screening finding and is not a standalone diagnosis.", "Seek professional clinical assessment."),
        }
        rule_id, name, severity, explanation, action = protein_rules[protein]
        add(rule_id, name, severity, f"Urine protein: {protein}", explanation, action, NICE_SOURCE)

    raw_weeks = _value(visit_data, "gestational_age_weeks")
    weeks = _number(raw_weeks, whole_number=True, positive=True)
    if weeks is None or weeks > 45:
        status = "missing" if _missing(raw_weeks) else "invalid"
        add(
            "GA005", "Missing or invalid gestational age", "INFORMATION",
            f"Gestational age: {status}",
            "Gestational age is unavailable or outside the supported recording range; gestational context cannot be assessed.",
            "Confirm and record gestational age before interpreting gestation-related findings.",
            EDUCATIONAL_SOURCE,
        )
    elif raised_bp:
        if weeks < 20:
            add(
                "GA001", "Raised blood pressure before 20 weeks", "WARNING",
                f"Raised BP at {weeks} weeks",
                "Raised blood pressure recorded before 20 weeks may require assessment for pre-existing hypertension; this rule does not diagnose it.",
                "Arrange professional assessment of the blood pressure and pregnancy history.",
                f"{MOH_BP_SOURCE}; NICE NG133 terms",
            )
        else:
            add(
                "GA002", "Raised blood pressure at or after 20 weeks", "WARNING",
                f"Raised BP at {weeks} weeks",
                "Raised blood pressure at or after 20 weeks requires assessment in the pregnancy context. A single record does not establish gestational hypertension.",
                "Arrange professional clinical assessment; applicable confirmation protocols require additional measurements.",
                f"{MOH_BP_SOURCE}; NICE NG133 terms",
            )
            if protein in ("+1", "+2", "+3", "+4"):
                add(
                    "GA003", "Raised BP with positive urine protein at or after 20 weeks", "URGENT",
                    f"Raised BP and {protein} urine protein at {weeks} weeks",
                    "Raised blood pressure and a positive dipstick result together after 20 weeks warrant prompt assessment for possible pre-eclampsia. These findings do not establish a diagnosis.",
                    "Arrange prompt professional assessment and quantitative urine protein testing as clinically appropriate.",
                    f"MOH Perinatal Care Manual §5.2.1; {NICE_SOURCE}",
                )
    if (protein in ("+1", "+2", "+3", "+4")
            and systolic is not None and diastolic is not None
            and not raised_systolic and not raised_diastolic):
        add(
            "GA004", "Positive urine protein with below-threshold BP", "WARNING",
            f"{protein} urine protein with BP {systolic}/{diastolic} mmHg",
            "A positive dipstick result with currently below-threshold recorded blood pressure still requires context and professional review.",
            "Arrange professional clinical review and quantitative urine protein testing as appropriate.",
            NICE_SOURCE,
        )

    symptoms = _symptom_set(_value(visit_data, "maternal_warning_signs"))
    symptom_rules = {
        "headache": ("SYM001", "Severe or persistent headache recorded", "WARNING", "A severe or persistent headache is a symptom that requires clinical review in context.", "Arrange prompt professional clinical assessment."),
        "visual_disturbance": ("SYM002", "Visual disturbance recorded", "URGENT", "Visual disturbance is a warning symptom requiring urgent professional assessment.", "Seek urgent professional clinical assessment."),
        "epigastric_pain": ("SYM003", "Upper abdominal or epigastric pain recorded", "URGENT", "Upper abdominal or epigastric pain is a warning symptom requiring urgent professional assessment.", "Seek urgent professional clinical assessment."),
        "difficulty_breathing": ("SYM004", "Difficulty breathing recorded", "URGENT", "Difficulty breathing may require urgent professional assessment.", "Seek urgent professional clinical assessment."),
        "reduced_urine_output": ("SYM005", "Reduced urine output recorded", "WARNING", "Reduced urine output requires professional assessment in the clinical context.", "Arrange prompt professional clinical assessment."),
        "nausea_vomiting": ("SYM006", "Nausea or vomiting recorded", "CAUTION", "Nausea or vomiting is recorded for clinical review in context and is not proof of pre-eclampsia.", "Discuss the symptom with a qualified health professional."),
        "seizure": ("SYM007", "Seizure or convulsion recorded", "EMERGENCY", "A seizure or convulsion is an emergency warning sign regardless of other recorded measurements.", "Seek immediate emergency medical assistance. Do not wait for another measurement."),
    }
    for symptom_code, rule in symptom_rules.items():
        if symptom_code in symptoms:
            add(rule[0], rule[1], rule[2], symptom_code, rule[3], rule[4], SYMPTOM_SOURCE)

    other_symptoms = _value(visit_data, "other_symptoms")
    if ("other_symptoms" in symptoms or not _missing(other_symptoms)):
        add(
            "SYM008", "Other symptom recorded", "CAUTION",
            str(other_symptoms).strip() or "Other symptoms checkbox selected",
            "An additional symptom was recorded and has not been classified by a predefined rule.",
            "Arrange review by a qualified health professional.",
            EDUCATIONAL_SOURCE,
        )

    symptom_combination_rules = [
        ("headache", "COM001", "Raised BP with headache recorded"),
        ("visual_disturbance", "COM002", "Raised BP with visual disturbance recorded"),
        ("epigastric_pain", "COM003", "Raised BP with upper abdominal pain recorded"),
        ("difficulty_breathing", "COM004", "Raised BP with difficulty breathing recorded"),
    ]
    if raised_bp:
        for symptom_code, rule_id, rule_name in symptom_combination_rules:
            if symptom_code in symptoms:
                symptom_severity = symptom_rules[symptom_code][2]
                combined_severities = bp_alert_severities + [symptom_severity]
                severity = max(
                    combined_severities,
                    key=lambda value: SEVERITY_ORDER[value],
                )
                add(
                    rule_id, rule_name, severity,
                    f"Raised BP with {symptom_code}",
                    "Raised blood pressure and this warning symptom were recorded together; the combination warrants professional assessment and is not a diagnosis.",
                    "Seek urgent professional clinical assessment.",
                    f"{NICE_SOURCE}; educational combined-review rule",
                )
    warning_symptoms = {
        "headache", "visual_disturbance", "epigastric_pain",
        "difficulty_breathing", "reduced_urine_output", "nausea_vomiting", "seizure",
    }
    if protein in ("+1", "+2", "+3", "+4") and symptoms.intersection(warning_symptoms):
        combined_severity = "URGENT" if "seizure" in symptoms or symptoms.intersection(
            {"visual_disturbance", "epigastric_pain", "difficulty_breathing"}
        ) else "WARNING"
        add(
            "COM005", "Positive urine protein with warning symptoms", combined_severity,
            f"{protein} urine protein with recorded warning symptom(s)",
            "A positive screening result and warning symptom(s) were recorded together and need professional review; they do not establish a diagnosis.",
            "Arrange prompt professional assessment; use emergency services for seizure or immediate danger.",
            f"{NICE_SOURCE}; educational combined-review rule",
        )

    # Optional laboratory measurements: absent results are skipped. Invalid
    # supplied values are identified without interpreting them as normal.
    lab_specs = [
        ("platelet_count", "Platelet count", True, True),
        ("serum_creatinine", "Serum creatinine", False, True),
        ("alt_value", "ALT", False, True),
        ("ast_value", "AST", False, True),
        ("alt_upper_limit", "ALT laboratory upper limit", False, True),
        ("ast_upper_limit", "AST laboratory upper limit", False, True),
        ("urine_protein_creatinine_ratio", "Urine protein-to-creatinine ratio", False, False),
        ("urine_albumin_creatinine_ratio", "Urine albumin-to-creatinine ratio", False, False),
        ("urine_output_ml", "Urine output", False, False),
        ("urine_output_period_hours", "Urine output measurement period", False, True),
    ]
    valid_labs = {}
    invalid_labs = []
    for key, label, whole_number, positive in lab_specs:
        raw = _value(visit_data, key)
        if _missing(raw):
            valid_labs[key] = None
            continue
        number = _number(raw, whole_number=whole_number, positive=positive)
        if number is None:
            invalid_labs.append(label)
        valid_labs[key] = number
    if invalid_labs:
        add(
            "LAB007", "Invalid optional laboratory or urine-output value", "INFORMATION",
            ", ".join(invalid_labs),
            "One or more supplied optional measurements are not valid numeric values for their field.",
            "Verify the measurement, units, and entry before clinical interpretation.",
            EDUCATIONAL_SOURCE,
        )

    platelet_count = valid_labs["platelet_count"]
    if platelet_count is not None and platelet_count < 150000:
        add(
            "LAB001", "Low recorded platelet count", "WARNING",
            f"Platelet count {platelet_count} per microlitre",
            "The recorded platelet count is below 150,000 per microlitre, a finding NICE lists for professional assessment in the context of pre-eclampsia.",
            "Arrange professional assessment and review with the laboratory and clinical context.",
            NICE_SOURCE,
        )
    creatinine = valid_labs["serum_creatinine"]
    if creatinine is not None and creatinine >= 90:
        add(
            "LAB002", "Elevated recorded serum creatinine", "WARNING",
            f"Serum creatinine {creatinine:g} micromol/L",
            "The recorded serum creatinine is at least 90 micromol/L, a finding NICE lists for clinical concern in the context of pre-eclampsia.",
            "Arrange professional assessment and review with the laboratory and clinical context.",
            NICE_SOURCE,
        )
    alt = valid_labs["alt_value"]
    alt_upper_limit = valid_labs["alt_upper_limit"]
    if alt is not None and (alt > 70 or (alt_upper_limit is not None and alt > 2 * alt_upper_limit)):
        add(
            "LAB003", "Elevated recorded ALT", "WARNING",
            f"ALT {alt:g} IU/L" + (f" (laboratory upper limit {alt_upper_limit:g} IU/L)" if alt_upper_limit else ""),
            "ALT is above 70 IU/L or above twice the supplied laboratory upper limit, a finding NICE lists for professional concern in context.",
            "Arrange professional assessment and interpret using the reporting laboratory's reference range.",
            NICE_SOURCE,
        )
    ast = valid_labs["ast_value"]
    ast_upper_limit = valid_labs["ast_upper_limit"]
    if ast is not None and ast_upper_limit is not None and ast > ast_upper_limit:
        add(
            "LAB004", "AST above supplied laboratory upper limit", "WARNING",
            f"AST {ast:g} IU/L (laboratory upper limit {ast_upper_limit:g} IU/L)",
            "AST is above the documented laboratory upper limit. No universal AST cutoff is applied by this rule.",
            "Arrange professional assessment and interpret using the reporting laboratory's reference range.",
            "NICE NG133 definition terms; laboratory-specific upper limit supplied with the result",
        )
    elif ast is not None and ast_upper_limit is None:
        add(
            "LAB008", "AST cannot be evaluated without laboratory upper limit", "INFORMATION",
            f"AST {ast:g} IU/L; laboratory upper limit not supplied",
            "An AST value was supplied, but the reporting laboratory's upper limit is missing, so no AST threshold comparison was made.",
            "Add the laboratory's documented upper limit before interpreting this value.",
            EDUCATIONAL_SOURCE,
        )
    pcr = valid_labs["urine_protein_creatinine_ratio"]
    if pcr is not None and pcr >= 30:
        add(
            "LAB005", "Raised urine protein-to-creatinine ratio", "WARNING",
            f"Protein-to-creatinine ratio {pcr:g} mg/mmol",
            "The quantitative urine protein-to-creatinine ratio is at least 30 mg/mmol, the NICE threshold for significant proteinuria.",
            "Arrange professional assessment and interpret with the overall clinical context.",
            NICE_SOURCE,
        )
    acr = valid_labs["urine_albumin_creatinine_ratio"]
    if acr is not None and acr >= 8:
        add(
            "LAB006", "Raised urine albumin-to-creatinine ratio", "WARNING",
            f"Albumin-to-creatinine ratio {acr:g} mg/mmol",
            "The quantitative urine albumin-to-creatinine ratio is at least 8 mg/mmol, the NICE threshold when using ACR as an alternative test in context.",
            "Arrange professional assessment and interpret with the overall clinical context.",
            NICE_SOURCE,
        )

    if alerts:
        overall_severity = max(
            (alert["severity"] for alert in alerts),
            key=lambda value: SEVERITY_ORDER[value],
        )
        if overall_severity == "EMERGENCY":
            summary = "An emergency warning sign was recorded. Seek immediate emergency assistance. This is an educational flag, not a diagnosis."
        elif overall_severity == "URGENT":
            summary = "One or more findings require urgent professional assessment. This is not a diagnosis."
        elif overall_severity == "WARNING":
            summary = "One or more findings require professional review. This is not a diagnosis."
        elif overall_severity == "CAUTION":
            summary = "Review the recorded findings and any incomplete information with a qualified health professional."
        else:
            summary = "Only informational findings were triggered. This does not establish that the patient is healthy or rule out a condition."
    else:
        overall_severity = "INFORMATION"
        summary = "No predefined alert rule was triggered by the supplied information. This does not clinically clear the patient or rule out a condition."

    return {
        "rule_version": RULE_VERSION,
        "overall_severity": overall_severity,
        "summary": summary,
        "alerts": alerts,
    }
