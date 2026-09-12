"""Smoke test hạ tầng — docs/design/02_10_thiet_ke_test.md mục 2.10.2 dòng cuối.

Chạy **mỗi khi sửa `docker-compose.yml`** hoặc một Dockerfile trong `infra/`:

    python infra/smoke_test.py            # kiểm tra mọi thành phần đang chạy
    python infra/smoke_test.py --list     # chỉ liệt kê các phép kiểm tra

Khác với `tests/e2e/` (kiểm tra *hành vi nghiệp vụ* của hệ thống), script này chỉ kiểm tra *hạ tầng có
đấu nối đúng* hay không: cổng có mở, Kafka có produce/consume được từ host, model log lên MLflow có tải
lại được **từ bên trong một container khác**, Airflow REST có trả 200, Prometheus có scrape được backend,
Grafana có nạp được dashboard và giải được datasource.

Thành phần nào chưa chạy thì phép kiểm tra tương ứng được **bỏ qua** kèm lời nhắc lệnh cần chạy, chứ
không báo lỗi — vì các profile của compose được bật độc lập với nhau.

Script tự dọn: registered model tạm được xoá sau mỗi lần chạy. Các run thì nằm trong experiment riêng
tên `smoke_test` để không lẫn vào `risk_forecasting` / `anomaly_detection`.
"""

import os
import socket
import subprocess
import sys
import uuid
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "tests" / "e2e"))

PASS, SKIP, FAIL = "ĐẠT", "BỎ QUA", "LỖI"
results: list[tuple[str, str, str]] = []


def record(name: str, status: str, detail: str = "") -> None:
    results.append((name, status, detail))
    mark = {PASS: "  ok ", SKIP: "  -- ", FAIL: " LỖI"}[status]
    print(f"{mark} {name}" + (f" — {detail}" if detail else ""))


def port_open(host: str, port: int, timeout: float = 2.0) -> bool:
    try:
        with socket.create_connection((host, int(port)), timeout):
            return True
    except OSError:
        return False


# Địa chỉ nhìn từ HOST (khác với hostname trong mạng docker mà các container dùng cho nhau).
# Đặt biến môi trường cùng tên để ghi đè, ví dụ khi chạy script từ một máy khác.
HOST_ENDPOINTS = {
    "POSTGRES_ADDR": "localhost:5432",
    "KAFKA_ADDR": "localhost:29092",
    "MLFLOW_URL": "http://localhost:5000",
    "AIRFLOW_API": "http://localhost:8080/api/v1",
    "PROMETHEUS_URL": "http://localhost:9090",
    "GRAFANA_URL": "http://localhost:3001",
}


def env() -> dict:
    """Tên database, tài khoản lấy từ .env; địa chỉ lấy từ HOST_ENDPOINTS (ghi đè được bằng biến môi trường)."""
    from dotenv import dotenv_values

    values = {k: v for k, v in dotenv_values(REPO_ROOT / ".env").items() if v is not None}
    values.update(os.environ)
    for key, default in HOST_ENDPOINTS.items():
        values.setdefault(key, default)
    return values


# ------------------------------------------------------------------------------------------ các phép kiểm tra


def check_postgres(cfg: dict) -> None:
    """Postgres mở cổng và có đủ 4 database mà hệ thống cần."""
    host, _, port = cfg["POSTGRES_ADDR"].partition(":")
    if not port_open(host, port):
        return record("PostgreSQL", SKIP, f"{host}:{port} chưa mở — `docker compose up -d postgres`")
    import psycopg2

    dsn = (f"host={host} port={port} dbname={cfg['POSTGRES_DB']} "
           f"user={cfg['POSTGRES_USER']} password={cfg['POSTGRES_PASSWORD']}")
    with psycopg2.connect(dsn) as conn, conn.cursor() as cur:
        cur.execute("SELECT datname FROM pg_database")
        names = {row[0] for row in cur.fetchall()}
        cur.execute("SELECT extname FROM pg_extension WHERE extname = 'timescaledb'")
        timescale = cur.fetchone() is not None
    missing = {cfg["POSTGRES_DB"], "mlflow_db", "airflow_db", "rpm_test"} - names
    if missing:
        return record("PostgreSQL", FAIL, f"thiếu database {sorted(missing)} — xem infra/postgres-init/")
    if not timescale:
        return record("PostgreSQL", FAIL, "chưa bật extension timescaledb trên database chính")
    record("PostgreSQL", PASS, f"{len(names)} database, timescaledb đã bật")


def check_kafka(cfg: dict) -> None:
    """Từ host produce rồi consume lại đúng message trên một topic tạm."""
    bootstrap = cfg["KAFKA_ADDR"]
    host, _, port = bootstrap.partition(":")
    if not port_open(host, port):
        return record("Kafka", SKIP, f"{bootstrap} chưa mở — `docker compose up -d zookeeper kafka`")
    from confluent_kafka import Consumer, Producer
    from confluent_kafka.admin import AdminClient, NewTopic

    topic = f"smoke-test-{uuid.uuid4().hex[:8]}"
    admin = AdminClient({"bootstrap.servers": bootstrap})
    admin.create_topics([NewTopic(topic, num_partitions=1, replication_factor=1)])[topic].result()
    try:
        payload = uuid.uuid4().hex.encode()
        producer = Producer({"bootstrap.servers": bootstrap})
        producer.produce(topic, key=b"smoke", value=payload)
        if producer.flush(30) != 0:
            return record("Kafka", FAIL, "produce không flush hết")
        consumer = Consumer({"bootstrap.servers": bootstrap, "group.id": f"smoke-{uuid.uuid4()}",
                             "auto.offset.reset": "earliest", "enable.auto.commit": False})
        consumer.subscribe([topic])
        try:
            for _ in range(60):
                message = consumer.poll(1.0)
                if message is not None and not message.error():
                    if message.value() != payload:
                        return record("Kafka", FAIL, "message đọc lại không khớp message đã gửi")
                    return record("Kafka", PASS, f"produce/consume qua {bootstrap}")
            record("Kafka", FAIL, "không đọc lại được message trong 60 giây")
        finally:
            consumer.close()
    finally:
        admin.delete_topics([topic])


def check_mlflow(cfg: dict) -> None:
    """Log một model nhỏ từ host, rồi tải lại **từ trong container** stream-consumer.

    Đây là phép kiểm tra quan trọng nhất của hạ tầng MLflow: log được từ host không có nghĩa là container
    khác tải được — đường dẫn artifact phải đi qua proxy `mlflow-artifacts:/`, và lỗi này từng xảy ra thật
    (model log từ Windows ghi đường dẫn dấu `\\`, container Linux không mở được).
    """
    uri = cfg["MLFLOW_URL"]
    host, port = uri.split("//")[1].split(":")[0], uri.rsplit(":", 1)[1]
    if not port_open(host, port):
        return record("MLflow", SKIP, f"{uri} chưa mở — `docker compose up -d mlflow`")

    import mlflow
    from mlflow import MlflowClient
    from sklearn.linear_model import LogisticRegression

    name = f"smoke_test_{uuid.uuid4().hex[:8]}"
    mlflow.set_tracking_uri(uri)
    mlflow.set_experiment("smoke_test")
    client = MlflowClient(uri)
    try:
        model = LogisticRegression().fit([[0.0], [1.0]], [0, 1])
        with mlflow.start_run():
            info = mlflow.sklearn.log_model(model, name="model", registered_model_name=name)
        # Không dùng get_latest_versions: đã deprecated từ MLflow 2.9 cùng với khái niệm stage.
        version = client.search_model_versions(f"name='{name}'")[0].version
        client.set_registered_model_alias(name, "champion", version)

        if mlflow.sklearn.load_model(info.model_uri) is None:
            return record("MLflow", FAIL, "không tải lại được model từ host")

        container = _running_container("stream-consumer")
        if container is None:
            return record("MLflow", PASS, "log + đăng ký + alias + tải lại từ host"
                                          " (bỏ qua phần tải từ container: chưa chạy profile app)")
        code = (
            "import mlflow;"
            "mlflow.set_tracking_uri('http://mlflow:5000');"
            f"m = mlflow.sklearn.load_model('models:/{name}@champion');"
            "print('LOADED', m.predict([[0.5]])[0])"
        )
        proc = subprocess.run(["docker", "exec", container, "python", "-c", code],
                              capture_output=True, text=True, timeout=300)
        if "LOADED" not in proc.stdout:
            return record("MLflow", FAIL, f"container không tải được model:\n{proc.stdout}\n{proc.stderr[-500:]}")
        record("MLflow", PASS, f"log từ host → tải lại được trong container {container}")
    finally:
        try:
            client.delete_registered_model(name)
        except Exception:
            print(f"      (chú ý: chưa xoá được registered model tạm {name}, xoá tay trên MLflow UI)")


def check_airflow(cfg: dict) -> None:
    """REST API của Airflow trả 200 với basic auth và thấy đủ 2 DAG của hệ thống."""
    import base64
    import json
    import urllib.error
    import urllib.request

    api = cfg["AIRFLOW_API"]
    host, port = api.split("//")[1].split("/")[0].split(":")
    if not port_open(host, port):
        return record("Airflow REST", SKIP,
                      f"{host}:{port} chưa mở — `docker compose up -d airflow-webserver airflow-scheduler`")
    user = cfg.get("AIRFLOW_WWW_USER", "admin")
    password = cfg.get("AIRFLOW_WWW_PASSWORD", "changeme")
    token = base64.b64encode(f"{user}:{password}".encode()).decode()
    request = urllib.request.Request(f"{api}/dags", headers={"Authorization": f"Basic {token}"})
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            if response.status != 200:
                return record("Airflow REST", FAIL, f"HTTP {response.status}")
            dags = {d["dag_id"] for d in json.load(response)["dags"]}
    except urllib.error.HTTPError as exc:
        return record("Airflow REST", FAIL, f"HTTP {exc.code} — kiểm tra AIRFLOW_WWW_USER/PASSWORD trong .env")
    missing = {"drift_check", "retrain_pipeline"} - dags
    if missing:
        return record("Airflow REST", FAIL, f"thiếu DAG {sorted(missing)}")
    record("Airflow REST", PASS, f"200, thấy {len(dags)} DAG gồm drift_check và retrain_pipeline")


def check_prometheus(cfg: dict) -> None:
    """Prometheus scrape được backend (không chỉ scrape chính nó)."""
    import json
    import urllib.request

    base = cfg["PROMETHEUS_URL"]
    host, port = base.split("//")[1].split(":")
    if not port_open(host, port):
        return record("Prometheus", SKIP, f"{base} chưa mở — `docker compose up -d prometheus`")
    with urllib.request.urlopen(f"{base}/api/v1/targets", timeout=30) as response:
        targets = json.load(response)["data"]["activeTargets"]
    health = {t["labels"]["job"]: t["health"] for t in targets}
    if health.get("backend") is None:
        return record("Prometheus", FAIL, "không có target `backend` — kiểm tra infra/prometheus.yml")
    if health["backend"] != "up":
        return record("Prometheus", SKIP if _running_container("backend") is None else FAIL,
                      f"target backend đang `{health['backend']}`"
                      + ("" if _running_container("backend") else " (backend chưa chạy: profile app)"))
    record("Prometheus", PASS, f"target: {health}")


def check_grafana(cfg: dict) -> None:
    """Grafana nạp được dashboard trong provisioning và giải được datasource theo uid."""
    import base64
    import json
    import urllib.request

    base = cfg["GRAFANA_URL"]
    host, port = base.split("//")[1].split(":")
    if not port_open(host, port):
        return record("Grafana", SKIP, f"{base} chưa mở — `docker compose up -d grafana`")
    user = cfg.get("GRAFANA_ADMIN_USER", "admin")
    password = cfg.get("GRAFANA_ADMIN_PASSWORD", "admin")
    token = base64.b64encode(f"{user}:{password}".encode()).decode()

    def get(path: str):
        request = urllib.request.Request(f"{base}{path}",
                                         headers={"Authorization": f"Basic {token}"})
        with urllib.request.urlopen(request, timeout=30) as response:
            return json.load(response)

    sources = {d["uid"] for d in get("/api/datasources")}
    if "prometheus" not in sources:
        return record("Grafana", FAIL,
                      "không có datasource uid=prometheus — dashboard sẽ báo 'Datasource not found'")
    dashboards = {d["uid"] for d in get("/api/search?type=dash-db")}
    if "rpm-backend" not in dashboards:
        return record("Grafana", FAIL, "chưa nạp dashboard rpm-backend từ infra/grafana/provisioning/")
    probe = get("/api/datasources/proxy/uid/prometheus/api/v1/query?query=up")
    if probe.get("status") != "success":
        return record("Grafana", FAIL, "datasource uid=prometheus không truy vấn được Prometheus")
    record("Grafana", PASS, f"{len(dashboards)} dashboard, datasource uid=prometheus truy vấn được")


CHECKS = [
    ("PostgreSQL", check_postgres),
    ("Kafka", check_kafka),
    ("MLflow", check_mlflow),
    ("Airflow REST", check_airflow),
    ("Prometheus", check_prometheus),
    ("Grafana", check_grafana),
]


def _running_container(service: str) -> str | None:
    """Tên container đang chạy của một service trong compose, hoặc None."""
    proc = subprocess.run(["docker", "compose", "ps", "-q", service],
                          capture_output=True, text=True, cwd=REPO_ROOT)
    container = proc.stdout.strip().splitlines()
    return container[0][:12] if container and container[0] else None


def main() -> None:
    if "--list" in sys.argv:
        for name, function in CHECKS:
            print(f"  {name:14} {(function.__doc__ or '').splitlines()[0]}")
        return

    cfg = env()
    print("Smoke test hạ tầng (thành phần chưa chạy sẽ được bỏ qua)\n")
    for name, function in CHECKS:
        try:
            function(cfg)
        except Exception as exc:
            record(name, FAIL, f"{type(exc).__name__}: {exc}")

    counts = {status: sum(1 for _, s, _ in results if s == status) for status in (PASS, SKIP, FAIL)}
    print(f"\n{counts[PASS]} đạt, {counts[SKIP]} bỏ qua, {counts[FAIL]} lỗi")
    if counts[FAIL]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
