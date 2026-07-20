import os
import sqlite3
import json
import hashlib
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Optional
from fastapi import FastAPI, Request, Response, HTTPException, Depends, UploadFile, File
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel
from pathlib import Path
from ssl_config import create_ssl_context, get_tls_version_string
from mqtt_publisher import FOTAMQTTPublisher
<<<<<<< HEAD
=======
from vault_kms_client import get_vault_client

DB_FILE = "fota_orchestrator.db"
FIRMWARE_DIR = "./app/firmware"
CERTS_DIR = "./app/certs"

# Initialize MQTT publisher (optional, non-blocking)
mqtt_publisher = FOTAMQTTPublisher(broker_host="mqtt-broker", enabled=True)

<<<<<<< HEAD
=======
# Get Vault KMS client
vault_client = get_vault_client()

def init_db():
    print("[DIAGNOSTIC] Starting init_db()...", flush=True)
    
    print(f"[DIAGNOSTIC] Connecting to SQLite database file: {DB_FILE}...", flush=True)
    conn = sqlite3.connect(DB_FILE, timeout=10)
    cursor = conn.cursor()
    
    print("[DIAGNOSTIC] Creating schema tables...", flush=True)
    
    # Devices table — certificate-based identity
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS devices (
            certificate_cn TEXT PRIMARY KEY,
            device_id TEXT UNIQUE NOT NULL,
            hardware TEXT NOT NULL,
            current_firmware_version TEXT,
            security_status TEXT,
            last_pull_timestamp TEXT,
            certificate_fingerprint TEXT NOT NULL,
            registered_at TEXT NOT NULL,
            certificate_expiry TEXT,
            metadata TEXT
        )
    """)
    
    # Firmware binaries table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS firmware (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            version TEXT UNIQUE NOT NULL,
            hardware_target TEXT NOT NULL,
            binary_path TEXT NOT NULL,
            binary_hash TEXT NOT NULL,
            signature_algorithm TEXT NOT NULL,
            signature_hex TEXT NOT NULL,
            public_key_hex TEXT NOT NULL,
            rollback_prevention_level INTEGER DEFAULT 0,
            released_at TEXT NOT NULL,
            ledger_hash TEXT,
            metadata TEXT
        )
    """)
    
    # Audit logs — immutable trail of all pull events
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS audit_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            device_certificate_cn TEXT NOT NULL,
            device_id TEXT,
            action TEXT NOT NULL,
            firmware_version TEXT,
            binary_hash TEXT,
            signature_valid INTEGER,
            ledger_validated INTEGER,
            timestamp TEXT NOT NULL,
            details TEXT,
            FOREIGN KEY (device_certificate_cn) REFERENCES devices(certificate_cn)
        )
    """)
    
    # Ledger queries — track blockchain CMS interactions
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS ledger_queries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            firmware_hash TEXT NOT NULL,
            query_timestamp TEXT NOT NULL,
            ledger_status TEXT,
            ledger_response TEXT,
            device_certificate_cn TEXT,
            FOREIGN KEY (device_certificate_cn) REFERENCES devices(certificate_cn)
        )
    """)
    
    conn.commit()
    print("[DIAGNOSTIC] All schema tables created successfully.", flush=True)
    
    print("[DIAGNOSTIC] Closing database connection...", flush=True)
    conn.close()
    print("[DIAGNOSTIC] init_db() completed successfully!", flush=True)

def ensure_directories():
    """Create required directories for firmware and certificates"""
    os.makedirs(FIRMWARE_DIR, exist_ok=True)
    os.makedirs(CERTS_DIR, exist_ok=True)
    print(f"[DIAGNOSTIC] Directories ensured: {FIRMWARE_DIR}, {CERTS_DIR}", flush=True)

@asynccontextmanager
async def lifespan(app: FastAPI):
    print("[DIAGNOSTIC] Lifespan startup sequence triggered.", flush=True)
    try:
        init_db()
        ensure_directories()
        mqtt_publisher.connect()  # Optional notification layer

        # Check Vault KMS health
        vault_ready = await vault_client.health_check()
        if vault_ready:
            print("[DIAGNOSTIC] Vault KMS is ready for operations", flush=True)
            # Get Root CA certificate
            ca_cert = await vault_client.get_root_ca()
            if ca_cert:
                print("[DIAGNOSTIC] Root CA certificate loaded from Vault", flush=True)
        else:
            print("[DIAGNOSTIC] WARNING: Vault KMS not accessible (will retry on demand)", flush=True)
    except Exception as e:
        print(f"[DIAGNOSTIC] CRITICAL ERROR DURING DB INIT: {e}", flush=True)
    print("[DIAGNOSTIC] Lifespan startup sequence finished passing control to Uvicorn.", flush=True)
    yield
    print("[DIAGNOSTIC] Lifespan shutdown sequence triggered.", flush=True)
    mqtt_publisher.disconnect()  # Cleanup on shutdown

app = FastAPI(title="Secure FOTA Orchestrator Server — mTLS + MQTT Notifications", lifespan=lifespan)

def get_device_certificate_cn(request: Request) -> str:
    """
    Extract device identity from mTLS client certificate CN.
    In production with mTLS, FastAPI receives the cert via:
    - Direct uvicorn SSL context, or
    - Request headers set by reverse proxy/load balancer
    
    For now, check X-Client-Cert-CN header (debug mode).
    """
    cert_cn = request.headers.get("X-Client-Cert-CN")
    if not cert_cn:
        raise HTTPException(status_code=401, detail="Missing mTLS client certificate")
    return cert_cn

def get_device_from_certificate(cert_cn: str) -> dict:
    """
    Validate that the certificate CN corresponds to a registered device.
    """
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute("SELECT * FROM devices WHERE certificate_cn = ?", (cert_cn,))
    device = cursor.fetchone()
    conn.close()
    
    if not device:
        raise HTTPException(status_code=403, detail="Device certificate not registered")
    
    return dict(device)

def get_available_firmware(hardware_target: str, device_version: Optional[str] = None) -> list:
    """Fetch firmware versions available for a device"""
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute(
        "SELECT version, hardware_target, binary_hash, rollback_prevention_level, released_at, ledger_hash FROM firmware WHERE hardware_target = ? ORDER BY version DESC",
        (hardware_target,)
    )
    firmware_list = cursor.fetchall()
    conn.close()
    
    return [dict(fw) for fw in firmware_list]

def get_firmware_metadata(version: str) -> dict:
    """Fetch firmware metadata including signature and public key"""
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute(
        "SELECT version, hardware_target, binary_path, binary_hash, signature_algorithm, signature_hex, public_key_hex, ledger_hash FROM firmware WHERE version = ?",
        (version,)
    )
    firmware = cursor.fetchone()
    conn.close()
    
    if not firmware:
        return None
    
    return dict(firmware)

def log_audit_event(device_cert_cn: str, device_id: str, action: str, firmware_version: Optional[str] = None, 
                    binary_hash: Optional[str] = None, signature_valid: Optional[bool] = None, 
                    ledger_validated: Optional[bool] = None, details: Optional[str] = None):
    """Write immutable audit trail entry"""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    now = datetime.utcnow().isoformat() + "Z"
    cursor.execute("""
        INSERT INTO audit_logs 
        (device_certificate_cn, device_id, action, firmware_version, binary_hash, signature_valid, ledger_validated, timestamp, details)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        device_cert_cn, device_id, action, firmware_version, binary_hash, 
        1 if signature_valid else 0, 1 if ledger_validated else 0, now, details
    ))
    
    conn.commit()
    conn.close()

def compute_file_hash(file_path: str) -> str:
    """Compute SHA-256 hash of a file"""
    sha256_hash = hashlib.sha256()
    with open(file_path, "rb") as f:
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()

# ============================================================================
# HEALTH CHECK
# ============================================================================

@app.get("/health")
async def health_check():
    """Health check endpoint with TLS and MQTT status"""
    mqtt_status = mqtt_publisher.get_status()
    return {
        "status": "healthy",
        "service": "FOTA Orchestrator mTLS Server",
        "tls_requirement": "TLS v1.2 minimum (TLS v1.3 supported)",
        "architecture": "Transport Boundary (mTLS + HTTPS Pull) + Verification Boundary (ECDSA-SHA256 + Ledger) + Notification Layer (MQTT optional)",
        "mqtt": mqtt_status,
        "channels": {
            "https_transport": "Firmware download (secure, always required)",
            "mqtt_notification": "Update notifications (optional, convenience)"
        },
        "endpoints": {
            "device_registration": "POST /api/v1/devices/register (mTLS required)",
            "firmware_list": "GET /api/v1/firmware (mTLS required)",
            "firmware_metadata": "GET /api/v1/firmware/{version}/metadata (mTLS required)",
            "firmware_binary": "GET /api/v1/firmware/{version}/binary (mTLS required)",
            "firmware_upload": "POST /api/v1/firmware/upload (publishes MQTT notification)",
            "ledger_validation": "POST /api/v1/ledger/validate-hash (mTLS required)",
            "audit_trail": "GET /api/v1/audit/pull-events (mTLS required)",
            "mqtt_status": "GET /api/v1/mqtt/status"
        }
    }

# ============================================================================
# TRANSPORT BOUNDARY ENDPOINTS (mTLS + HTTPS Pull)
# ============================================================================

class DeviceRegistration(BaseModel):
    """Device registration with certificate CN as identity"""
    device_id: str
    hardware: str
    certificate_fingerprint: str
    certificate_expiry: str
    metadata: Optional[dict] = None

@app.post("/api/v1/devices/register")
async def register_device(
    request: Request,
    registration: DeviceRegistration,
    cert_cn: str = Depends(get_device_certificate_cn)
):
    """
    Register a device using its mTLS client certificate CN as primary identity.
    The certificate CN becomes the device's unique identifier.
    """
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    now = datetime.utcnow().isoformat() + "Z"
    
    cursor.execute("SELECT certificate_cn FROM devices WHERE certificate_cn = ?", (cert_cn,))
    exists = cursor.fetchone()
    
    if exists:
        conn.close()
        return {
            "status": "device_already_registered",
            "certificate_cn": cert_cn,
            "device_id": registration.device_id
        }
    
    metadata_json = json.dumps(registration.metadata) if registration.metadata else None
    cursor.execute("""
        INSERT INTO devices 
        (certificate_cn, device_id, hardware, certificate_fingerprint, certificate_expiry, registered_at, metadata)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (
        cert_cn,
        registration.device_id,
        registration.hardware,
        registration.certificate_fingerprint,
        registration.certificate_expiry,
        now,
        metadata_json
    ))
    
    conn.commit()
    conn.close()
    
    log_audit_event(cert_cn, registration.device_id, "DEVICE_REGISTERED", details=f"Device {registration.device_id} registered with cert CN {cert_cn}")
    
    return {
        "status": "success",
        "certificate_cn": cert_cn,
        "device_id": registration.device_id,
        "registered_at": now
    }

@app.get("/api/v1/firmware")
async def list_available_firmware(
    request: Request,
    hardware_target: str,
    cert_cn: str = Depends(get_device_certificate_cn)
) -> dict:
    """
    Device pulls the list of available firmware versions for its hardware.
    (HTTPS PULL mechanism - Transport Boundary)
    """
    device = get_device_from_certificate(cert_cn)
    firmware_list = get_available_firmware(hardware_target, device.get("current_firmware_version"))
    
    log_audit_event(cert_cn, device["device_id"], "FIRMWARE_LIST_PULLED", details=f"Device pulled firmware list for {hardware_target}")
    
    return {
        "status": "success",
        "hardware_target": hardware_target,
        "available_firmware": firmware_list,
        "note": "If MQTT notifications were received, firmware version should match one below"
    }

@app.get("/api/v1/firmware/{version}/metadata")
async def get_firmware_sig_and_key(
    request: Request,
    version: str,
    cert_cn: str = Depends(get_device_certificate_cn)
) -> dict:
    """
    Device pulls firmware metadata: signature, public key, and ledger hash.
    Used for Verification Boundary (Asymmetric Code Signing + Ledger Check).
    (HTTPS PULL mechanism - Verification Boundary)
    """
    device = get_device_from_certificate(cert_cn)
    firmware = get_firmware_metadata(version)
    
    if not firmware:
        log_audit_event(cert_cn, device["device_id"], "FIRMWARE_PULL_FAILED", firmware_version=version, details=f"Firmware {version} not found")
        raise HTTPException(status_code=404, detail=f"Firmware version {version} not found")
    
    log_audit_event(cert_cn, device["device_id"], "FIRMWARE_METADATA_PULLED", firmware_version=version, binary_hash=firmware["binary_hash"])
    
    return {
        "status": "success",
        "version": firmware["version"],
        "binary_hash": firmware["binary_hash"],
        "signature_algorithm": firmware["signature_algorithm"],
        "signature_hex": firmware["signature_hex"],
        "public_key_hex": firmware["public_key_hex"],
        "ledger_hash": firmware["ledger_hash"],
        "note": "Device should verify signature and query ledger before installing"
    }

@app.get("/api/v1/firmware/{version}/binary")
async def pull_firmware_binary(
    request: Request,
    version: str,
    cert_cn: str = Depends(get_device_certificate_cn)
):
    """
    Device pulls the firmware binary file over secure HTTPS/mTLS.
    (HTTPS PULL mechanism - Transport Boundary)
    """
    device = get_device_from_certificate(cert_cn)
    firmware = get_firmware_metadata(version)
    
    if not firmware:
        log_audit_event(cert_cn, device["device_id"], "FIRMWARE_PULL_FAILED", firmware_version=version, details=f"Firmware {version} not found")
        raise HTTPException(status_code=404, detail=f"Firmware version {version} not found")
    
    binary_path = Path(firmware["binary_path"])
    if not binary_path.exists():
        log_audit_event(cert_cn, device["device_id"], "FIRMWARE_PULL_FAILED", firmware_version=version, details=f"Binary file not found on server")
        raise HTTPException(status_code=500, detail="Firmware binary not available")
    
    log_audit_event(cert_cn, device["device_id"], "FIRMWARE_BINARY_PULLED", firmware_version=version, binary_hash=firmware["binary_hash"])
    
    return FileResponse(
        path=binary_path,
        media_type="application/octet-stream",
        filename=f"firmware-{version}.bin"
    )

# ============================================================================
# VERIFICATION BOUNDARY ENDPOINTS (Ledger Integration)
# ============================================================================

class LedgerQueryRequest(BaseModel):
    """Query blockchain CMS for firmware hash validation"""
    firmware_hash: str
    firmware_version: str

@app.post("/api/v1/ledger/validate-hash")
async def query_ledger_for_hash(
    request: Request,
    ledger_query: LedgerQueryRequest,
    cert_cn: str = Depends(get_device_certificate_cn)
) -> dict:
    """
    Device validates firmware against blockchain CMS (immutable ledger).
    This endpoint queries the ledger and returns validation status.
    (Ready for Blockchain CMS integration)
    """
    device = get_device_from_certificate(cert_cn)
    
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    now = datetime.utcnow().isoformat() + "Z"
    
    # Log the ledger query
    cursor.execute("""
        INSERT INTO ledger_queries (firmware_hash, query_timestamp, device_certificate_cn)
        VALUES (?, ?, ?)
    """, (ledger_query.firmware_hash, now, cert_cn))
    
    conn.commit()
    conn.close()
    
    # TODO: Integrate with Blockchain CMS
    ledger_status = "pending_validation"
    ledger_response = {
        "status": ledger_status,
        "firmware_hash": ledger_query.firmware_hash,
        "timestamp": now,
        "message": "Awaiting blockchain CMS validation (colleague's responsibility)"
    }
    
    log_audit_event(
        cert_cn, device["device_id"], "LEDGER_VALIDATION_QUERIED",
        firmware_version=ledger_query.firmware_version,
        binary_hash=ledger_query.firmware_hash,
        ledger_validated=(ledger_status == "valid"),
        details=f"Ledger query for {ledger_query.firmware_hash}: {ledger_status}"
    )
    
    return {
        "status": "success",
        "ledger_response": ledger_response
    }

# ============================================================================
# AUDIT TRAIL ENDPOINT
# ============================================================================

@app.get("/api/v1/audit/pull-events")
async def get_pull_audit_trail(
    request: Request,
    limit: int = 100,
    cert_cn: str = Depends(get_device_certificate_cn)
) -> dict:
    """
    Retrieve immutable audit trail of all pull events for this device.
    """
    device = get_device_from_certificate(cert_cn)
    
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute(
        "SELECT * FROM audit_logs WHERE device_certificate_cn = ? ORDER BY timestamp DESC LIMIT ?",
        (cert_cn, limit)
    )
    logs = cursor.fetchall()
    conn.close()
    
    return {
        "status": "success",
        "device_certificate_cn": cert_cn,
        "device_id": device["device_id"],
        "audit_trail": [dict(log) for log in logs]
    }

# ============================================================================
# NOTIFICATION LAYER (MQTT - Optional Enhancement)
# ============================================================================

class FirmwareUpload(BaseModel):
    """Firmware upload request with metadata"""
    version: str
    hardware_target: str
    urgency: str = "recommended"
    release_notes: Optional[str] = None

@app.post("/api/v1/firmware/upload")
async def upload_firmware(
    version: str,
    hardware_target: str,
    urgency: str = "recommended",
    release_notes: Optional[str] = None,
    file: UploadFile = File(...)
):
    """
    Upload firmware binary and publish MQTT notification.
    HTTPS channel: Firmware secure upload and storage
    MQTT channel: Instant notification to devices (optional)
    """
    try:
        # Save firmware to disk
        firmware_path = f"{FIRMWARE_DIR}/firmware-{version}.bin"
        with open(firmware_path, "wb") as f:
            content = await file.read()
            f.write(content)
        
        # Compute hash
        binary_hash = compute_file_hash(firmware_path)
        
        # Store metadata in database
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        
        now = datetime.utcnow().isoformat() + "Z"
        
        # Check if firmware already exists
        cursor.execute("SELECT id FROM firmware WHERE version = ?", (version,))
        exists = cursor.fetchone()
        
        if exists:
            # Update existing
            cursor.execute("""
                UPDATE firmware SET 
                    binary_path = ?, 
                    binary_hash = ?,
                    released_at = ?
                WHERE version = ?
            """, (firmware_path, binary_hash, now, version))
        else:
            # Insert new
            cursor.execute("""
                INSERT INTO firmware 
                (version, hardware_target, binary_path, binary_hash, signature_algorithm, 
                 signature_hex, public_key_hex, released_at, ledger_hash)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                version, hardware_target, firmware_path, binary_hash,
                "ECDSA-SHA256", "placeholder_signature", "placeholder_public_key", now, "placeholder_ledger_hash"
            ))
        
        conn.commit()
        conn.close()
        
        # Publish MQTT notification (optional, non-blocking)
        mqtt_notified = False
        if mqtt_publisher.connected:
            mqtt_notified = mqtt_publisher.publish_firmware_available(
                hardware_target=hardware_target,
                version=version,
                urgency=urgency,
                release_notes=release_notes,
                binary_hash=binary_hash
            )
        
        # Log audit event
        log_audit_event(
            "server", "admin", "FIRMWARE_UPLOADED",
            firmware_version=version,
            binary_hash=binary_hash,
            details=f"Firmware {version} uploaded for {hardware_target} (MQTT notification: {mqtt_notified})"
        )
        
        return {
            "status": "success",
            "version": version,
            "hardware_target": hardware_target,
            "binary_hash": binary_hash,
            "file_size": len(content),
            "transport_channel": "HTTPS (secure upload)",
            "notification_channel": {
                "mqtt_enabled": mqtt_publisher.enabled,
                "mqtt_connected": mqtt_publisher.connected,
                "mqtt_notification_sent": mqtt_notified,
                "notification_topic": f"fota/notifications/{hardware_target}/firmware_available"
            },
            "timestamp": now
        }
    
    except Exception as e:
        log_audit_event("server", "admin", "FIRMWARE_UPLOAD_FAILED", 
                       firmware_version=version,
                       details=f"Upload failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Firmware upload failed: {str(e)}")

@app.post("/api/v1/notifications/maintenance")
async def publish_maintenance_notification(
    hardware_target: str,
    start_time: str,
    end_time: str,
    reason: str = "Scheduled maintenance"
):
    """
    Publish maintenance window notification via MQTT.
    Devices can prepare for server downtime.
    """
    if not mqtt_publisher.connected:
        raise HTTPException(status_code=503, detail="MQTT broker not connected")
    
    success = mqtt_publisher.publish_maintenance_window(
        hardware_target=hardware_target,
        start_time=start_time,
        end_time=end_time,
        reason=reason
    )
    
    if success:
        log_audit_event("server", "admin", "MAINTENANCE_NOTIFICATION_PUBLISHED",
                       details=f"Maintenance window: {start_time} - {end_time}")
    
    return {
        "status": "success" if success else "failed",
        "hardware_target": hardware_target,
        "start_time": start_time,
        "end_time": end_time,
        "notification_channel": "MQTT",
        "mqtt_published": success
    }

@app.post("/api/v1/notifications/rollback")
async def publish_rollback_notification(
    hardware_target: str,
    version: str,
    reason: str = "If needed"
):
    """
    Publish rollback availability notification via MQTT.
    Devices can know previous version is available.
    """
    if not mqtt_publisher.connected:
        raise HTTPException(status_code=503, detail="MQTT broker not connected")
    
    success = mqtt_publisher.publish_rollback_available(
        hardware_target=hardware_target,
        version=version,
        reason=reason
    )
    
    if success:
        log_audit_event("server", "admin", "ROLLBACK_NOTIFICATION_PUBLISHED",
                       firmware_version=version,
                       details=f"Rollback available for {hardware_target}")
    
    return {
        "status": "success" if success else "failed",
        "hardware_target": hardware_target,
        "version": version,
        "notification_channel": "MQTT",
        "mqtt_published": success
    }

@app.get("/api/v1/mqtt/status")
async def get_mqtt_status():
    """
    Get MQTT notification layer status.
    Shows whether notifications are available.
    """
    return {
        "notification_layer": mqtt_publisher.get_status(),
        "mqtt_topics_available": [
            "fota/notifications/{hardware_target}/firmware_available",
            "fota/notifications/{hardware_target}/maintenance_window",
            "fota/notifications/{hardware_target}/rollback_available"
        ],
        "channels": {
            "https": "Firmware transport (always required, secure)",
            "mqtt": "Notifications (optional enhancement, best-effort)"
        },
        "note": "Devices work with or without MQTT. Firmware downloads always use HTTPS/mTLS regardless of MQTT availability."
    }
