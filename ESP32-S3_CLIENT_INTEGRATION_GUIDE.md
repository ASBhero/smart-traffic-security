# ESP32-S3 FOTA Client Integration Guide

## Complete API Specification for Real Server Mode

---

## 1. Base Server Connection

### URL, Port, and Protocol

```
Development Mode (Current):
├─ Protocol: HTTP (unencrypted, for testing only)
├─ Host: localhost (or your machine IP)
├─ Port: 8081
├─ Base URL: http://localhost:8081
└─ Requires: X-Client-Cert-CN header (simulates mTLS)

Production Mode (Planned):
├─ Protocol: HTTPS with mTLS
├─ Host: fota-server.example.com
├─ Port: 8443
├─ Base URL: https://fota-server.example.com:8443
├─ Requires: Client certificate (signed by HSM/KMS CA)
└─ No X-Client-Cert-CN header (real TLS cert used)
```

### TLS/mTLS Requirements

```
DEVELOPMENT MODE:
├─ No TLS (HTTP only)
├─ No client certificate needed
├─ Simulated: X-Client-Cert-CN header = device identity
├─ Example: X-Client-Cert-CN: device-001
└─ Use this for testing now

PRODUCTION MODE (Future):
├─ TLS v1.2 minimum (v1.3 supported)
├─ mTLS required:
│  ├─ Client certificate: device certificate (CN = device_id)
│  ├─ Signed by: HSM/KMS CA
│  ├─ Subject: CN=device-{device_id}
│  │   Example: CN=device-esp32-s3-001
│  └─ Certificate chain: device-cert ← HSM/KMS CA ← Root CA
├─ Server certificate: Validated against CA chain
├─ Cipher suites: ECDHE+AESGCM, ChaCha20, DHE variants
└─ Certificate lifecycle: Handled by HSM/KMS team
```

### CA Certificate & Device Certificate

```
Root CA Certificate:
├─ Provided by: HSM/KMS team
├─ Location: /path/to/ca.crt (PEM format)
├─ Usage: Validate server certificate
└─ Update: When HSM/KMS rotates CA

Device Certificate:
├─ Provided by: HSM/KMS team
├─ Subject CN: device-esp32-s3-001 (matches device_id)
├─ Format: PEM
├─ Path: /path/to/device.crt
├─ Private Key: /path/to/device.key
└─ Signed by: HSM/KMS CA (expires in ~1 year)
```

---

## 2. API Endpoints - Complete Specification

### Endpoint 1: Device Registration

```
POST /api/v1/devices/register

DEVELOPMENT MODE:
├─ URL: http://localhost:8081/api/v1/devices/register
├─ Headers:
│  ├─ X-Client-Cert-CN: device-esp32-s3-001  (development simulation)
│  └─ Content-Type: application/json
└─ No TLS certificate needed

PRODUCTION MODE:
├─ URL: https://fota-server.example.com:8443/api/v1/devices/register
├─ Headers:
│  └─ Content-Type: application/json
├─ mTLS: Use device certificate (CN = device_id)
└─ No X-Client-Cert-CN header
```

**Request Body:**
```json
{
  "device_id": "device-esp32-s3-001",
  "hardware": "ESP32-S3",
  "certificate_fingerprint": "a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0",
  "certificate_expiry": "2026-12-31T23:59:59Z",
  "metadata": {
    "firmware_target": "esp32s3",
    "capabilities": ["secure_boot", "flash_encryption", "ota_delta"],
    "current_firmware_version": "0.9.0",
    "mac_address": "AA:BB:CC:DD:EE:FF",
    "flash_size_mb": 8,
    "psram_mb": 8
  }
}
```

**Response (Success):**
```json
{
  "status": "success",
  "certificate_cn": "device-esp32-s3-001",
  "device_id": "device-esp32-s3-001",
  "registered_at": "2026-06-17T12:00:00Z"
}
```

**Response (Already Registered):**
```json
{
  "status": "device_already_registered",
  "certificate_cn": "device-esp32-s3-001",
  "device_id": "device-esp32-s3-001"
}
```

**Error Responses:**
```json
// Missing certificate
{
  "detail": "Missing mTLS client certificate"
}

// Invalid certificate
{
  "detail": "Device certificate not registered"
}

// Server error
{
  "status": "error",
  "message": "Database error or internal server error"
}
```

---

### Endpoint 2: List Available Firmware

```
GET /api/v1/firmware?hardware_target=ESP32-S3

DEVELOPMENT MODE:
├─ URL: http://localhost:8081/api/v1/firmware?hardware_target=ESP32-S3
├─ Headers:
│  └─ X-Client-Cert-CN: device-esp32-s3-001
└─ Query Parameters:
   └─ hardware_target: ESP32-S3 (required)

PRODUCTION MODE:
├─ URL: https://fota-server.example.com:8443/api/v1/firmware?hardware_target=ESP32-S3
├─ mTLS: Automatic device cert validation
└─ Query Parameters:
   └─ hardware_target: ESP32-S3 (required)
```

**Response:**
```json
{
  "status": "success",
  "hardware_target": "ESP32-S3",
  "available_firmware": [
    {
      "version": "1.0.0",
      "hardware_target": "ESP32-S3",
      "binary_hash": "abc123def456abc123def456abc123def456abc123def456abc123def456abc1",
      "rollback_prevention_level": 1,
      "released_at": "2026-06-17T00:00:00Z",
      "ledger_hash": "blockchain_tx_id_v1_0_0"
    },
    {
      "version": "0.9.5",
      "hardware_target": "ESP32-S3",
      "binary_hash": "def456abc123def456abc123def456abc123def456abc123def456abc123def4",
      "rollback_prevention_level": 0,
      "released_at": "2026-06-10T00:00:00Z",
      "ledger_hash": "blockchain_tx_id_v0_9_5"
    }
  ],
  "note": "If MQTT notifications were received, firmware version should match one below"
}
```

**Device Logic:**
```
1. Compare available versions against your current version (0.9.0)
2. Latest version is 1.0.0 (newer than current 0.9.0) → update available
3. Query metadata for version 1.0.0 next
```

---

### Endpoint 3: Get Firmware Metadata (Signature & Public Key)

```
GET /api/v1/firmware/{version}/metadata

DEVELOPMENT MODE:
├─ URL: http://localhost:8081/api/v1/firmware/1.0.0/metadata
├─ Headers:
│  └─ X-Client-Cert-CN: device-esp32-s3-001
└─ Path Parameters:
   └─ version: 1.0.0 (the firmware version you want)

PRODUCTION MODE:
├─ URL: https://fota-server.example.com:8443/api/v1/firmware/1.0.0/metadata
├─ mTLS: Automatic
└─ Path Parameters:
   └─ version: 1.0.0
```

**Response:**
```json
{
  "status": "success",
  "version": "1.0.0",
  "binary_hash": "abc123def456abc123def456abc123def456abc123def456abc123def456abc1",
  "signature_algorithm": "ECDSA-SHA256",
  "signature_hex": "a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3f4a5b6c7d8e9f0a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3f4a5b6c7d8e9f0",
  "public_key_hex": "e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3f4a5b6c7d8e9f0a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3f4a5b6c7d8e9f0",
  "ledger_hash": "blockchain_tx_id_v1_0_0",
  "note": "Device should verify signature and query ledger before installing"
}
```

**Device Logic:**
```
1. Extract public_key_hex (ECDSA public key)
2. Save locally for signature verification later
3. Extract signature_hex (ECDSA signature)
4. Next: Download binary
```

---

### Endpoint 4: Download Firmware Binary

```
GET /api/v1/firmware/{version}/binary

DEVELOPMENT MODE:
├─ URL: http://localhost:8081/api/v1/firmware/1.0.0/binary
├─ Headers:
│  └─ X-Client-Cert-CN: device-esp32-s3-001
├─ Path Parameters:
│  └─ version: 1.0.0
├─ Response: Binary file (octet-stream)
└─ Response Header:
   └─ Content-Type: application/octet-stream
   └─ Content-Disposition: attachment; filename=firmware-1.0.0.bin

PRODUCTION MODE:
├─ URL: https://fota-server.example.com:8443/api/v1/firmware/1.0.0/binary
├─ mTLS: Automatic (encrypted HTTPS)
└─ Response: Binary file (same)
```

**Response Headers:**
```
HTTP/1.1 200 OK
Content-Type: application/octet-stream
Content-Disposition: attachment; filename=firmware-1.0.0.bin
Content-Length: 2097152
Transfer-Encoding: chunked
```

**Response Body:**
```
[Binary firmware data - NOT JSON]
[Raw bytes of the firmware binary]
[Size depends on firmware: typically 2-8 MB for ESP32]
```

**Device Logic:**
```
1. Stream binary to device storage (don't load all in RAM)
2. Save to temporary location
3. Compute SHA-256 hash of downloaded binary
4. Compare hash against binary_hash from metadata
5. If hash matches: signature verification OK
6. If hash doesn't match: reject and report error
7. Next: Verify signature
```

---

### Endpoint 5: Verify Firmware Against Blockchain Ledger

```
POST /api/v1/ledger/validate-hash

DEVELOPMENT MODE:
├─ URL: http://localhost:8081/api/v1/ledger/validate-hash
├─ Headers:
│  ├─ X-Client-Cert-CN: device-esp32-s3-001
│  └─ Content-Type: application/json
└─ Body:
   ├─ firmware_hash: SHA-256 of binary (computed by device)
   └─ firmware_version: Version being validated

PRODUCTION MODE:
├─ URL: https://fota-server.example.com:8443/api/v1/ledger/validate-hash
├─ mTLS: Automatic
└─ Body: Same
```

**Request Body:**
```json
{
  "firmware_hash": "abc123def456abc123def456abc123def456abc123def456abc123def456abc1",
  "firmware_version": "1.0.0"
}
```

**Response (Valid):**
```json
{
  "status": "success",
  "ledger_response": {
    "status": "valid",
    "firmware_hash": "abc123def456abc123def456abc123def456abc123def456abc123def456abc1",
    "timestamp": "2026-06-17T12:00:00Z",
    "message": "Awaiting blockchain CMS validation (colleague's responsibility)"
  }
}
```

**Response (Valid - CMS Integrated):**
```json
{
  "status": "success",
  "ledger_response": {
    "status": "valid",
    "ledger_hash": "blockchain_tx_id_v1_0_0",
    "firmware_hash": "abc123def456abc123def456abc123def456abc123def456abc123def456abc1",
    "timestamp": "2026-06-17T12:00:00Z",
    "confirmed": true,
    "rollback_allowed": false
  }
}
```

**Response (Invalid - Hash Mismatch):**
```json
{
  "status": "success",
  "ledger_response": {
    "status": "invalid",
    "firmware_hash": "abc123def456abc123def456abc123def456abc123def456abc123def456abc1",
    "reason": "Hash not found in blockchain ledger",
    "message": "Firmware has been tampered with or is not approved"
  }
}
```

**Response (Rolled Back - Downgrade Prevented):**
```json
{
  "status": "success",
  "ledger_response": {
    "status": "rolled_back",
    "firmware_hash": "def456abc123def456abc123def456abc123def456abc123def456abc123def4",
    "reason": "Version rejected by CMS rollback prevention policy",
    "current_approved_version": "1.0.0",
    "requested_version": "0.9.5",
    "message": "Cannot downgrade firmware"
  }
}
```

**Device Logic:**
```
1. Query ledger with hash and version
2. Check response status:
   - "valid": Proceed to install
   - "invalid": Reject firmware, report error
   - "rolled_back": Reject downgrade, report error
   - "pending_validation": Wait or retry (CMS integration in progress)
```

**Possible Ledger Statuses:**
```
✅ "valid"                 → Firmware approved, safe to install
❌ "invalid"               → Firmware not in ledger, rejected
❌ "rolled_back"           → Downgrade prevented by policy
⏳ "pending_validation"    → Awaiting blockchain confirmation (retry)
❌ "tampered"              → Hash mismatch, reject
❌ "revoked"               → Firmware revoked, reject
```

---

## 3. Firmware Metadata Sample

### Complete Metadata Example

```json
{
  "version": "1.0.0",
  "version_number": 100,
  "security_version": 5,
  "hardware_target": "ESP32-S3",
  "binary_url": "https://fota-server.example.com:8443/api/v1/firmware/1.0.0/binary",
  "binary_hash": "abc123def456abc123def456abc123def456abc123def456abc123def456abc1",
  "binary_size_bytes": 2097152,
  "image_size": "2MB",
  "signature_hex": "a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3f4a5b6c7d8e9f0a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3f4a5b6c7d8e9f0",
  "signature_algorithm": "ECDSA-SHA256",
  "public_key_hex": "e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3f4a5b6c7d8e9f0a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3f4a5b6c7d8e9f0",
  "ledger_hash": "blockchain_tx_id_v1_0_0",
  "released_at": "2026-06-17T00:00:00Z",
  "rollback_prevention_level": 1,
  "urgency": "recommended",
  "release_notes": "Security patch for WiFi connectivity and improved OTA stability"
}
```

### Field Descriptions

```
version                    → Semantic version (e.g., "1.0.0")
version_number            → Numeric version for comparison (e.g., 100 = v1.0.0)
security_version          → Security patch level (incremented for security fixes)
hardware_target           → Target hardware (e.g., "ESP32-S3")
binary_url                → Direct download URL for binary
binary_hash               → SHA-256 hash of binary (computed by server)
binary_size_bytes         → Size in bytes (for progress tracking)
image_size                → Human-readable size (e.g., "2MB")
signature_hex             → ECDSA signature from HSM/KMS (verify locally)
signature_algorithm       → "ECDSA-SHA256" (always this)
public_key_hex            → ECDSA public key from HSM/KMS (verify signature)
ledger_hash               → Blockchain CMS transaction ID
released_at               → ISO 8601 timestamp
rollback_prevention_level → 0 = allowed, 1 = prevented (policy enforced)
urgency                   → "recommended" or "critical"
release_notes             → User-facing description
```

---

## 4. Cryptographic Details

### Hash Algorithm

```
Algorithm: SHA-256
Format: Hexadecimal string
Length: 64 characters (256 bits)
Example: abc123def456abc123def456abc123def456abc123def456abc123def456abc1

Device Implementation:
├─ Language: C/C++
├─ Library: mbedTLS (esp-idf includes this)
├─ Function: mbedtls_sha256()
└─ Usage:
   uint8_t hash[32];
   mbedtls_sha256(firmware_data, firmware_size, hash, 0);
   // Convert hash to hex string: "abc123..."
```

### Signature Algorithm

```
Algorithm: ECDSA with SHA-256
Curve: NIST P-256 (also called prime256v1 or secp256r1)
Format: DER-encoded (raw bytes)
Total Size: 64 bytes (32 bytes R + 32 bytes S)
Representation: Hexadecimal string (128 characters)

Device Implementation:
├─ Language: C/C++
├─ Library: mbedTLS (or alternative)
├─ Function: mbedtls_ecdsa_verify()
└─ Usage:
   // signature_hex = "a1b2c3d4..." (128 hex chars)
   // Decode hex to 64 bytes
   uint8_t sig[64];
   hex_to_bytes(signature_hex, sig);
   
   // public_key_hex = "e5f6a7b8..." (128 hex chars for coordinates)
   // Decode and construct public key
   mbedtls_ecp_point Q;
   hex_to_ecp_point(public_key_hex, &Q);
   
   // Verify: returns 0 if valid, non-zero if invalid
   result = mbedtls_ecdsa_verify(&grp, hash, hash_len, &Q, &sig_struct);
```

### Public Key Format

```
Format: Hexadecimal string representation of uncompressed point
Structure: 0x04 || X (32 bytes) || Y (32 bytes)
Total: 1 + 32 + 32 = 65 bytes = 130 hex characters

Example public_key_hex:
04e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3f4a5b6c7d8e9f0a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3f4a5b6c7d8e9f0

Parsing:
├─ First byte: 04 (uncompressed point indicator)
├─ Next 32 bytes: X coordinate
└─ Next 32 bytes: Y coordinate

Device Implementation:
```python
import binascii

def hex_to_public_key(hex_string):
    # Convert hex to bytes
    key_bytes = binascii.unhexlify(hex_string)
    
    # Verify length
    assert len(key_bytes) == 65, "Public key must be 65 bytes"
    
    # Verify format
    assert key_bytes[0] == 0x04, "Must be uncompressed point (0x04)"
    
    # Extract X and Y
    X = key_bytes[1:33]   # 32 bytes
    Y = key_bytes[33:65]  # 32 bytes
    
    return X, Y
```

### Signature Verification Example (Pseudocode)

```c
// 1. Download firmware binary
uint8_t firmware[firmware_size];
download_firmware(url, firmware);

// 2. Compute hash
uint8_t hash[32];
mbedtls_sha256(firmware, firmware_size, hash, 0);

// 3. Query ledger
ledger_response = query_ledger(firmware_hash_hex, version);
if (ledger_response.status != "valid") {
    reject_firmware();
    return;
}

// 4. Convert hex strings to bytes
uint8_t sig[64];
hex_to_bytes(signature_hex, sig);

uint8_t pub_key_bytes[65];
hex_to_bytes(public_key_hex, pub_key_bytes);

// 5. Extract public key coordinates
mbedtls_ecp_point Q;
extract_public_key_point(&Q, pub_key_bytes);

// 6. Verify signature
int verify_result = mbedtls_ecdsa_verify(
    &group,          // NIST P-256
    hash,            // SHA-256 of firmware
    32,              // hash length
    &Q,              // Public key point
    &sig             // ECDSA signature (R, S)
);

if (verify_result == 0) {
    // Signature valid!
    install_firmware(firmware);
} else {
    // Signature invalid!
    reject_firmware();
}
```

---

## 5. TLS/mTLS Configuration

### Development Mode (Now)

```
Connection Type: HTTP (unencrypted)
Certificate: None needed
Authentication: X-Client-Cert-CN header

Example Request:
    curl -H "X-Client-Cert-CN: device-esp32-s3-001" \
         http://localhost:8081/api/v1/devices/register \
         -d @request.json

Device Code (ESP32):
    esp_http_client_config_t config = {
        .url = "http://localhost:8081/api/v1/devices/register",
        .event_handler = http_event_handler,
        .method = HTTP_METHOD_POST,
    };
    
    esp_http_client_handle_t client = esp_http_client_init(&config);
    
    // Add header
    esp_http_client_set_header(client, "X-Client-Cert-CN", "device-esp32-s3-001");
    esp_http_client_set_header(client, "Content-Type", "application/json");
    
    // Send
    esp_http_client_perform(client);
```

### Production Mode (Future)

```
Connection Type: HTTPS with mTLS
Port: 8443
Protocol: TLS v1.2 (minimum)

Root CA Certificate:
├─ Provided by: HSM/KMS team
├─ Format: PEM (-----BEGIN CERTIFICATE-----)
├─ Storage: Embedded in firmware or external storage
└─ Purpose: Validate server certificate

Client Certificate:
├─ Provided by: HSM/KMS team
├─ Format: PEM (-----BEGIN CERTIFICATE-----)
├─ Subject CN: device-esp32-s3-001
├─ Storage: Embedded in firmware or external storage
└─ Purpose: Authenticate device to server

Client Private Key:
├─ Format: PEM (-----BEGIN PRIVATE KEY-----)
├─ Storage: Encrypted storage (secure enclave if available)
├─ Access: Device only (never transmitted)
└─ Purpose: Sign TLS handshake

Device Code (ESP32 with mTLS):
    // Root CA certificate (PEM)
    extern const uint8_t ca_cert_pem_start[] asm("_binary_ca_cert_pem_start");
    extern const uint8_t ca_cert_pem_end[] asm("_binary_ca_cert_pem_end");
    
    // Client certificate (PEM)
    extern const uint8_t device_cert_pem_start[] asm("_binary_device_cert_pem_start");
    extern const uint8_t device_cert_pem_end[] asm("_binary_device_cert_pem_end");
    
    // Client private key (PEM)
    extern const uint8_t device_key_pem_start[] asm("_binary_device_key_pem_start");
    extern const uint8_t device_key_pem_end[] asm("_binary_device_key_pem_end");
    
    esp_http_client_config_t config = {
        .url = "https://fota-server.example.com:8443/api/v1/devices/register",
        .event_handler = http_event_handler,
        .method = HTTP_METHOD_POST,
        .cert_pem = (const char *)ca_cert_pem_start,
        .client_cert_pem = (const char *)device_cert_pem_start,
        .client_key_pem = (const char *)device_key_pem_start,
        .skip_cert_common_name_check = false,
    };
```

### Certificate CN Mapping

```
Device ID Format:
└─ device-esp32-s3-{unique_id}

Certificate Subject CN:
└─ device-esp32-s3-001

Validation:
├─ Server extracts CN from client certificate
├─ CN format: device-{hardware_identifier}-{instance}
├─ Device ID matches CN: Registration accepted
├─ Device ID doesn't match CN: Registration rejected
└─ Example: CN "device-esp32-s3-001" → Device ID "device-esp32-s3-001"
```

---

## 6. Audit Event Reporting (Optional but Recommended)

```
POST /api/v1/audit/device-event

DEVELOPMENT MODE:
├─ URL: http://localhost:8081/api/v1/audit/device-event
├─ Headers:
│  ├─ X-Client-Cert-CN: device-esp32-s3-001
│  └─ Content-Type: application/json
└─ Body: Event details

PRODUCTION MODE:
├─ URL: https://fota-server.example.com:8443/api/v1/audit/device-event
├─ mTLS: Automatic
└─ Body: Event details
```

### Supported Audit Events

```
FOTA_STARTED
├─ Triggered: When device begins firmware update
├─ Payload:
    {
      "event": "FOTA_STARTED",
      "firmware_version": "1.0.0",
      "timestamp": "2026-06-17T12:30:00Z"
    }

FOTA_SUCCESS
├─ Triggered: After successful installation and reboot
├─ Payload:
    {
      "event": "FOTA_SUCCESS",
      "firmware_version": "1.0.0",
      "timestamp": "2026-06-17T12:35:00Z"
    }

FOTA_FAILED
├─ Triggered: If update fails at any stage
├─ Payload:
    {
      "event": "FOTA_FAILED",
      "firmware_version": "1.0.0",
      "error_code": "SIGNATURE_VERIFICATION_FAILED",
      "error_message": "ECDSA signature verification failed",
      "timestamp": "2026-06-17T12:30:15Z"
    }

ROLLBACK_EXECUTED
├─ Triggered: If device performs automatic rollback
├─ Payload:
    {
      "event": "ROLLBACK_EXECUTED",
      "failed_version": "1.0.0",
      "rolled_back_version": "0.9.5",
      "reason": "New firmware boot failed",
      "timestamp": "2026-06-17T12:31:00Z"
    }

FOTA_SIGNATURE_VERIFICATION_FAILED
├─ Triggered: Signature verification failed
├─ Payload:
    {
      "event": "FOTA_SIGNATURE_VERIFICATION_FAILED",
      "firmware_version": "1.0.0",
      "reason": "ECDSA verification returned error",
      "timestamp": "2026-06-17T12:30:15Z"
    }

FOTA_LEDGER_VALIDATION_FAILED
├─ Triggered: CMS ledger validation failed
├─ Payload:
    {
      "event": "FOTA_LEDGER_VALIDATION_FAILED",
      "firmware_version": "1.0.0",
      "ledger_status": "rolled_back",
      "reason": "Downgrade prevented by CMS policy",
      "timestamp": "2026-06-17T12:30:20Z"
    }
```

### Request Example (for reference)

```json
{
  "device_id": "device-esp32-s3-001",
  "event": "FOTA_SUCCESS",
  "firmware_version": "1.0.0",
  "timestamp": "2026-06-17T12:35:00Z",
  "duration_seconds": 300,
  "metadata": {
    "reboot_count": 1,
    "total_bytes_downloaded": 2097152,
    "download_speed_kbps": 1024,
    "verification_method": "ECDSA-SHA256"
  }
}
```

### Response Example

```json
{
  "status": "success",
  "event_id": "audit_1234567890",
  "timestamp": "2026-06-17T12:35:00Z",
  "logged_at_server": "2026-06-17T12:35:01Z"
}
```

---

## 7. Error Responses

### HTTP Status Codes

```
200 OK
└─ Request successful, response body contains data

400 Bad Request
├─ Invalid request format (missing required fields)
├─ Invalid JSON
└─ Example: Missing "device_id" in registration request

401 Unauthorized
├─ Missing or invalid certificate/authentication
├─ X-Client-Cert-CN header not provided (development mode)
├─ mTLS certificate not registered (production mode)
└─ Example: Certificate CN not found in device database

403 Forbidden
├─ Device certificate not registered
├─ Certificate CN doesn't match registered device
└─ Example: Attempting to access with unregistered certificate

404 Not Found
├─ Resource not found
├─ Firmware version doesn't exist
├─ Device not registered
└─ Example: GET /api/v1/firmware/99.0.0 (version doesn't exist)

500 Internal Server Error
├─ Server error (database, file system, etc.)
├─ Retry is safe (idempotent operations)
└─ Example: Database connection failure

503 Service Unavailable
├─ Service temporarily unavailable
├─ MQTT broker disconnected (non-critical)
├─ Retry after delay
└─ Example: CMS integration endpoint down
```

### Detailed Error Responses

```json
// Missing certificate (401)
{
  "detail": "Missing mTLS client certificate"
}

// Device not registered (403)
{
  "detail": "Device certificate not registered"
}

// Firmware not found (404)
{
  "status": "error",
  "detail": "Firmware version 99.0.0 not found"
}

// Invalid request (400)
{
  "detail": [
    {
      "type": "missing",
      "loc": ["body", "device_id"],
      "msg": "Field required",
      "input": {}
    }
  ]
}

// Server error (500)
{
  "status": "error",
  "message": "Internal server error",
  "timestamp": "2026-06-17T12:35:00Z"
}
```

---

## 8. Complete Device Integration Flow

### Flow Diagram

```
Device Startup
    │
    ├─→ Check if registered
    │   └─→ If not: POST /api/v1/devices/register
    │       └─→ Provide device_id, hardware, certificate info
    │
    ├─→ Check for firmware updates
    │   ├─→ Option A: Listen for MQTT notifications (optional)
    │   │   └─→ Topic: fota/notifications/ESP32-S3/firmware_available
    │   │   └─→ Extract version from message
    │   │
    │   └─→ Option B: Poll server (fallback)
    │       └─→ GET /api/v1/firmware?hardware_target=ESP32-S3
    │       └─→ Compare versions against current
    │
    ├─→ If update available: Download firmware
    │   ├─→ GET /api/v1/firmware/{version}/metadata
    │   │   └─→ Extract: signature_hex, public_key_hex, ledger_hash
    │   │
    │   ├─→ GET /api/v1/firmware/{version}/binary
    │   │   └─→ Stream binary to storage
    │   │   └─→ Compute SHA-256 hash
    │   │
    │   ├─→ Verify hash matches metadata.binary_hash
    │   │   └─→ If mismatch: Reject, report error
    │   │
    │   ├─→ Verify signature using public_key_hex
    │   │   └─→ If invalid: Reject, report error
    │   │
    │   ├─→ POST /api/v1/ledger/validate-hash
    │   │   └─→ Provide: firmware_hash, firmware_version
    │   │   └─→ Check: ledger_response.status
    │   │       └─→ If "valid": Proceed
    │   │       └─→ If "rolled_back": Reject downgrade
    │   │       └─→ If "invalid": Reject tampered firmware
    │   │
    │   └─→ If all checks pass: Install firmware
    │       ├─→ POST /api/v1/audit/device-event (FOTA_STARTED)
    │       ├─→ Install via OTA mechanism
    │       ├─→ Reboot
    │       ├─→ Verify boot successful
    │       └─→ POST /api/v1/audit/device-event (FOTA_SUCCESS)
    │
    └─→ Sleep 24 hours, repeat
```

---

## 9. Connection Troubleshooting

### Development Mode Issues

```
Issue: "Connection refused"
└─ Solution: Check server is running
   - Run: docker ps (verify fota_backend is UP)
   - Check: http://localhost:8081/health

Issue: "401 Unauthorized"
└─ Solution: Add X-Client-Cert-CN header
   - curl -H "X-Client-Cert-CN: device-esp32-s3-001" ...

Issue: "403 Forbidden"
└─ Solution: Register device first
   - POST /api/v1/devices/register before other requests

Issue: "404 Not Found"
└─ Solution: Check endpoint URL
   - Verify exact path (case-sensitive)
   - Check HTTP method (GET vs POST)
```

### Production Mode Issues

```
Issue: "certificate verify failed"
└─ Solution: Provide root CA certificate
   - Ensure ca_cert_pem is loaded
   - Verify certificate is not expired

Issue: "certificate required"
└─ Solution: Provide client certificate
   - Ensure device_cert_pem is loaded
   - Ensure device_key_pem is loaded

Issue: "CN mismatch"
└─ Solution: Certificate CN must match device_id
   - Certificate CN: device-esp32-s3-001
   - Device ID: device-esp32-s3-001
   - Must be identical
```

---

## 10. Testing Checklist for Device Team

- [ ] Device registration succeeds (POST /api/v1/devices/register)
- [ ] Firmware list retrieval works (GET /api/v1/firmware)
- [ ] Metadata download works (GET /api/v1/firmware/{version}/metadata)
- [ ] Binary download works (GET /api/v1/firmware/{version}/binary)
- [ ] Hash computation matches server hash
- [ ] Signature verification works with public key
- [ ] Ledger validation succeeds (POST /api/v1/ledger/validate-hash)
- [ ] Rollback prevention working (reject downgrades)
- [ ] Error handling for invalid firmware
- [ ] Audit events reported (optional)
- [ ] MQTT notifications received (optional)
- [ ] Fallback to polling works when MQTT unavailable
- [ ] Device successfully installs firmware
- [ ] Device reboots and runs new version

---

## 11. Contact & Support

For integration issues, contact:
- FOTA Server Owner: [Your contact]
- HSM/KMS Team: [Their contact]
- CMS Team: [Their contact]

Share this document with your device team for reference!
