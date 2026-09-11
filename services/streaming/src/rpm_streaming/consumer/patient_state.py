"""State của một bệnh nhân trong consumer: lịch sử giá trị đo theo giờ của đợt ICU đang phát lại.

Đặc trưng được tính bằng **đúng đường tính lúc huấn luyện** (`rpm_common`): forward-fill có giới hạn →
`build_hourly_features` trên toàn bộ lịch sử của đợt, rồi lấy giờ mới nhất. Mọi đặc trưng tại t chỉ phụ thuộc
dữ liệu ≤ t, nên kết quả trùng với dòng tương ứng lúc train. Baseline cá nhân cần 24 giờ đầu, vì vậy state giữ
cả đợt (tối đa vài trăm giờ) và được dựng lại từ toàn bộ `vital_records` của bệnh nhân khi consumer khởi động lại.
"""

from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID

import numpy as np
import pandas as pd

from rpm_common.anomaly import latest_window
from rpm_common.grid import fill_forward
from rpm_common.itemids import VITALS, obs_col
from rpm_common.pipeline import build_hourly_features

OBS_COLUMNS = [obs_col(v) for v in VITALS]


@dataclass
class PatientState:
    patient_id: UUID
    subject_id: int
    icustay_id: int
    age: float | None
    gender_male: float | None
    rows: list[dict] = field(default_factory=list)

    @property
    def last_hour_index(self) -> int | None:
        return self.rows[-1]["hour_index"] if self.rows else None

    def append(self, hour_index: int, recorded_at: datetime, vitals: dict[str, float | None]) -> None:
        if self.last_hour_index is not None and hour_index <= self.last_hour_index:
            raise ValueError(f"giờ {hour_index} không mới hơn giờ cuối {self.last_hour_index}")
        self.rows.append(
            {"hour_index": hour_index, "recorded_at": recorded_at}
            | {obs_col(v): np.nan if vitals.get(v) is None else float(vitals[v]) for v in VITALS}
        )

    def features(self) -> pd.DataFrame:
        """Đặc trưng theo giờ của cả đợt; giờ bị hụt (nếu có) được thêm vào như giờ không đo."""
        frame = pd.DataFrame(self.rows).set_index("hour_index")
        frame = frame.reindex(range(frame.index.min(), frame.index.max() + 1)).reset_index()
        grid = frame[["hour_index", *OBS_COLUMNS]].assign(
            icustay_id=self.icustay_id,
            age=np.nan if self.age is None else float(self.age),
            gender_male=np.nan if self.gender_male is None else float(self.gender_male),
        )
        return build_hourly_features(fill_forward(grid))

    @staticmethod
    def current_window(features: pd.DataFrame) -> np.ndarray | None:
        """Cửa sổ 12 giờ kết thúc ở giờ mới nhất, hoặc None khi chưa chấm điểm bất thường được."""
        return latest_window(features)
