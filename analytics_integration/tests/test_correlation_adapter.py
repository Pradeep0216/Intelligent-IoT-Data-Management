import unittest
from analytics_integration.adapters.correlation_adapter import adapt_correlation_response

class TestCorrelationAdapter(unittest.TestCase):

    def setUp(self):
        self.valid_context = {
            "method": "Rolling_Pearson_Correlation",
            "window_size": 30,
            "step_size": 5
        }

    def test_uses_alerts_array_not_changes(self):
        raw_payload = {
            "summary": {"total_windows_evaluated": 5},
            "changes": [
                {"metric_a": "temp", "metric_b": "press", "delta": 0.05, "alert_level": None}
            ],
            "alerts": [
                {
                    "metric_a": "temp",
                    "metric_b": "press",
                    "delta": 0.85,
                    "alert_level": "HIGH",
                    "timestamp": "2026-08-05T08:25:00Z"
                }
            ]
        }
        res = adapt_correlation_response(raw_payload, self.valid_context)
        self.assertEqual(res["status"], "success")
        self.assertEqual(len(res["alerts"]), 1)
        self.assertEqual(res["alerts"][0]["score"], 0.85)
        self.assertEqual(res["alerts"][0]["severity"], "HIGH")

    def test_service_error_handling(self):
        raw_error_payload = {"error": "Invalid time-series matrix length"}
        res = adapt_correlation_response(raw_error_payload, self.valid_context)
        self.assertEqual(res["status"], "error")
        self.assertEqual(len(res["errors"]), 1)
        self.assertEqual(res["errors"][0]["code"], "CORRELATION_SERVICE_ERROR")
        self.assertIn("Invalid time-series", res["errors"][0]["message"])

    def test_service_status_error_handling(self):
        raw_error_payload = {"status": "error", "message": "CSV parsing failure on Port 5001"}
        res = adapt_correlation_response(raw_error_payload, self.valid_context)
        self.assertEqual(res["status"], "error")
        self.assertEqual(res["errors"][0]["message"], "CSV parsing failure on Port 5001")

    def test_missing_context_error(self):
        raw_payload = {"alerts": []}
        res = adapt_correlation_response(raw_payload, None)
        self.assertEqual(res["status"], "error")
        self.assertEqual(res["errors"][0]["code"], "MISSING_REQUEST_CONTEXT")

if __name__ == "__main__":
    unittest.main()