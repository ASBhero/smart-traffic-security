# Complete FOTA System Architecture

## System Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         COMPLETE FOTA ECOSYSTEM                             │
└─────────────────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────────────────┐
│                           SERVER SIDE (Backend)                              │
├──────────────────────────────────────────────────────────────────────────────┤
│                                                                               │
│  ┌────────────────┐    ┌────────────────┐    ┌────────────────┐             │
│  │   HSM/KMS      │    │   CMS          │    │  FOTA Server   │             │
│  │  (Team #1)     │◄───┤  (Team #2)     │◄───│  (Your Task)   │             │
│  │                │    │                │    │                │             │
│  │ • Key Gen      │    │ • Firmware     │    │ • Device Mgmt  │             │
│  │ • Key Storage  │    │   Ledger       │    │ • Firmware Mgmt│             │
│  │ • Crypto Ops   │    │ • Hash Index   │    │ • Pull Srv     │             │
│  │ • PKI          │    │ • Rollback     │    │ • Audit Trail  │             │
│  │                │    │   Prevention   │    │ • MQTT Notif   │             │
│  └────────────────┘    └────────────────┘    └────────────────┘             │
│         ▲                      ▲                      │                      │
│         │                      │                      │                      │
│         │ Sign Firmware        │ Validate Hash       │ Publish to           │
│         │ Get Public Key       │ Check Ledger        │ Devices              │
│         │                      │                      │                      │
│  ┌──────────────────────────────────────────────────────────────┐           │
│  │                   Admin/Management Interface                 │           │
│  │  ┌─────────────┬──────────────┬──────────────┬─────────────┐ │           │
│  │  │ Upload FW   │ Sign with HSM│ Publish CMS  │ Notify      │ │           │
│  │  │ Firmware    │ Keys         │ Ledger Hash  │ Devices    │ │           │
│  │  └─────────────┴──────────────┴──────────────┴─────────────┘ │           │
│  └──────────────────────────────────────────────────────────────┘           │
│                                                                               │
└──────────────────────────────────────────────────────────────────────────────┘

                              NETWORK (Internet)

┌──────────────────────────────────────────────────────────────────────────────┐
│                          CLIENT SIDE (Devices)                               │
├──────────────────────────────────────────────────────────────────────────────┤
│                                                                               │
│  ┌────────────────────────────────────────────────────────────────┐         │
│  │                    FOTA Client (Team #3)                       │         │
│  │  ┌──────────────────────────────────────────────────────────┐  │         │
│  │  │  Device (ESP32, STM32, etc.)                             │  │         │
│  │  │                                                          │  │         │
│  │  │  1. Register via HTTPS/mTLS                             │  │         │
│  │  │     └─ Device cert (signed by HSM/KMS CA)               │  │         │
│  │  │                                                          │  │         │
│  │  │  2. Receive MQTT notification (optional)                │  │         │
│  │  │     └─ "Firmware v1.0.0 available"                      │  │         │
│  │  │                                                          │  │         │
│  │  │  3. Pull firmware list via HTTPS/mTLS                   │  │         │
│  │  │     └─ Encrypted, authenticated                         │  │         │
│  │  │                                                          │  │         │
│  │  │  4. Get metadata (signature + public key)               │  │         │
│  │  │     └─ Public key from HSM/KMS (via FOTA Server)        │  │         │
│  │  │                                                          │  │         │
│  │  │  5. Download binary via HTTPS/mTLS                      │  │         │
│  │  │     └─ Encrypted, integrity protected                   │  │         │
│  │  │                                                          │  │         │
│  │  │  6. Verify signature (device-side)                      │  │         │
│  │  │     └─ Use public key from HSM/KMS to verify            │  │         │
│  │  │     └─ Signature: ECDSA-SHA256                          │  │         │
│  │  │                                                          │  │         │
│  │  │  7. Query CMS ledger via HTTPS/mTLS                     │  │         │
│  │  │     └─ Validate hash on blockchain                      │  │         │
│  │  │     └─ Check for rollback prevention                    │  │         │
│  │  │                                                          │  │         │
│  │  │  8. Install firmware (if all checks pass)               │  │         │
│  │  │     └─ Secure boot verifies signature                   │  │         │
│  │  │     └─ Flash encryption protects code                   │  │         │
│  │  │                                                          │  │         │
│  │  └──────────────────────────────────────────────────────────┘  │         │
│  │                                                                │  │         │
│  │  Physical Boundary (Device):                                  │  │         │
│  │  ├─ Secure Boot (hardware root of trust)                      │  │         │
│  │  ├─ Flash Encryption (code protected)                         │  │         │
│  │  └─ Device Certificate (unique identity)                      │  │         │
│  └────────────────────────────────────────────────────────────────┘         │
│                                                                               │
└──────────────────────────────────────────────────────────────────────────────┘
```

---

## Integration Points: FOTA Server ↔ HSM/KMS

### **1. Firmware Signing (Pre-Upload)**

```
Admin/CI Pipeline
     ↓
HSM/KMS: Sign firmware binary
     │
     ├─ Input: firmware-v1.0.0.bin
     ├─ Algorithm: ECDSA-SHA256
     ├─ Private Key: Held in HSM (never exposed)
     └─ Output: signature_hex (e.g., "a1b2c3d4...")
     ↓
FOTA Server: Store firmware
     │
     ├─ Save binary to disk
     ├─ Store metadata: {version, signature_hex, public_key_hex}
     └─ Publish via MQTT notification
     ↓
Device: Verify signature
     └─ Use public_key_hex to verify signature_hex
```

**API Endpoint Needed (HSM/KMS → FOTA Server):**
```python
@app.post("/api/v1/firmware/sign-and-upload")
async def sign_and_upload_firmware(
    version: str,
    hardware_target: str,
    file: UploadFile
):
    """
    1. Receive firmware from HSM/KMS (already signed)
    2. Extract signature and public key from HSM response
    3. Store firmware with metadata
    4. Publish MQTT notification
    """
    # HSM/KMS colleague provides:
    # - firmware binary
    # - signature_hex
    # - public_key_hex
    # - signature_algorithm (ECDSA-SHA256)
```

---

### **2. Public Key Management**

```
HSM/KMS
├─ Generates key pairs (ECDSA P-256)
├─ Private key: Stored in HSM (never exported)
└─ Public key: Exported to FOTA Server

FOTA Server
├─ Stores public_key_hex in firmware metadata
├─ Serves public key to devices: GET /api/v1/firmware/{version}/metadata
└─ Returns: {signature_hex, public_key_hex, ledger_hash}

Device
├─ Receives public_key_hex via HTTPS/mTLS
├─ Verifies signature locally: verify(signature_hex, binary, public_key_hex)
└─ Installs firmware if valid
```

**Database Schema Update:**
```sql
-- Already in your firmware table:
firmware (
    version TEXT PRIMARY KEY,
    hardware_target TEXT,
    binary_path TEXT,
    binary_hash TEXT,
    signature_algorithm TEXT,  -- "ECDSA-SHA256" (from HSM/KMS)
    signature_hex TEXT,        -- Signature from HSM/KMS
    public_key_hex TEXT,       -- Public key from HSM/KMS
    rollback_prevention_level INTEGER,
    released_at TEXT,
    ledger_hash TEXT,          -- From CMS
    metadata TEXT
)
```

---

### **3. Certificate Chain (Device Authentication)**

```
HSM/KMS: Root CA
├─ Generates root certificate
├─ Generates intermediate CA (if multi-level)
└─ Issues device certificates (signed with HSM private key)

FOTA Server: Verify device certs
├─ Stores CA chain: /app/certs/ca.crt (from HSM/KMS)
├─ Receives device cert in mTLS handshake
└─ Validates: device cert signed by CA from HSM/KMS

Device: Use certificate
├─ Receives device certificate (signed by HSM/KMS CA)
├─ Uses for HTTPS/mTLS connection
└─ FOTA Server validates cert chain
```

**Implementation:**
```python
# In ssl_config.py, the CA certificate is loaded from HSM/KMS:
context.load_verify_locations(
    certfile=os.environ.get('CLIENT_CA_CERT', '/app/certs/ca.crt')
    # ↑ This CA cert should come from HSM/KMS colleague
)
```

---

## Integration Points: FOTA Server ↔ CMS

### **1. Firmware Hash Ledger**

```
FOTA Server: Upload firmware
├─ Compute binary_hash (SHA-256)
└─ Publish to CMS: {version, hardware_target, binary_hash, timestamp}

CMS: Record firmware hash
├─ Store in blockchain ledger
└─ Return: ledger_hash (blockchain transaction ID)

FOTA Server: Store ledger reference
└─ Save ledger_hash in firmware metadata

Device: Validate against ledger
├─ Compute firmware hash after download
├─ Query FOTA Server: POST /api/v1/ledger/validate-hash
├─ FOTA Server queries CMS: "Is this hash in ledger?"
└─ CMS returns: {status: "valid" | "invalid" | "rolled_back"}
```

**API Endpoint (FOTA Server → CMS):**
```python
@app.post("/api/v1/ledger/validate-hash")
async def query_ledger_for_hash(
    request: Request,
    ledger_query: LedgerQueryRequest,
    cert_cn: str = Depends(get_device_certificate_cn)
):
    """
    Device queries CMS through FOTA Server
    """
    device = get_device_from_certificate(cert_cn)
    
    # TODO: Call CMS colleague's API
    # Example:
    cms_response = await query_cms_ledger(
        firmware_hash=ledger_query.firmware_hash,
        firmware_version=ledger_query.firmware_version
    )
    
    # CMS returns: {status: "valid" | "invalid" | "rolled_back", ...}
    return {
        "status": "success",
        "ledger_response": cms_response
    }
```

---

### **2. Rollback Prevention**

```
CMS: Maintain rollback prevention level
├─ Track current approved version
├─ Track previous versions
└─ Prevent devices from downgrading to older versions

FOTA Server: Check rollback level
├─ Store: firmware.rollback_prevention_level
├─ Query CMS for approval before serving firmware
└─ Return to device: "OK to install" or "Rollback prevented"

Device: Respect rollback prevention
├─ Check current firmware version
├─ Query FOTA Server for new version
├─ FOTA Server validates via CMS
└─ Install only if version >= minimum approved
```

**SQL Schema:**
```sql
firmware (
    version TEXT,
    rollback_prevention_level INTEGER,  -- 0 = no prevention, 1 = strict
    -- ...
)

-- CMS records:
approved_versions (
    hardware_target TEXT,
    current_version TEXT,
    min_allowed_version TEXT,
    deprecated_versions TEXT[]  -- cannot downgrade to these
)
```

---

## Complete Data Flow: Firmware Upload to Device Installation

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          COMPLETE WORKFLOW                                  │
└─────────────────────────────────────────────────────────────────────────────┘

STEP 1: Admin Initiates Firmware Release
────────────────────────────────────────
Admin: "Release firmware v1.0.0 for ESP32-S3"
  └─→ HSM/KMS: Sign the binary
      └─→ Input: firmware-v1.0.0.bin
      └─→ Output: {signature_hex, public_key_hex}

STEP 2: Upload to FOTA Server
──────────────────────────────
HSM/KMS: POST /api/v1/firmware/upload
  ├─ Body: {version, hardware_target, binary, signature_hex, public_key_hex}
  └─→ FOTA Server stores firmware + metadata

STEP 3: Publish to CMS Ledger
──────────────────────────────
FOTA Server: Compute binary_hash (SHA-256)
  └─→ CMS: "Register firmware v1.0.0 hash: abc123def456..."
      └─→ CMS records in blockchain ledger
      └─→ CMS returns: ledger_hash (blockchain tx ID)

STEP 4: FOTA Server Stores Complete Metadata
──────────────────────────────────────────────
Database entry:
{
  version: "1.0.0",
  hardware_target: "ESP32-S3",
  binary_hash: "abc123def456...",
  signature_hex: "signature_from_hsm_kms",
  public_key_hex: "public_key_from_hsm_kms",
  ledger_hash: "blockchain_tx_id",
  rollback_prevention_level: 1
}

STEP 5: Notify Devices (MQTT)
──────────────────────────────
FOTA Server: Publish to MQTT
  └─→ Topic: fota/notifications/ESP32-S3/firmware_available
  └─→ Message: {version, urgency, binary_hash, ledger_hash}

STEP 6: Device Receives Notification
─────────────────────────────────────
Device: Receives MQTT notification instantly
  └─→ "Firmware v1.0.0 available for ESP32-S3"

STEP 7: Device Registration (first time)
─────────────────────────────────────────
Device: POST /api/v1/devices/register
  ├─ Headers: X-Client-Cert-CN = device-001
  ├─ Cert: Signed by HSM/KMS CA
  └─→ FOTA Server validates cert chain
      └─→ Stores device in database

STEP 8: Device Pulls Firmware List
──────────────────────────────────
Device: GET /api/v1/firmware?hardware_target=ESP32-S3
  ├─ Auth: mTLS (device cert from HSM/KMS)
  └─→ FOTA Server returns available versions

STEP 9: Device Pulls Metadata
──────────────────────────────
Device: GET /api/v1/firmware/1.0.0/metadata
  ├─ Auth: mTLS
  └─→ FOTA Server returns:
      {
        binary_hash: "abc123def456...",
        signature_hex: "signature_from_hsm_kms",
        public_key_hex: "public_key_from_hsm_kms",
        ledger_hash: "blockchain_tx_id"
      }

STEP 10: Device Downloads Binary
─────────────────────────────────
Device: GET /api/v1/firmware/1.0.0/binary
  ├─ Auth: mTLS (encrypted channel)
  └─→ FOTA Server streams firmware binary

STEP 11: Device Verifies Signature (Local)
───────────────────────────────────────────
Device: verify_signature(binary, signature_hex, public_key_hex)
  ├─ Algorithm: ECDSA-SHA256
  ├─ Public key: Received from FOTA Server (from HSM/KMS)
  └─→ Result: "Signature valid" or "Signature invalid" (reject)

STEP 12: Device Queries CMS Ledger
──────────────────────────────────
Device: POST /api/v1/ledger/validate-hash
  ├─ Body: {firmware_hash, firmware_version}
  └─→ FOTA Server: Query CMS colleague's ledger API
      └─→ CMS: Check blockchain for hash match
      └─→ CMS: Check rollback prevention
      └─→ CMS returns: {status: "valid", ledger_hash: "..."}

STEP 13: Device Checks Rollback Prevention
───────────────────────────────────────────
Device: Compare current_version vs new_version
  ├─ Current: v0.9.0
  ├─ New: v1.0.0
  ├─ CMS approved: v1.0.0 >= min_allowed
  └─→ OK to install

STEP 14: Device Installs Firmware
──────────────────────────────────
Device: Install firmware
  ├─ 1. Verify signature (done in step 11)
  ├─ 2. Verify ledger (done in step 12)
  ├─ 3. Secure boot checks signature again (hardware)
  ├─ 4. Flash encryption protects installation
  └─→ Firmware installed successfully

STEP 15: Device Reports Status
───────────────────────────────
Device: POST /api/v1/audit/pull-event (optional)
  └─→ FOTA Server logs: "device-001: FIRMWARE_INSTALLED v1.0.0"

STEP 16: Device Next Check
──────────────────────────
Device: Waits for next notification (MQTT) or polls after 24h
  └─→ Loop back to STEP 6
```

---

## Integration Checklist

### **HSM/KMS Team Responsibilities** (Team #1)

- [ ] Generate ECDSA P-256 key pairs for firmware signing
- [ ] Export public keys to FOTA Server (secure handoff)
- [ ] Generate CA certificate for device authentication
- [ ] Issue device certificates (one per device) signed with HSM key
- [ ] Provide API endpoint: `/sign-firmware` (HSM signs binaries)
- [ ] Provide API endpoint: `/verify-public-key` (returns public key hex)
- [ ] Document: Key rotation policy, certificate expiry, revocation process

### **CMS Team Responsibilities** (Team #2)

- [ ] Implement blockchain ledger (store firmware hashes)
- [ ] Provide API endpoint: `/register-firmware-hash` (record in ledger)
- [ ] Provide API endpoint: `/validate-firmware-hash` (check ledger)
- [ ] Implement rollback prevention logic
- [ ] Provide API endpoint: `/check-rollback-prevention`
- [ ] Track firmware versions and rollback history
- [ ] Document: Ledger format, transaction IDs, API contracts

### **FOTA Server Responsibilities** (Your Task)

- [x] Device registration with mTLS certificates (from HSM/KMS)
- [x] Firmware management (upload, store, serve)
- [x] Firmware metadata with signature and public key (from HSM/KMS)
- [x] Ledger integration (query CMS, return validation status)
- [x] Immutable audit trail
- [x] MQTT notifications (optional)
- [ ] **NEW:** Integrate HSM/KMS signing endpoint
- [ ] **NEW:** Validate device certs against HSM/KMS CA
- [ ] **NEW:** Call CMS ledger validation APIs

### **FOTA Client Responsibilities** (Team #4)

- [ ] Device certificate (signed by HSM/KMS)
- [ ] mTLS connection to FOTA Server
- [ ] Firmware download via HTTPS/mTLS
- [ ] Signature verification (using public key from FOTA Server)
- [ ] CMS ledger validation
- [ ] Secure boot verification
- [ ] Flash encryption

---

## Remaining Integration Work for FOTA Server

### **1. HSM/KMS Integration Endpoint**

Add to `main.py`:

```python
@app.post("/api/v1/firmware/sign-and-upload")
async def sign_and_upload_firmware(
    version: str,
    hardware_target: str,
    urgency: str = "recommended",
    file: UploadFile = File(...)
):
    """
    Receive pre-signed firmware from HSM/KMS
    """
    # Call HSM/KMS: Sign the firmware
    hsm_response = await call_hsm_kms_sign(
        firmware_binary=await file.read(),
        algorithm="ECDSA-SHA256"
    )
    
    signature_hex = hsm_response["signature_hex"]
    public_key_hex = hsm_response["public_key_hex"]
    
    # Store in database with signature from HSM/KMS
    # ... (rest of upload logic)
    
    return {
        "status": "success",
        "version": version,
        "signed_by": "HSM/KMS",
        "signature_hex": signature_hex,
        "public_key_hex": public_key_hex
    }
```

### **2. CMS Ledger Integration Endpoint**

Already exists, but needs HSM/KMS call:

```python
@app.post("/api/v1/ledger/validate-hash")
async def query_ledger_for_hash(
    request: Request,
    ledger_query: LedgerQueryRequest,
    cert_cn: str = Depends(get_device_certificate_cn)
):
    """
    Query CMS ledger for firmware hash validation
    """
    # Call CMS: Validate hash
    cms_response = await call_cms_ledger_validate(
        firmware_hash=ledger_query.firmware_hash,
        firmware_version=ledger_query.firmware_version
    )
    
    return {
        "status": "success",
        "ledger_response": cms_response
    }
```

### **3. Environment Variables for Team Integrations**

Add to `.env`:

```bash
# HSM/KMS Integration
HSM_KMS_ENDPOINT=http://hsm-kms-server:8080
HSM_KMS_API_KEY=your-api-key
HSM_SIGN_ALGORITHM=ECDSA-SHA256
HSM_CLIENT_CA_CERT=/app/certs/hsm-ca.crt

# CMS Integration
CMS_ENDPOINT=http://cms-server:8080
CMS_API_KEY=your-api-key
CMS_LEDGER_TYPE=blockchain

# MQTT
MQTT_BROKER=mqtt-broker
MQTT_PORT=1883
```

---

## System Security Properties

```
┌─────────────────────────────────────────────────────────────────┐
│                    SECURITY GUARANTEES                          │
└─────────────────────────────────────────────────────────────────┘

Transport Boundary (HTTPS/mTLS)
├─ Device identity: Certificate (signed by HSM/KMS CA)
├─ Server identity: Certificate
├─ Encryption: TLS v1.2
├─ Authentication: Mutual
└─ Guarantee: Only authenticated devices reach firmware

Verification Boundary (Asymmetric Signing)
├─ Firmware signed: With HSM/KMS private key
├─ Device verifies: With public key from FOTA Server
├─ Algorithm: ECDSA-SHA256
├─ Hash verified: SHA-256
└─ Guarantee: Firmware authenticity and integrity

Ledger Boundary (Blockchain CMS)
├─ Firmware hash: Recorded on blockchain
├─ Rollback: Prevented by CMS policy
├─ Tampering: Detected by ledger
├─ Audit: Immutable blockchain history
└─ Guarantee: No firmware substitution or rollback

Physical Boundary (Device Hardware)
├─ Root of trust: Secure boot (hardware)
├─ Code protection: Flash encryption
├─ Key storage: Secure enclave
└─ Guarantee: Firmware cannot be replaced or read unencrypted
```

---

## Next Steps

1. **HSM/KMS Team:** Provide endpoint for firmware signing
2. **CMS Team:** Provide endpoint for ledger validation
3. **Your Server:** Implement integration calls to HSM/KMS and CMS
4. **FOTA Client Team:** Implement device-side verification and ledger checks
5. **All Teams:** Document API contracts and error handling

This completes the **Ultimate Security Architecture** with all four components working together.
