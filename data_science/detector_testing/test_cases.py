import numpy as np
import pandas as pd


def normal_data():
    return pd.DataFrame({
        "sensor": [10, 11, 10, 12, 11, 10, 12, 11, 10, 11]
    })


def obvious_anomalies():
    return pd.DataFrame({
        "sensor": [10, 11, 10, 12, 11, 500, 10, 11, -400, 10]
    })


def no_anomalies():
    return pd.DataFrame({
        "sensor": [10, 10, 10, 10, 10, 10, 10, 10, 10, 10]
    })


def too_few_readings():
    return pd.DataFrame({
        "sensor": [10, 11]
    })


def missing_values():
    return pd.DataFrame({
        "sensor": [10, 11, np.nan, 12, 13, 11]
    })


def invalid_values():
    return pd.DataFrame({
        "sensor": [10, 11, "invalid", 12, 13]
    })


def different_sensor_scales():
    return pd.DataFrame({
        "temperature": [20, 21, 20, 22, 21, 20, 23, 21],
        "pressure": [100000, 100200, 99900, 100100, 100300, 100000, 100400, 100100]
    })


def configuration_data():
    return pd.DataFrame({
        "sensor": [
            10, 11, 10, 12, 11,
            10, 12, 11, 10, 11,
            500, -400
        ]
    })
