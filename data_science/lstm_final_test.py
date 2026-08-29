import pandas as pd
import numpy as np

from sklearn.preprocessing import MinMaxScaler
from sklearn.metrics import precision_score, recall_score, f1_score, roc_auc_score

from detectors.lstm_detector import LSTMDetector
from anomaly_injector import inject_all


DATASET = "datasets/complex_clean.csv"

SEQUENCE_LENGTH = 20
HIDDEN_SIZE = 16
LEARNING_RATE = 0.001
EPOCHS = 20
BATCH_SIZE = 32


df = pd.read_csv(DATASET)
df.columns = df.columns.str.strip()

features = df[["s1", "s2", "s3"]].copy()

# Same chronological split used during tuning.
train_end = int(len(features) * 0.70)

remaining = len(features) - train_end
validation_size = int(remaining * 0.30)

validation_end = train_end + validation_size

train = features.iloc[:train_end].copy()
validation = features.iloc[train_end:validation_end].copy()
test = features.iloc[validation_end:].copy()

print("=" * 70)
print("LSTM FINAL TEST")
print("=" * 70)

print(f"Train rows:      {len(train)}")
print(f"Validation rows: {len(validation)}")
print(f"Final test rows: {len(test)}")

# Fit scaler ONLY on training data.
scaler = MinMaxScaler()

train_scaled = pd.DataFrame(
    scaler.fit_transform(train),
    columns=train.columns,
    index=train.index,
)

test_scaled = pd.DataFrame(
    scaler.transform(test),
    columns=test.columns,
    index=test.index,
)

# Best configuration from tuning.
detector = LSTMDetector(
    sequence_length=SEQUENCE_LENGTH,
    hidden_size=HIDDEN_SIZE,
    num_layers=1,
    learning_rate=LEARNING_RATE,
    epochs=EPOCHS,
    batch_size=BATCH_SIZE,
    threshold_percentile=95,
)

print()
print("Training final LSTM...")
detector.fit(train_scaled)

# Inject anomalies ONLY into the final test data.
test_with_anomalies, labels = inject_all(
    test_scaled.copy()
)

print("Running final test...")
result = detector.detect(test_with_anomalies)

y_true = np.asarray(labels) != "normal"
y_pred = result["anomaly_flag"].to_numpy()
scores = result["score"].to_numpy()

precision = precision_score(
    y_true,
    y_pred,
    zero_division=0,
)

recall = recall_score(
    y_true,
    y_pred,
    zero_division=0,
)

f1 = f1_score(
    y_true,
    y_pred,
    zero_division=0,
)

auc = roc_auc_score(
    y_true,
    scores,
)

print()
print("=" * 70)
print("FINAL TEST RESULTS")
print("=" * 70)

print(f"Precision:          {precision:.4f}")
print(f"Recall:             {recall:.4f}")
print(f"F1:                 {f1:.4f}")
print(f"ROC-AUC:            {auc:.4f}")
print(f"Threshold:          {detector.threshold:.6f}")
print(f"Predicted anomalies: {int(y_pred.sum())}")
print(f"Actual anomalies:    {int(y_true.sum())}")
print(f"Runtime:             {result['runtime']:.6f}s")

print()
print("=" * 70)
print("CONFIGURATION")
print("=" * 70)

print("Sequence length:", SEQUENCE_LENGTH)
print("Hidden size:", HIDDEN_SIZE)
print("Learning rate:", LEARNING_RATE)
print("Epochs:", EPOCHS)

print()
print("FINAL TEST COMPLETED")