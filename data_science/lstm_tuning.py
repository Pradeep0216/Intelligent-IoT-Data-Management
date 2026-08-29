import itertools

import numpy as np
import pandas as pd
from sklearn.metrics import f1_score, precision_score, recall_score, roc_auc_score
from sklearn.preprocessing import MinMaxScaler

from anomaly_injector import inject_all
from detectors.lstm_detector import LSTMDetector


DATASET = "datasets/complex_clean.csv"

# Keep this small initially because you are running on CPU.
SEQUENCE_LENGTHS = [10, 20, 30]
HIDDEN_SIZES = [16, 32, 64]
LEARNING_RATES = [0.001, 0.0005]

EPOCHS = 20
BATCH_SIZE = 32

TRAIN_RATIO = 0.70
VALIDATION_RATIO = 0.30

RANDOM_SEED = 42


def load_data():
    """Load and prepare the clean benchmark dataset."""

    df = pd.read_csv(DATASET)

    # Match the repository preprocessing behaviour.
    df.columns = df.columns.str.strip()

    # complex_clean.csv contains the three sensor columns.
    sensor_columns = ["s1", "s2", "s3"]

    missing = [
        column
        for column in sensor_columns
        if column not in df.columns
    ]

    if missing:
        raise ValueError(
            f"Missing expected sensor columns: {missing}. "
            f"Available columns: {list(df.columns)}"
        )

    return df[sensor_columns].copy()


def split_train_validation_test(df):
    """
    Chronological split:

        70% train
        21% validation
         9% final test

    The final test portion remains untouched during tuning.
    """

    n = len(df)

    train_end = int(n * TRAIN_RATIO)

    remaining = n - train_end
    validation_end = train_end + int(
        remaining * VALIDATION_RATIO
    )

    train = df.iloc[:train_end].copy()
    validation = df.iloc[train_end:validation_end].copy()
    test = df.iloc[validation_end:].copy()

    return train, validation, test


def scale_data(train, validation, test):
    """
    Fit the scaler ONLY on the training data.
    """

    scaler = MinMaxScaler()

    train_scaled = pd.DataFrame(
        scaler.fit_transform(train),
        columns=train.columns,
        index=train.index,
    )

    validation_scaled = pd.DataFrame(
        scaler.transform(validation),
        columns=validation.columns,
        index=validation.index,
    )

    test_scaled = pd.DataFrame(
        scaler.transform(test),
        columns=test.columns,
        index=test.index,
    )

    return train_scaled, validation_scaled, test_scaled


def evaluate_configuration(
    train_scaled,
    validation_scaled,
    sequence_length,
    hidden_size,
    learning_rate,
):
    """
    Train one LSTM configuration on the training set and
    evaluate it on a separately injected validation set.
    """

    detector = LSTMDetector(
        sequence_length=sequence_length,
        hidden_size=hidden_size,
        num_layers=1,
        learning_rate=learning_rate,
        epochs=EPOCHS,
        batch_size=BATCH_SIZE,
        threshold_percentile=95,
    )

    # Train ONLY on the clean training data.
    detector.fit(train_scaled)

    # Inject controlled anomalies into validation data.
    validation_with_anomalies, labels = inject_all(
        validation_scaled.copy()
    )

    # Detect using the already-trained model.
    result = detector.detect(validation_with_anomalies)

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

    try:
        auc = roc_auc_score(
            y_true,
            scores,
        )
    except ValueError:
        auc = float("nan")

    return {
        "sequence_length": sequence_length,
        "hidden_size": hidden_size,
        "learning_rate": learning_rate,
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "roc_auc": auc,
        "threshold": detector.threshold,
        "predicted_anomalies": int(y_pred.sum()),
        "actual_anomalies": int(y_true.sum()),
    }


def main():
    np.random.seed(RANDOM_SEED)

    print("=" * 70)
    print("LSTM HYPERPARAMETER TUNING")
    print("=" * 70)

    df = load_data()

    print(f"Dataset rows: {len(df)}")
    print(f"Features: {list(df.columns)}")

    train, validation, test = split_train_validation_test(df)

    print()
    print("Chronological split:")
    print(f"Train rows:      {len(train)}")
    print(f"Validation rows: {len(validation)}")
    print(f"Final test rows: {len(test)}")

    train_scaled, validation_scaled, test_scaled = scale_data(
        train,
        validation,
        test,
    )

    configurations = list(
        itertools.product(
            SEQUENCE_LENGTHS,
            HIDDEN_SIZES,
            LEARNING_RATES,
        )
    )

    print()
    print(f"Configurations to test: {len(configurations)}")
    print()

    results = []

    for number, (
        sequence_length,
        hidden_size,
        learning_rate,
    ) in enumerate(configurations, start=1):

        print(
            f"[{number}/{len(configurations)}] "
            f"seq={sequence_length}, "
            f"hidden={hidden_size}, "
            f"lr={learning_rate}"
        )

        try:
            result = evaluate_configuration(
                train_scaled,
                validation_scaled,
                sequence_length,
                hidden_size,
                learning_rate,
            )

            results.append(result)

            print(
                f"    Precision: {result['precision']:.4f} | "
                f"Recall: {result['recall']:.4f} | "
                f"F1: {result['f1']:.4f} | "
                f"AUC: {result['roc_auc']:.4f}"
            )

        except Exception as error:
            print(f"    FAILED: {error}")

    if not results:
        raise RuntimeError(
            "All LSTM configurations failed."
        )

    results_df = pd.DataFrame(results)

    results_df = results_df.sort_values(
        by=["f1", "roc_auc"],
        ascending=False,
    ).reset_index(drop=True)

    print()
    print("=" * 70)
    print("VALIDATION RESULTS")
    print("=" * 70)

    print(
        results_df.to_string(
            index=False,
            float_format=lambda x: f"{x:.4f}",
        )
    )

    best = results_df.iloc[0]

    print()
    print("=" * 70)
    print("BEST VALIDATION CONFIGURATION")
    print("=" * 70)

    print(
        f"Sequence length : {int(best['sequence_length'])}"
    )
    print(
        f"Hidden size     : {int(best['hidden_size'])}"
    )
    print(
        f"Learning rate   : {best['learning_rate']}"
    )
    print(
        f"Validation F1   : {best['f1']:.4f}"
    )
    print(
        f"Validation AUC  : {best['roc_auc']:.4f}"
    )

    # Save tuning results for evidence.
    results_df.to_csv(
        "lstm_tuning_results.csv",
        index=False,
    )

    print()
    print(
        "Saved tuning results to "
        "lstm_tuning_results.csv"
    )

    print()
    print(
        "IMPORTANT: The final test set was NOT used "
        "to select the configuration."
    )


if __name__ == "__main__":
    main()