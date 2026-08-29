import pandas as pd

from detector_runner import run_detector


df = pd.read_csv(
    "datasets/complex.csv",
    index_col=0
)


result = run_detector(
    detector_name="isolationforest",
    dataframe=df,
    parameters={
        "n_estimators": 100,
        "contamination": 0.05
    }
)


print(result)
