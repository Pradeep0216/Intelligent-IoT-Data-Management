import pandas as pd
import numpy as np
import os

OUT = "cca109_datasets"
os.makedirs(OUT, exist_ok=True)

n = 120
t = np.arange(n)
s1 = np.sin(t / 10) * 10 + 50
s2 = np.sin(t / 10 + 0.3) * 10 + 50
s3 = np.cos(t / 15) * 5 + 20

base = pd.DataFrame({
    "time": t,
    "s1": s1.round(4),
    "s2": s2.round(4),
    "s3": s3.round(4)
})

# 1 - Missing values in a sensor column
c1 = base.copy()
c1.loc[10:14, "s1"] = np.nan
c1.loc[40, "s2"] = np.nan
c1.loc[60:62, "s3"] = np.nan
c1.to_csv(f"{OUT}/case1_missing_values.csv", index=False)

# 2 - Two different timestamp formats in the same file
ts = pd.date_range("2026-01-01 00:00:00", periods=n, freq="min")
mixed = [x.strftime("%Y-%m-%d %H:%M:%S") for x in ts]
for i in range(30, 45):
    mixed[i] = ts[i].strftime("%d/%m/%Y %H:%M")
c2 = base.copy()
c2["time"] = mixed
c2.to_csv(f"{OUT}/case2_mixed_timestamps.csv", index=False)

# 3 - Renamed or missing columns
c3 = base.copy().rename(columns={"s3": "sensor_three"})
c3.to_csv(f"{OUT}/case3_renamed_column.csv", index=False)

# 4 - Duplicate rows / duplicate timestamps
c4 = pd.concat([base, base.iloc[20:25], base.iloc[50:53]])
c4 = c4.sort_values("time").reset_index(drop=True)
c4.to_csv(f"{OUT}/case4_duplicates.csv", index=False)

# 5 - Non-numeric values in a sensor column
c5 = base.copy().astype({"s1": object, "s2": object})
c5.loc[15, "s1"] = "N/A"
c5.loc[16, "s1"] = "error"
c5.loc[70, "s2"] = "--"
c5.loc[71, "s2"] = "sensor_offline"
c5.to_csv(f"{OUT}/case5_non_numeric.csv", index=False)

print("Created in", OUT + "/")
for f in sorted(os.listdir(OUT)):
    print(" ", f)