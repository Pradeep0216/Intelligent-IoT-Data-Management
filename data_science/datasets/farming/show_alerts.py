"""Shows exactly what the detector caught for the farming dataset, in
human-readable form (not just the summary counts).

Run from anywhere:

    python data_science/datasets/farming/show_alerts.py
"""
# Importing quick_check (in this same folder) also sets up sys.path so
# analytics_integration is importable, regardless of the current directory.
from quick_check import load_clean_data
from analytics_integration.pipeline import run_analytics_pipeline


def main():
    data = load_clean_data()
    response = run_analytics_pipeline(
        df=data,
        timestamp_col="timestamp",
        entity_id="greenhouse_ch80502",
        model_metric="temp_c",
        correlation_streams=["temp_c", "humidity_pct"],
        detector_name="isolationforest",
        detector_parameters={"contamination": 0.05},
        correlation_window_size=20,
        correlation_step_size=10,
        correlation_method="pearson",
    )
    alerts = response["alerts"]
    point_alerts = [a for a in alerts if a["alert_type"] == "POINTWISE_ANOMALY"]
    corr_alerts = [a for a in alerts if a["alert_type"] == "CORRELATION_CHANGE"]

    print(f"Total alerts: {len(alerts)} ({len(point_alerts)} point anomalies, "
          f"{len(corr_alerts)} correlation-change alerts)\n")

    print("Top 10 point anomalies by score (highest = most anomalous):")
    for a in sorted(point_alerts, key=lambda a: a["score"], reverse=True)[:10]:
        v = a["supporting_values"]["sensor_value"]
        print(f"  {a['timestamp']}  temp_c={v:>5}  score={a['score']:.4f}")

    print("\nTop 10 correlation-change alerts by severity/score:")
    sev_rank = {"HIGH": 2, "MEDIUM": 1, "LOW": 0, None: -1}
    top_corr = sorted(corr_alerts, key=lambda a: (sev_rank[a["severity"]], a["score"]), reverse=True)[:10]
    for a in top_corr:
        sv = a["supporting_values"]
        print(f"  {a['timestamp']}  severity={a['severity']:<6}  "
              f"{sv['previous_correlation']:+.2f} -> {sv['current_correlation']:+.2f}")

    print("\nThat's a sample. Every alert has this much detail; see run_analytics_pipeline's "
          "full return value (response['alerts']) for all of it.")


if __name__ == "__main__":
    main()
