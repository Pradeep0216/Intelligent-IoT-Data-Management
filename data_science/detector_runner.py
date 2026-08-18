import pandas as pd

# NOTE: originally `from detectors.isolation_forest_detector import IsolationForestDetector`
# (Pradeep0216-patch-1). That module doesn't exist -- the real file is
# detectors/iforest_detector.py -- so a plain `import detector_runner` failed
# before run_detector() was ever reachable, blocking every code path in the
# runner. Fixed here to wire the runner up to the real detector module as
# part of bringing the full validator -> runner -> detector -> evaluator ->
# report pipeline together for data_science/tests/test_full_pipeline.py.
from detectors.iforest_detector import IsolationForestDetector


def run_detector(detector_name, dataframe, parameters=None):

    if parameters is None:
        parameters = {}

    detector_name = detector_name.lower()

    if detector_name == "isolationforest":

        detector = IsolationForestDetector(**parameters)

    else:
        return {
            "status": "failed",
            "error": f"Detector '{detector_name}' is not supported"
        }

    try:

        result = detector.detect(dataframe)

        return {
            "status": "success",
            "model_name": result["model_name"],
            "anomaly_flag": result["anomaly_flag"],
            "score": result["score"],
            "timestamp": result["timestamp"],
            "runtime": result["runtime"]
        }

    except Exception as e:

        return {
            "status": "failed",
            "model_name": detector_name,
            "error": str(e)
        }
