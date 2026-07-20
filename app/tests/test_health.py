"""
Smoke tests for the FOTA Orchestrator Server.

These tests validate the core API contracts without requiring:
  - A running Docker container
  - An MQTT broker (gracefully absent)
  - A Vault KMS server (gracefully absent)
  - Real TLS certificates

The TestClient patches X-Client-Cert-CN headers to simulate mTLS authentication.
"""
import pytest


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------

class TestHealthEndpoint:
    def test_health_returns_200(self, client):
        """The /health endpoint must always return HTTP 200."""
        response = client.get("/health")
        assert response.status_code == 200

    def test_health_has_status_field(self, client):
        """The health response must include a 'status' field equal to 'healthy'."""
        response = client.get("/health")
        data = response.json()
        assert data.get("status") == "healthy"

    def test_health_has_service_field(self, client):
        """The health response must describe the service name."""
        response = client.get("/health")
        data = response.json()
        assert "service" in data
        assert "FOTA" in data["service"]

    def test_health_has_mqtt_field(self, client):
        """The health response must include MQTT status (even when disconnected)."""
        response = client.get("/health")
        data = response.json()
        assert "mqtt" in data

    def test_health_has_endpoints_field(self, client):
        """The health response must list available API endpoints."""
        response = client.get("/health")
        data = response.json()
        assert "endpoints" in data


# ---------------------------------------------------------------------------
# Authentication guard (mTLS enforcement)
# ---------------------------------------------------------------------------

class TestAuthenticationGuard:
    def test_firmware_list_requires_cert_header(self, client):
        """Without X-Client-Cert-CN header, firmware list must return 401."""
        response = client.get("/api/v1/firmware", params={"hardware_target": "ESP32-S3"})
        assert response.status_code == 401

    def test_firmware_metadata_requires_cert_header(self, client):
        """Without X-Client-Cert-CN, firmware metadata must return 401."""
        response = client.get("/api/v1/firmware/1.0.0/metadata")
        assert response.status_code == 401

    def test_firmware_binary_requires_cert_header(self, client):
        """Without X-Client-Cert-CN, firmware binary download must return 401."""
        response = client.get("/api/v1/firmware/1.0.0/binary")
        assert response.status_code == 401

    def test_audit_trail_requires_cert_header(self, client):
        """Without X-Client-Cert-CN, audit trail must return 401."""
        response = client.get("/api/v1/audit/pull-events")
        assert response.status_code == 401


# ---------------------------------------------------------------------------
# Device registration
# ---------------------------------------------------------------------------

class TestDeviceRegistration:
    def test_register_new_device_returns_success(self, client):
        """Registering a new device must return HTTP 200 with status=success."""
        response = client.post(
            "/api/v1/devices/register",
            json={
                "device_id": "esp32-reg-001",  # unique device_id per test
                "hardware": "ESP32-S3",
                "certificate_fingerprint": "AA:BB:CC:DD:EE:FF:00:11:22:33:44:55:66:77:88:99",
                "certificate_expiry": "2035-01-01T00:00:00Z",
                "metadata": {"location": "lab", "purpose": "ci-test"}
            },
            headers={"X-Client-Cert-CN": "ci-test-device-001"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data.get("status") in ("success", "device_already_registered")

    def test_register_device_returns_certificate_cn(self, client):
        """Registration response must echo the certificate CN."""
        response = client.post(
            "/api/v1/devices/register",
            json={
                "device_id": "esp32-reg-002",  # different device_id — avoids UNIQUE violation
                "hardware": "ESP32-S3",
                "certificate_fingerprint": "11:22:33:44:55:66:77:88:99:AA:BB:CC:DD:EE:FF:00",
                "certificate_expiry": "2035-01-01T00:00:00Z"
            },
            headers={"X-Client-Cert-CN": "ci-test-device-002"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data.get("certificate_cn") == "ci-test-device-002"

    def test_register_same_device_twice_is_idempotent(self, client):
        """Re-registering an existing device must not raise an error."""
        payload = {
            "device_id": "esp32-dupe-001",
            "hardware": "ESP32-S3",
            "certificate_fingerprint": "AA:BB:CC:00:11:22:33:44:55:66:77:88:99:DD:EE:FF",
            "certificate_expiry": "2035-01-01T00:00:00Z"
        }
        headers = {"X-Client-Cert-CN": "ci-dupe-device-001"}
        r1 = client.post("/api/v1/devices/register", json=payload, headers=headers)
        r2 = client.post("/api/v1/devices/register", json=payload, headers=headers)
        assert r1.status_code == 200
        assert r2.status_code == 200
        assert r2.json().get("status") == "device_already_registered"


# ---------------------------------------------------------------------------
# Firmware list (authenticated device)
# ---------------------------------------------------------------------------

class TestFirmwareList:
    """Tests for the firmware list endpoint, requiring a registered device."""

    @pytest.fixture(autouse=True)
    def register_device(self, client):
        """Register a test device before each test in this class."""
        client.post(
            "/api/v1/devices/register",
            json={
                "device_id": "fw-list-test-device",
                "hardware": "ESP32-S3",
                "certificate_fingerprint": "11:22:33:44:55:66:77:88:99:AA:BB:CC:DD:EE:FF:00",
                "certificate_expiry": "2035-01-01T00:00:00Z"
            },
            headers={"X-Client-Cert-CN": "fw-list-test-cn"}
        )

    def test_firmware_list_returns_200_for_registered_device(self, client):
        """A registered device can list firmware."""
        response = client.get(
            "/api/v1/firmware",
            params={"hardware_target": "ESP32-S3"},
            headers={"X-Client-Cert-CN": "fw-list-test-cn"}
        )
        assert response.status_code == 200

    def test_firmware_list_response_has_available_firmware_key(self, client):
        """Firmware list response must include 'available_firmware' array."""
        response = client.get(
            "/api/v1/firmware",
            params={"hardware_target": "ESP32-S3"},
            headers={"X-Client-Cert-CN": "fw-list-test-cn"}
        )
        data = response.json()
        assert "available_firmware" in data
        assert isinstance(data["available_firmware"], list)

    def test_unregistered_device_cannot_list_firmware(self, client):
        """A device with an unregistered certificate must get 403."""
        response = client.get(
            "/api/v1/firmware",
            params={"hardware_target": "ESP32-S3"},
            headers={"X-Client-Cert-CN": "ghost-device-not-registered"}
        )
        assert response.status_code == 403


# ---------------------------------------------------------------------------
# MQTT status (public endpoint)
# ---------------------------------------------------------------------------

class TestMQTTStatus:
    def test_mqtt_status_returns_200(self, client):
        """The MQTT status endpoint is public and must return HTTP 200."""
        response = client.get("/api/v1/mqtt/status")
        assert response.status_code == 200

    def test_mqtt_status_has_notification_layer(self, client):
        """MQTT status must include a 'notification_layer' key."""
        response = client.get("/api/v1/mqtt/status")
        data = response.json()
        assert "notification_layer" in data
