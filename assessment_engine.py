"""Deterministic overall assessments built only from existing rule findings."""

import re

from monitoring_rules import SEVERITY_ORDER

ASSESSMENT_VERSION = "1.0"

CATEGORY_BY_SEVERITY = {
    "INFORMATION": "NO PREDEFINED ALERT RULES TRIGGERED",
    "CAUTION": "MONITORING REQUIRED",
    "WARNING": "CONCERNING FINDINGS",
    "URGENT": "URGENT CLINICAL ASSESSMENT REQUIRED",
    "EMERGENCY": "EMERGENCY",
}

NO_ALERT_SUMMARY = (
    "No predefined monitoring alert rules were triggered by the information "
    "recorded for this visit."
)
NO_ALERT_EXPLANATION = (
    "This result does not rule out preeclampsia or any other pregnancy-related "
    "complication. Continue routine antenatal care and seek professional "
    "assessment if symptoms or concerns arise."
)
EMERGENCY_MESSAGE = (
    "Emergency warning sign recorded. Seek immediate emergency medical assistance."
)
SEIZURE_MESSAGE = (
    "Seizure/convulsion recorded — EMERGENCY. Seek immediate emergency medical "
    "assistance. This application cannot diagnose eclampsia."
)
PREECLAMPSIA_MESSAGE = "Findings warrant assessment for possible preeclampsia."
PREECLAMPSIA_DISCLAIMER = (
    "This is a screening flag, not a diagnosis. Diagnosis requires assessment "
    "by a qualified healthcare professional."
)

_ORGAN_DYSFUNCTION_RULES = {"LAB001", "LAB002", "LAB003", "LAB004"}
_PROTEIN_RULES = {"UR003", "UR004", "UR005", "UR006", "LAB005", "LAB006"}


def _recommendation_key(text):
    """Normalize whitespace and punctuation for safe recommendation deduplication."""
    return re.sub(r"[^a-z0-9]+", " ", str(text).casefold()).strip()


def build_overall_assessment(evaluation):
    """Combine an existing monitoring evaluation into a stable assessment.

    No clinical rules or thresholds are evaluated here. Category and flags are
    derived only from the severity and rule IDs already emitted by
    ``monitoring_rules.evaluate_visit``.
    """
    alerts = [dict(alert) for alert in evaluation.get("alerts", [])]
    known_severities = [
        alert.get("severity")
        for alert in alerts
        if alert.get("severity") in SEVERITY_ORDER
    ]
    engine_severity = evaluation.get("overall_severity")
    if engine_severity in SEVERITY_ORDER:
        known_severities.append(engine_severity)
    severity = max(known_severities, key=SEVERITY_ORDER.get) if known_severities else "INFORMATION"
    category = CATEGORY_BY_SEVERITY[severity]
    rule_ids = {alert.get("rule_id") for alert in alerts}

    emergency = severity == "EMERGENCY" or "SYM007" in rule_ids
    seizure_recorded = "SYM007" in rule_ids
    raised_bp_after_20_weeks = "GA002" in rule_ids
    possible_preeclampsia = (
        "GA003" in rule_ids
        or (
            raised_bp_after_20_weeks
            and bool(rule_ids.intersection(_PROTEIN_RULES | _ORGAN_DYSFUNCTION_RULES))
        )
    )

    if severity == "INFORMATION":
        summary = NO_ALERT_SUMMARY
        explanation = NO_ALERT_EXPLANATION
    elif emergency:
        summary = SEIZURE_MESSAGE if seizure_recorded else EMERGENCY_MESSAGE
        explanation = (
            "An existing monitoring rule marked an emergency finding. Emergency "
            "status takes priority over every other recorded result. This "
            "application cannot diagnose eclampsia."
        )
    elif severity == "URGENT":
        summary = (
            "One or more existing monitoring rules require urgent clinical assessment. "
            "This is a monitoring result, not a diagnosis."
        )
        explanation = (
            "The urgent category is determined by the highest severity emitted "
            "by the existing monitoring rules."
        )
    elif severity == "WARNING":
        summary = (
            "One or more existing monitoring findings warrant professional "
            "clinical assessment. This is not a diagnosis."
        )
        explanation = (
            "The concerning category is determined by the highest severity "
            "emitted by the existing monitoring rules."
        )
    else:
        summary = (
            "One or more findings need monitoring, follow-up, or review. "
            "This result does not rule out a complication."
        )
        explanation = (
            "The monitoring category is determined by the highest existing "
            "rule severity. Incomplete measurements are not treated as normal."
        )

    indexed_alerts = list(enumerate(alerts))
    indexed_alerts.sort(
        key=lambda item: (
            -SEVERITY_ORDER.get(item[1].get("severity"), 0),
            item[0],
        )
    )
    individual_recommendations = [
        {
            "rule_id": alert.get("rule_id"),
            "severity": alert.get("severity", "INFORMATION"),
            "reason": alert.get("rule_name", "Recorded monitoring finding"),
            "recommendation": alert.get("suggested_action", "Review with a qualified healthcare professional."),
        }
        for _, alert in indexed_alerts
        if alert.get("suggested_action")
    ]

    combined_by_key = {}
    for item in individual_recommendations:
        recommendation = item["recommendation"].strip()
        key = _recommendation_key(recommendation)
        if not key:
            continue
        if key not in combined_by_key:
            combined_by_key[key] = {
                "priority": item["severity"],
                "recommendation": recommendation,
                "rule_ids": [],
                "reasons": [],
            }
        combined = combined_by_key[key]
        if SEVERITY_ORDER[item["severity"]] > SEVERITY_ORDER[combined["priority"]]:
            combined["priority"] = item["severity"]
        if item["rule_id"] not in combined["rule_ids"]:
            combined["rule_ids"].append(item["rule_id"])
        if item["reason"] not in combined["reasons"]:
            combined["reasons"].append(item["reason"])

    combined_recommendations = sorted(
        combined_by_key.values(),
        key=lambda item: -SEVERITY_ORDER[item["priority"]],
    )
    if severity == "INFORMATION":
        baseline_recommendation = {
            "priority": "INFORMATION",
            "recommendation": NO_ALERT_EXPLANATION,
            "rule_ids": [],
            "reasons": ["No actionable alert severity was emitted"],
        }
        combined_recommendations.append(baseline_recommendation)

    if possible_preeclampsia:
        preeclampsia_explanation = (
            "The existing rules recorded raised blood pressure at or after 20 weeks "
            "together with a positive urine protein rule or a documented "
            "laboratory review finding."
        )
    else:
        preeclampsia_explanation = None

    return {
        "assessment_version": ASSESSMENT_VERSION,
        "overall_category": category,
        "overall_severity": severity,
        "summary": summary,
        "triggered_findings": alerts,
        "triggered_rule_count": len(alerts),
        "possible_preeclampsia_concern": possible_preeclampsia,
        "possible_preeclampsia_message": (
            PREECLAMPSIA_MESSAGE if possible_preeclampsia else None
        ),
        "possible_preeclampsia_disclaimer": (
            PREECLAMPSIA_DISCLAIMER if possible_preeclampsia else None
        ),
        "possible_preeclampsia_explanation": preeclampsia_explanation,
        "emergency": emergency,
        "emergency_message": (
            SEIZURE_MESSAGE if seizure_recorded else EMERGENCY_MESSAGE
        ) if emergency else None,
        "individual_recommendations": individual_recommendations,
        "combined_recommendations": combined_recommendations,
        "explanation": explanation,
    }
