"""Gọi Airflow REST API (basic auth) để kích hoạt và theo dõi DAG retrain_pipeline — docs/design/02_4 mục 2.4.3."""

from datetime import datetime, timezone

import httpx

from app.core.config import Settings


class AirflowError(RuntimeError):
    """Airflow không phản hồi hoặc trả lỗi; router đổi thành 502."""


class AirflowClient:
    def __init__(self, settings: Settings, transport: httpx.BaseTransport | None = None):
        self.dag_id = settings.retrain_dag_id
        self.http = httpx.Client(
            base_url=settings.airflow_api_url.rstrip("/"),
            auth=(settings.airflow_www_user, settings.airflow_www_password),
            timeout=10.0,
            transport=transport,
        )

    def _request(self, method: str, path: str, **kwargs) -> dict:
        try:
            response = self.http.request(method, path, **kwargs)
        except httpx.HTTPError as exc:
            raise AirflowError(f"không kết nối được Airflow: {exc}") from exc
        if response.status_code >= 400:
            raise AirflowError(f"Airflow trả {response.status_code}: {response.text[:300]}")
        return response.json()

    def trigger_retrain(self, conf: dict) -> dict:
        run_id = f"manual__{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%f')}"
        return self._request("POST", f"/dags/{self.dag_id}/dagRuns", json={"dag_run_id": run_id, "conf": conf})

    def get_run(self, dag_run_id: str) -> dict:
        return self._request("GET", f"/dags/{self.dag_id}/dagRuns/{dag_run_id}")
