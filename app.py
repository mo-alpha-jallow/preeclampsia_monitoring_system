from datetime import date

import altair as alt
import pandas as pd
import streamlit as st
from database import (
    URINE_PROTEIN_VALUES,
    add_antenatal_visit,
    add_patient,
    get_all_patients,
    get_dashboard_data,
    get_patient_by_id,
    get_patient_visits,
    get_visit_monitoring,
    initialize_database,
    update_patient,
)


def _light_chart(chart):
    """Give Altair charts the same light, high-contrast style as the app."""
    return (
        chart.configure(background="#FFFFFF")
        .configure_view(fill="#FFFFFF", stroke="#E2E8F0")
        .configure_title(color="#16324F", font="Segoe UI", fontSize=16, anchor="start")
        .configure_axis(
            labelColor="#334155",
            titleColor="#16324F",
            gridColor="#E8EEF4",
            domainColor="#A8B8C5",
            tickColor="#A8B8C5",
            labelFont="Segoe UI",
            titleFont="Segoe UI",
        )
        .configure_legend(
            labelColor="#334155",
            titleColor="#16324F",
            orient="bottom",
            labelFont="Segoe UI",
            titleFont="Segoe UI",
        )
    )


def _render_monitoring_evaluation(evaluation):
    """Show a saved assessment snapshot and the rules behind that result."""
    assessment = evaluation.get("assessment")
    if assessment is None:
        from assessment_engine import build_overall_assessment

        assessment = build_overall_assessment(evaluation)

    severity = assessment["overall_severity"]
    icons = {
        "INFORMATION": "🔵",
        "CAUTION": "🟡",
        "WARNING": "🟠",
        "URGENT": "🔴",
        "EMERGENCY": "🚨",
    }
    st.markdown("### Overall Assessment")
    heading = f"{icons.get(severity, 'ℹ️')} {assessment['overall_category']}"
    if severity == "EMERGENCY":
        st.error(heading)
        st.error(assessment["emergency_message"])
    elif severity == "URGENT":
        st.error(heading)
    elif severity == "WARNING":
        st.warning(heading)
    elif severity == "CAUTION":
        st.info(heading)
    else:
        st.success(heading)
    st.write(assessment["summary"])
    st.caption(f"Triggered rule findings: {assessment['triggered_rule_count']}")

    if assessment["possible_preeclampsia_concern"]:
        st.warning(assessment["possible_preeclampsia_message"])
        st.write(assessment["possible_preeclampsia_disclaimer"])
        st.caption(assessment["possible_preeclampsia_explanation"])

    alerts = assessment.get("triggered_findings", evaluation.get("alerts", []))
    if not alerts:
        st.info("No triggered findings are available for this saved assessment.")
    else:
        st.markdown("#### Triggered Findings")
        for alert in alerts:
            with st.container(border=True):
                st.markdown(
                    f"**{icons.get(alert['severity'], 'ℹ️')} {alert['severity']} · "
                    f"{alert['rule_id']} — {alert['rule_name']}**"
                )
                st.text(f"Measurement or condition: {alert['measurement']}")
                st.write(f"**Why flagged:** {alert['explanation']}")
                st.caption(f"Rule source: {alert['guideline_source']}")

    st.markdown("#### Recommendations")
    for recommendation in assessment["combined_recommendations"]:
        with st.container(border=True):
            st.markdown(
                f"**{icons.get(recommendation['priority'], 'ℹ️')} "
                f"{recommendation['priority']} priority**"
            )
            st.write(recommendation["recommendation"])
            if recommendation["reasons"]:
                st.caption("Related findings: " + ", ".join(recommendation["reasons"]))

    with st.expander("Individual rule recommendations"):
        for recommendation in assessment["individual_recommendations"]:
            st.write(
                f"**{recommendation['rule_id']} · {recommendation['reason']}** — "
                f"{recommendation['recommendation']}"
            )

    st.caption("Assessment explanation: " + assessment["explanation"])
    st.caption(
        "Educational monitoring support only. This application does not diagnose "
        "preeclampsia or eclampsia, predict outcomes, or replace professional assessment."
    )


try:
    initialize_database()
    database_ready = True
except RuntimeError:
    database_ready = False


st.set_page_config(
    page_title="Pre-eclampsia Monitoring System",
    page_icon="🩺",
    layout="wide",
)

if not database_ready:
    st.error(
        "The application database could not be opened or initialized. "
        "Check that the database file is available and writable, then restart the app."
    )
    st.stop()

st.markdown(
    """
    <style>
    :root {
        --navy: #16324F;
        --navy-2: #234B68;
        --teal: #0F8B8D;
        --teal-dark: #0A7072;
        --canvas: #F4F7FB;
        --surface: #FFFFFF;
        --ink: #243447;
        --muted: #52677D;
        --line: #E2E8F0;
    }
    .stApp { background: var(--canvas); color: var(--ink); font-family: "Segoe UI", Arial, sans-serif; }
    [data-testid="stHeader"] { background: rgba(244,247,251,.96); }
    [data-testid="stMainBlockContainer"] { max-width: 1440px; padding: 1.7rem 2.2rem 3rem; }
    h1, h2, h3, h4 { color: var(--navy) !important; letter-spacing: -0.02em; }
    h1 { font-weight: 750 !important; font-size: clamp(1.8rem,3vw,2.5rem) !important; line-height: 1.18 !important; }
    h2 { font-weight: 700 !important; font-size: clamp(1.35rem,2.2vw,1.8rem) !important; margin-top: 1.6rem !important; }
    h3 { font-weight: 680 !important; font-size: 1.2rem !important; margin-top: 1.2rem !important; }
    h4 { font-weight: 650 !important; }
    p, label, [data-testid="stMarkdownContainer"], [data-testid="stCaptionContainer"] { color: var(--ink); }
    [data-testid="stCaptionContainer"] p { color: #52677D !important; }
    [data-testid="stSidebar"] { background: linear-gradient(180deg,#132B43 0%,#16324F 100%); border-right: 1px solid #284761; }
    [data-testid="stSidebar"] h1, [data-testid="stSidebar"] h2, [data-testid="stSidebar"] h3,
    [data-testid="stSidebar"] p, [data-testid="stSidebar"] label,
    [data-testid="stSidebar"] [data-testid="stMarkdownContainer"] { color: #F7FAFC !important; }
    [data-testid="stSidebar"] [data-testid="stCaptionContainer"] p { color: #DCE8F1 !important; }
    [data-testid="stSidebar"] [data-testid="stRadio"] > label { color: #DCE8F1 !important; font-size: .76rem; font-weight: 700; letter-spacing: .08em; text-transform: uppercase; }
    [data-testid="stSidebar"] div[role="radiogroup"] label { border-radius: 9px; padding: .4rem .55rem; transition: background-color .15s ease; }
    [data-testid="stSidebar"] div[role="radiogroup"] label:hover { background: rgba(255,255,255,.1); }
    [data-testid="stSidebar"] div[role="radiogroup"] label:has(input:checked) { background: rgba(15,139,141,.34); box-shadow: inset 3px 0 #67D2C6; }
    [data-testid="stMetric"] { background: var(--surface); border: 1px solid var(--line); border-top: 3px solid var(--teal); border-radius: 14px; padding: 1rem 1.1rem; box-shadow: 0 5px 18px rgba(22,50,79,.055); min-height: 112px; }
    [data-testid="stMetricLabel"] p { color: #52677D !important; font-size: .84rem; font-weight: 650; }
    [data-testid="stMetricValue"] { color: var(--navy) !important; font-weight: 750; }
    [data-testid="stVerticalBlockBorderWrapper"] { background: var(--surface); border-color: var(--line) !important; border-radius: 14px; box-shadow: 0 5px 18px rgba(22,50,79,.04); }
    [data-testid="stForm"] { background: var(--surface); border: 1px solid var(--line); border-radius: 14px; padding: 1.25rem 1.4rem; box-sizing: border-box; max-width: 1080px; width: 100%; }
    [data-testid="stTextInput"] input, [data-testid="stNumberInput"] input, [data-testid="stDateInput"] input,
    [data-testid="stSelectbox"] div[data-baseweb="select"] > div, [data-testid="stTextArea"] textarea {
        background: #FFFFFF !important; color: var(--ink) !important; border-color: #C7D2DE !important; border-radius: 9px;
    }
    [data-testid="stTextInput"] input::placeholder, [data-testid="stNumberInput"] input::placeholder,
    [data-testid="stTextArea"] textarea::placeholder { color: #52677D !important; opacity: 1; }
    [data-testid="stSelectbox"] [data-baseweb="select"] *, [data-baseweb="popover"] [role="option"],
    [data-baseweb="menu"], [data-baseweb="popover"] [role="option"] * { background-color: #FFFFFF !important; color: var(--ink) !important; }
    [data-testid="stTextInput"] input:focus, [data-testid="stNumberInput"] input:focus,
    [data-testid="stTextArea"] textarea:focus, [data-testid="stSelectbox"] [role="combobox"]:focus { border-color: var(--teal) !important; box-shadow: 0 0 0 1px var(--teal) !important; }
    .stButton button[kind="primary"], [data-testid="stFormSubmitButton"] button[kind="primary"] { background: var(--teal) !important; border-color: var(--teal) !important; color: #FFFFFF !important; border-radius: 9px; font-weight: 700; }
    .stButton button[kind="primary"]:hover, [data-testid="stFormSubmitButton"] button[kind="primary"]:hover { background: var(--teal-dark) !important; border-color: var(--teal-dark) !important; }
    .stButton button, [data-testid="stFormSubmitButton"] button { background: #FFFFFF; color: var(--navy) !important; border: 1px solid #B8C7D3; border-radius: 9px; font-weight: 650; }
    button:focus-visible, input:focus-visible, textarea:focus-visible, [role="combobox"]:focus-visible { outline: 3px solid #42B8AE !important; outline-offset: 2px !important; }
    [data-testid="stDataFrame"] { border: 1px solid var(--line); border-radius: 11px; overflow: hidden; background: #FFFFFF; }
    [data-testid="stAlert"] { border-radius: 11px; }
    [data-testid="stExpander"] { border-color: var(--line); border-radius: 11px; background: #FFFFFF; }
    .st-key-rule-monitoring-summary [data-testid="column"]:nth-child(2) [data-testid="stMetric"] { border-top-color: #D5A63C; }
    .st-key-rule-monitoring-summary [data-testid="column"]:nth-child(3) [data-testid="stMetric"] { border-top-color: #D17835; }
    .st-key-rule-monitoring-summary [data-testid="column"]:nth-child(4) [data-testid="stMetric"] { border-top-color: #C65D4B; }
    .st-key-rule-monitoring-summary [data-testid="column"]:nth-child(5) [data-testid="stMetric"] { border-top-color: #B4433E; }
    .st-key-assessment-summary [data-testid="column"]:nth-child(2) [data-testid="stMetric"] { border-top-color: #0F8B8D; }
    .st-key-assessment-summary [data-testid="column"]:nth-child(3) [data-testid="stMetric"] { border-top-color: #D5A63C; }
    .st-key-assessment-summary [data-testid="column"]:nth-child(4) [data-testid="stMetric"] { border-top-color: #D17835; }
    .st-key-assessment-summary [data-testid="column"]:nth-child(5) [data-testid="stMetric"] { border-top-color: #B4433E; }
    hr { border-color: var(--line); }
    @media (max-width: 900px) {
        [data-testid="stMainBlockContainer"] { padding: 1.3rem 1.25rem 2.4rem; }
        [data-testid="stHorizontalBlock"] { flex-wrap: wrap; gap: .8rem; }
        [data-testid="stHorizontalBlock"] > [data-testid="column"] { flex: 1 1 230px !important; width: auto !important; min-width: min(100%,230px); }
    }
    @media (max-width: 560px) {
        [data-testid="stMainBlockContainer"] { padding: 1rem .9rem 2rem; }
        [data-testid="stMetric"] { min-height: 88px; padding: .8rem; }
        h1 { font-size: 1.75rem !important; }
        h2 { font-size: 1.35rem !important; }
        h3 { font-size: 1.12rem !important; }
        [data-testid="stForm"] { padding: .9rem; }
    }
    </style>
    """,
    unsafe_allow_html=True,
)

st.sidebar.title("🩺 Care Monitor")
st.sidebar.caption("PRE-ECLAMPSIA MONITORING SYSTEM")
page = st.sidebar.radio(
    "Navigation",
    [
        "Dashboard",
        "Patient Registration",
        "Patient Records",
        "Antenatal Visits",
        "Patient Visit History",
    ],
    format_func=lambda item: {
        "Dashboard": "📊  Dashboard",
        "Patient Registration": "➕  Patient Registration",
        "Patient Records": "👥  Patient Records",
        "Antenatal Visits": "🩺  Antenatal Visits",
        "Patient Visit History": "🗂️  Patient Visit History",
    }[item],
)
st.sidebar.caption("Educational monitoring support only · Not a diagnostic system")

if page == "Dashboard":
    st.title("Pre-eclampsia Monitoring Dashboard")
    st.write(
        "Overview of patient records, antenatal visits and rule-based maternal monitoring."
    )

    st.warning(
        "This application is an educational monitoring support tool and is not a "
        "diagnostic system. It does not replace professional clinical assessment."
    )

    st.subheader("Dashboard Overview")
    try:
        dashboard_data = get_dashboard_data()
    except RuntimeError:
        st.error("Dashboard data could not be loaded. Please try again shortly.")
    else:
        summary = dashboard_data["summary"]
        metric_columns = st.columns(4)
        metric_columns[0].metric(
            "👤 Registered Patients", summary["total_patients"]
        )
        metric_columns[1].metric(
            "🩺 Antenatal Visits", summary["total_visits"]
        )
        metric_columns[2].metric(
            "📅 Visits This Month", summary["visits_this_month"]
        )
        metric_columns[3].metric(
            "🤰 Patients With Visits", summary["patients_with_visits"]
        )

        st.subheader("Rule-Based Monitoring Overview")
        st.caption(
            "Counts represent saved rule evaluations and flagged visits. They "
            "are not counts of confirmed diagnoses."
        )
        monitoring_overview = dashboard_data["monitoring_overview"]
        with st.container(key="rule-monitoring-summary"):
            monitoring_columns = st.columns(5)
        monitoring_columns[0].metric(
            "Visits Evaluated", monitoring_overview["evaluated_visits"]
        )
        monitoring_columns[1].metric(
            "🟡 Caution Flags", monitoring_overview["caution_visits"]
        )
        monitoring_columns[2].metric(
            "🟠 Warning Flags", monitoring_overview["warning_visits"]
        )
        monitoring_columns[3].metric(
            "🔴 Urgent Flags", monitoring_overview["urgent_visits"]
        )
        monitoring_columns[4].metric(
            "🚨 Emergency Flags", monitoring_overview["emergency_visits"]
        )

        st.subheader("Overall Assessment Summary")
        st.caption(
            "Counts are saved visit assessments, not diagnoses. Each visit is "
            "counted once in its overall category."
        )
        assessment_overview = dashboard_data["assessment_overview"]
        with st.container(key="assessment-summary"):
            assessment_columns = st.columns(5)
        assessment_columns[0].metric(
            "No Alert Rules", assessment_overview["no_alert_visits"]
        )
        assessment_columns[1].metric(
            "Monitoring Required", assessment_overview["monitoring_required_visits"]
        )
        assessment_columns[2].metric(
            "Concerning", assessment_overview["concerning_visits"]
        )
        assessment_columns[3].metric(
            "Urgent", assessment_overview["urgent_visits"]
        )
        assessment_columns[4].metric(
            "Emergency", assessment_overview["emergency_visits"]
        )

        st.subheader("Antenatal Data Visualisations")
        st.caption(
            "Charts show recorded information only. They may be incomplete and "
            "are not a diagnosis or a complete clinical assessment."
        )

        with st.container(border=True):
            st.markdown("#### Blood Pressure Trends")
            patients_with_visits = [
                patient
                for patient in dashboard_data["patient_overview"]
                if patient["visit_count"] > 0
            ]
            if not patients_with_visits:
                st.info("Blood pressure trends will appear after visits are recorded.")
            else:
                trend_patient_names = {
                    patient["patient_id"]: patient["full_name"]
                    for patient in patients_with_visits
                }
                trend_patient_id = st.selectbox(
                    "Select a patient for blood pressure trends",
                    options=list(trend_patient_names),
                    format_func=lambda patient_id: (
                        f"{patient_id} — {trend_patient_names[patient_id]}"
                    ),
                    key="dashboard_bp_patient_id",
                )
                patient_trends = [
                    record
                    for record in dashboard_data["blood_pressure_trends"]
                    if record["patient_id"] == trend_patient_id
                ]
                if len(patient_trends) < 2:
                    st.info(
                        "At least two visits are needed to show a blood pressure trend for this patient."
                    )
                else:
                    st.caption(
                        f"Showing {trend_patient_names[trend_patient_id]} "
                        f"(Patient ID {trend_patient_id}) only."
                    )
                    pressure_rows = []
                    for record in patient_trends:
                        pressure_rows.extend(
                            [
                                {
                                    "Visit Date": pd.to_datetime(record["visit_date"]),
                                    "Measurement": "Systolic BP",
                                    "Blood Pressure (mmHg)": record["systolic_bp"],
                                },
                                {
                                    "Visit Date": pd.to_datetime(record["visit_date"]),
                                    "Measurement": "Diastolic BP",
                                    "Blood Pressure (mmHg)": record["diastolic_bp"],
                                },
                            ]
                        )
                    pressure_frame = pd.DataFrame(pressure_rows)
                    pressure_chart = (
                        alt.Chart(pressure_frame)
                        .mark_line(point=True, strokeWidth=3)
                        .encode(
                            x=alt.X(
                                "Visit Date:T",
                                title="Visit date",
                                axis=alt.Axis(format="%d %b %Y", labelAngle=-30),
                            ),
                            y=alt.Y(
                                "Blood Pressure (mmHg):Q",
                                title="Blood pressure (mmHg)",
                            ),
                            color=alt.Color(
                                "Measurement:N",
                                title="Measurement",
                                scale=alt.Scale(
                                    domain=["Systolic BP", "Diastolic BP"],
                                    range=["#15324B", "#128078"],
                                ),
                            ),
                            tooltip=[
                                alt.Tooltip("Visit Date:T", title="Visit date", format="%d %b %Y"),
                                alt.Tooltip("Measurement:N", title="Measurement"),
                                alt.Tooltip("Blood Pressure (mmHg):Q", title="Blood pressure", format=".0f"),
                            ],
                        )
                        .properties(height=320)
                    )
                    st.caption(
                        "Dashed lines show the existing educational rule engine's "
                        "140 mmHg systolic and 90 mmHg diastolic review markers. "
                        "They are monitoring references, not diagnoses."
                    )
                    reference_frame = pd.DataFrame(
                        [
                            {
                                "Reference": "Systolic review marker (140 mmHg)",
                                "Reference Value": 140,
                            },
                            {
                                "Reference": "Diastolic review marker (90 mmHg)",
                                "Reference Value": 90,
                            },
                        ]
                    )
                    reference_chart = (
                        alt.Chart(reference_frame)
                        .mark_rule(strokeDash=[6, 4], strokeWidth=1.5)
                        .encode(
                            y=alt.Y("Reference Value:Q"),
                            color=alt.Color(
                                "Reference:N",
                                title="Educational review marker",
                                scale=alt.Scale(
                                    domain=[
                                        "Systolic review marker (140 mmHg)",
                                        "Diastolic review marker (90 mmHg)",
                                    ],
                                    range=["#D17835", "#73A9C2"],
                                ),
                            ),
                            tooltip=[
                                alt.Tooltip("Reference:N", title="Reference"),
                                alt.Tooltip("Reference Value:Q", title="mmHg", format=".0f"),
                            ],
                        )
                    )
                    pressure_chart = alt.layer(pressure_chart, reference_chart)
                    st.altair_chart(
                        _light_chart(pressure_chart), width="stretch", theme=None
                    )

        visit_chart_column, urine_chart_column = st.columns(2)
        with visit_chart_column:
            with st.container(border=True):
                st.markdown("#### Antenatal Visits by Month")
                monthly_visits = dashboard_data["monthly_visits"]
                if monthly_visits:
                    monthly_frame = pd.DataFrame(
                        [
                            {
                                "Month": record["visit_month"],
                                "Recorded Visits": record["visit_count"],
                            }
                            for record in monthly_visits
                        ]
                    )
                    monthly_chart = (
                        alt.Chart(monthly_frame)
                        .mark_bar(color="#0F8B8D", cornerRadiusTopLeft=4, cornerRadiusTopRight=4)
                        .encode(
                            x=alt.X("Month:O", title="Month", sort=None),
                            y=alt.Y("Recorded Visits:Q", title="Number of visits", scale=alt.Scale(nice=True)),
                            tooltip=[
                                alt.Tooltip("Month:O", title="Month"),
                                alt.Tooltip("Recorded Visits:Q", title="Recorded visits"),
                            ],
                        )
                        .properties(height=300)
                    )
                    st.altair_chart(
                        _light_chart(monthly_chart), width="stretch", theme=None
                    )
                    if len(monthly_visits) == 1:
                        st.caption(
                            "Visits are currently recorded in one month, so a longer-term pattern is not available."
                        )
                else:
                    st.info("Visit activity will appear after visits are recorded.")

        with urine_chart_column:
            with st.container(border=True):
                st.markdown("#### Urine Protein Results")
                urine_counts = dashboard_data["urine_protein_summary"]
                if sum(urine_counts.values()) == 0:
                    st.info("Urine protein results will appear after visits are recorded.")
                else:
                    display_results = [
                        ("Negative", "Negative"),
                        ("Trace", "Trace"),
                        ("1+", "+1"),
                        ("2+", "+2"),
                        ("3+", "+3"),
                        ("4+", "+4"),
                        ("Not tested", "Not tested"),
                    ]
                    urine_frame = pd.DataFrame(
                        [
                            {"Urine Protein Result": label, "Recorded Visits": urine_counts[value]}
                            for label, value in display_results
                            if urine_counts[value] > 0
                        ]
                    )
                    urine_chart = (
                        alt.Chart(urine_frame)
                        .mark_bar(cornerRadiusEnd=4)
                        .encode(
                            y=alt.Y(
                                "Urine Protein Result:N",
                                title=None,
                                sort=[label for label, _ in display_results],
                            ),
                            x=alt.X("Recorded Visits:Q", title="Number of visits", scale=alt.Scale(nice=True), axis=alt.Axis(tickMinStep=1)),
                            color=alt.Color(
                                "Urine Protein Result:N",
                                legend=None,
                                scale=alt.Scale(
                                    domain=[label for label, _ in display_results],
                                    range=["#234B68", "#0F8B8D", "#73A9C2", "#5B9C8A", "#E4B363", "#D17835", "#8A78A6"],
                                ),
                            ),
                            tooltip=[
                                alt.Tooltip("Urine Protein Result:N", title="Urine protein"),
                                alt.Tooltip("Recorded Visits:Q", title="Recorded visits"),
                            ],
                        )
                        .properties(height=270)
                    )
                    st.altair_chart(
                        _light_chart(urine_chart), width="stretch", theme=None
                    )

        with st.container(border=True):
            st.markdown("#### Gestational Age Distribution")
            gestational_distribution = dashboard_data[
                "gestational_age_distribution"
            ]
            if gestational_distribution:
                gestational_frame = pd.DataFrame(
                    [
                        {
                            "Gestational Age (weeks)": record[
                                "gestational_age_weeks"
                            ],
                            "Recorded Visits": record["visit_count"],
                        }
                        for record in gestational_distribution
                    ]
                )
                gestational_chart = (
                    alt.Chart(gestational_frame)
                    .mark_bar(color="#128078", cornerRadiusTopLeft=3, cornerRadiusTopRight=3)
                    .encode(
                        x=alt.X(
                            "Gestational Age (weeks):Q",
                            title="Gestational age (completed weeks)",
                            axis=alt.Axis(tickMinStep=1),
                        ),
                        y=alt.Y("Recorded Visits:Q", title="Number of visits", scale=alt.Scale(nice=True)),
                        tooltip=[
                            alt.Tooltip("Gestational Age (weeks):Q", title="Gestational age", format=".0f"),
                            alt.Tooltip("Recorded Visits:Q", title="Recorded visits"),
                        ],
                    )
                    .properties(height=300)
                )
                st.altair_chart(
                    _light_chart(gestational_chart), width="stretch", theme=None
                )
            else:
                st.info("Gestational age distribution will appear after visits are recorded.")

        with st.container(border=True):
            st.markdown("#### Saved Assessment Distribution")
            st.caption(
                "Counts are saved visit assessments in each category, not disease prevalence."
            )
            assessment_order = [
                "No predefined alert rules triggered",
                "Monitoring required",
                "Concerning findings",
                "Urgent clinical assessment required",
                "Emergency",
            ]
            assessment_fields = [
                "no_alert_visits",
                "monitoring_required_visits",
                "concerning_visits",
                "urgent_visits",
                "emergency_visits",
            ]
            assessment_colours = ["#73A9C2", "#0F8B8D", "#E4B363", "#D17835", "#B4433E"]
            assessment_frame = pd.DataFrame(
                [
                    {
                        "Assessment Category": category,
                        "Saved Assessments": assessment_overview[field] or 0,
                    }
                    for category, field in zip(assessment_order, assessment_fields)
                ]
            )
            if int(assessment_frame["Saved Assessments"].sum()) == 0:
                st.info("Saved assessment counts will appear after antenatal visits are evaluated.")
            else:
                assessment_chart = (
                    alt.Chart(assessment_frame)
                    .mark_bar(cornerRadiusEnd=4)
                    .encode(
                        x=alt.X("Saved Assessments:Q", title="Number of saved assessments", axis=alt.Axis(tickMinStep=1)),
                        y=alt.Y("Assessment Category:N", title=None, sort=assessment_order),
                        color=alt.Color(
                            "Assessment Category:N",
                            legend=None,
                            scale=alt.Scale(domain=assessment_order, range=assessment_colours),
                        ),
                        tooltip=[
                            alt.Tooltip("Assessment Category:N", title="Assessment category"),
                            alt.Tooltip("Saved Assessments:Q", title="Saved assessments"),
                        ],
                    )
                    .properties(height=245)
                )
                st.altair_chart(
                    _light_chart(assessment_chart), width="stretch", theme=None
                )

        st.subheader("Recent Patient Registrations")
        recent_patients = dashboard_data["recent_patients"]
        if recent_patients:
            registration_rows = [
                {
                    "Patient ID": patient["patient_id"],
                    "Full Name": patient["full_name"],
                    "Age": patient["age"] if patient["age"] is not None else "Not provided",
                    "Registration Date": patient["registration_date"],
                }
                for patient in recent_patients
            ]
            st.dataframe(registration_rows, hide_index=True, width="stretch")
        else:
            st.info("No patients have been registered yet.")

        st.subheader("Recent Antenatal Visits")
        recent_visits = dashboard_data["recent_visits"]
        if recent_visits:
            recent_rows = [
                {
                    "Patient ID": visit["patient_id"],
                    "Patient Name": visit["full_name"],
                    "Visit Date": visit["visit_date"],
                    "Gestational Age (weeks)": visit["gestational_age_weeks"],
                    "Systolic BP (mmHg)": visit["systolic_bp"],
                    "Diastolic BP (mmHg)": visit["diastolic_bp"],
                    "Urine Protein": visit["urine_protein"],
                }
                for visit in recent_visits
            ]
            st.dataframe(recent_rows, hide_index=True, width="stretch")
        else:
            st.info("No antenatal visits have been recorded yet.")

        st.subheader("Recent Overall Assessments")
        recent_assessments = dashboard_data["recent_assessments"]
        if recent_assessments:
            assessment_rows = [
                {
                    "Patient ID": record["patient_id"],
                    "Patient Name": record["full_name"],
                    "Visit Date": record["visit_date"],
                    "Overall Category": (
                        record["assessment"]["overall_category"]
                        if record.get("assessment")
                        else "Assessment unavailable"
                    ),
                    "Assessment Summary": (
                        record["assessment"]["summary"]
                        if record.get("assessment")
                        else "Saved assessment could not be read."
                    ),
                }
                for record in recent_assessments
            ]
            st.dataframe(assessment_rows, hide_index=True, width="stretch")
        else:
            st.info("Overall assessments will appear after a visit is recorded.")

        st.subheader("Recorded Monitoring Data Summary")
        st.caption(
            "These are summaries of recorded fields only. They are not a "
            "complete clinical assessment or diagnosis."
        )
        summary_columns = st.columns(2)
        minimum_weeks = summary["minimum_gestational_age"]
        maximum_weeks = summary["maximum_gestational_age"]
        if minimum_weeks is None or maximum_weeks is None:
            gestational_age_span = "No visits"
        else:
            gestational_age_span = f"{minimum_weeks}–{maximum_weeks} weeks"
        summary_columns[0].metric(
            "Recorded Gestational Age Span", gestational_age_span
        )
        summary_columns[1].metric(
            "Urine Protein Results Recorded",
            sum(dashboard_data["urine_protein_summary"].values()),
        )
        urine_rows = [
            {"Urine Protein Result": result, "Visit Count": count}
            for result, count in dashboard_data["urine_protein_summary"].items()
        ]
        st.dataframe(urine_rows, hide_index=True, width="stretch")

        st.subheader("Patient Overview")
        patient_overview = dashboard_data["patient_overview"]
        if patient_overview:
            patient_rows = [
                {
                    "Patient ID": patient["patient_id"],
                    "Full Name": patient["full_name"],
                    "Age": patient["age"] if patient["age"] is not None else "Not provided",
                    "Registration Date": patient["registration_date"],
                    "Antenatal Visits": patient["visit_count"],
                    "Visit Status": (
                        "Visits recorded" if patient["visit_count"] else "No visits yet"
                    ),
                }
                for patient in patient_overview
            ]
            st.dataframe(patient_rows, hide_index=True, width="stretch")
        else:
            st.info("No patients have been registered yet.")

elif page == "Patient Registration":
    st.title("Patient Registration")
    st.write("Register a patient to create their record in the system.")

    registration_form_version = st.session_state.get("registration_form_version", 0)
    with st.form(f"patient_registration_form_{registration_form_version}"):
        st.markdown("#### Patient details")
        full_name = st.text_input(
            "Full Name *", max_chars=150,
            key=f"registration_name_{registration_form_version}",
        )
        age_column, contact_column = st.columns(2)
        with age_column:
            age = st.number_input(
                "Age *", min_value=1, max_value=120, value=None, step=1,
                placeholder="Enter age in whole years",
                key=f"registration_age_{registration_form_version}",
            )
        with contact_column:
            contact_number = st.text_input(
                "Contact Number (optional)", max_chars=30,
                help="Leave this blank if no contact number is available.",
                key=f"registration_contact_{registration_form_version}",
            )
        submitted = st.form_submit_button("Register Patient", type="primary")

    if submitted:
        st.session_state.pop("last_registered_patient_id", None)
        if not full_name.strip():
            st.error("Please enter the patient's full name.")
        elif age is None:
            st.error("Please enter the patient's age as a whole number.")
        else:
            try:
                patient_id = add_patient(
                    full_name=full_name,
                    age=int(age),
                    contact_number=contact_number.strip() or None,
                )
                st.session_state["last_registered_patient_id"] = patient_id
                st.session_state["registration_form_version"] = registration_form_version + 1
                st.rerun()
            except ValueError as error:
                st.error(str(error))
            except RuntimeError:
                st.error("The patient could not be saved. Please try again shortly.")

    registered_patient_id = st.session_state.get("last_registered_patient_id")
    if registered_patient_id is not None:
        st.success(f"Patient registered successfully. Patient ID: {registered_patient_id}")

elif page == "Patient Records":
    st.title("Patient Records")
    st.write("Search registered patients and view their saved details.")

    try:
        patients = get_all_patients()
    except RuntimeError:
        st.error("Patient records could not be loaded. Please try again shortly.")
        patients = []

    if not patients:
        st.info("No patients have been registered yet.")
    else:
        search_term = st.text_input(
            "Search by Patient ID or Full Name",
            placeholder="Enter an ID or part of a name",
        ).strip()

        if search_term:
            matching_patients = [
                patient for patient in patients
                if str(patient["patient_id"]) == search_term
                or search_term.casefold() in patient["full_name"].casefold()
            ]
        else:
            matching_patients = patients

        if not matching_patients:
            st.info("No matching patient was found. Check the ID or name and try again.")
        else:
            table_rows = [
                {
                    "Patient ID": patient["patient_id"],
                    "Full Name": patient["full_name"],
                    "Age": patient["age"] if patient["age"] is not None else "Not provided",
                    "Contact Number": patient["contact_number"] or "Not provided",
                    "Registration Date": patient["registration_date"],
                }
                for patient in matching_patients
            ]
            st.dataframe(table_rows, hide_index=True, width="stretch")

            patient_options = [patient["patient_id"] for patient in matching_patients]
            patient_names = {
                patient["patient_id"]: patient["full_name"]
                for patient in matching_patients
            }
            selected_patient_id = st.selectbox(
                "Select a patient to view details",
                options=patient_options,
                format_func=lambda patient_id: (
                    f"{patient_id} — {patient_names[patient_id]}"
                ),
            )

            try:
                selected_patient = get_patient_by_id(selected_patient_id)
            except RuntimeError:
                st.error("Patient details could not be loaded. Please try again shortly.")
                selected_patient = None
            if selected_patient:
                heading_column, edit_button_column = st.columns([0.88, 0.12])
                with heading_column:
                    st.subheader("Patient Details")
                with edit_button_column:
                    if st.button(
                        "✏️",
                        help="Edit patient details",
                        key=f"toggle_patient_edit_{selected_patient_id}",
                    ):
                        st.session_state["editing_patient_id"] = selected_patient_id

                detail_left, detail_right = st.columns(2)
                with detail_left:
                    st.write(f"**Patient ID:** {selected_patient['patient_id']}")
                    st.write(f"**Full Name:** {selected_patient['full_name']}")
                    st.write(
                        "**Age:** "
                        f"{selected_patient['age'] if selected_patient['age'] is not None else 'Not provided'}"
                    )
                with detail_right:
                    st.write(
                        "**Contact Number:** "
                        f"{selected_patient['contact_number'] or 'Not provided'}"
                    )
                    st.write(
                        "**Registration Date:** "
                        f"{selected_patient['registration_date']}"
                    )

                if st.session_state.get("editing_patient_id") == selected_patient_id:
                    st.markdown("#### Edit Patient")
                    st.write("Update the patient's name, age, or contact number.")
                    edit_form_version_key = (
                        f"edit_patient_form_version_{selected_patient_id}"
                    )
                    edit_form_version = st.session_state.get(
                        edit_form_version_key, 0
                    )
                    with st.form(
                        f"edit_patient_form_{selected_patient_id}_{edit_form_version}"
                    ):
                        edited_name = st.text_input(
                            "Full Name *",
                            value=selected_patient["full_name"],
                            max_chars=150,
                            key=f"edit_name_{selected_patient_id}_{edit_form_version}",
                        )
                        edited_age = st.number_input(
                            "Age *",
                            min_value=1,
                            max_value=120,
                            value=selected_patient["age"],
                            step=1,
                            key=f"edit_age_{selected_patient_id}_{edit_form_version}",
                        )
                        edited_contact = st.text_input(
                            "Contact Number (optional)",
                            value=selected_patient["contact_number"] or "",
                            max_chars=30,
                            key=f"edit_contact_{selected_patient_id}_{edit_form_version}",
                        )
                        save_changes = st.form_submit_button(
                            "Save Changes", type="primary"
                        )
                        cancel_edit = st.form_submit_button("Cancel")

                    if cancel_edit:
                        st.session_state["editing_patient_id"] = None
                        st.session_state[edit_form_version_key] = edit_form_version + 1
                        st.rerun()
                    elif save_changes:
                        if not edited_name.strip():
                            st.error("Please enter the patient's full name.")
                        elif edited_age is None:
                            st.error("Please enter the patient's age as a whole number.")
                        else:
                            try:
                                updated = update_patient(
                                    patient_id=selected_patient_id,
                                    full_name=edited_name,
                                    age=int(edited_age),
                                    contact_number=edited_contact.strip() or None,
                                )
                                if updated:
                                    st.session_state["patient_update_success_id"] = (
                                        selected_patient_id
                                    )
                                    st.session_state["editing_patient_id"] = None
                                    st.session_state[edit_form_version_key] = (
                                        edit_form_version + 1
                                    )
                                    st.rerun()
                                st.error("That patient record could not be found.")
                            except ValueError as error:
                                st.error(str(error))
                            except RuntimeError:
                                st.error("The patient could not be updated. Please try again shortly.")

                if st.session_state.get("patient_update_success_id") == selected_patient_id:
                    st.success("Patient details updated successfully.")

elif page == "Patient Visit History":
    st.title("Patient Visit History")
    st.write("Review recorded antenatal visits for one patient at a time.")

    try:
        patients = get_all_patients()
    except RuntimeError:
        st.error("Registered patients could not be loaded. Please try again shortly.")
        patients = []

    if not patients:
        st.info("No registered patients are available yet.")
    else:
        patient_names = {
            patient["patient_id"]: patient["full_name"] for patient in patients
        }
        selected_patient_id = st.selectbox(
            "Select a patient",
            options=list(patient_names),
            format_func=lambda patient_id: (
                f"{patient_id} — {patient_names[patient_id]}"
            ),
            key="history_patient_id",
        )
        try:
            selected_patient = get_patient_by_id(selected_patient_id)
        except RuntimeError:
            st.error("Patient details could not be loaded. Please try again shortly.")
            selected_patient = None

        if selected_patient:
            st.info(
                f"Patient: {selected_patient['full_name']} "
                f"(Patient ID: {selected_patient['patient_id']})"
            )
            try:
                visits = get_patient_visits(selected_patient_id)
            except RuntimeError:
                st.error("Visit history could not be loaded. Please try again shortly.")
                visits = []

            if not visits:
                st.info("No antenatal visits have been recorded for this patient yet.")
            else:
                history_rows = [
                    {
                        "Visit ID": visit["visit_id"],
                        "Visit Date": visit["visit_date"],
                        "Overall Category": (
                            visit["assessment"]["overall_category"]
                            if visit.get("assessment")
                            else "No assessment available"
                        ),
                        "Assessment Summary": (
                            visit["assessment"]["summary"]
                            if visit.get("assessment")
                            else "No overall assessment is available for this historical visit."
                        ),
                        "Gestational Age (weeks)": visit["gestational_age_weeks"],
                        "Blood Pressure": (
                            f"{visit['systolic_bp']}/{visit['diastolic_bp']} mmHg"
                        ),
                        "Urine Protein": visit["urine_protein"],
                    }
                    for visit in visits
                ]
                st.dataframe(history_rows, hide_index=True, width="stretch")

                visit_by_id = {visit["visit_id"]: visit for visit in visits}
                selected_visit_id = st.selectbox(
                    "Select a visit to view full details",
                    options=list(visit_by_id),
                    format_func=lambda visit_id: (
                        f"Visit {visit_id} — "
                        f"{visit_by_id[visit_id]['visit_date']}"
                    ),
                    key=f"history_visit_id_{selected_patient_id}",
                )
                selected_visit = visit_by_id[selected_visit_id]

                st.subheader("Visit Details")
                details_left, details_right = st.columns(2)
                with details_left:
                    st.write(f"**Visit ID:** {selected_visit['visit_id']}")
                    st.write(f"**Patient ID:** {selected_patient_id}")
                    st.write(f"**Patient Name:** {selected_patient['full_name']}")
                    st.write(f"**Visit Date:** {selected_visit['visit_date']}")
                    st.write(
                        "**Gestational Age:** "
                        f"{selected_visit['gestational_age_weeks']} weeks"
                    )
                with details_right:
                    st.write(
                        f"**Systolic BP:** {selected_visit['systolic_bp']} mmHg"
                    )
                    st.write(
                        f"**Diastolic BP:** {selected_visit['diastolic_bp']} mmHg"
                    )
                    st.write(
                        f"**Urine Protein:** {selected_visit['urine_protein']}"
                    )
                st.write(
                    "**Clinical Notes:** "
                    f"{selected_visit['notes'] or 'No additional notes'}"
                )

                st.subheader("Overall Monitoring Assessment")
                if selected_visit.get("monitoring_evaluated_at") is None:
                    st.info(
                        "No overall assessment is available for this historical visit."
                    )
                elif selected_visit.get("assessment") is None:
                    st.info(
                        "No overall assessment is available for this historical visit. "
                        "Its original monitoring findings remain available below."
                    )
                    for alert in selected_visit.get("alerts", []):
                        with st.container(border=True):
                            st.markdown(
                                f"**{alert['severity']} · {alert['rule_id']} — "
                                f"{alert['rule_name']}**"
                            )
                            st.write(alert["explanation"])
                            st.write("**Suggested action:** " + alert["suggested_action"])
                else:
                    _render_monitoring_evaluation(
                        {
                            "overall_severity": selected_visit["overall_severity"],
                            "monitoring_summary": selected_visit["monitoring_summary"],
                            "alerts": selected_visit.get("alerts", []),
                            "assessment": selected_visit["assessment"],
                        }
                    )

elif page == "Antenatal Visits":
    st.title("Antenatal Visit Recording")
    st.write("Record a patient's visit measurements and urine protein result.")

    try:
        patients = get_all_patients()
    except RuntimeError:
        st.error("Registered patients could not be loaded. Please try again shortly.")
        patients = []

    if not patients:
        st.info("No registered patients are available. Register a patient before recording a visit.")
    else:
        patient_ids = [patient["patient_id"] for patient in patients]
        patient_names = {
            patient["patient_id"]: patient["full_name"] for patient in patients
        }
        selected_patient_id = st.selectbox(
            "Select a patient *",
            options=patient_ids,
            format_func=lambda patient_id: (
                f"{patient_id} — {patient_names[patient_id]}"
            ),
            key="visit_patient_id",
        )
        try:
            selected_patient = get_patient_by_id(selected_patient_id)
        except RuntimeError:
            st.error("Patient details could not be loaded. Please try again shortly.")
            selected_patient = None

        if selected_patient:
            st.info(
                f"Selected patient: {selected_patient['full_name']} "
                f"(Patient ID: {selected_patient['patient_id']})"
            )

            saved_visit = st.session_state.get("last_saved_visit")
            if saved_visit and saved_visit["patient_id"] == selected_patient_id:
                st.success(
                    f"Visit saved successfully. Visit ID: {saved_visit['visit_id']} · "
                    f"Patient: {selected_patient['full_name']} "
                    f"(Patient ID: {selected_patient_id})"
                )
                try:
                    saved_evaluation = get_visit_monitoring(saved_visit["visit_id"])
                    if saved_evaluation:
                        st.subheader("Overall Monitoring Assessment")
                        _render_monitoring_evaluation(saved_evaluation)
                except RuntimeError:
                    st.error(
                        "The visit was saved, but its assessment could not be "
                        "loaded. Please reopen the visit history or try again."
                    )

            form_version = st.session_state.get("visit_form_version", 0)
            form_key = f"antenatal_visit_form_{selected_patient_id}_{form_version}"
            with st.form(form_key):
                st.markdown("#### Pregnancy Information")
                date_column, gestation_column = st.columns(2)
                with date_column:
                    visit_date = st.date_input(
                        "Visit Date *",
                        value=date.today(),
                        key=f"visit_date_{selected_patient_id}_{form_version}",
                    )
                with gestation_column:
                    gestational_age_weeks = st.number_input(
                        "Gestational Age (completed weeks) *",
                        min_value=1,
                        max_value=45,
                        value=None,
                        step=1,
                        placeholder="Enter completed weeks (1–45)",
                        help="Enter pregnancy duration in completed weeks.",
                        key=f"visit_gestational_age_{selected_patient_id}_{form_version}",
                    )

                st.markdown("#### Blood Pressure")
                systolic_column, diastolic_column = st.columns(2)
                with systolic_column:
                    systolic_bp = st.number_input(
                        "Systolic Blood Pressure (mmHg) *",
                        min_value=1,
                        value=None,
                        step=1,
                        placeholder="Enter a positive whole number",
                        help="Record the measured value in mmHg.",
                        key=f"visit_systolic_{selected_patient_id}_{form_version}",
                    )
                with diastolic_column:
                    diastolic_bp = st.number_input(
                        "Diastolic Blood Pressure (mmHg) *",
                        min_value=1,
                        value=None,
                        step=1,
                        placeholder="Enter a positive whole number",
                        help="Record the measured value in mmHg.",
                        key=f"visit_diastolic_{selected_patient_id}_{form_version}",
                    )

                st.markdown("#### Urine Protein and Notes")
                urine_protein = st.selectbox(
                    "Urine Protein *",
                    options=URINE_PROTEIN_VALUES,
                    key=f"visit_urine_protein_{selected_patient_id}_{form_version}",
                )
                notes = st.text_area(
                    "Clinical Notes (optional)",
                    max_chars=2000,
                    key=f"visit_notes_{selected_patient_id}_{form_version}",
                )

                st.markdown("#### Maternal Warning Signs")
                st.caption(
                    "Record symptoms reported for this visit. Their presence or "
                    "absence alone does not diagnose or rule out a condition."
                )
                symptom_left, symptom_right = st.columns(2)
                with symptom_left:
                    headache_present = st.checkbox(
                        "Severe or persistent headache",
                        key=f"symptom_headache_{selected_patient_id}_{form_version}",
                    )
                    visual_disturbance = st.checkbox(
                        "Blurred vision or other visual disturbances",
                        key=f"symptom_visual_{selected_patient_id}_{form_version}",
                    )
                    epigastric_pain = st.checkbox(
                        "Upper abdominal or epigastric pain",
                        key=f"symptom_epigastric_{selected_patient_id}_{form_version}",
                    )
                    nausea_vomiting = st.checkbox(
                        "Nausea or vomiting",
                        key=f"symptom_nausea_{selected_patient_id}_{form_version}",
                    )
                with symptom_right:
                    difficulty_breathing = st.checkbox(
                        "Difficulty breathing",
                        key=f"symptom_breathing_{selected_patient_id}_{form_version}",
                    )
                    reduced_urine_output = st.checkbox(
                        "Reduced urine output",
                        key=f"symptom_urine_output_{selected_patient_id}_{form_version}",
                    )
                    seizure = st.checkbox(
                        "Seizure or convulsion",
                        key=f"symptom_seizure_{selected_patient_id}_{form_version}",
                    )
                    other_symptoms_selected = st.checkbox(
                        "Other symptoms",
                        key=f"symptom_other_{selected_patient_id}_{form_version}",
                    )
                other_symptoms = st.text_input(
                    "Describe other symptoms (optional)",
                    max_chars=500,
                    key=f"other_symptoms_{selected_patient_id}_{form_version}",
                )

                st.markdown("#### Optional Laboratory Measurements")
                st.caption(
                    "Enter values and laboratory reference limits only when they "
                    "are available on the report. Missing optional values are skipped."
                )
                lab_left, lab_right = st.columns(2)
                with lab_left:
                    platelet_count = st.number_input(
                        "Platelet count (per microlitre)",
                        min_value=0,
                        value=None,
                        step=1000,
                        key=f"platelets_{selected_patient_id}_{form_version}",
                    )
                    serum_creatinine = st.number_input(
                        "Serum creatinine (micromol/L)",
                        min_value=0.0,
                        value=None,
                        step=0.1,
                        format="%.1f",
                        key=f"creatinine_{selected_patient_id}_{form_version}",
                    )
                    alt_value = st.number_input(
                        "ALT (IU/L)", min_value=0.0, value=None, step=0.1,
                        format="%.1f", key=f"alt_{selected_patient_id}_{form_version}",
                    )
                    alt_upper_limit = st.number_input(
                        "ALT lab upper limit (IU/L, optional)",
                        min_value=0.0, value=None, step=0.1, format="%.1f",
                        key=f"alt_uln_{selected_patient_id}_{form_version}",
                    )
                    ast_value = st.number_input(
                        "AST (IU/L)", min_value=0.0, value=None, step=0.1,
                        format="%.1f", key=f"ast_{selected_patient_id}_{form_version}",
                    )
                    ast_upper_limit = st.number_input(
                        "AST lab upper limit (IU/L, optional)",
                        min_value=0.0, value=None, step=0.1, format="%.1f",
                        key=f"ast_uln_{selected_patient_id}_{form_version}",
                    )
                with lab_right:
                    urine_protein_creatinine_ratio = st.number_input(
                        "Urine protein-to-creatinine ratio (mg/mmol)",
                        min_value=0.0, value=None, step=0.1, format="%.1f",
                        key=f"pcr_{selected_patient_id}_{form_version}",
                    )
                    urine_albumin_creatinine_ratio = st.number_input(
                        "Urine albumin-to-creatinine ratio (mg/mmol)",
                        min_value=0.0, value=None, step=0.1, format="%.1f",
                        key=f"acr_{selected_patient_id}_{form_version}",
                    )
                    urine_output_ml = st.number_input(
                        "Urine output (mL)", min_value=0.0, value=None,
                        step=1.0, format="%.1f",
                        key=f"urine_output_{selected_patient_id}_{form_version}",
                    )
                    urine_output_period_hours = st.number_input(
                        "Urine output measurement period (hours)",
                        min_value=0.0, value=None, step=0.5, format="%.1f",
                        key=f"urine_output_period_{selected_patient_id}_{form_version}",
                    )
                visit_submitted = st.form_submit_button(
                    "Save Visit", type="primary"
                )

            if visit_submitted:
                if selected_patient is None:
                    st.error("Please select a registered patient.")
                elif not isinstance(visit_date, date):
                    st.error("Please select a valid visit date.")
                elif visit_date > date.today():
                    st.error("Visit date cannot be in the future.")
                elif gestational_age_weeks is None:
                    st.error("Please enter gestational age in completed weeks.")
                elif not 1 <= gestational_age_weeks <= 45:
                    st.error("Gestational age must be between 1 and 45 completed weeks.")
                elif systolic_bp is None:
                    st.error("Please enter the systolic blood pressure.")
                elif diastolic_bp is None:
                    st.error("Please enter the diastolic blood pressure.")
                elif systolic_bp <= 0 or diastolic_bp <= 0:
                    st.error("Please enter both blood pressure readings as positive whole numbers.")
                elif systolic_bp <= diastolic_bp:
                    st.error(
                        "Systolic blood pressure must be greater than diastolic "
                        "blood pressure. This visit was not saved."
                    )
                elif urine_protein not in URINE_PROTEIN_VALUES:
                    st.error("Select a valid urine protein option.")
                elif platelet_count is not None and not float(platelet_count).is_integer():
                    st.error("Platelet count must be a whole number.")
                elif (other_symptoms_selected and not other_symptoms.strip()):
                    st.error("Please describe the other symptoms you selected.")
                else:
                    try:
                        maternal_warning_signs = [
                            code
                            for code, selected in (
                                ("headache", headache_present),
                                ("visual_disturbance", visual_disturbance),
                                ("epigastric_pain", epigastric_pain),
                                ("nausea_vomiting", nausea_vomiting),
                                ("difficulty_breathing", difficulty_breathing),
                                ("reduced_urine_output", reduced_urine_output),
                                ("seizure", seizure),
                                ("other_symptoms", other_symptoms_selected),
                            )
                            if selected
                        ]
                        visit_id = add_antenatal_visit(
                            patient_id=selected_patient_id,
                            visit_date=visit_date,
                            gestational_age_weeks=int(gestational_age_weeks),
                            systolic_bp=int(systolic_bp),
                            diastolic_bp=int(diastolic_bp),
                            urine_protein=urine_protein,
                            notes=notes.strip() or None,
                            maternal_warning_signs=maternal_warning_signs,
                            other_symptoms=other_symptoms.strip() or None,
                            platelet_count=int(platelet_count) if platelet_count is not None else None,
                            serum_creatinine=serum_creatinine,
                            alt_value=alt_value,
                            alt_upper_limit=alt_upper_limit,
                            ast_value=ast_value,
                            ast_upper_limit=ast_upper_limit,
                            urine_protein_creatinine_ratio=urine_protein_creatinine_ratio,
                            urine_albumin_creatinine_ratio=urine_albumin_creatinine_ratio,
                            urine_output_ml=urine_output_ml,
                            urine_output_period_hours=urine_output_period_hours,
                        )
                        st.session_state["last_saved_visit"] = {
                            "visit_id": visit_id,
                            "patient_id": selected_patient_id,
                        }
                        st.session_state["visit_form_version"] = form_version + 1
                        st.rerun()
                    except ValueError as error:
                        st.error(str(error))
                    except RuntimeError:
                        st.error("The visit could not be saved. Please review the entries and try again shortly.")

else:
    st.title(page)
    st.info("Coming soon. This section is not available yet.")
