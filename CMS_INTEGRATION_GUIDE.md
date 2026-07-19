# CMS Integration Guide for FOTA Server

## Overview

Your FOTA Server is now integrated with the **CMS (Certificate Management System)** for blockchain ledger management, firmware validation, and device status tracking.

---

## CMS Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    CMS Server (Port 8000)                   │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  Ledger Service (Blockchain)                               │
│  ├─ Firmware upload registration                           │
│  ├─ Immutable ledger entries                               │
│  ├─ Hash validation                                        │
│  └─ Rollback prevention                                    │
│                                                             │
│  Device Management                                         │
│  ├─ Device registration                                    │
│  ├─ Certificate issuance                                   │
│  ├─ Certificate revocation                                 │
│  └─ Public key storage                                     │
│                                                             │
│  Firmware Distribution                                     │
│  ├─ Latest firmware queries                                │
│  ├─ Firmware metadata storage                              │
│  └─ Approval workflow                                      │
│                                                             │
│  Status Tracking                                           │
│  ├─ FOTA update events (DOWNLOADING, VERIFYING, etc.)      │
│  ├─ Device firmware status                                 │
│  └─ Audit logging                                          │
│                                                             │
│  HSM/KMS Integration                                       │
│  └─ Firmware signing (calls Vault at 8200)                 │
│                                                             │
└─────────────────────────────────────────────────────────────┘
         ↕↕↕ HTTP Connection ↕↕↕
┌─────────────────────────────────────────────────────────────┐
│            FOTA Server (Your Application)                   │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  cms_client.py                                             │
│  ├─ register_device() → POST /devices/register             │
│  ├─ upload_firmware() → POST /firmware/upload              │
│  ├─ validate_firmware_hash() → POST /ledger/validate       │
│  ├─ get_latest_firmware() → GET /firmware/latest/{id}      │
│  ├─ update_firmware_status() → POST /firmware/update-status│
│  ├─ issue_certificate() → POST /certificates/issue         │
│  ├─ revoke_certificate() → POST /devices/revoke/{id}       │
│  └─ get_ledger_status() → GET /ledger/status/{hash}        │
│                                                             │
│  main.py Integration                                       │
│  ├─ POST /api/v1/firmware/upload                           │
│  │  ├─ Sign with Vault KMS                                │
│  │  └─ Register with CMS ledger                            │
│  │                                                         │
│  └─ POST /api/v1/ledger/validate-hash                      │
│     ├─ Query CMS ledger                                    │
│     └─ Return validation status                            │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## CMS API Endpoints

### 1. Device Registration
```
POST /api/v1/devices/register

Request:
{
    "id": "ESP32_01",
    "public_key": "-----BEGIN PUBLIC KEY-----\n..."
}

Response:
{
    "device_id": "ESP32_01",
    "status": "registered"
}
```

### 2. Firmware Upload (Ledger Registration)
```
POST /api/v1/firmware/upload

Request:
{
    "firmware": "firmware-1.0.0.bin",
    "hash": "e3b0c44298fc1c149afbf4c8996fb92427ae41e...",
    "signature": "vault:v1:MEUCIQDxK3kH3GHVHYdM6q5ZAG9sMhH+...",
    "hardware_target": "ESP32-S3",
    "version": "1.0.0"
}

Response:
{
    "firmware": "firmware-1.0.0.bin",
    "hash": "e3b0c44298fc1c149afbf4c8996fb92427ae41e...",
    "signature": "vault:v1:MEUCIQDxK3kH3GHVHYdM6q5ZAG9sMhH+...",
    "status": "stored",
    "ledger_hash": "abc123def456..."
}
```

### 3. Validate Firmware Hash
```
POST /api/v1/ledger/validate

Request:
{
    "hash": "e3b0c44298fc1c149afbf4c8996fb92427ae41e...",
    "device_id": "ESP32_01"
}

Response:
{
    "valid": true,
    "status": "valid"
}
```

### 4. Get Latest Firmware
```
GET /api/v1/firmware/latest/{device_id}

Response:
{
    "version": 1,
    "firmware": "firmware-1.0.0.bin",
    "hash": "e3b0c44298fc1c149afbf4c8996fb92427ae41e...",
    "signature": "vault:v1:MEUCIQDxK3kH3GHVHYdM6q5ZAG9sMhH+..."
}
```

### 5. Update Firmware Status
```
POST /api/v1/firmware/update-status

Request:
{
    "device_id": "ESP32_01",
    "status": "SUCCESS",
    "firmware_version": "1.0.0",
    "details": "Firmware installed successfully"
}

Response:
{
    "device_id": "ESP32_01",
    "status": "SUCCESS",
    "timestamp": "2024-01-15T10:30:45Z"
}

Supported Statuses:
- DOWNLOADING
- VERIFYING
- INSTALLED
- SUCCESS
- FAILED
- ROLLBACK
```

### 6. Issue Certificate
```
POST /api/v1/certificates/issue

Request:
{
    "device_id": "ESP32_01",
    "public_key": "-----BEGIN PUBLIC KEY-----\n...",
    "ttl": "365d"
}

Response:
{
    "device_id": "ESP32_01",
    "certificate": "-----BEGIN CERTIFICATE-----\n...",
    "status": "issued"
}
```

### 7. Revoke Certificate
```
POST /api/v1/devices/revoke/{device_id}

Request:
{
    "reason": "Device compromised"
}

Response:
{
    "device_id": "ESP32_01",
    "status": "revoked"
}
```

---

## Integration Flow

### Firmware Upload (Complete Flow)
```
1. Admin uploads firmware
   POST /api/v1/firmware/upload (FOTA)
   
2. FOTA Server processes
   ├─ Save binary
   ├─ Compute SHA-256 hash
   ├─ Sign with Vault KMS
   ├─ Call CMS to register in ledger
   │  POST /api/v1/firmware/upload (CMS)
   │  ├─ CMS saves firmware
   │  ├─ CMS creates ledger entry
   │  └─ CMS returns ledger_hash
   ├─ Store firmware + signature + ledger_hash in DB
   ├─ Publish MQTT notification
   └─ Return success response

3. Device receives notification
   ├─ Queries: GET /api/v1/firmware
   ├─ Gets metadata: GET /api/v1/firmware/{version}/metadata
   ├─ Downloads binary: GET /api/v1/firmware/{version}/binary
   ├─ Validates signature locally
   ├─ Queries ledger: POST /api/v1/ledger/validate-hash
   │  ├─ FOTA queries CMS: POST /api/v1/ledger/validate (CMS)
   │  ├─ CMS validates in blockchain
   │  └─ CMS returns: valid/invalid
   ├─ Installs firmware
   └─ Reports status: POST /api/v1/ledger/update-status
      └─ FOTA updates CMS: POST /api/v1/firmware/update-status (CMS)
```

---

## Python Client Usage

### Initialize
```python
from cms_client import get_cms_client

cms_client = get_cms_client()
```

### Register Device
```python
result = await cms_client.register_device(
    device_id="ESP32_01",
    public_key="-----BEGIN PUBLIC KEY-----\n..."
)
```

### Upload Firmware to Ledger
```python
result = await cms_client.upload_firmware(
    firmware_name="firmware-1.0.0.bin",
    firmware_hash="e3b0c44298fc1c149afbf4c8996fb92427ae41e...",
    firmware_signature="vault:v1:MEUCIQDxK3kH3GHVHYdM6q5ZAG9sMhH+...",
    hardware_target="ESP32-S3",
    version="1.0.0"
)
# Returns: {"firmware": "...", "hash": "...", "status": "stored", "ledger_hash": "..."}
```

### Validate Firmware Hash
```python
result = await cms_client.validate_firmware_hash(
    firmware_hash="e3b0c44298fc1c149afbf4c8996fb92427ae41e...",
    device_id="ESP32_01"
)
# Returns: {"valid": true, "status": "valid"}
```

### Update Device Status
```python
result = await cms_client.update_firmware_status(
    device_id="ESP32_01",
    status="SUCCESS",
    firmware_version="1.0.0",
    details="Installation successful"
)
```

### Issue Certificate
```python
result = await cms_client.issue_certificate(
    device_id="ESP32_01",
    public_key="-----BEGIN PUBLIC KEY-----\n...",
    ttl="365d"
)
```

---

## Database Integration

### CMS Firmware Table Fields
```sql
firmware (
    version TEXT,           -- e.g., "1.0.0"
    hardware_target TEXT,   -- e.g., "ESP32-S3"
    binary_hash TEXT,       -- SHA-256 from FOTA
    signature_hex TEXT,     -- From Vault KMS
    ledger_hash TEXT,       -- From CMS (NEW!)
    ...
)
```

### Ledger Hash Storage
When firmware is uploaded to CMS:
- CMS creates blockchain entry
- CMS returns `ledger_hash` (SHA-256 of blockchain block)
- FOTA stores this `ledger_hash` in database
- Device receives `ledger_hash` in metadata
- Device uses for validation

---

## Environment Variables

```bash
# CMS Connection
export CMS_URL="http://127.0.0.1:8000"
export CMS_API_VERSION="v1"

# Vault KMS (already configured)
export VAULT_URL="http://127.0.0.1:8200"
export VAULT_TOKEN="root"

# MQTT (already configured)
export MQTT_BROKER="mqtt-broker"
```

---

## Status Update Workflow

Device lifecycle status tracking:

```
Device Starts Update
    ↓
DOWNLOADING (getting firmware)
    ↓
VERIFYING (checking signature)
    ↓
INSTALLED (writing to flash)
    ↓
SUCCESS or FAILED
    ↓
[Optional] ROLLBACK (if failed)
```

Each status update is:
1. Logged in FOTA audit trail
2. Sent to CMS ledger (immutable record)
3. Available for querying later

---

## Security Model

```
┌─────────────────────────────────────────────────────┐
│              Security Boundaries                    │
├─────────────────────────────────────────────────────┤
│                                                     │
│  Transport: HTTPS/mTLS                             │
│  ├─ FOTA ↔ Device (mTLS with device certs)         │
│  ├─ FOTA ↔ Vault (HTTPS + token)                   │
│  └─ FOTA ↔ CMS (HTTP dev mode, HTTPS prod)         │
│                                                     │
│  Verification: Digital Signatures                   │
│  ├─ Firmware signed by Vault KMS (ECDSA-SHA256)    │
│  ├─ Signature verified by device                   │
│  └─ Signature stored in CMS ledger                 │
│                                                     │
│  Immutability: Blockchain Ledger                    │
│  ├─ CMS records all firmware uploads                │
│  ├─ CMS records all status updates                  │
│  └─ Ledger entries cannot be modified               │
│                                                     │
│  Integrity: Hash Validation                        │
│  ├─ Device validates hash matches                  │
│  ├─ CMS validates hash in ledger                   │
│  └─ Prevents firmware substitution                 │
│                                                     │
└─────────────────────────────────────────────────────┘
```

---

## Rollback Prevention

```
Device Firmware Update Rule:
    incoming_version > current_version

Implementation:
1. CMS publishes only latest approved firmware
2. Device verifies: new_version > old_version
3. If old_version ≥ new_version, reject update
4. Secure Boot verifies before installation
5. If installation fails, rollback to previous

Immutable Record:
├─ All firmware versions in CMS ledger
├─ All device status updates in ledger
└─ Cannot delete old versions (prevents downgrade)
```

---

## Error Handling

### Common Response Codes
```
200 OK - Success
201 Created - Resource created
400 Bad Request - Invalid input
404 Not Found - Resource not found
500 Internal Server Error - Server error
```

### Error Response Format
```json
{
    "detail": "Error description"
}
```

### Common Errors

**CMS Not Accessible**
```json
{
    "error": "Failed to upload firmware to CMS ledger"
}
```

**Hash Validation Failed**
```json
{
    "valid": false,
    "status": "invalid"
}
```

**Device Not Found**
```json
{
    "detail": "Device ESP32_01 not found"
}
```

---

## Integration Status

| Component | Status | Notes |
|-----------|--------|-------|
| CMS Client | ✅ Complete | All operations implemented |
| Device Registration | ✅ Ready | Can register in CMS |
| Firmware Upload | ✅ Ready | Can register in ledger |
| Ledger Validation | ✅ Ready | Can validate hashes |
| Status Tracking | ✅ Ready | Can track FOTA updates |
| Certificate Management | ✅ Ready | Can issue/revoke certs |
| Rollback Prevention | ✅ Complete | Version checking in place |

---

## Testing

### 1. Check CMS Health
```bash
curl http://127.0.0.1:8000/docs
# Should see Swagger UI
```

### 2. Register Device
```bash
curl -X POST http://127.0.0.1:8000/api/v1/devices/register \
  -H "Content-Type: application/json" \
  -d '{
    "id": "ESP32_TEST",
    "public_key": "-----BEGIN PUBLIC KEY-----\nMFkwEwYHKoZIzj0CAQYIKoZIzj0DAQcDQgAE...\n-----END PUBLIC KEY-----"
  }'
```

### 3. Upload Firmware to Ledger
```bash
curl -X POST http://127.0.0.1:8000/api/v1/firmware/upload \
  -H "Content-Type: application/json" \
  -d '{
    "firmware": "firmware-1.0.0.bin",
    "hash": "e3b0c44298fc1c149afbf4c8996fb92427ae41e...",
    "signature": "vault:v1:MEUCIQDxK3kH3GHVHYdM6q5ZAG9sMhH+...",
    "hardware_target": "ESP32-S3",
    "version": "1.0.0"
  }'
```

### 4. Validate Hash
```bash
curl -X POST http://127.0.0.1:8000/api/v1/ledger/validate \
  -H "Content-Type: application/json" \
  -d '{
    "hash": "e3b0c44298fc1c149afbf4c8996fb92427ae41e...",
    "device_id": "ESP32_TEST"
  }'
```

---

## Production Deployment

### Required Services
- CMS Server (port 8000)
- Vault HSM/KMS (port 8200)
- FOTA Server (port 8081/8443)
- MQTT Broker (port 1883)
- SQLite Database
- Blockchain Service (if not embedded in CMS)

### Configuration
```bash
# .env or docker-compose.yml
CMS_URL=http://cms:8000
VAULT_URL=http://vault:8200
MQTT_BROKER=mqtt-broker
DATABASE_URL=sqlite:///fota.db
```

---

## Questions?

Refer to:
- `app/cms_client.py` — Implementation
- CMS Swagger: http://127.0.0.1:8000/docs
- CMS OpenAPI: http://127.0.0.1:8000/openapi.json
