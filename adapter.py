from datetime import datetime, timezone
from typing import Dict, Any, List

def adapt_correlation_alert_response(raw_response: Dict[str, Any]) -> Dict[str, Any]:
    """
    Translates raw output from Port 5001 /detect-correlation-alert endpoint 
    into standard API Contract V1.0 format.
    
    Task AI: 016 - Correlation Output Adapter
    """
    if not isinstance(raw_response, dict):
        raise ValueError("Input response must be a dictionary.")

    # Base Envelope Fields
    status = raw_response.get("status", "success")
    iso_timestamp = datetime.now(timezone.utc).isoformat()

    adapted_alerts: List[Dict[str, Any]] = []
    raw_alerts = raw_response.get("alerts", [])

    # Map Port 5001 Alert Objects to V1.0 Contract
    for alert in raw_alerts:
        stream_1 = alert.get("stream_1", "unknown_s1")
        stream_2 = alert.get("stream_2", "unknown_s2")
        alert_level = alert.get("alert_level", "INFO")
        
        adapted_item = {
            "timestamp": iso_timestamp,
            "source_port": 5001,
            "target_metric": f"{stream_1}_vs_{stream_2}",
            "value": alert.get("current_corr", 0.0),
            "status": alert_level,
            "supporting_values": {
                "stream_1": stream_1,
                "stream_2": stream_2,
                "previous_corr": alert.get("previous_corr"),
                "current_corr": alert.get("current_corr"),
                "delta": alert.get("delta"),
                "window_index": alert.get("window_index"),
                "start_time": alert.get("start_time"),
                "end_time": alert.get("end_time"),
                "reason": alert.get("reason", "Correlation change detected.")
            }
        }
        adapted_alerts.append(adapted_item)

    return {
        "status": status,
        "adapted_at": iso_timestamp,
        "summary": raw_response.get("summary", {}),
        "metrics": adapted_alerts
    }


if __name__ == "__main__":
    sample_raw_output = {
        "status": "success",
        "summary": {"alerts": 1, "changes": 5, "processed_rows": 100},
        "alerts": [
            {
                "alert_level": "HIGH",
                "stream_1": "s1",
                "stream_2": "s2",
                "previous_corr": -0.9466,
                "current_corr": 0.6852,
                "delta": 1.6319,
                "window_index": 15,
                "start_time": "2026-07-25 10:00:00",
                "end_time": "2026-07-25 10:05:00",
                "reason": "Correlation change exceeds threshold."
            }
        ]
    }

    import json
    print(json.dumps(adapt_correlation_alert_response(sample_raw_output), indent=2))