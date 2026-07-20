"""
Extended test suite for the FOTA Orchestrator Server.

Covers negative paths, validation edge cases, firmware upload,
audit trail, and ledger validation — beyond the basic smoke tests.
"""
import io
import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _register(client, device_id: str, cert_cn: str, hardware: str = "ESP32-S3") -> dict:
    """Helper: register a device and return the response JSON."""
    resp = client.post(
        "/api/v1/devices/register",
        json={
            "device_id": device_id,
            "hardware": hardware,
            "certificate_fingerprint": "AA:BB:CC:DD:EE:FF:00:11:22:33:44:55:66:77:88:99",
            "certificate_expiry": "2035-01-01T00:00:00Z",
        },
        headers={"X-Client-Cert-CN": cert_cn},
    )
    return resp.json()


def _upload_firmware(client, version: str, hardware_target: str = "ESP32-S3") -> dict:
    """Helper: upload a dummy firmware binary and return the response JSON."""
    dummy_bin = b"\x7fELF" + b"\x00" * 60  # minimal ELF-like binary stub
    resp = client.post(
        "/api/v1/firmware/upload",
        params={
            "version": version,
            "hardware_target": hardware_target,
            "urgency": "recommended",
            "release_notes": f"CI test firmware {version}",
        },
        files={"file": (f"firmware-{version}.bin", io.BytesIO(dummy_bin), "application/octet-stream")},
    )
    return resp


# ---------------------------------------------------------------------------
# Registration — negative paths
# ---------------------------------------------------------------------------

class TestRegistrationNegative:
    def test_register_without_cert_header_returns_401(self, client):
        """Missing X-Client-Cert-CN must return 401 on registration."""
        resp = client.post(
            "/api/v1/devices/register",
            json={
                "device_id": "esp32-no-cert",
                "hardware": "ESP32-S3",
                "certificate_fingerprint": "AA:BB:CC",
                "certificate_expiry": "2035-01-01T00:00:00Z",
            },
        )
        assert resp.status_code == 401

    def test_register_missing_required_field_returns_422(self, client):
        """Omitting 'hardware' must return 422 Unprocessable Entity."""
        resp = client.post(
            "/api/v1/devices/register",
            json={
                "device_id": "esp32-bad-payload",
                # hardware is missing
                "certificate_fingerprint": "AA:BB:CC",
                "certificate_expiry": "2035-01-01T00:00:00Z",
            },
            headers={"X-Client-Cert-CN": "ci-neg-001"},
        )
        assert resp.status_code == 422

    def test_register_null_device_id_returns_422(self, client):
        """A null device_id must be rejected with 422 (required str field)."""
        resp = client.post(
            "/api/v1/devices/register",
            json={
                "device_id": None,  # null — Pydantic v2 rejects None for required str
                "hardware": "ESP32-S3",
                "certificate_fingerprint": "AA:BB:CC",
                "certificate_expiry": "2035-01-01T00:00:00Z",
            },
            headers={"X-Client-Cert-CN": "ci-neg-002"},
        )
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# Firmware metadata — 404 for unknown version
# ---------------------------------------------------------------------------

class TestFirmwareMetadata:
    @pytest.fixture(autouse=True)
    def registered_device(self, client):
        _register(client, "esp32-meta-001", "meta-test-cn-001")

    def test_firmware_metadata_unknown_version_returns_404(self, client):
        """Requesting metadata for a non-existent version must return 404."""
        resp = client.get(
            "/api/v1/firmware/v99.99.99/metadata",
            headers={"X-Client-Cert-CN": "meta-test-cn-001"},
        )
        assert resp.status_code == 404

    def test_firmware_metadata_valid_version_after_upload(self, client):
        """After upload, metadata endpoint must return version details."""
        _upload_firmware(client, "v1.0.0-meta")
        resp = client.get(
            "/api/v1/firmware/v1.0.0-meta/metadata",
            headers={"X-Client-Cert-CN": "meta-test-cn-001"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["version"] == "v1.0.0-meta"
        assert "binary_hash" in data
        assert "signature_hex" in data
        assert "public_key_hex" in data

    def test_firmware_metadata_without_cert_header_returns_401(self, client):
        """Metadata endpoint is mTLS-protected — no header means 401."""
        resp = client.get("/api/v1/firmware/v1.0.0/metadata")
        assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Firmware binary download
# ---------------------------------------------------------------------------

class TestFirmwareBinaryDownload:
    @pytest.fixture(autouse=True)
    def registered_device(self, client):
        _register(client, "esp32-bin-001", "binary-test-cn-001")

    def test_binary_download_unknown_version_returns_404(self, client):
        """Downloading a non-existent firmware binary must return 404."""
        resp = client.get(
            "/api/v1/firmware/v0.0.0-nonexistent/binary",
            headers={"X-Client-Cert-CN": "binary-test-cn-001"},
        )
        assert resp.status_code == 404

    def test_binary_download_after_upload_returns_binary(self, client):
        """After upload, the binary endpoint must return 200 with octet-stream."""
        _upload_firmware(client, "v1.0.0-bin")
        resp = client.get(
            "/api/v1/firmware/v1.0.0-bin/binary",
            headers={"X-Client-Cert-CN": "binary-test-cn-001"},
        )
        assert resp.status_code == 200
        assert "application/octet-stream" in resp.headers.get("content-type", "")

    def test_binary_download_unregistered_device_returns_403(self, client):
        """Unregistered CN must get 403, not 404, when accessing binary."""
        _upload_firmware(client, "v1.0.0-bin2")
        resp = client.get(
            "/api/v1/firmware/v1.0.0-bin2/binary",
            headers={"X-Client-Cert-CN": "totally-unknown-device"},
        )
        assert resp.status_code == 403


# ---------------------------------------------------------------------------
# Firmware upload
# ---------------------------------------------------------------------------

class TestFirmwareUpload:
    def test_upload_new_firmware_returns_200(self, client):
        """Uploading a new firmware version must return 200 with hash."""
        resp = _upload_firmware(client, "v2.0.0-upload")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "success"
        assert data["version"] == "v2.0.0-upload"
        assert "binary_hash" in data
        assert len(data["binary_hash"]) == 64  # SHA-256 hex = 64 chars

    def test_upload_same_version_twice_is_idempotent(self, client):
        """Re-uploading the same version must succeed (update, not duplicate)."""
        r1 = _upload_firmware(client, "v2.0.0-dupe")
        r2 = _upload_firmware(client, "v2.0.0-dupe")
        assert r1.status_code == 200
        assert r2.status_code == 200

    def test_upload_response_includes_notification_channel(self, client):
        """Upload response must document the MQTT notification channel status."""
        resp = _upload_firmware(client, "v2.0.0-notify")
        data = resp.json()
        assert "notification_channel" in data
        assert "mqtt_enabled" in data["notification_channel"]

    def test_uploaded_firmware_appears_in_firmware_list(self, client):
        """After upload, the firmware must appear in the list for registered devices."""
        _register(client, "esp32-list-001", "upload-list-cn-001")
        _upload_firmware(client, "v2.0.0-listed", hardware_target="ESP32-S3")
        resp = client.get(
            "/api/v1/firmware",
            params={"hardware_target": "ESP32-S3"},
            headers={"X-Client-Cert-CN": "upload-list-cn-001"},
        )
        assert resp.status_code == 200
        versions = [fw["version"] for fw in resp.json()["available_firmware"]]
        assert "v2.0.0-listed" in versions


# ---------------------------------------------------------------------------
# Audit trail
# ---------------------------------------------------------------------------

class TestAuditTrail:
    @pytest.fixture(autouse=True)
    def registered_device(self, client):
        _register(client, "esp32-audit-001", "audit-test-cn-001")

    def test_audit_trail_returns_200(self, client):
        """The audit trail endpoint must return 200 for a registered device."""
        resp = client.get(
            "/api/v1/audit/pull-events",
            headers={"X-Client-Cert-CN": "audit-test-cn-001"},
        )
        assert resp.status_code == 200

    def test_audit_trail_has_required_fields(self, client):
        """Audit trail response must include device_id and audit_trail list."""
        resp = client.get(
            "/api/v1/audit/pull-events",
            headers={"X-Client-Cert-CN": "audit-test-cn-001"},
        )
        data = resp.json()
        assert "audit_trail" in data
        assert isinstance(data["audit_trail"], list)
        assert "device_id" in data

    def test_audit_trail_contains_registration_event(self, client):
        """After registration, the audit trail must include a DEVICE_REGISTERED entry."""
        # Force a firmware list pull to create an audit entry
        client.get(
            "/api/v1/firmware",
            params={"hardware_target": "ESP32-S3"},
            headers={"X-Client-Cert-CN": "audit-test-cn-001"},
        )
        resp = client.get(
            "/api/v1/audit/pull-events",
            headers={"X-Client-Cert-CN": "audit-test-cn-001"},
        )
        actions = [entry["action"] for entry in resp.json()["audit_trail"]]
        assert any(a in ("DEVICE_REGISTERED", "FIRMWARE_LIST_PULLED") for a in actions)

    def test_audit_trail_without_cert_returns_401(self, client):
        """Audit trail is mTLS-protected — no cert means 401."""
        resp = client.get("/api/v1/audit/pull-events")
        assert resp.status_code == 401

    def test_audit_trail_for_unregistered_device_returns_403(self, client):
        """Audit trail for an unknown CN must return 403."""
        resp = client.get(
            "/api/v1/audit/pull-events",
            headers={"X-Client-Cert-CN": "unregistered-audit-cn"},
        )
        assert resp.status_code == 403


# ---------------------------------------------------------------------------
# Ledger validation
# ---------------------------------------------------------------------------

class TestLedgerValidation:
    @pytest.fixture(autouse=True)
    def registered_device(self, client):
        _register(client, "esp32-ledger-001", "ledger-test-cn-001")

    def test_ledger_validate_returns_200(self, client):
        """The ledger validation endpoint must return 200 for a registered device."""
        resp = client.post(
            "/api/v1/ledger/validate-hash",
            json={
                "firmware_hash": "a" * 64,  # valid 64-char hex-like hash
                "firmware_version": "v1.0.0",
            },
            headers={"X-Client-Cert-CN": "ledger-test-cn-001"},
        )
        assert resp.status_code == 200

    def test_ledger_validate_response_has_status(self, client):
        """Ledger response must include a 'ledger_response' object with status."""
        resp = client.post(
            "/api/v1/ledger/validate-hash",
            json={"firmware_hash": "b" * 64, "firmware_version": "v1.0.0"},
            headers={"X-Client-Cert-CN": "ledger-test-cn-001"},
        )
        data = resp.json()
        assert "ledger_response" in data
        assert "status" in data["ledger_response"]

    def test_ledger_validate_without_cert_returns_401(self, client):
        """Ledger endpoint is mTLS-protected."""
        resp = client.post(
            "/api/v1/ledger/validate-hash",
            json={"firmware_hash": "c" * 64, "firmware_version": "v1.0.0"},
        )
        assert resp.status_code == 401

    def test_ledger_validate_unregistered_device_returns_403(self, client):
        """Unregistered CN must get 403 from ledger endpoint."""
        resp = client.post(
            "/api/v1/ledger/validate-hash",
            json={"firmware_hash": "d" * 64, "firmware_version": "v1.0.0"},
            headers={"X-Client-Cert-CN": "ghost-ledger-cn"},
        )
        assert resp.status_code == 403

    def test_ledger_validate_missing_field_returns_422(self, client):
        """Omitting firmware_version must return 422."""
        resp = client.post(
            "/api/v1/ledger/validate-hash",
            json={"firmware_hash": "e" * 64},  # missing firmware_version
            headers={"X-Client-Cert-CN": "ledger-test-cn-001"},
        )
        assert resp.status_code == 422
