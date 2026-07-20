"""
Pytest fixtures for FOTA server tests.

Uses FastAPI's TestClient to run the app in-process (no running server needed).
Bypasses mTLS by setting the X-Client-Cert-CN header directly in test requests.
All database operations use a temporary SQLite file that is cleaned up after each test.
"""
import os
import sys
import tempfile
import pytest

# Ensure the app directory is on the path so imports work
APP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if APP_DIR not in sys.path:
    sys.path.insert(0, APP_DIR)

# Set environment variables BEFORE importing the app so that
# Vault, MQTT, and DB paths are pointed at CI-safe defaults
os.environ.setdefault("VAULT_URL", "http://127.0.0.1:18200")  # non-existent; graceful fail
os.environ.setdefault("VAULT_TOKEN", "ci-test-token")
os.environ.setdefault("ENV", "ci")


@pytest.fixture(scope="session")
def tmp_db(tmp_path_factory):
    """Provide a temporary SQLite database file for the test session."""
    db_dir = tmp_path_factory.mktemp("db")
    db_path = str(db_dir / "test_fota.db")
    return db_path


@pytest.fixture(scope="session")
def client(tmp_db, tmp_path_factory):
    """
    Create a TestClient for the FOTA FastAPI app.
    Uses a temporary DB and firmware directory so tests are fully isolated.
    """
    from starlette.testclient import TestClient

    firmware_dir = str(tmp_path_factory.mktemp("firmware"))
    certs_dir = str(tmp_path_factory.mktemp("certs"))

    # Patch module-level constants before the app module is used
    import main as app_module
    app_module.DB_FILE = tmp_db
    app_module.FIRMWARE_DIR = firmware_dir
    app_module.CERTS_DIR = certs_dir

    with TestClient(app_module.app, raise_server_exceptions=True) as c:
        yield c


@pytest.fixture
def device_headers():
    """Standard mTLS bypass headers for a registered test device."""
    return {"X-Client-Cert-CN": "test-device-001"}
