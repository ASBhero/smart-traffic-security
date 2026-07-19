# CMS Integration - Testing & Deployment Guide

## Quick Start

### 1. Start All Services

```bash
# Terminal 1: Start CMS (if not running)
cd /path/to/cms-project
docker compose up

# Terminal 2: Start FOTA Server (from project root)
docker compose up --build
```

### 2. Verify CMS is Running

```bash
# Check CMS API
curl http://127.0.0.1:8000/docs

# Should show Swagger UI
```

### 3. Verify FOTA + CMS Integration

```bash
curl http://localhost:8081/api/v1/cms/status

# Expected:
{
  "status": "connected",
  "cms_endpoint": "http://127.0.0.1:8000",
  "api_version": "v1",
  "features": [...]
}
```

---

## Testing Workflow

### Step 1: Register Device

```bash
# FOTA Server
curl -X POST \
  -H "X-Client-Cert-CN: test-device-001" \
  -H "Content-Type: application/json" \
  -d '{
    "device_id": "ESP32-001",
    "hardware": "ESP32-S3",
    "certificate_fingerprint": "AA:BB:CC:DD",
    "certificate_expiry": "2025-01-15T00:00:00Z"
  }' \
  http://localhost:8081/api/v1/devices/register
```

Expected response:
```json
{
  "status": "success",
  "certificate_cn": "test-device-001",
  "device_id": "ESP32-001",
  "cms_registered": true,
  "registered_at": "2024-01-15T10:30:45Z"
}
```

### Step 2: Create Test Firmware

```bash
# Create dummy firmware file
echo "ESP32-S3 Firmware Version 1.0.0" > firmware_v1.0.0.bin

# Or random binary
dd if=/dev/urandom of=firmware_v1.0.0.bin bs=1M count=1
```

### Step 3: Upload Firmware (Vault Signs + CMS Ledger)

```bash
curl -X POST \
  -H "X-Client-Cert-CN: admin-device" \
  -F "file=@firmware_v1.0.0.bin" \
  "http://localhost:8081/api/v1/firmware/upload?version=1.0.0&hardware_target=ESP32-S3&urgency=recommended"
```

Expected response:
```json
{
  "status": "success",
  "version": "1.0.0",
  "binary_hash": "e3b0c44298fc1c149afbf4c8996fb92427ae41e...",
  "signature_hex": "vault:v1:MEUCIQDxK3kH3GHVHYdM6q5ZAG9sMhH+...",
  "signature_source": "Vault Transit Engine (fota-key)",
  "public_key_source": "Vault PKI (fota-devices role)",
  "ledger_hash": "abc123def456...",
  "ledger_source": "CMS Blockchain",
  "cms_status": "registered",
  "channels": {
    "transport": "HTTPS (secure upload)",
    "signing": "Vault Transit Engine (HSM-backed)",
    "ledger": "CMS Blockchain (immutable)",
    "notification": "MQTT"
  }
}
```

### Step 4: Device Pulls Firmware List

```bash
curl -H "X-Client-Cert-CN: test-device-001" \
  "http://localhost:8081/api/v1/firmware?hardware_target=ESP32-S3"
```

Expected response:
```json
{
  "status": "success",
  "hardware_target": "ESP32-S3",
  "available_firmware": [
    {
      "version": "1.0.0",
      "hardware_target": "ESP32-S3",
      "binary_hash": "e3b0c44298fc1c149afbf4c8996fb92427ae41e...",
      "ledger_hash": "abc123def456...",
      "released_at": "2024-01-15T10:30:45Z"
    }
  ]
}
```

### Step 5: Device Pulls Firmware Metadata

```bash
curl -H "X-Client-Cert-CN: test-device-001" \
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
  "public_key_hex": "{\"keys\":{...}}",
  "public_key_source": "Vault PKI",
  "ledger_hash": "abc123def456...",
  "ledger_source": "CMS Blockchain"
}
```

### Step 6: Device Validates in CMS Ledger

```bash
curl -X POST \
  -H "X-Client-Cert-CN: test-device-001" \
  -H "Content-Type: application/json" \
  -d '{
    "firmware_hash": "e3b0c44298fc1c149afbf4c8996fb92427ae41e...",
    "firmware_version": "1.0.0"
  }' \
  http://localhost:8081/api/v1/ledger/validate-hash
```

Expected response:
```json
{
  "status": "success",
  "ledger_response": {
    "status": "valid",
    "firmware_hash": "e3b0c44298fc1c149afbf4c8996fb92427ae41e...",
    "source": "CMS Blockchain Ledger",
    "ledger_hash": "abc123def456...",
    "timestamp": "2024-01-15T10:30:45Z"
  }
}
```

### Step 7: Download Firmware Binary

```bash
curl -H "X-Client-Cert-CN: test-device-001" \
  "http://localhost:8081/api/v1/firmware/1.0.0/binary" \
  -o firmware_downloaded.bin
```

### Step 8: Check Audit Trail

```bash
curl -H "X-Client-Cert-CN: test-device-001" \
  "http://localhost:8081/api/v1/audit/pull-events"
```

Expected response:
```json
{
  "status": "success",
  "device_certificate_cn": "test-device-001",
  "device_id": "ESP32-001",
  "audit_trail": [
    {
      "action": "LEDGER_VALIDATION_QUERIED",
      "timestamp": "2024-01-15T10:30:50Z",
      "details": "Ledger query for e3b0c44298fc1c149afbf4c8996fb92427ae41e...: valid"
    },
    {
      "action": "FIRMWARE_BINARY_PULLED",
      "timestamp": "2024-01-15T10:30:48Z"
    },
    {
      "action": "FIRMWARE_METADATA_PULLED",
      "timestamp": "2024-01-15T10:30:47Z"
    },
    ...
  ]
}
```

---

## Data Flow Verification

### 1. Check Database

```bash
# Firmware stored with ledger hash
sqlite3 app/fota_orchestrator.db \
  "SELECT version, cms_status, length(ledger_hash) as ledger_hash_len FROM firmware;"

# Expected:
# 1.0.0|registered|32
```

### 2. Check CMS Blockchain

```bash
# Query CMS directly
curl http://127.0.0.1:8000/api/v1/ledger/status/e3b0c44298fc1c149afbf4c8996fb92427ae41e...

# Should return blockchain entry
```

### 3. Check Audit Logs

```bash
sqlite3 app/fota_orchestrator.db \
  "SELECT action, details FROM audit_logs ORDER BY timestamp DESC LIMIT 5;"
```

---

## Complete Bash Test Script

```bash
#!/bin/bash

set -e  # Exit on error

echo "=== FOTA Server + Vault KMS + CMS Ledger Integration Test ==="

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 1. Health checks
echo -e "\n${BLUE}1. Checking service health...${NC}"

echo -n "  Vault: "
curl -s http://127.0.0.1:8200/v1/sys/seal-status | jq -r .sealed

echo -n "  CMS: "
curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:8000/docs

echo -n "  FOTA: "
curl -s http://localhost:8081/health | jq -r .status

# 2. Register device
echo -e "\n${BLUE}2. Registering device in FOTA...${NC}"
REG_RESPONSE=$(curl -s -X POST \
  -H "X-Client-Cert-CN: test-device-001" \
  -H "Content-Type: application/json" \
  -d '{
    "device_id": "ESP32-TEST-001",
    "hardware": "ESP32-S3",
    "certificate_fingerprint": "AA:BB:CC",
    "certificate_expiry": "2025-01-15T00:00:00Z"
  }' \
  http://localhost:8081/api/v1/devices/register)

echo "  Device ID: $(echo $REG_RESPONSE | jq -r .device_id)"
echo "  CMS Registered: $(echo $REG_RESPONSE | jq -r .cms_registered)"

# 3. Create test firmware
echo -e "\n${BLUE}3. Creating test firmware...${NC}"
echo "Test firmware content" > /tmp/firmware.bin
echo "  File size: $(stat -f%z /tmp/firmware.bin 2>/dev/null || stat -c%s /tmp/firmware.bin) bytes"

# 4. Upload firmware
echo -e "\n${BLUE}4. Uploading firmware (Vault signs, CMS ledgers)...${NC}"
UPLOAD_RESPONSE=$(curl -s -X POST \
  -H "X-Client-Cert-CN: admin" \
  -F "file=@/tmp/firmware.bin" \
  "http://localhost:8081/api/v1/firmware/upload?version=1.0.0&hardware_target=ESP32-S3")

FIRMWARE_HASH=$(echo $UPLOAD_RESPONSE | jq -r .binary_hash)
SIGNATURE=$(echo $UPLOAD_RESPONSE | jq -r .signature_hex)
LEDGER_HASH=$(echo $UPLOAD_RESPONSE | jq -r .ledger_hash)
CMS_STATUS=$(echo $UPLOAD_RESPONSE | jq -r .cms_status)

echo "  Hash: ${FIRMWARE_HASH:0:16}..."
echo "  Signature: ${SIGNATURE:0:20}..."
echo "  Ledger Hash: $LEDGER_HASH"
echo "  CMS Status: $CMS_STATUS"

# 5. Device pulls firmware list
echo -e "\n${BLUE}5. Device pulling firmware list...${NC}"
FIRMWARE_LIST=$(curl -s -H "X-Client-Cert-CN: test-device-001" \
  "http://localhost:8081/api/v1/firmware?hardware_target=ESP32-S3")

AVAILABLE=$(echo $FIRMWARE_LIST | jq '.available_firmware | length')
echo "  Available firmware versions: $AVAILABLE"

# 6. Device pulls metadata
echo -e "\n${BLUE}6. Device pulling firmware metadata...${NC}"
METADATA=$(curl -s -H "X-Client-Cert-CN: test-device-001" \
  "http://localhost:8081/api/v1/firmware/1.0.0/metadata")

echo "  Signature Source: $(echo $METADATA | jq -r .signature_source)"
echo "  Public Key Source: $(echo $METADATA | jq -r .public_key_source)"
echo "  Ledger Source: $(echo $METADATA | jq -r .ledger_source)"

# 7. Device queries ledger
echo -e "\n${BLUE}7. Device querying CMS ledger...${NC}"
LEDGER=$(curl -s -X POST \
  -H "X-Client-Cert-CN: test-device-001" \
  -H "Content-Type: application/json" \
  -d "{
    \"firmware_hash\": \"$FIRMWARE_HASH\",
    \"firmware_version\": \"1.0.0\"
  }" \
  http://localhost:8081/api/v1/ledger/validate-hash)

LEDGER_STATUS=$(echo $LEDGER | jq -r .ledger_response.status)
echo "  Ledger Validation: ${GREEN}$LEDGER_STATUS${NC}"

# 8. Check audit trail
echo -e "\n${BLUE}8. Checking audit trail...${NC}"
AUDIT=$(curl -s -H "X-Client-Cert-CN: test-device-001" \
  "http://localhost:8081/api/v1/audit/pull-events?limit=3")

AUDIT_COUNT=$(echo $AUDIT | jq '.audit_trail | length')
echo "  Recent audit entries: $AUDIT_COUNT"

echo -e "\n${GREEN}=== All tests completed successfully! ===${NC}"
```

Save as `test_cms_integration.sh`:
```bash
chmod +x test_cms_integration.sh
./test_cms_integration.sh
```

---

## Expected Test Results

| Test | Expected | Status |
|------|----------|--------|
| Vault health | sealed=false | ✓ |
| CMS health | HTTP 200 | ✓ |
| FOTA health | status=healthy | ✓ |
| Device registration | cms_registered=true | ✓ |
| Firmware upload | cms_status=registered | ✓ |
| Firmware metadata | ledger_source=CMS Blockchain | ✓ |
| Ledger validation | status=valid | ✓ |
| Audit trail | entries > 0 | ✓ |

---

## Troubleshooting

### CMS Not Accessible
```bash
# Check CMS running
curl http://127.0.0.1:8000/docs

# Check network
netstat -an | grep 8000

# View CMS logs
docker logs <cms-container>
```

### Ledger Validation Failing
```bash
# Check hash is correct
echo -n "data" | sha256sum

# Verify CMS API directly
curl -X POST http://127.0.0.1:8000/api/v1/ledger/validate \
  -H "Content-Type: application/json" \
  -d '{"hash": "...", "device_id": "ESP32-001"}'
```

### Database Issues
```bash
# Check firmware table
sqlite3 app/fota_orchestrator.db "SELECT * FROM firmware LIMIT 1;"

# Check ledger entries
sqlite3 app/fota_orchestrator.db "SELECT * FROM ledger_queries LIMIT 1;"
```

---

## Environment Variables

Create `.env` file:
```bash
# FOTA Server
VAULT_URL=http://127.0.0.1:8200
VAULT_TOKEN=root
CMS_URL=http://127.0.0.1:8000
MQTT_BROKER=mqtt-broker

# CMS
CMS_API_VERSION=v1
DATABASE_URL=sqlite:///cms.db
UPLOAD_DIRECTORY=./firmware
```

---

## Performance

Benchmark complete firmware upload flow:

```bash
# Upload 10 different firmware versions
for i in {1..10}; do
  echo "Firmware v$i" > /tmp/firmware_v$i.bin
  
  time curl -s -X POST \
    -H "X-Client-Cert-CN: admin" \
    -F "file=@/tmp/firmware_v$i.bin" \
    "http://localhost:8081/api/v1/firmware/upload?version=$i.0.0&hardware_target=ESP32-S3" \
    > /dev/null
done
```

Expected: ~200-300ms per firmware (Vault signing + CMS ledger)

---

## Production Checklist

- [ ] Vault running and healthy
- [ ] CMS running and healthy
- [ ] FOTA Server connected to both
- [ ] Firmware successfully signs with Vault
- [ ] Firmware successfully ledgers in CMS
- [ ] Device can pull and validate
- [ ] Audit trail complete
- [ ] MQTT notifications working
- [ ] Database backed up
- [ ] Logs configured

---

Done! Your complete FOTA system is ready. 🚀
