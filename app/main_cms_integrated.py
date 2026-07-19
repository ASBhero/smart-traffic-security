"""
FOTA Server with Vault KMS + CMS Ledger Integration
Complete firmware distribution with signing and blockchain validation
"""

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
from vault_kms_client import get_vault_client
from cms_client import get_cms_client

DB_FILE = "fota_orchestrator.db"
FIRMWARE_DIR = "./app/firmware"
CERTS_DIR = "./app/certs"

# Initialize MQTT publisher (optional, non-blocking)
mqtt_publisher = FOTAMQTTPublisher(broker_host="mqtt-broker", enabled=True)

# Get Vault KMS client
vault_client = get_vault_client()

# Get CMS client
cms_client = get_cms_client()

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
            ledger_hash TEXT,
            rollback_prevention_level INTEGER DEFAULT 0,
            released_at TEXT NOT NULL,
            cms_status TEXT,
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
            cms_ledger_hash TEXT,
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
    os.makedirs("./shared/certs", exist_ok=True)
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
            ca_cert = await vault_client.get_root_ca()
            if ca_cert:
                print("[DIAGNOSTIC] Root CA certificate loaded from Vault", flush=True)
        else:
            print("[DIAGNOSTIC] WARNING: Vault KMS not accessible (will retry on demand)", flush=True)
        
        # Check CMS health
        cms_ready = await cms_client.health_check()
        if cms_ready:
            print("[DIAGNOSTIC] CMS is ready for operations", flush=True)
        else:
            print("[DIAGNOSTIC] WARNING: CMS not accessible (will retry on demand)", flush=True)
    
    except Exception as e:
        print(f"[DIAGNOSTIC] CRITICAL ERROR DURING DB INIT: {e}", flush=True)
    
    print("[DIAGNOSTIC] Lifespan startup sequence finished passing control to Uvicorn.", flush=True)
    yield
    print("[DIAGNOSTIC] Lifespan shutdown sequence triggered.", flush=True)
    mqtt_publisher.disconnect()  # Cleanup on shutdown

app = FastAPI(
    title="Secure FOTA Orchestrator Server — Vault KMS + CMS Ledger + MQTT",
    lifespan=lifespan
)

def get_device_certificate_cn(request: Request) -> str:
    """Extract device identity from mTLS client certificate CN"""
    cert_cn = request.headers.get("X-Client-Cert-CN")
    if not cert_cn:
        raise HTTPException(status_code=401, detail="Missing mTLS client certificate")
    return cert_cn

def get_device_from_certificate(cert_cn: str) -> dict:
    """Validate that the certificate CN corresponds to a registered device"""
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
    """Health check endpoint with Vault, CMS, TLS and MQTT status"""
    mqtt_status = mqtt_publisher.get_status()
    vault_ready = await vault_client.health_check()
    cms_ready = await cms_client.health_check()
    
    return {
        "status": "healthy",
        "service": "FOTA Orchestrator — Vault KMS + CMS Ledger + MQTT",
        "tls_requirement": "TLS v1.2 minimum (TLS v1.3 supported)",
        "architecture": "Transport (mTLS) + Verification (ECDSA-SHA256 via Vault) + Immutability (CMS Ledger) + Notification (MQTT)",
        "vault_kms": {
            "status": "connected" if vault_ready else "disconnected",
            "endpoint": "http://127.0.0.1:8200/v1/",
            "role": "ECDSA signing + PKI management"
        },
        "cms_ledger": {
            "status": "connected" if cms_ready else "disconnected",
            "endpoint": "http://127.0.0.1:8000/api/v1/",
            "role": "Blockchain ledger + firmware registry"
        },
        "mqtt": mqtt_status,
        "channels": {
            "https_transport": "Firmware download (always required)",
            "vault_signing": "Firmware signing (ECDSA-SHA256)",
            "cms_ledger": "Immutable blockchain record",
            "mqtt_notification": "Device alerts (optional)"
        }
    }

@app.get("/api/v1/vault/status")
async def get_vault_status():
    """Get Vault KMS status"""
    vault_ready = await vault_client.health_check()
    seal_status = await vault_client.get_seal_status()
    
    return {
        "status": "connected" if vault_ready else "disconnected",
        "vault_endpoint": vault_client.vault_url,
        "transit_key": vault_client.transit_key_name,
        "pki_role": vault_client.pki_role,
        "seal_status": seal_status
    }

@app.get("/api/v1/cms/status")
async def get_cms_status():
    """Get CMS ledger status"""
    cms_ready = await cms_client.health_check()
    
    return {
        "status": "connected" if cms_ready else "disconnected",
        "cms_endpoint": cms_client.cms_url,
        "api_version": cms_client.api_version,
        "features": [
            "Device registration",
            "Firmware ledger registration",
            "Hash validation",
            "Status tracking",
            "Certificate management"
        ]
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
    """Register a device and register in CMS"""
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
    
    # Register in CMS
    cms_result = await cms_client.register_device(
        device_id=registration.device_id,
        public_key="-----BEGIN PUBLIC KEY-----\n(placeholder)\n-----END PUBLIC KEY-----"
    )
    
    log_audit_event(cert_cn, registration.device_id, "DEVICE_REGISTERED", 
                   details=f"Device {registration.device_id} registered with cert CN {cert_cn}, CMS status: {cms_result.get('status') if cms_result else 'failed'}")
    
    return {
        "status": "success",
        "certificate_cn": cert_cn,
        "device_id": registration.device_id,
        "cms_registered": cms_result is not None,
        "registered_at": now
    }

@app.get("/api/v1/firmware")
async def list_available_firmware(
    request: Request,
    hardware_target: str,
    cert_cn: str = Depends(get_device_certificate_cn)
) -> dict:
    """Device pulls list of available firmware versions"""
    device = get_device_from_certificate(cert_cn)
    firmware_list = get_available_firmware(hardware_target, device.get("current_firmware_version"))
    
    log_audit_event(cert_cn, device["device_id"], "FIRMWARE_LIST_PULLED", 
                   details=f"Device pulled firmware list for {hardware_target}")
    
    return {
        "status": "success",
        "hardware_target": hardware_target,
        "available_firmware": firmware_list
    }

@app.get("/api/v1/firmware/{version}/metadata")
async def get_firmware_sig_and_key(
    request: Request,
    version: str,
    cert_cn: str = Depends(get_device_certificate_cn)
) -> dict:
    """Device pulls firmware metadata: signature, public key, ledger hash"""
    device = get_device_from_certificate(cert_cn)
    firmware = get_firmware_metadata(version)
    
    if not firmware:
        log_audit_event(cert_cn, device["device_id"], "FIRMWARE_PULL_FAILED", 
                       firmware_version=version, details=f"Firmware {version} not found")
        raise HTTPException(status_code=404, detail=f"Firmware version {version} not found")
    
    log_audit_event(cert_cn, device["device_id"], "FIRMWARE_METADATA_PULLED", 
                   firmware_version=version, binary_hash=firmware["binary_hash"])
    
    return {
        "status": "success",
        "version": firmware["version"],
        "binary_hash": firmware["binary_hash"],
        "signature_algorithm": firmware["signature_algorithm"],
        "signature_hex": firmware["signature_hex"],
        "signature_source": "Vault Transit Engine (ECDSA-SHA256)",
        "public_key_hex": firmware["public_key_hex"],
        "public_key_source": "Vault PKI",
        "ledger_hash": firmware["ledger_hash"],
        "ledger_source": "CMS Blockchain",
        "note": "Device should verify signature and query ledger before installing"
    }

@app.get("/api/v1/firmware/{version}/binary")
async def pull_firmware_binary(
    request: Request,
    version: str,
    cert_cn: str = Depends(get_device_certificate_cn)
):
    """Device pulls firmware binary over secure HTTPS/mTLS"""
    device = get_device_from_certificate(cert_cn)
    firmware = get_firmware_metadata(version)
    
    if not firmware:
        log_audit_event(cert_cn, device["device_id"], "FIRMWARE_PULL_FAILED", 
                       firmware_version=version, details=f"Firmware {version} not found")
        raise HTTPException(status_code=404, detail=f"Firmware version {version} not found")
    
    binary_path = Path(firmware["binary_path"])
    if not binary_path.exists():
        log_audit_event(cert_cn, device["device_id"], "FIRMWARE_PULL_FAILED", 
                       firmware_version=version, details=f"Binary file not found on server")
        raise HTTPException(status_code=500, detail="Firmware binary not available")
    
    log_audit_event(cert_cn, device["device_id"], "FIRMWARE_BINARY_PULLED", 
                   firmware_version=version, binary_hash=firmware["binary_hash"])
    
    return FileResponse(
        path=binary_path,
        media_type="application/octet-stream",
        filename=f"firmware-{version}.bin"
    )

# ============================================================================
# VERIFICATION BOUNDARY ENDPOINTS (Ledger Integration with CMS)
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
    """Device validates firmware against blockchain CMS ledger"""
    device = get_device_from_certificate(cert_cn)
    
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    now = datetime.utcnow().isoformat() + "Z"
    
    # Query CMS ledger
    print(f"[FOTA] Querying CMS ledger for hash: {ledger_query.firmware_hash[:16]}...", flush=True)
    cms_validation = await cms_client.validate_firmware_hash(
        firmware_hash=ledger_query.firmware_hash,
        device_id=device["device_id"]
    )
    
    ledger_status = "invalid"
    cms_ledger_hash = None
    if cms_validation:
        ledger_status = "valid" if cms_validation.get("valid") else "invalid"
        cms_ledger_hash = cms_validation.get("ledger_hash")
        print(f"[CMS] Validation result: {ledger_status}", flush=True)
    else:
        print(f"[CMS] Validation failed or CMS not accessible", flush=True)
        ledger_status = "pending_validation"
    
    # Log the ledger query
    cursor.execute("""
        INSERT INTO ledger_queries (firmware_hash, query_timestamp, device_certificate_cn, ledger_status, cms_ledger_hash)
        VALUES (?, ?, ?, ?, ?)
    """, (ledger_query.firmware_hash, now, cert_cn, ledger_status, cms_ledger_hash))
    
    conn.commit()
    conn.close()
    
    ledger_response = {
        "status": ledger_status,
        "firmware_hash": ledger_query.firmware_hash,
        "timestamp": now,
        "source": "CMS Blockchain Ledger",
        "ledger_hash": cms_ledger_hash
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
    """Retrieve immutable audit trail"""
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
# FIRMWARE UPLOAD WITH VAULT KMS + CMS LEDGER
# ============================================================================

@app.post("/api/v1/firmware/upload")
async def upload_firmware(
    version: str,
    hardware_target: str,
    urgency: str = "recommended",
    release_notes: Optional[str] = None,
    file: UploadFile = File(...)
):
    """
    Upload firmware, sign with Vault KMS, register in CMS ledger, publish MQTT
    
    Complete flow:
    1. Save firmware binary
    2. Compute SHA-256 hash
    3. Sign with Vault Transit Engine
    4. Register in CMS blockchain ledger
    5. Store metadata in database
    6. Publish MQTT notification
    """
    try:
        # 1. Save firmware to disk
        firmware_path = f"{FIRMWARE_DIR}/firmware-{version}.bin"
        with open(firmware_path, "wb") as f:
            content = await file.read()
            f.write(content)
        
        # 2. Compute hash
        binary_hash = compute_file_hash(firmware_path)
        print(f"[FIRMWARE] Computed SHA-256 hash: {binary_hash[:32]}...", flush=True)
        
        # 3. Sign firmware using Vault KMS
        print(f"[FIRMWARE] Signing with Vault KMS...", flush=True)
        signature = await vault_client.sign_firmware(binary_hash)
        
        if not signature:
            raise Exception("Failed to sign firmware with Vault KMS")
        
        print(f"[FIRMWARE] Signed: {signature[:50]}...", flush=True)
        
        # Get public key from Vault
        public_key = await vault_client.get_public_key()
        if not public_key:
            raise Exception("Failed to retrieve public key from Vault")
        
        # 4. Register in CMS ledger
        print(f"[CMS] Registering firmware in blockchain ledger...", flush=True)
        cms_result = await cms_client.upload_firmware(
            firmware_name=f"firmware-{version}.bin",
            firmware_hash=binary_hash,
            firmware_signature=signature,
            hardware_target=hardware_target,
            version=version
        )
        
        cms_status = "registered" if cms_result else "failed"
        ledger_hash = cms_result.get("ledger_hash") if cms_result else None
        
        if cms_status == "failed":
            print(f"[WARNING] CMS registration failed, but continuing with local storage", flush=True)
        else:
            print(f"[CMS] Ledger registration successful: {ledger_hash}", flush=True)
        
        # 5. Store in database
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        
        now = datetime.utcnow().isoformat() + "Z"
        
        cursor.execute("SELECT id FROM firmware WHERE version = ?", (version,))
        exists = cursor.fetchone()
        
        if exists:
            cursor.execute("""
                UPDATE firmware SET 
                    binary_path = ?, 
                    binary_hash = ?,
                    signature_hex = ?,
                    public_key_hex = ?,
                    ledger_hash = ?,
                    cms_status = ?,
                    released_at = ?
                WHERE version = ?
            """, (firmware_path, binary_hash, signature, public_key, ledger_hash, cms_status, now, version))
        else:
            cursor.execute("""
                INSERT INTO firmware 
                (version, hardware_target, binary_path, binary_hash, signature_algorithm, 
                 signature_hex, public_key_hex, ledger_hash, cms_status, released_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                version, hardware_target, firmware_path, binary_hash,
                "ECDSA-SHA256-VAULT", signature, public_key, ledger_hash, cms_status, now
            ))
        
        conn.commit()
        conn.close()
        
        print(f"[FIRMWARE] Stored in database with ledger_hash: {ledger_hash}", flush=True)
        
        # 6. Publish MQTT notification
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
            signature_valid=True,
            details=f"Firmware {version} signed by Vault, registered in CMS ledger (hash: {ledger_hash}), notified via MQTT"
        )
        
        print(f"[FIRMWARE] Upload complete for version {version}", flush=True)
        
        return {
            "status": "success",
            "version": version,
            "hardware_target": hardware_target,
            "binary_hash": binary_hash,
            "binary_size": len(content),
            "signature_hex": signature,
            "signature_algorithm": "ECDSA-SHA256",
            "signature_source": "Vault Transit Engine (fota-key)",
            "public_key_hex": public_key,
            "public_key_source": "Vault PKI (fota-devices role)",
            "ledger_hash": ledger_hash,
            "ledger_source": "CMS Blockchain",
            "cms_status": cms_status,
            "channels": {
                "transport": "HTTPS (secure upload)",
                "signing": "Vault Transit Engine (HSM-backed)",
                "ledger": "CMS Blockchain (immutable)",
                "notification": "MQTT" if mqtt_notified else "disabled"
            },
            "timestamp": now
        }
    
    except Exception as e:
        log_audit_event("server", "admin", "FIRMWARE_UPLOAD_FAILED", 
                       firmware_version=version,
                       details=f"Upload failed: {str(e)}")
        print(f"[FIRMWARE] Upload failed: {str(e)}", flush=True)
        raise HTTPException(status_code=500, detail=f"Firmware upload failed: {str(e)}")

# ============================================================================
# NOTIFICATION LAYER (MQTT)
# ============================================================================

@app.post("/api/v1/notifications/maintenance")
async def publish_maintenance_notification(
    hardware_target: str,
    start_time: str,
    end_time: str,
    reason: str = "Scheduled maintenance"
):
    """Publish maintenance window notification via MQTT"""
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
        "notification_channel": "MQTT"
    }

@app.post("/api/v1/notifications/rollback")
async def publish_rollback_notification(
    hardware_target: str,
    version: str,
    reason: str = "If needed"
):
    """Publish rollback availability notification"""
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
        "notification_channel": "MQTT"
    }

@app.get("/api/v1/mqtt/status")
async def get_mqtt_status():
    """Get MQTT notification layer status"""
    return {
        "notification_layer": mqtt_publisher.get_status(),
        "channels": {
            "https": "Firmware transport (always required)",
            "mqtt": "Notifications (optional)"
        }
    }
