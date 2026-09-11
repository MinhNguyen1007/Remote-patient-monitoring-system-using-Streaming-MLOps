"""LSTM-Autoencoder phát hiện bất thường và wrapper MLflow pyfunc — docs/design/02_9 mục 2.9.3.

Wrapper nhận cửa sổ z-score gốc hình (n, 12, 6) và trả `anomaly_score` ∈ [0, 1]: bước căn giữa, model Keras và
phân phối MSE tham chiếu (cửa sổ NORMAL của validation) nằm chung trong một model MLflow, nên consumer chỉ cần
một lần gọi `predict`. File này được đính kèm model qua `code_paths`; consumer cần cài `rpm_common` và tensorflow.
"""

import numpy as np
from mlflow.pyfunc import PythonModel

from rpm_common.anomaly import (
    N_CHANNELS,
    WINDOW_HOURS,
    anomaly_score_from_mse,
    center_windows,
    reconstruction_mse,
)

ARCHITECTURE = "LSTM(64)-LSTM(32)-RepeatVector-LSTM(32)-LSTM(64)-TimeDistributed(Dense(6))"
INPUT_TRANSFORM = "center_per_window_channel"
LEARNING_RATE = 1e-3
BATCH_SIZE = 32
MAX_EPOCHS = 200
EARLY_STOPPING_PATIENCE = 15


def build_lstm_autoencoder(length: int = WINDOW_HOURS, n_channels: int = N_CHANNELS):
    import keras
    from keras import layers

    inputs = keras.Input(shape=(length, n_channels))
    x = layers.LSTM(64, return_sequences=True)(inputs)
    x = layers.LSTM(32, return_sequences=False)(x)
    x = layers.RepeatVector(length)(x)
    x = layers.LSTM(32, return_sequences=True)(x)
    x = layers.LSTM(64, return_sequences=True)(x)
    outputs = layers.TimeDistributed(layers.Dense(n_channels))(x)
    model = keras.Model(inputs, outputs, name="lstm_autoencoder")
    model.compile(optimizer=keras.optimizers.Adam(learning_rate=LEARNING_RATE), loss="mse")
    return model


def fit_autoencoder(train: np.ndarray, validation: np.ndarray, seed: int):
    """Huấn luyện tái tạo cửa sổ đã căn giữa; early stopping theo loss validation, giữ trọng số tốt nhất.

    Nhận cửa sổ z-score gốc như `make_windows` trả về; việc căn giữa làm bên trong, giống lúc chấm điểm.
    """
    import keras
    import tensorflow as tf

    keras.utils.set_random_seed(seed)
    tf.config.experimental.enable_op_determinism()
    train, validation = center_windows(train), center_windows(validation)
    model = build_lstm_autoencoder(train.shape[1], train.shape[2])
    history = model.fit(
        train,
        train,
        validation_data=(validation, validation),
        epochs=MAX_EPOCHS,
        batch_size=BATCH_SIZE,
        shuffle=True,
        callbacks=[
            keras.callbacks.EarlyStopping(
                monitor="val_loss", patience=EARLY_STOPPING_PATIENCE, restore_best_weights=True
            )
        ],
        verbose=0,
    )
    return model, history.history


def window_mse(model, windows: np.ndarray) -> np.ndarray:
    """MSE tái tạo của từng cửa sổ z-score gốc (căn giữa rồi mới đưa vào autoencoder)."""
    centered = center_windows(windows)
    return reconstruction_mse(centered, model.predict(centered, verbose=0))


def artifact_path(context, name: str) -> str:
    """Đường dẫn artifact dùng được trên mọi hệ điều hành.

    MLflow ghi đường dẫn tương đối của artifact theo dấu phân cách của máy log model (`artifacts\\x.keras` trên
    Windows), nên container Linux không mở được. Dấu `/` hợp lệ trên cả Windows lẫn Linux.
    """
    return context.artifacts[name].replace("\\", "/")


class AnomalyDetector(PythonModel):
    """Artifact: `autoencoder` (file .keras) và `mse_reference` (file .npy, MSE cửa sổ NORMAL của validation)."""

    def load_context(self, context):
        import keras

        self.autoencoder = keras.models.load_model(artifact_path(context, "autoencoder"), compile=False)
        self.mse_reference = np.load(artifact_path(context, "mse_reference"))

    def predict(self, context, model_input, params=None):
        windows = np.asarray(model_input, dtype=np.float32)
        if windows.ndim != 3 or windows.shape[1:] != (WINDOW_HOURS, N_CHANNELS):
            raise ValueError(f"cần cửa sổ hình (n, {WINDOW_HOURS}, {N_CHANNELS}), nhận {windows.shape}")
        return anomaly_score_from_mse(window_mse(self.autoencoder, windows), self.mse_reference)
