import sys
import os
import unittest

# Ensure root repository folder is in Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from analytics_integration.adapters.correlation_adapter import adapt_correlation_response


class TestCorrelationAdapter(unittest.TestCase):

    def setUp(self):
        self.request_context = {
            "method": "Rolling_Pearson_Correlation",
            "window_size": 30,
            "step_size": 5
        }

    def test_valid_response_with_alerts(self):
        raw_payload = {
            "changes": [
                {
                    "stream_1": "temperature",
                    "stream_2": "pressure",
                    "alert_level": "HIGH",
                    "reason": "Correlation between temperature and pressure changed by 0.79.",
                    "previous_corr": 0.91,
                    "current_corr": 0.12,
                    "delta": 0.79,
                    "window_index": 4,
                    "start_time": "2026-08-05T08:20:00Z",
                    "end_time": "2026-08-05T08:25:00Z"
                }
            ]
        }
        
        res = adapt_correlation_response(raw_payload, request_context=self.request_context)
        
        self.assertEqual(res["status"], "success")
        self.assertEqual(res["summary"]["alert_count"], 1)
        self.assertEqual(len(res["errors"]), 0)
        
        alert = res["alerts"][0]
        self.assertEqual(alert["alert_type"], "CORRELATION_CHANGE")
        self.assertEqual(alert["timestamp"], "2026-08-05T08:25:00Z")  # Event timestamp (window end)
        self.assertEqual(alert["target"]["metrics"], ["temperature", "pressure"])
        self.assertEqual(alert["score"], 0.79)
        self.assertEqual(alert["time_window"]["window_size"], 30)

    def test_successful_response_with_no_alerts(self):
        raw_payload = {"changes": []}
        res = adapt_correlation_response(raw_payload, request_context=self.request_context)
        
        self.assertEqual(res["status"], "success")
        self.assertEqual(res["summary"]["processed_items"], 0)
        self.assertEqual(res["summary"]["alert_count"], 0)
        self.assertEqual(res["alerts"], [])
        self.assertEqual(res["errors"], [])

    def test_missing_request_context(self):
        raw_payload = {"changes": []}
        res = adapt_correlation_response(raw_payload, request_context=None)
        
        self.assertEqual(res["status"], "error")
        self.assertTrue(len(res["errors"]) > 0)
        self.assertEqual(res["errors"][0]["code"], "MISSING_REQUEST_CONTEXT")

    def test_missing_required_alert_fields(self):
        raw_payload = {
            "changes": [
                {
                    "stream_1": "temperature",
                    # missing stream_2, delta, end_time
                }
            ]
        }
        res = adapt_correlation_response(raw_payload, request_context=self.request_context)
        
        self.assertEqual(res["status"], "error")
        self.assertEqual(res["errors"][0]["code"], "MISSING_REQUIRED_ALERT_FIELD")


if __name__ == "__main__":
    unittest.main()