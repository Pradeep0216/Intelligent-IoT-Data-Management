import time

import numpy as np
import pandas as pd
import torch
import torch.nn as nn
from torch.utils.data import DataLoader, TensorDataset


class LSTMModel(nn.Module):
    """
    Small PyTorch LSTM for next-step multivariate sensor prediction.
    """

    def __init__(
        self,
        input_size,
        hidden_size=32,
        num_layers=1,
        output_size=None,
    ):
        super().__init__()

        if output_size is None:
            output_size = input_size

        self.lstm = nn.LSTM(
            input_size=input_size,
            hidden_size=hidden_size,
            num_layers=num_layers,
            batch_first=True,
        )

        self.output_layer = nn.Linear(
            hidden_size,
            output_size,
        )

    def forward(self, x):
        lstm_output, _ = self.lstm(x)

        # Use the final time step to predict the next sensor vector.
        last_output = lstm_output[:, -1, :]

        return self.output_layer(last_output)


class LSTMDetector:
    """
    LSTM-based anomaly detector for IoT sensor time-series data.

    The model learns temporal patterns from training data.
    Anomaly scores are calculated using next-step prediction error.
    """

    def __init__(
        self,
        sequence_length=20,
        hidden_size=32,
        num_layers=1,
        learning_rate=0.001,
        epochs=20,
        batch_size=32,
        threshold_percentile=95,
    ):
        self.sequence_length = sequence_length
        self.hidden_size = hidden_size
        self.num_layers = num_layers
        self.learning_rate = learning_rate
        self.epochs = epochs
        self.batch_size = batch_size
        self.threshold_percentile = threshold_percentile

        self.model = None
        self.threshold = None
        self.sensor_columns = None

        self.model_name = "LSTMDetector"

        self.device = torch.device(
            "cuda" if torch.cuda.is_available() else "cpu"
        )

        # Reproducibility for the PoC.
        torch.manual_seed(42)

    def _get_numeric_data(self, df):
        """
        Select numeric sensor columns from the input dataframe.
        """

        if df is None or df.empty:
            raise ValueError("Input dataframe is empty")

        numeric_df = df.select_dtypes(include=["number"]).copy()

        if numeric_df.shape[1] == 0:
            raise ValueError(
                "No numeric sensor columns available for LSTM"
            )

        return numeric_df

    def _create_sequences(self, values):
        """
        Convert a time series into sliding-window sequences.

        Example with sequence_length=3:

            [x1, x2, x3] -> x4
            [x2, x3, x4] -> x5
            [x3, x4, x5] -> x6
        """

        if len(values) <= self.sequence_length:
            raise ValueError(
                f"Not enough rows ({len(values)}) for "
                f"sequence_length={self.sequence_length}"
            )

        X = []
        y = []

        for i in range(len(values) - self.sequence_length):
            X.append(
                values[i : i + self.sequence_length]
            )

            y.append(
                values[i + self.sequence_length]
            )

        return (
            np.asarray(X, dtype=np.float32),
            np.asarray(y, dtype=np.float32),
        )

    def fit(self, df):
        """
        Train the LSTM using chronological training data.

        The input dataframe should already be prepared/scaled by the
        shared data pipeline.
        """

        numeric_df = self._get_numeric_data(df)

        self.sensor_columns = numeric_df.columns.tolist()

        values = numeric_df.to_numpy(dtype=np.float32)

        X, y = self._create_sequences(values)

        X_tensor = torch.tensor(X, dtype=torch.float32)
        y_tensor = torch.tensor(y, dtype=torch.float32)

        dataset = TensorDataset(X_tensor, y_tensor)

        loader = DataLoader(
            dataset,
            batch_size=self.batch_size,
            shuffle=False,
        )

        self.model = LSTMModel(
            input_size=len(self.sensor_columns),
            hidden_size=self.hidden_size,
            num_layers=self.num_layers,
            output_size=len(self.sensor_columns),
        ).to(self.device)

        criterion = nn.MSELoss()

        optimizer = torch.optim.Adam(
            self.model.parameters(),
            lr=self.learning_rate,
        )

        self.model.train()

        for epoch in range(self.epochs):
            epoch_loss = 0.0

            for batch_X, batch_y in loader:
                batch_X = batch_X.to(self.device)
                batch_y = batch_y.to(self.device)

                optimizer.zero_grad()

                predictions = self.model(batch_X)

                loss = criterion(
                    predictions,
                    batch_y,
                )

                loss.backward()
                optimizer.step()

                epoch_loss += loss.item()

        # Calculate prediction errors on training data.
        training_scores = self._prediction_scores(
            numeric_df
        )

        self.threshold = float(
            np.percentile(
                training_scores,
                self.threshold_percentile,
            )
        )

        return self

    def _prediction_scores(self, df):
        """
        Calculate one MSE prediction-error score for each
        available sequence.
        """

        numeric_df = df[self.sensor_columns]

        values = numeric_df.to_numpy(dtype=np.float32)

        X, y = self._create_sequences(values)

        X_tensor = torch.tensor(
            X,
            dtype=torch.float32,
        ).to(self.device)

        y_tensor = torch.tensor(
            y,
            dtype=torch.float32,
        ).to(self.device)

        self.model.eval()

        with torch.no_grad():
            predictions = self.model(X_tensor)

            errors = torch.mean(
                (predictions - y_tensor) ** 2,
                dim=1,
            )

        return errors.cpu().numpy()

    def detect(self, df):
        """
        Detect anomalies using prediction error.

        Returns the standard detector output format used by
        the Models pipeline.
        """

        if df is None or df.empty:
            raise ValueError("Input dataframe is empty")

        start_time = time.time()

        numeric_df = self._get_numeric_data(df)

        # Standalone use: train automatically if no fitted model exists.
        if self.model is None or self.threshold is None:
           raise RuntimeError(
              "LSTMDetector has not been fitted. "
              "Call fit(training_data) before detect(test_data)."
           )
        # Ensure the detection data contains the same sensors
        # used during training.
        missing_columns = [
            column
            for column in self.sensor_columns
            if column not in numeric_df.columns
        ]

        if missing_columns:
            raise ValueError(
                f"Missing sensor columns required by LSTM: "
                f"{missing_columns}"
            )

        scores = self._prediction_scores(
            numeric_df
        )

        # The first sequence_length rows do not have a prediction.
        aligned_scores = np.zeros(len(df), dtype=float)

        aligned_scores[
            self.sequence_length :
        ] = scores

        anomaly_flags = (
            aligned_scores >= self.threshold
        )

        score_series = pd.Series(
            aligned_scores,
            index=df.index,
            dtype=float,
        )

        flag_series = pd.Series(
            anomaly_flags,
            index=df.index,
            dtype=bool,
        )

        runtime = time.time() - start_time

        return {
            "model_name": self.model_name,
            "timestamp": df.index,
            "anomaly_flag": flag_series,
            "score": score_series,
            "runtime": runtime,
        }
