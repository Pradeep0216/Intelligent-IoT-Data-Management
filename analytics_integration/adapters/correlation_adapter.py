from datetime import datetime, timezone
from typing import Dict, Any, List, Optional


def adapt_correlation_response(
    raw_response: Dict[str, Any], 
    request_context: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Adapts raw Correlation output into the Draft V0.1 Shared Analytics Alert Contract.
    
    Args:
        raw_response: Dict containing raw correlation payload (e.g. from Port 5001).
        request_context: Dict containing request configuration like method, window_size, step_size.
    
    Returns:
        Dict following the Draft V0.1 shared response envelope structure.
    """
    # 1. Capture current execution time in ISO 8601 UTC for generated_at
    now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    
    # Base outer response structure (Draft V0.1)
    response_envelope = {
        "status": "success",
        "generated_at": now_iso,
        "alerts": [],
        "summary": {
            "processed_items": 0,
            "alert_count": 0
        },
        "errors": []
    }

    # 2. Strict Request Context Validation
    if not request_context:
        response_envelope["status"] = "error"
        response_envelope["errors"].append({
            "code": "MISSING_REQUEST_CONTEXT",
            "field": "request_context",
            "message": "request_context is required and must contain method, window_size, and step_size."
        })
        return response_envelope

    required_context_keys = ["method", "window_size", "step_size"]
    missing_context = [k for k in required_context_keys if k not in request_context]
    if missing_context:
        response_envelope["status"] = "error"
        response_envelope["errors"].append({
            "code": "INVALID_REQUEST_CONTEXT",
            "field": "request_context",
            "message": f"Missing required request context keys: {', '.join(missing_context)}"
        })
        return response_envelope

    # 3. Handle Raw Response Validation
    if not isinstance(raw_response, dict):
        response_envelope["status"] = "error"
        response_envelope["errors"].append({
            "code": "INVALID_RAW_RESPONSE",
            "field": "raw_response",
            "message": "raw_response must be a dictionary object."
        })
        return response_envelope

    # Extract correlation items/alerts list from raw response
    raw_alerts = raw_response.get("changes", raw_response.get("alerts", []))
    
    if not isinstance(raw_alerts, list):
        response_envelope["status"] = "error"
        response_envelope["errors"].append({
            "code": "INVALID_ALERTS_TYPE",
            "field": "alerts",
            "message": "Raw alerts or changes must be a list."
        })
        return response_envelope

    response_envelope["summary"]["processed_items"] = len(raw_alerts)

    # 4. Process and Map Each Correlation Alert
    adapted_alerts = []
    
    for idx, raw_alert in enumerate(raw_alerts):
        # Validate essential raw fields without using dangerous fallbacks/defaults
        stream_1 = raw_alert.get("stream_1")
        stream_2 = raw_alert.get("stream_2")
        delta = raw_alert.get("delta")
        end_time = raw_alert.get("end_time")

        if not stream_1 or not stream_2 or delta is None or not end_time:
            response_envelope["status"] = "error"
            response_envelope["errors"].append({
                "code": "MISSING_REQUIRED_ALERT_FIELD",
                "field": f"alerts[{idx}]",
                "message": f"Alert at index {idx} missing required fields (stream_1, stream_2, delta, or end_time)."
            })
            return response_envelope

        # Map to Draft V0.1 Alert structure
        alert_obj = {
            "timestamp": end_time,  # Event timestamp from raw window end time
            "alert_type": "CORRELATION_CHANGE",
            "target": {
                "entity_id": None,
                "metrics": [stream_1, stream_2]
            },
            "method": request_context.get("method", "Rolling_Pearson_Correlation"),
            "score": delta,
            "score_metadata": {
                "type": "absolute_correlation_delta",
                "normalized": False
            },
            "severity": raw_alert.get("alert_level", "HIGH"),
            "message": raw_alert.get(
                "reason", 
                f"Correlation between {stream_1} and {stream_2} changed by {delta}."
            ),
            "time_window": {
                "start": raw_alert.get("start_time"),
                "end": end_time,
                "window_size": request_context["window_size"],
                "step_size": request_context["step_size"]
            },
            "supporting_values": {
                "previous_correlation": raw_alert.get("previous_corr"),
                "current_correlation": raw_alert.get("current_corr"),
                "delta": delta,
                "window_index": raw_alert.get("window_index")
            },
            "source": {
                "component": "correlation"
            },
            "alert_id": None
        }
        
        adapted_alerts.append(alert_obj)

    # 5. Finalize Envelope
    response_envelope["alerts"] = adapted_alerts
    response_envelope["summary"]["alert_count"] = len(adapted_alerts)
    
    return response_envelope