# Educational Antenatal Monitoring Rules

## Purpose and limitations

This document describes an explainable educational rules engine. It is not a
clinically validated decision-support system. It does not diagnose
pre-eclampsia or eclampsia, predict outcomes, recommend medication, or replace
assessment by a qualified health professional. Blood pressure and urine
protein are only part of a broader clinical assessment. A single visit does
not establish a diagnosis. Absence of a triggered rule does not rule out a
condition.

BP bands below use the educational categories requested for this project.
The Malaysian Perinatal Care Manual defines hypertension as 140/90 mmHg on two
occasions 4–6 hours apart and lists mild, moderate and severe measurement
bands. This database stores visit dates but not time of day or measurement
conditions; BP009 therefore flags repeated elevated visit records and does not
claim protocol confirmation. Severe-range values create an urgent flag
without waiting for a repeat record.

## Reference sources

1. Malaysian Ministry of Health, *Perinatal Care Manual*, 4th Edition,
   Section 5.2.1, pp. 171–172 (released May 2023):
   <https://hq.moh.gov.my/bpkk/images/PERINATAL_CARE_MANUAL_4th_Edition_2020_11Mei2023.pdf>
2. NICE NG133, *Hypertension in pregnancy: diagnosis and management*:
   <https://www.nice.org.uk/guidance/ng133/chapter/Recommendations>

NICE recommends interpreting proteinuria with a full clinical review,
quantifying a positive dipstick (1+ or more), and uses PCR 30 mg/mmol or ACR
8 mg/mmol thresholds. NICE also lists creatinine at least 90 micromol/L,
ALT over 70 IU/L or twice the laboratory upper limit, and platelets below
150,000/microlitre as findings of concern in the context it describes.

## Severity levels

| Level | Display meaning |
| --- | --- |
| INFORMATION | Informational result or incomplete interpretation notice |
| CAUTION | Review the entry or discuss it in context |
| WARNING | Professional review is recommended |
| URGENT | Seek urgent professional clinical assessment |
| EMERGENCY | Seek immediate emergency medical assistance |

The overall level is the highest severity among the triggered findings.
Every triggered rule is still shown individually. A seizure record always
produces EMERGENCY severity.

## Blood pressure rules

All BP values are evaluated independently. A systolic finding is not
suppressed by a lower diastolic value, and vice versa. The alert bands are
screening/review categories, not diagnoses.

| Rule | Condition / measurement | Severity | Explanation and suggested action | Source |
| --- | --- | --- | --- | --- |
| BP001 | Systolic <140 **and** diastolic <90 mmHg | INFORMATION | Neither value reaches the configured threshold. This does not prove health or exclude pre-eclampsia; continue assessment in context. | MOH §5.2.1; NICE NG133 |
| BP002 | Systolic 140–149 mmHg | CAUTION | Mild systolic band; review with a qualified professional. | MOH §5.2.1 |
| BP003 | Diastolic 90–99 mmHg | CAUTION | Mild diastolic band; review with a qualified professional. | MOH §5.2.1 |
| BP004 | Systolic 150–159 mmHg | WARNING | Moderate systolic band; arrange professional review. | MOH §5.2.1 |
| BP005 | Diastolic 100–109 mmHg | WARNING | Moderate diastolic band; arrange professional review. | MOH §5.2.1 |
| BP006 | Systolic ≥160 mmHg | URGENT | Severe systolic band; seek urgent professional assessment without waiting for a repeat record. | MOH §5.2.1; NICE NG133 |
| BP007 | Diastolic ≥110 mmHg | URGENT | Severe diastolic band; seek urgent professional assessment without waiting for a repeat record. | MOH §5.2.1; NICE NG133 |
| BP008 | Systolic ≥140 **and** diastolic ≥90 mmHg | Highest applicable BP severity | Combined finding shown in addition to independent systolic and diastolic findings. | MOH §5.2.1; NICE NG133 |
| BP009 | At least 2 distinct visit records have systolic ≥140 **or** diastolic ≥90 | WARNING | Repeated elevated records; their timing and measurement conditions are unknown, so this is not diagnostic confirmation. Arrange professional review. | MOH §5.2.1 describes 4–6-hour confirmation; app has no time field |
| BP010 | Either BP value missing, nonnumeric, nonfinite, nonpositive or not a whole number | CAUTION | Incomplete/invalid BP is never considered normal. Record valid measurements and review. | Educational completeness rule |

## Urine protein rules

Dipstick results are screening results. Grades are not converted to quantitative
protein values. If dipstick screening is 1+ or more, NICE recommends
quantitative assessment using PCR or ACR as appropriate.

| Rule | Condition | Severity | Explanation and suggested action | Source |
| --- | --- | --- | --- | --- |
| UR001 | Recorded result is Negative | INFORMATION | Negative dipstick screen only; it does not exclude a condition. Interpret in context. | NICE NG133 §1.2 |
| UR002 | Trace | CAUTION | Monitor and interpret with the clinical context; do not diagnose. | Educational review flag |
| UR003 | 1+ | WARNING | Positive screening result; arrange professional review and appropriate quantitative testing. | NICE NG133 §1.2.3 |
| UR004 | 2+ | WARNING | Stronger positive screening result; professional assessment and quantitative testing are appropriate. | NICE NG133 §1.2.3 |
| UR005 | 3+ | URGENT | Positive screening finding requiring prompt clinical review. | Educational severity selection; NICE NG133 §1.2.3 |
| UR006 | 4+ | URGENT | Strong positive screening finding; professional assessment required. | Educational severity selection; NICE NG133 §1.2.3 |
| UR007 | Missing, invalid or Not tested | CAUTION | Missing/untested is not treated as negative. Record a result when available and interpret in context. | Educational completeness rule |

## Gestational-age and combined findings

| Rule | Condition | Severity | Explanation and suggested action | Source |
| --- | --- | --- | --- | --- |
| GA001 | Raised BP before 20 weeks | WARNING | Possible pre-existing hypertension needs professional assessment; this is not a diagnosis. | NICE NG133 terms; educational review rule |
| GA002 | Raised BP at or after 20 weeks | WARNING | Assessment in pregnancy context is recommended. One record does not confirm gestational hypertension. | MOH §5.2.1; NICE NG133 terms |
| GA003 | Raised BP and 1+ or higher urine protein at ≥20 weeks | URGENT | Combined findings warrant prompt assessment for possible pre-eclampsia; they do not establish it. | MOH §5.2.1; NICE NG133 §1.2 |
| GA004 | 1+ or higher urine protein with both recorded BP values below 140/90 | WARNING | Positive dipstick still warrants professional review and appropriate quantitative testing. | NICE NG133 §1.2 |
| GA005 | Missing, invalid or out-of-range gestational age | INFORMATION | Gestational context cannot be evaluated; verify the record. | Educational completeness rule |
| COM001 | Raised BP plus headache | Highest of BP severity and WARNING | Combined review prompt; arrange urgent/professional assessment in context. | NICE NG133 symptom terms; educational combination |
| COM002 | Raised BP plus visual disturbance | URGENT | Combined warning finding; seek urgent assessment. | NICE NG133 §1.5.2; educational combination |
| COM003 | Raised BP plus upper abdominal/epigastric pain | URGENT | Combined warning finding; seek urgent assessment. | NICE NG133 §1.5.2; educational combination |
| COM004 | Raised BP plus difficulty breathing | URGENT | Combined warning finding; seek urgent assessment. | NICE NG133 §1.5.2 concern for pulmonary oedema; educational combination |
| COM005 | Positive dipstick plus warning symptom(s) | WARNING or URGENT | Combined findings need prompt professional assessment. Severity is raised for seizure, visual disturbance, epigastric pain or breathing difficulty. | NICE NG133; educational combination |

Gestational age is evaluated at the visit as recorded. Exactly 20 weeks is in
the 20-weeks-or-later group. Missing symptom information is not evidence that
symptoms are absent.

## Maternal warning-sign rules

| Rule | Recorded symptom | Severity | Suggested action | Source/context |
| --- | --- | --- | --- | --- |
| SYM001 | Severe or persistent headache | WARNING | Arrange prompt professional assessment. | NICE NG133 impending-eclampsia/severe pre-eclampsia symptom terms; app severity is educational |
| SYM002 | Blurred vision or visual disturbance | URGENT | Seek urgent professional assessment. | NICE NG133 §1.5.2 and severe pre-eclampsia terms |
| SYM003 | Upper abdominal or epigastric pain | URGENT | Seek urgent professional assessment. | NICE NG133 §1.5.2 and severe pre-eclampsia terms |
| SYM004 | Difficulty breathing | URGENT | Seek urgent professional assessment. | NICE NG133 §1.5.2 concern for signs of pulmonary oedema |
| SYM005 | Reduced urine output | WARNING | Arrange professional assessment. | NICE NG133 severe pre-eclampsia terms |
| SYM006 | Nausea or vomiting | CAUTION | Record for clinical review in context; this alone is not proof of pre-eclampsia. | NICE NG133 severe pre-eclampsia terms; app severity is educational |
| SYM007 | Seizure or convulsion | EMERGENCY | Seek immediate emergency assistance; do not wait for another measurement. | NICE NG133 definition of eclampsia; user-specified emergency handling |
| SYM008 | Other symptom text or checkbox | CAUTION | The text is not classified by a predefined clinical rule; arrange professional review. | Educational completeness rule |

## Optional laboratory and urine-output rules

| Rule | Condition | Severity | Suggested action | Source/context |
| --- | --- | --- | --- | --- |
| LAB001 | Platelet count <150,000/microlitre | WARNING | Professional assessment with lab and clinical context. | NICE NG133 §1.5.2 |
| LAB002 | Serum creatinine ≥90 micromol/L | WARNING | Professional assessment with lab and clinical context. | NICE NG133 §1.5.2 |
| LAB003 | ALT >70 IU/L **or** >2 times a supplied lab upper limit | WARNING | Professional assessment; use the reporting lab's reference range. | NICE NG133 §1.5.2 |
| LAB004 | AST above supplied lab upper limit | WARNING | Professional assessment using that lab's range. No universal AST cutoff is used. | Lab-specific rule per task; NICE NG133 discusses transaminases in context |
| LAB005 | Urine protein-to-creatinine ratio ≥30 mg/mmol | WARNING | Professional assessment in the full clinical context. | NICE NG133 §1.2.6 |
| LAB006 | Urine albumin-to-creatinine ratio ≥8 mg/mmol | WARNING | Professional assessment in the full clinical context. | NICE NG133 §1.2.7 |
| LAB007 | A supplied optional measurement is invalid | INFORMATION | Verify the measurement and units before interpretation. | Educational data-quality rule |
| LAB008 | AST supplied without lab upper limit | INFORMATION | AST is not evaluated; add the reporting lab's documented upper limit. | Educational completeness rule |

Missing optional measurements are skipped, not assumed normal. ALT/AST
upper-limit fields are optional and should only contain the reporting
laboratory's stated limit. Urine output is stored with a measurement period
in hours; no urine-output threshold is implemented because none was specified
with a verified source for this project.

## Overall patient assessment (assessment version 1.0)

`assessment_engine.build_overall_assessment()` combines the alert list and
overall severity returned by the existing `monitoring_rules.evaluate_visit()`.
It does not evaluate new measurements, add clinical thresholds, or create a
second alert engine. Its result is deterministic for identical rule-engine
input. The highest severity from the existing evaluation determines the
assessment category:

| Existing severity | Assessment category |
| --- | --- |
| INFORMATION | NO PREDEFINED ALERT RULES TRIGGERED |
| CAUTION | MONITORING REQUIRED |
| WARNING | CONCERNING FINDINGS |
| URGENT | URGENT CLINICAL ASSESSMENT REQUIRED |
| EMERGENCY | EMERGENCY |

Informational findings (for example, an informational note about a recorded
negative dipstick screen) remain visible. They do not change the category from
the no-actionable-alert category. That category explicitly says that absence
of an alert does not rule out pre-eclampsia or another complication.

### Possible pre-eclampsia concern

The assessment displays a separate possible-concern flag only when an
existing rule reports raised blood pressure at or after 20 weeks together
with an existing positive urine protein finding, or with one of the existing
laboratory review findings (LAB001–LAB004). The positive urine protein set
uses the existing dipstick rules UR003–UR006 and quantitative rules LAB005
and LAB006. This is a screening flag and not a diagnosis. Protein alone,
raised blood pressure before 20 weeks, and unrelated findings do not trigger
this combined flag. The flag reuses the documented BP/gestational and NICE
protein/laboratory rules described above; it does not add cutoffs.

### Recommendations and emergency handling

Individual recommendations come directly from the triggered rules'
`suggested_action` values. The assessment sorts these by existing severity,
deduplicates identical recommendations (normalizing whitespace and
punctuation), and combines their rule IDs and reasons. It does not prescribe
medication or treatment. If a seizure rule (SYM007) is present, EMERGENCY
overrides every lower severity and the assessment displays the immediate
emergency message. The application does not diagnose or predict eclampsia.

### Saved assessment history and dashboard

Each evaluated visit stores an assessment JSON snapshot, `assessment_version`,
and timestamp on that visit row. Re-evaluating replaces that visit's snapshot
within the same database transaction; a unique assessment record is not
created for every refresh. Visit history reads the snapshot belonging to the
selected visit. Older visits without a snapshot remain unchanged and show
that no overall assessment is available; the application does not generate
one retroactively. Dashboard category counts use one visit per category and
only visits with a saved snapshot.

Assessment version is currently **1.0**. Existing monitoring rule version is
stored separately and remains **1.0**. This software is educational, is not
clinically validated, and is not a complete assessment. All clinical actions
must be determined by a qualified healthcare professional using current
local guidance. The source guidance remains the Malaysian Ministry of Health
Perinatal Care Manual and NICE NG133 linked above.

## Data fields and migration

Optional visit fields include maternal warning-sign codes and free-text other
symptoms; platelet count (per microlitre); serum creatinine (micromol/L); ALT
and AST values and optional laboratory upper limits (IU/L); PCR and ACR
(mg/mmol); urine output (mL) and its period (hours). New visits are evaluated
atomically with their database save. Each evaluation stores its rule version,
overall severity, summary, triggered alerts, and versioned overall assessment.
Older visits remain intact and are shown as not evaluated or without an overall
assessment; the system does not invent retrospective data, assessments or alerts.

## Application input checks

Input checks are separate from monitoring rules. Patient names are limited to
150 characters, contact numbers to 30 characters, and patient age to 1–120
whole years. Visit notes and other-symptom text are limited to 2,000 and 500
characters. Visit dates must be valid calendar dates and cannot be in the
future. Gestational age uses the application's existing supported entry
range of 1–45 completed weeks.

Blood pressure must be entered as positive whole-number readings, and the
systolic reading must be greater than the diastolic reading. There is no
arbitrary upper input cap: large recorded readings are passed to the existing
monitoring rules for review. These input checks do not add or change clinical
alert thresholds. Optional lab values must be finite and non-negative;
platelet counts must be positive whole numbers, and supplied laboratory upper
limits must be positive. Urine output and its period must be provided together,
with a positive period. Missing optional values remain missing and are not
converted to zero. Symptom entries must use the supported form options, and
the “other symptoms” option requires a description.
