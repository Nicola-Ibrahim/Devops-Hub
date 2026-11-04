from fastapi.testclient import TestClient

from app.main import app


def test_health_endpoint_is_ready():
    response = TestClient(app).get("/healthz")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_database_failure_does_not_disclose_connection_string(monkeypatch, tmp_path):
    path = tmp_path / "database_url"
    path.write_text("postgresql://user:private-synthetic-value@db.invalid/demo")
    path.chmod(0o400)
    monkeypatch.setenv("DATABASE_URL_FILE", str(path))

    def fail(*_args, **_kwargs):
        raise OSError(path.read_text())

    monkeypatch.setattr("app.database.psycopg.connect", fail)
    response = TestClient(app).get("/healthz")
    assert response.status_code == 503
    assert "private-synthetic-value" not in response.text


def test_database_readiness_uses_the_private_reference(monkeypatch, tmp_path):
    path = tmp_path / "database_url"
    path.write_text("postgresql://test-only-reference")
    path.chmod(0o400)
    monkeypatch.setenv("DATABASE_URL_FILE", str(path))

    class Connection:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def execute(self, query):
            assert query == "SELECT 1"
            return self

        def fetchone(self):
            return (1,)

    def connect(value, *, connect_timeout):
        assert value == path.read_text()
        assert connect_timeout == 2
        return Connection()

    monkeypatch.setattr("app.database.psycopg.connect", connect)
    assert TestClient(app).get("/healthz").status_code == 200
