"""CCA116 evidence runner: one full pipeline run over the shared datasets.

Produces every number the task asks for, runtime, alert count, false positive
review and a sample alert payload, into docs/evidence/CCA116_tommy/.
Nothing is typed in by hand.

    cd correlation_alert && python testing/run_shared_datasets.py
"""

import json
import os
import sys
import time
from collections import Counter

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from main import detect_correlation_change_alert, to_iso8601  # noqa: E402

SERVICE_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(os.path.dirname(SERVICE_ROOT), "datasets", "nab_realtraffic")
EVIDENCE_DIR = os.path.join(SERVICE_ROOT, "docs", "evidence", "CCA116_tommy")

WINDOW, STEP, METHOD = 30, 5, "pearson"
TRAFFIC = ["occupancy_t4013", "speed_t4013", "occupancy_6005", "speed_6005"]
AWS = ["ec2_cpu", "ec2_net", "elb_req"]

lines = []


def out(text=""):
    lines.append(text)
    print(text)


def run(filename, streams):
    df = pd.read_csv(os.path.join(DATA_DIR, filename))
    start = time.perf_counter()
    result = detect_correlation_change_alert(
        df, "timestamp", streams, window_size=WINDOW, step_size=STEP, method=METHOD
    )
    result["runtime"] = time.perf_counter() - start
    result["rate"] = len(result["alerts"]) / max(1, len(result["changes"]))
    return result


def report(name, r):
    out(f"{name}")
    out(f"  rows kept        {len(r['processed_data'])}")
    out(f"  windows          {len(r['windows'])}")
    out(f"  comparisons      {len(r['changes'])}")
    out(f"  alerts           {len(r['alerts'])}")
    out(f"  alerts/comparison{r['rate']:.4f}")
    out(f"  by severity      {dict(Counter(a['alert_level'] for a in r['alerts']))}")
    out(f"  runtime          {r['runtime']:.3f} s")
    out()


def main():
    os.makedirs(EVIDENCE_DIR, exist_ok=True)

    out("CCA116, correlation pipeline run over the shared datasets")
    out("=" * 68)
    out(f"Generated {to_iso8601(pd.Timestamp.now(tz='UTC'))}")
    out(f"pandas {pd.__version__}, numpy {np.__version__}")
    out(f"window_size={WINDOW}, step_size={STEP}, method={METHOD}")
    out()

    primary = run("traffic_4stream_merged.csv", TRAFFIC)
    control = run("aws_control_merged.csv", AWS)

    report("traffic_4stream_merged.csv, primary", primary)
    report("aws_control_merged.csv, negative control", control)

    out("False positive review")
    out("-" * 68)
    out(f"  real data          {primary['rate']:.2%}")
    out(f"  independent data   {control['rate']:.2%}")
    out(f"  ratio              {primary['rate'] / control['rate']:.2f}x")
    out(f"  HIGH on independent data {Counter(a['alert_level'] for a in control['alerts'])['HIGH']}")
    out(f"  HIGH on real data        {Counter(a['alert_level'] for a in primary['alerts'])['HIGH']}")
    out()
    out("  The AWS streams are independent, so the correct answer there is close")
    out("  to zero. The pipeline fires almost as often on noise as on real data,")
    out("  and only the noise produces HIGH alerts. The alert logic barely")
    out("  separates signal from noise. Belongs to CCA113.")
    out()

    # Outlier removal against the ground truth labels
    raw = pd.read_csv(
        os.path.join(DATA_DIR, "traffic_4stream_merged.csv"), parse_dates=["timestamp"]
    )
    labels = json.load(open(os.path.join(DATA_DIR, "labels_subset.json")))
    anomaly = pd.Series(False, index=raw.index)
    for key, windows in labels.items():
        if "realTraffic" in key:
            for begin, end in windows:
                anomaly |= raw["timestamp"].between(pd.Timestamp(begin), pd.Timestamp(end))

    out("Outlier removal against NAB ground truth")
    out("-" * 68)
    out(f"  labelled anomaly rows {int(anomaly.sum())} of {len(raw)}")
    removed = labelled = 0
    for col in TRAFFIC:
        q1, q3 = raw[col].quantile(0.25), raw[col].quantile(0.75)
        flagged = ~raw[col].between(q1 - 3 * (q3 - q1), q3 + 3 * (q3 - q1))
        removed += int(flagged.sum())
        labelled += int((flagged & anomaly).sum())
        out(f"  {col:18s} removed {int(flagged.sum()):3d}, labelled {int((flagged & anomaly).sum()):3d}")
    out(f"  total removed {removed}, labelled {labelled} ({labelled / removed:.0%})")

    before = raw["occupancy_t4013"].corr(raw["speed_t4013"])
    after = primary["processed_data"]["occupancy_t4013"].corr(
        primary["processed_data"]["speed_t4013"]
    )
    out(f"  global Pearson, primary pair: {before:.4f} before, {after:.4f} after")
    out()
    out("  remove_outliers uses an IQR factor of 3.0 and deletes mostly the")
    out("  labelled anomalies, halving the measured strength of the primary")
    out("  pair. Preprocessing is removing the events the service exists to")
    out("  detect. No accuracy number can be trusted until this is settled.")
    out()

    # The sample must be exactly what the API puts on the wire. It used to add
    # method, window_size and step_size, which the alert object does not carry
    # in Contract v1 sections 6 and 12, and it formatted the timestamps by hand
    # instead of going through the shared serialiser.
    alert = primary["alerts"][0]
    sample = {
        key: to_iso8601(value) if key in ("start_time", "end_time") else value
        for key, value in alert.items()
    }
    with open(os.path.join(EVIDENCE_DIR, "sample_alert_contract_v1.json"), "w") as f:
        json.dump(sample, f, indent=2)

    out("Sample alert, Contract v1 shape")
    out("-" * 68)
    out(json.dumps(sample, indent=2))

    with open(os.path.join(EVIDENCE_DIR, "shared_datasets_run.txt"), "w") as f:
        f.write("\n".join(lines) + "\n")


if __name__ == "__main__":
    main()
