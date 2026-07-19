# Vault KMS Integration - Testing Guide

## Quick Start Testing

### 1. Verify Vault is Running

```bash
# Check Vault health
curl --header "X-Vault-Token: root" \
     http://127.0.0.1:8200/v1/sys/seal-status
```

Expected response:
```json
{
  "sealed": false,
  "t": 3,
  "n": 5,
  "progress": 0,
  "version": "1.15.0"
}
```

---

### 2. Check FOTA Server Health (Now with Vault Status)

```bash
curl http://localhost:8081/health
```

Expected response:
```json
{
  "status": "healthy",
  "service": "FOTA Orchestrator mTLS Server + Vault KMS",
  "vault_kms": {
    "status": "connected",
    "endpoint": "http://127.0.0.1:8200/v1/"
  },
  "mqtt": {...},
  "channels": {
    "https_transport": "Firmware download (secure)",
    "vault_signing": "Firmware signing with HSM",
    "mqtt_notification": "Update notifications"
  }
}
```

---

### 3. Get Vault Status

```bash
curl http://localhost:8081/api/v1/vault/status
```

Expected response:
```json
{
  "status": "connected",
  "vault_endpoint": "http://127.0.0.1:8200",
  "transit_key": "fota-key",
  "pki_role": "fota-devices",
  "seal_status": {...},
  "ca_certificate_cached": true,
  "ca_certificate_path": "./shared/certs/root_ca.crt"
}
```

---

### 4. Upload Firmware (Signed by Vault)

Create a test firmware file:
```bash
# Create dummy firmware binary
echo "This is test firmware" > firmware_test_1.0.0.bin
```

Upload with Vault signing:
```bash
curl -X POST \
  -H "X-Client-Cert-CN: device-esp32-s3-test" \
  -F "file=@firmware_test_1.0.0.bin" \
  "http://localhost:8081/api/v1/firmware/upload?version=1.0.0&hardware_target=ESP32-S3&urgency=recommended"
```

Expected response:
```json
{
  "status": "success",
  "version": "1.0.0",
  "hardware_target": "ESP32-S3",
  "binary_hash": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
  "binary_size": 19,
  "signature_hex": "vault:v1:MEUCIQDxK3kH3GHVHYdM6q5ZAG9sMhH+Mk5g3zH7YZbWj...",
  "signature_algorithm": "ECDSA-SHA256",
  "signature_source": "Vault Transit Engine (fota-key)",
  "public_key_hex": "{\"keys\":{\"1\":{\"creation_time\":\"...\",\"public_key\":\"-----BEGIN PUBLIC KEY...\"}}",
  "public_key_source": "Vault PKI (fota-devices role)",
  "notification_channel": {
    "mqtt_enabled": true,
    "mqtt_connected": true,
    "mqtt_notification_sent": true
  },
  "timestamp": "2024-01-15T10:30:45.123456Z"
}
```

---

### 5. Verify Signature was Stored

Check database:
```bash
sqlite3 app/fota_orchestrator.db "SELECT version, signature_algorithm, length(signature_hex) as sig_len FROM firmware;"
```

Expected output:
```
1.0.0|ECDSA-SHA256-VAULT|156
```

---

### 6. Test Device Firmware Metadata Retrieval

Register device:
```bash
curl -X POST \
  -H "X-Client-Cert-CN: device-esp32-s3-001" \
  -H "Content-Type: application/json" \
  -d '{
    "device_id": "esp32-s3-001",
    "hardware": "ESP32-S3",
    "certificate_fingerprint": "AB:CD:EF:12:34:56",
    "certificate_expiry": "2025-01-15T00:00:00Z"
  }' \
  http://localhost:8081/api/v1/devices/register
```

Get firmware list:
```bash
curl -H "X-Client-Cert-CN: device-esp32-s3-001" \
  "http://localhost:8081/api/v1/firmware?hardware_target=ESP32-S3"
```

Get firmware metadata (with Vault signature):
```bash
curl -H "X-Client-Cert-CN: device-esp32-s3-001" \
  "http://localhost:8081/api/v1/firmware/1.0.0/metadata"
```

Expected response:
```json
{
  "status": "success",
  "version": "1.0.0",
  "binary_hash": "e3b0c44298fc1c149afbf4c8996fb92427ae41e...",
  "signature_algorithm": "ECDSA-SHA256-VAULT",
  "signature_hex": "vault:v1:MEUCIQDxK3kH3GHVHYdM6q5ZAG9sMhH+...",
  "signature_source": "Vault Transit Engine (ECDSA-SHA256)",
  "public_key_hex": "{\"keys\":{\"1\":{...}}}",
  "public_key_source": "Vault PKI",
  "ledger_hash": "placeholder_ledger_hash"
}
```

---

### 7. Test Vault Direct Signing

Sign a hash directly with Vault:
```bash
# Create test hash
HASH="e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"

# Convert to base64
HASH_B64=$(echo -n $HASH | xxd -r -p | base64)

# Sign with Vault
curl -X POST \
  --header "X-Vault-Token: root" \
  -H "Content-Type: application/json" \
  -d "{\"input\": \"$HASH_B64\"}" \
  http://127.0.0.1:8200/v1/transit/sign/fota-key
```

Expected response:
```json
{
  "data": {
    "signature": "vault:v1:MEUCIQDxK3kH3GHVHYdM6q5ZAG9sMhH+Mk5g3zH7YZbWj...",
    "key_version": 1
  }
}
```

---

### 8. Test Vault Signature Verification

Verify with Vault:
```bash
SIGNATURE="vault:v1:MEUCIQDxK3kH3GHVHYdM6q5ZAG9sMhH+Mk5g3zH7YZbWj..."
HASH_B64="5jJYEcWYQZZiYYeQYcYXAg=="

curl -X POST \
  --header "X-Vault-Token: root" \
  -H "Content-Type: application/json" \
  -d "{\"input\": \"$HASH_B64\", \"signature\": \"$SIGNATURE\"}" \
  http://127.0.0.1:8200/v1/transit/verify/fota-key
```

Expected response:
```json
{
  "data": {
    "valid": true
  }
}
```

---

### 9. Check Root CA Certificate

```bash
# From Vault
curl --header "X-Vault-Token: root" \
  http://127.0.0.1:8200/v1/pki/cert/ca

# Or from local cache
cat ./shared/certs/root_ca.crt
```

---

### 10. Test Audit Trail

Check audit logs for signing operations:
```bash
sqlite3 app/fota_orchestrator.db "SELECT timestamp, action, details FROM audit_logs ORDER BY timestamp DESC LIMIT 5;"
```

Expected output:
```
2024-01-15 10:30:45|FIRMWARE_UPLOADED|Firmware 1.0.0 uploaded, signed by Vault KMS...
2024-01-15 10:30:00|DEVICE_REGISTERED|Device esp32-s3-001 registered...
```

---

## Test Script (Bash)

```bash
#!/bin/bash

echo "=== FOTA Server + Vault KMS Testing ==="

# 1. Check Vault
echo -e "\n1. Checking Vault health..."
curl -s --header "X-Vault-Token: root" \
  http://127.0.0.1:8200/v1/sys/seal-status | jq .sealed

# 2. Check FOTA Server
echo -e "\n2. Checking FOTA Server health..."
curl -s http://localhost:8081/health | jq .vault_kms.status

# 3. Upload firmware
echo -e "\n3. Creating test firmware..."
echo "TEST_FIRMWARE_DATA" > /tmp/firmware.bin

echo -e "\n4. Uploading firmware (will be signed by Vault)..."
UPLOAD_RESPONSE=$(curl -s -X POST \
  -H "X-Client-Cert-CN: test-device" \
  -F "file=@/tmp/firmware.bin" \
  "http://localhost:8081/api/v1/firmware/upload?version=2.0.0&hardware_target=ESP32-S3")

echo "$UPLOAD_RESPONSE" | jq .

# Extract signature
SIGNATURE=$(echo "$UPLOAD_RESPONSE" | jq -r .signature_hex)
echo -e "\n5. Obtained signature: ${SIGNATURE:0:50}..."

# 4. Register device and get firmware
echo -e "\n6. Registering device..."
curl -s -X POST \
  -H "X-Client-Cert-CN: test-device-001" \
  -H "Content-Type: application/json" \
  -d '{
    "device_id": "test-001",
    "hardware": "ESP32-S3",
    "certificate_fingerprint": "AA:BB:CC",
    "certificate_expiry": "2025-01-01T00:00:00Z"
  }' \
  http://localhost:8081/api/v1/devices/register | jq .

# 5. Get firmware metadata
echo -e "\n7. Retrieving firmware metadata..."
curl -s -H "X-Client-Cert-CN: test-device-001" \
  "http://localhost:8081/api/v1/firmware/2.0.0/metadata" | jq .

echo -e "\n=== Testing Complete ==="
```

---

## Expected Results Summary

| Test | Expected | Status |
|------|----------|--------|
| Vault health | sealed=false | ✓ |
| FOTA health | vault_kms.status="connected" | ✓ |
| Upload firmware | signature from Vault | ✓ |
| Firmware metadata | signature_algorithm="ECDSA-SHA256-VAULT" | ✓ |
| Database | signature stored | ✓ |
| Audit log | FIRMWARE_UPLOADED action | ✓ |

---

## Troubleshooting Tests

### Vault not accessible
```bash
# Test connectivity
telnet 127.0.0.1 8200

# Check firewall
netstat -an | grep 8200
```

### Signature invalid
```bash
# Verify the hash was encoded correctly
echo -n "your_hash_here" | xxd -r -p | base64
```

### Database queries
```bash
# Check firmware table
sqlite3 app/fota_orchestrator.db ".schema firmware"

# Check audit logs
sqlite3 app/fota_orchestrator.db "SELECT * FROM audit_logs LIMIT 1;"
```

---

## Performance Baseline

Run multiple uploads to measure:
```bash
for i in {1..10}; do
  time curl -s -X POST \
    -H "X-Client-Cert-CN: test" \
    -F "file=@firmware.bin" \
    "http://localhost:8081/api/v1/firmware/upload?version=$i.0.0&hardware_target=ESP32-S3" > /dev/null
done
```

Expected: ~100-200ms per firmware upload (Vault signing included)

---

## Files for Testing

Create test files:
```bash
# Small binary
dd if=/dev/urandom of=firmware_small.bin bs=1M count=1

# Larger binary
dd if=/dev/urandom of=firmware_large.bin bs=1M count=10

# Text firmware
echo "FOTA Firmware Version 1.0.0" > firmware_text.bin
```

---

Done! Your Vault KMS integration is ready for testing. 🚀
