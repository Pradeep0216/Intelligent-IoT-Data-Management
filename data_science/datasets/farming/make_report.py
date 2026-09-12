"""Builds the stakeholder PDF report for the Smart Farming Models/AIntl
evaluation from outputs/task2_results.json and outputs/*.png.

Run from data_science/datasets/farming/.
"""
import json
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Image, Table, TableStyle,
    ListFlowable, ListItem, PageBreak, HRFlowable, KeepTogether,
)
from reportlab.lib.enums import TA_LEFT

OUT_DIR = Path("outputs")
RESULTS = json.load(open(OUT_DIR / "task2_results.json"))
PDF_PATH = "Smart_Farming_Models_AIntl_Evaluation_Report.pdf"

styles = getSampleStyleSheet()
styles.add(ParagraphStyle(name="H1c", parent=styles["Heading1"], fontSize=18, spaceAfter=10, textColor=colors.HexColor("#1b4332")))
styles.add(ParagraphStyle(name="H2c", parent=styles["Heading2"], fontSize=13, spaceBefore=14, spaceAfter=6, textColor=colors.HexColor("#2d6a4f")))
styles.add(ParagraphStyle(name="H3c", parent=styles["Heading3"], fontSize=11, spaceBefore=8, spaceAfter=4, textColor=colors.HexColor("#40916c")))
styles.add(ParagraphStyle(name="Body", parent=styles["BodyText"], fontSize=9.7, leading=14, alignment=TA_LEFT, spaceAfter=6))
styles.add(ParagraphStyle(name="Meta", parent=styles["BodyText"], fontSize=9, textColor=colors.grey))
styles.add(ParagraphStyle(name="Caption", parent=styles["BodyText"], fontSize=8.3, textColor=colors.grey, alignment=1, spaceAfter=12))

story = []

def h1(t): story.append(Paragraph(t, styles["H1c"]))
def h2(t): story.append(Paragraph(t, styles["H2c"]))
def h3(t): story.append(Paragraph(t, styles["H3c"]))
def p(t): story.append(Paragraph(t, styles["Body"]))
def bullets(items):
    story.append(ListFlowable([ListItem(Paragraph(i, styles["Body"])) for i in items],
                               bulletType="bullet", leftIndent=14, spaceBefore=2, spaceAfter=8))
def rule():
    story.append(HRFlowable(width="100%", thickness=0.6, color=colors.HexColor("#cccccc"), spaceBefore=4, spaceAfter=10))
def fig(path, caption, width=15*cm):
    from PIL import Image as PILImage
    iw, ih = PILImage.open(path).size
    h = width * ih / iw
    story.append(KeepTogether([Image(path, width=width, height=h), Paragraph(caption, styles["Caption"])]))

# ---------------------------------------------------------------- Title
story.append(Paragraph("Smart Farming (ThingSpeak Channel 80502)", styles["H1c"]))
story.append(Paragraph("Models / AIntl Pipeline Evaluation: Task 2 Report", styles["H2c"]))
story.append(Paragraph(
    "Branch: <b>kim/report/farming</b> (experiment only, not merged into <b>main</b>) &nbsp;|&nbsp; "
    "Location: <b>data_science/datasets/farming/</b>", styles["Meta"]))
rule()

# ---------------------------------------------------------------- Summary
h2("Executive Summary")
p("This report evaluates how the current Models/AIntl pipeline "
  "(<i>Dataset -&gt; Models input validation -&gt; Isolation Forest runtime -&gt; Models adapter -&gt; "
  "Correlation path -&gt; Correlation adapter -&gt; Analytics response -&gt; Draft V0.1 validation</i>) "
  "behaves against a real, independently-sourced IoT dataset: a public ThingSpeak greenhouse "
  "climate-monitoring channel. No changes were made to the Models, Correlation, or AIntl "
  "implementation code; this is a behavioural evaluation of the pipeline as it stands.")
bullets([
    f"<b>{RESULTS['n_rows']:,} readings</b> processed end-to-end through the full AIntl pipeline in "
    f"<b>{RESULTS['full_pipeline_wall_time_s']:.2f}s</b>, producing a Draft-V0.1-validated response with "
    f"<b>{RESULTS['full_pipeline_alert_count']} alerts</b> "
    f"({RESULTS['full_pipeline_alert_types'].get('POINTWISE_ANOMALY',0)} point anomalies, "
    f"{RESULTS['full_pipeline_alert_types'].get('CORRELATION_CHANGE',0)} correlation-change alerts).",
    f"Isolation Forest flagged <b>{RESULTS['n_anomalies']} of {RESULTS['n_rows']:,} readings "
    f"({RESULTS['anomaly_pct']:.2f}%)</b> as anomalous on the air-temperature channel. Flags were "
    "concentrated on real, one-off excursions (a multi-hour heat spike and a separate cold dip), "
    "not the recurring day/night cycle, and were <b>100% deterministic</b> across repeated runs.",
    "The Correlation module produced a real but <b>unexpected</b> contrast: the deliberately weaker "
    f"pairing (<code>temp_c</code> vs <code>co2_ppm</code>, {RESULTS['corr_alerts_temp_co2']} alerts) "
    f"triggered <b>more</b> alerts than the genuinely physically-linked pairing "
    f"(<code>temp_c</code> vs <code>humidity_pct</code>, {RESULTS['corr_alerts_temp_humidity']} alerts), "
    "because a near-constant, floored channel makes rolling Pearson correlation numerically unstable, "
    "a failure mode the module does not currently distinguish from a genuine relationship change.",
    "This dataset has <b>no ground-truth anomaly labels</b>; per the evaluation brief, no precision/"
    "recall/F1/AUC is reported. Evaluation instead relies on independent statistical cross-checks, "
    "determinism, and domain plausibility, detailed below.",
])

# ---------------------------------------------------------------- Source
h2("Dataset Source and Provenance")
bullets([
    "<b>Source:</b> ThingSpeak public channel 80502 (MathWorks ThingSpeak IoT platform), "
    "https://thingspeak.com/channels/80502, retrieved via the public feeds.csv endpoint, no API key required.",
    "<b>What it is:</b> greenhouse climate-computer readings logged roughly once a minute: air temperature, "
    "a second temperature probe, relative humidity, and CO2, plus four derived psychrometric quantities "
    "(wet-bulb temperature, absolute humidity, dew point, humidity deficit).",
    "<b>Coverage:</b> 27 June to 12 October 2019, arriving as three disjoint export blocks separated by two "
    "multi-week outages (47 and 55 days).",
    "<b>Field identification (Task 1):</b> ThingSpeak exports only <code>field1..field8</code> with no labels. "
    "The mapping used here was derived from the data itself and verified numerically by recomputing published "
    "psychrometric formulas from <code>temp_c</code>/<code>humidity_pct</code> and matching them to the file "
    "(errors at the 0.1 rounding resolution of the source data). This confirmed 4 of the 8 fields "
    "(<code>wet_bulb_c</code>, <code>abs_humidity_gm3</code>, <code>dew_point_c</code>, "
    "<code>humidity_deficit_gm3</code>) are deterministic functions of temperature and humidity, not "
    "independent sensor readings, and they were excluded from correlation analysis on that basis.",
])
h3("Transformations applied before the pipeline run")
bullets([
    "Renamed <code>field1..field8</code> to their identified names.",
    "Removed 22 rows (0.29% of the file) where every field reports a fixed error-code sentinel "
    "(<code>99.9</code> / <code>455</code> / <code>9999</code> / <code>0.0</code>) instead of a real reading.",
    "Selected the single longest continuous export block (7-12 Oct 2019, 7,261 rows at ~60s cadence) as the "
    "working series, to avoid two multi-week outages sitting inside rolling correlation windows.",
    "Formatted <code>created_at</code> as an ISO-8601 string, the format <code>analytics_integration.pipeline</code> expects.",
    "No imputation, resampling, or scaling was required beyond this.",
])
h3("Variable choice")
bullets([
    "<b>Models anomaly-detection metric:</b> <code>temp_c</code> (air temperature).",
    "<b>Correlation pair A (primary):</b> <code>temp_c</code> vs <code>humidity_pct</code>, physically forced "
    "to move in opposite directions (warmer air holds more moisture), giving a known-sign relationship to test.",
    "<b>Correlation pair B (contrast):</b> <code>temp_c</code> vs <code>co2_ppm</code>, deliberately weaker, "
    "since the CO2 channel sits at its ~400ppm outdoor-baseline floor for most of the record.",
])

story.append(PageBreak())

# ---------------------------------------------------------------- Methodology
h2("Methodology")
p("The pipeline was run exactly as implemented in <code>analytics_integration.pipeline."
  "run_analytics_pipeline</code>, calling in turn the Models path (input validator -&gt; "
  "<code>IsolationForestDetector</code> -&gt; Models adapter) and the Correlation path (Correlation Flask "
  "service -&gt; Correlation adapter), before both are combined into a single envelope and checked against "
  "the Draft V0.1 response contract. Configuration used throughout:")
cfg = [["Parameter", "Value"], ["entity_id", "greenhouse_ch80502"], ["model_metric", "temp_c"],
       ["correlation_streams", "[temp_c, humidity_pct] and [temp_c, co2_ppm]"],
       ["detector_name", "isolationforest"], ["detector_parameters", "{contamination: 0.05}"],
       ["correlation_window_size / step_size", "20 / 10"], ["correlation_method", "pearson"]]
t = Table(cfg, colWidths=[6.5*cm, 9.5*cm])
t.setStyle(TableStyle([
    ("BACKGROUND", (0,0), (-1,0), colors.HexColor("#2d6a4f")),
    ("TEXTCOLOR", (0,0), (-1,0), colors.white),
    ("FONTSIZE", (0,0), (-1,-1), 9),
    ("GRID", (0,0), (-1,-1), 0.4, colors.HexColor("#cccccc")),
    ("ROWBACKGROUNDS", (0,1), (-1,-1), [colors.white, colors.HexColor("#f4f4f4")]),
    ("VALIGN", (0,0), (-1,-1), "MIDDLE"),
    ("TOPPADDING", (0,0), (-1,-1), 4), ("BOTTOMPADDING", (0,0), (-1,-1), 4),
]))
story.append(t)
story.append(Spacer(1, 10))

# ---------------------------------------------------------------- Data integrity
h2("Data Integrity / EDA")
bullets([
    "7,488 raw readings x 10 columns (<code>created_at</code>, <code>entry_id</code>, <code>field1..field8</code>); "
    "all sensor fields numeric (float64).",
    "Zero duplicate rows, zero duplicate timestamps, zero <code>NaN</code> values anywhere in the raw file.",
    "That apparent cleanliness is misleading: 22 rows (0.29%) encode sensor failure as fixed error-code "
    "<i>values</i>, not <code>NaN</code>, invisible to any missing-value check.",
    "<code>co2_ppm</code> is heavily right-skewed with a hard floor at ~400ppm; <code>temp_c</code>/<code>temp2_c</code> "
    "are roughly bell-shaped; <code>humidity_pct</code> is wider and slightly left-skewed.",
])
fig(str(OUT_DIR / "eda_distributions.png"),
    "Figure 1: Distributions of the 4 independent sensor channels (fault rows excluded).")

# ---------------------------------------------------------------- Validator evidence
h2("Evidence: What the Input Validator Actually Catches")
p("Three checks were run against the unmodified pipeline:")
bullets([
    "<b>Missing field mapping</b> -&gt; correctly rejected. Calling the pipeline with <code>model_metric=\"temp_c\"</code> "
    "against the raw, unmapped file (which only has <code>field1..field8</code>) raises "
    "<code>ValueError: Input data is missing required columns</code>.",
    "<b>Duplicate timestamps / NaN sensor values</b> -&gt; correctly rejected, exactly as documented, with clear "
    "<code>InputValidationError</code> messages.",
    "<b>Fault-sentinel values (99.9 / 9999 / 455 / 0.0)</b> -&gt; <u>not</u> caught. These are valid, non-null "
    "floats, so the validator accepts them without complaint. The practical risk was limited on this run "
    "(the real fault block fell entirely in a block already excluded for other reasons), but a sentinel value "
    "chosen inside a sensor's normal operating range would pass through completely undetected. This is a gap "
    "in the validator's contract worth raising, not a defect introduced by this run.",
])

# ---------------------------------------------------------------- Models path
h2("Models Path: Isolation Forest on temp_c")
bullets([
    f"<b>{RESULTS['n_anomalies']} / {RESULTS['n_rows']:,} readings ({RESULTS['anomaly_pct']:.2f}%)</b> flagged, "
    f"in line with the configured 5% contamination.",
    f"Models runtime: <b>{RESULTS['models_runtime_s']*1000:.1f} ms</b> for the full 7,261-row series.",
    "Flags were concentrated on 4 of 5 calendar days, with 2 of 5 days (7 and 11 Oct) receiving <b>zero</b> "
    "flags and 241 of 357 flags falling on a single day (9 Oct). That day's cluster lines up with a real "
    "multi-hour temperature spike to 29.1°C; a second, smaller cluster on 10 Oct lines up with a separate "
    "cold dip to ~22.3-22.6°C (see Figure 2). A detector mistaking the recurring day/night cycle for anomalous "
    "would instead flag similar counts at the same hour on every day, which is not what happened.",
    f"<b>100%</b> of independently-identified top/bottom 0.5th-percentile <code>temp_c</code> readings were "
    "also flagged by the detector, and repeated runs were <b>bit-for-bit deterministic</b>.",
])
fig(str(OUT_DIR / "anomaly_timeseries.png"),
    "Figure 2: Air temperature with IsolationForest-flagged anomalies (7-12 Oct 2019). "
    "Flags cluster on the real heat spike (9 Oct) and cold dip (10 Oct), not the recurring daily cycle.")
fig(str(OUT_DIR / "anomaly_hour_of_day.png"),
    "Figure 3: Left, hour-of-day distribution of flagged anomalies vs all readings. Right, flagged "
    "anomalies by calendar date. 2 of 5 days received zero flags.")

# ---------------------------------------------------------------- Correlation path
h2("Correlation Path: Two Experiments")
bullets([
    f"<b>temp_c vs humidity_pct</b> (primary, physically-linked pair): <b>{RESULTS['corr_alerts_temp_humidity']} alerts</b> "
    f"({RESULTS['corr_severity_temp_humidity'].get('HIGH',0)} HIGH / "
    f"{RESULTS['corr_severity_temp_humidity'].get('MEDIUM',0)} MEDIUM / "
    f"{RESULTS['corr_severity_temp_humidity'].get('LOW',0)} LOW). Overall Pearson r = "
    f"{RESULTS['pearson_temp_humidity_overall']:.3f}, matching the expected negative sign.",
    f"<b>temp_c vs co2_ppm</b> (deliberately weaker pair): <b>{RESULTS['corr_alerts_temp_co2']} alerts</b> "
    f"({RESULTS['corr_severity_temp_co2'].get('HIGH',0)} HIGH / "
    f"{RESULTS['corr_severity_temp_co2'].get('MEDIUM',0)} MEDIUM / "
    f"{RESULTS['corr_severity_temp_co2'].get('LOW',0)} LOW).",
    "<b>This is the reverse of what was expected</b>: the weaker pair produced more alerts, and more "
    "severe ones. The mechanism: <code>co2_ppm</code> sits flat at its sensor floor for long stretches, so a "
    "20-reading window covering one of those stretches has almost no variance in that channel, so a few ppm of "
    "sensor jitter then dominates the Pearson coefficient, swinging it erratically between roughly +1 and -1. "
    "That is numerical instability from a near-constant channel, not a genuine drifting relationship, but the "
    "Correlation module currently reports both identically as <code>CORRELATION_CHANGE</code> alerts.",
])
fig(str(OUT_DIR / "correlation_rolling.png"),
    "Figure 4: Rolling correlation for both pairs. The co2 pairing (bottom) oscillates far more erratically "
    "than the humidity pairing (top), consistent with variance-floor instability rather than a real relationship.")
fig(str(OUT_DIR / "correlation_severity.png"),
    "Figure 5: CORRELATION_CHANGE severity breakdown. The weaker, floored pairing produced more HIGH-severity "
    "alerts than the genuinely physically-linked pairing.")

story.append(PageBreak())

# ---------------------------------------------------------------- Full pipeline + runtime
h2("Full AIntl Pipeline and Runtime")
bullets([
    f"The complete path (Models, Correlation, envelope building, and Draft V0.1 response validation) ran "
    f"end-to-end with no code changes and completed in <b>{RESULTS['full_pipeline_wall_time_s']:.2f}s</b> for "
    f"the full 7,261-row block, producing <b>{RESULTS['full_pipeline_alert_count']} total alerts</b> "
    f"({RESULTS['full_pipeline_alert_types'].get('POINTWISE_ANOMALY',0)} POINTWISE_ANOMALY, "
    f"{RESULTS['full_pipeline_alert_types'].get('CORRELATION_CHANGE',0)} CORRELATION_CHANGE).",
    "Runtime scaled close to linearly with row count from 300 to 7,261 rows, with no errors or warnings at "
    "any scale tested.",
])
fig(str(OUT_DIR / "runtime_scalability.png"),
    "Figure 6: AIntl pipeline wall-clock time vs. rows processed.")

# ---------------------------------------------------------------- Limitations
h2("Limitations")
bullets([
    "<b>No ground-truth labels</b>: no precision/recall/F1/AUC is reported; evaluation is qualitative "
    "(anomaly rate, timing plausibility, an independent statistical cross-check, determinism, and alert "
    "behaviour under two contrasting correlation pairs).",
    "<b>The input validator does not recognise domain-specific fault sentinels</b>, only literal "
    "<code>NaN</code>. A sentinel value inside a sensor's normal operating range would go undetected.",
    "<b>Neither the validator nor the correlation window is gap-aware</b>: a rolling window is defined by "
    "row count, not elapsed time, so it can silently straddle a real outage if that outage is not removed "
    "upstream by hand, as it was here.",
    "<b>The Correlation module cannot distinguish real drift from noise-driven instability</b> in a "
    "near-constant channel, as demonstrated directly by the co2 experiment above. A variance-floor guard "
    "would help, since floored/near-constant channels (a sensor at its detection limit, a valve permanently "
    "closed) are common in real IoT deployments.",
    "<b>temp2_c's physical location is undocumented</b> (soil, root zone, or elsewhere in the air).",
    "Single device, single 5-day working block; no cross-device or cross-season comparison possible.",
    "The Models path was exercised univariately (one channel at a time), not across multiple channels jointly.",
])

# ---------------------------------------------------------------- Conclusions
h2("Conclusions and Recommendations")
p("This experiment provides further evidence that the Models/AIntl MVP generalises beyond its original "
  "NAB-derived development data to a second, independently-sourced, real IoT deployment with a materially "
  "different character: a strong daily periodicity, a live (not synthetic) sensor fault, and a genuinely "
  "physically-linked pair of channels. Preprocessing required was light (fault-sentinel removal and block "
  "selection, no imputation), and the full pipeline completed in well under two seconds for the whole usable "
  "block.")
p("Recommended follow-ups, in priority order:")
bullets([
    "Add a variance-floor guard to the Correlation module so a near-constant channel does not generate "
    "high-severity alerts purely from numerical instability.",
    "Document the input validator's fault-sentinel blind spot as a known boundary (NaN-only) rather than an "
    "assumed one, for teams integrating ThingSpeak-style devices that encode faults as sentinel values.",
    "Consider gap-awareness (elapsed time, not row count) for the rolling-correlation window.",
    "Extend the Models path to multivariate anomaly detection across the independent channels together.",
])

story.append(Spacer(1, 16))
story.append(Paragraph(
    "Full reproducible analysis, code, and figures: <code>data_science/datasets/farming/notebook.ipynb</code> "
    "on branch <code>kim/report/farming</code>.", styles["Meta"]))

doc = SimpleDocTemplate(PDF_PATH, pagesize=A4,
                         leftMargin=1.8*cm, rightMargin=1.8*cm, topMargin=1.6*cm, bottomMargin=1.6*cm,
                         title="Smart Farming Models/AIntl Evaluation Report")
doc.build(story)
print("Wrote", PDF_PATH)
