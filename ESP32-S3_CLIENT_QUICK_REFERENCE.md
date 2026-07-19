# ESP32-S3 FOTA Client - Quick Reference Card

## One-Page Integration Summary

### Base URL & Authentication

```
DEVELOPMENT (Now):
http://localhost:8081
Header: X-Client-Cert-CN: device-esp32-s3-001

PRODUCTION (Future):
https://fota-server.example.com:8443
mTLS: Client certificate (CN=device-esp32-s3-001)
```

---

## API Endpoints

### 1. Register Device
```
POST /api/v1/devices/register
Required: X-Client-Cert-CN header (dev mode) or mTLS cert (prod)

Request:
{
  "device_id": "device-esp32-s3-001",
  "hardware": "ESP32-S3",
  "certificate_fingerprint": "a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0",
  "certificate_expiry": "2026-12-31T23:59:59Z"
}

Response:
{
  "status": "success",
  "device_id": "device-esp32-s3-001",
  "registered_at": "2026-06-17T12:00:00Z"
}
```

### 2. List Firmware
```
GET /api/v1/firmware?hardware_target=ESP32-S3
Required: X-Client-Cert-CN header (dev) or mTLS (prod)

Response:
{
  "status": "success",
  "available_firmware": [
    {
      "version": "1.0.0",
      "binary_hash": "abc123...",
      "ledger_hash": "blockchain_tx_id"
    }
  ]
}
```

### 3. Get Metadata (Signature + Public Key)
```
GET /api/v1/firmware/1.0.0/metadata
Required: X-Client-Cert-CN or mTLS

Response:
{
  "status": "success",
  "version": "1.0.0",
  "binary_hash": "abc123def456...",
  "signature_algorithm": "ECDSA-SHA256",
  "signature_hex": "a1b2c3d4...",
  "public_key_hex": "e5f6a7b8..."
}
```

### 4. Download Binary
```
GET /api/v1/firmware/1.0.0/binary
Required: X-Client-Cert-CN or mTLS

Response: [Raw binary data - NOT JSON]
```

### 5. Validate Against Ledger
```
POST /api/v1/ledger/validate-hash
Required: X-Client-Cert-CN or mTLS

Request:
{
  "firmware_hash": "abc123...",
  "firmware_version": "1.0.0"
}

Response:
{
  "status": "success",
  "ledger_response": {
    "status": "valid",      ← Accept
    // OR "rolled_back"     ← Reject (downgrade prevented)
    // OR "invalid"         ← Reject (tampering detected)
  }
}
```

---

## Device Flow (Simple)

1. Register: `POST /api/v1/devices/register`
2. List: `GET /api/v1/firmware?hardware_target=ESP32-S3`
3. Compare versions → Pick newest
4. Get metadata: `GET /api/v1/firmware/{version}/metadata`
5. Download: `GET /api/v1/firmware/{version}/binary`
6. Verify hash: `computed_hash == metadata.binary_hash`
7. Verify signature: `ecdsa_verify(binary, sig, pubkey)`
8. Validate ledger: `POST /api/v1/ledger/validate-hash`
9. Install if all pass

---

## Cryptography

| Item | Value |
|------|-------|
| Hash Algorithm | SHA-256 |
| Hash Format | Hex string (64 chars) |
| Signature Algorithm | ECDSA with SHA-256 |
| Curve | NIST P-256 (prime256v1) |
| Signature Format | Hex string (128 chars, 64 bytes raw) |
| Public Key Format | Hex uncompressed point (130 chars: 04+X+Y) |

**Verification (pseudocode):**
```c
hash = sha256(firmware_binary)
sig = hex_to_bytes(signature_hex)  // 64 bytes
pubkey = hex_to_point(public_key_hex)  // X, Y coordinates
ecdsa_verify(hash, sig, pubkey) == 0  // Success
```

---

## Headers

```
Development Mode:
Header: X-Client-Cert-CN
Value: device-esp32-s3-001

All Requests:
Header: Content-Type
Value: application/json  (for POST)
```

---

## Ledger Validation Results

| Status | Meaning | Action |
|--------|---------|--------|
| `valid` | Approved in blockchain | Install |
| `invalid` | Not in ledger/tampered | Reject |
| `rolled_back` | Downgrade prevented | Reject |
| `pending_validation` | Awaiting blockchain | Retry |

---

## Error Codes

| Status | Meaning |
|--------|---------|
| 200 | Success |
| 400 | Bad request (invalid JSON) |
| 401 | Missing certificate |
| 403 | Not registered |
| 404 | Firmware not found |
| 500 | Server error |

---

## Debugging

**Test connection:**
```bash
curl -H "X-Client-Cert-CN: device-esp32-s3-001" \
     http://localhost:8081/health
```

**Check server status:**
```bash
curl http://localhost:8081/health
```

**View available endpoints:**
```bash
curl http://localhost:8081/health | python -m json.tool
```

---

## Migration from Mock to Real

| Stage | URL | Auth | Notes |
|-------|-----|------|-------|
| Mock | localhost:8081 | X-Client-Cert-CN header | For testing |
| Dev | localhost:8081 | X-Client-Cert-CN header | Current |
| Prod | fota-server.example.com:8443 | mTLS certificate | Future |

Just change the URL and switch from header to certificate!

---

## Certificate Setup (Production)

**Files needed:**
- `ca.crt` — Root CA (validates server)
- `device.crt` — Device certificate (authenticates device, CN=device-id)
- `device.key` — Device private key (never transmitted)

**Validation:**
- Server cert must be signed by CA
- Device cert CN must match device_id
- All files in PEM format

---

## Device Events (Optional but Recommended)

```
POST /api/v1/audit/device-event

Events:
- FOTA_STARTED
- FOTA_SUCCESS
- FOTA_FAILED
- ROLLBACK_EXECUTED
- FOTA_SIGNATURE_VERIFICATION_FAILED
- FOTA_LEDGER_VALIDATION_FAILED
```

---

## Contact

FOTA Server: [Server IP/hostname]
Server Team: [Contact info]
HSM/KMS: [Contact info for certificates]
CMS: [Contact info for ledger]

---

## Checklist Before Going Live

- [ ] Device registration works
- [ ] Firmware list retrieval works
- [ ] Signature verification works
- [ ] Ledger validation works
- [ ] Device can install firmware
- [ ] Device reboots successfully
- [ ] Device runs new firmware
- [ ] Audit events logged (if enabled)
- [ ] Error handling implemented
- [ ] Tested on real ESP32-S3 hardware
