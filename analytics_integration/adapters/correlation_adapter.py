from datetime import datetime, timezone

def adapt_correlation_response(raw_response: dict, request_context: dict = None) -> dict:
    if not isinstance(raw_response, dict):
        raise ValueError("raw_response must be a dictionary")
    
    # 1. Preserve Correlation service errors
    if "error" in raw_response or raw_response.get("status") == "error":
        error_msg = raw_response.get("error") or raw_response.get("message") or "Unknown correlation service error"
        return {
            "status": "error",
            "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "alerts": [],
            "summary": {
                "processed_items": 0,
                "alert_count": 0
            },
            "errors": [
                {
                    "code": "CORRELATION_SERVICE_ERROR",
                    "field": "service_response",
                    "message": error_msg
                }
            ]
        }

    # 2. Validate request context
    if request_context is None or not isinstance(request_context, dict):
        return {
            "status": "error",
            "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "alerts": [],
            "summary": {
                "processed_items": 0,
                "alert_count": 0
            },
            "errors": [
                {
                    "code": "MISSING_REQUEST_CONTEXT",
                    "field": "request_context",
                    "message": "request_context must be provided"
                }
            ]
        }

    method = request_context.get("method", "Rolling_Pearson_Correlation")
    window_size = request_context.get("window_size", 30)
    step_size = request_context.get("step_size", 5)

    adapted_alerts = []
    
    # 3. Use 'alerts' list as the source (ignoring normal 'changes')
    raw_alerts = raw_response.get("alerts", [])
    for item in raw_alerts:
        metric_a = item.get("metric_a") or item.get("stream_1", "unknown_a")
        metric_b = item.get("metric_b") or item.get("stream_2", "unknown_b")
        
        score_val = item.get("delta") or item.get("correlation_delta") or item.get("score")
        alert_level = item.get("alert_level") or item.get("severity")  # do not default to HIGH
        
        time_end = item.get("timestamp") or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

        alert_obj = {
            "timestamp": time_end,
            "alert_type": "CORRELATION_CHANGE",
            "target": {
                "entity_id": item.get("entity_id", None),
                "metrics": [metric_a, metric_b]
            },
            "method": method,
            "score": score_val,
            "score_metadata": {
                "type": "absolute_correlation_delta",
                "normalized": False
            },
            "severity": alert_level,
            "message": item.get("message", f"Correlation between {metric_a} and {metric_b} changed by {score_val}."),
            "time_window": {
                "start": item.get("window_start"),
                "end": time_end,
                "window_size": window_size,
                "step_size": step_size
            },
            "supporting_values": {
                "previous_correlation": item.get("previous_correlation"),
                "current_correlation": item.get("current_correlation"),
                "delta": score_val,
                "window_index": item.get("window_index")
            },
            "source": {
                "component": "correlation"
            },
            "alert_id": None
        }
        adapted_alerts.append(alert_obj)

    return {
        "status": "success",
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "alerts": adapted_alerts,
        "summary": {
            "processed_items": raw_response.get("summary", {}).get("total_windows_evaluated", len(raw_alerts)),
            "alert_count": len(adapted_alerts)
        },
        "errors": []
    }