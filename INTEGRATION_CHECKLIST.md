# FOTA Server Integration Checklist

## Your Role: Bridge Between Teams

You are the **central integration point** connecting:
- **HSM/KMS Team** (firmware signing, device certs, key management)
- **CMS Team** (ledger validation, rollback prevention)
- **FOTA Client Team** (devices pulling firmware)

---

## HSM/KMS Integration Tasks

### Phase 1: Understand HSM/KMS Team's Deliverables

- [ ] **Ask HSM/KMS Team:**
  - What endpoint signs firmware? (e.g., `POST /sign`)
  - What format do they return signature and public key in?
  - How do they export CA certificate for device verification?
  - What algorithm do they use? (e.g., ECDSA-SHA256)
  - How are device certificates issued?
  - What's the certificate CN format? (e.g., `device-{device_id}`)
  - Certificate validity period?
  - Revocation mechanism?

- [ ] **Receive from HSM/KMS:**
  - [ ] Endpoint URL: `http://<hsm-kms-server>:<port>`
  - [ ] API documentation
  - [ ] CA certificate (to validate device certs)
  - [ ] Example request/response JSON
  - [ ] API key or authentication method

### Phase 2: Add HSM/KMS Config to FOTA Server

Create `./app/hsm_kms_client.py`:

```python
import os
import httpx
import json
from typing import Optional

class HSMKMSClient:
    def __init__(self, endpoint: str = None, api_key: str = None):
        self.endpoint = endpoint or os.getenv("HSM_KMS_ENDPOINT", "http://hsm-kms:8080")
        self.api_key = api_key or os.getenv("HSM_KMS_API_KEY")
    
    async def sign_firmware(self, firmware_binary: bytes, algorithm: str = "ECDSA-SHA256"):
        """
        Call HSM/KMS to sign firmware
        Returns: {signature_hex, public_key_hex, algorithm}
        """
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.endpoint}/sign",
                headers={"Authorization": f"Bearer {self.api_key}"},
                json={
                    "binary": firmware_binary.hex(),
                    "algorithm": algorithm
                }
            )
            if response.status_code == 200:
                return response.json()  # {signature_hex, public_key_hex}
            else:
                raise Exception(f"HSM/KMS signing failed: {response.text}")
    
    async def get_public_key(self, key_id: str):
        """Get public key from HSM/KMS"""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.endpoint}/public-key/{key_id}",
                headers={"Authorization": f"Bearer {self.api_key}"}
            )
            return response.json()  # {public_key_hex}
    
    async def get_ca_certificate(self):
        """Get CA certificate for device verification"""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.endpoint}/ca-certificate",
                headers={"Authorization": f"Bearer {self.api_key}"}
            )
            return response.text  # PEM certificate
```

- [ ] Update `requirements.txt` to add `httpx>=0.24.0`
- [ ] Add environment variables to docker-compose.yaml:
  ```yaml
  environment:
    - HSM_KMS_ENDPOINT=http://hsm-kms:8080
    - HSM_KMS_API_KEY=${HSM_KMS_API_KEY}
  ```

### Phase 3: Integrate HSM/KMS into Firmware Upload

- [ ] Modify `/api/v1/firmware/upload` to call HSM/KMS for signing
- [ ] Store `signature_hex` and `public_key_hex` in database
- [ ] Validate CA certificate chain from HSM/KMS

---

## CMS Integration Tasks

### Phase 1: Understand CMS Team's Deliverables

- [ ] **Ask CMS Team:**
  - What endpoint registers firmware hashes?
  - What endpoint validates firmware hashes?
  - What format do they return ledger validation?
  - How do they handle rollback prevention?
  - What blockchain are they using?
  - What's the transaction ID format?
  - How do they track firmware versions?
  - API response format on success/failure?

- [ ] **Receive from CMS:**
  - [ ] Endpoint URL: `http://<cms-server>:<port>`
  - [ ] API documentation
  - [ ] Example request/response JSON
  - [ ] Rollback prevention logic
  - [ ] API key or authentication method

### Phase 2: Add CMS Config to FOTA Server

Create `./app/cms_client.py`:

```python
import os
import httpx
import json
from typing import Optional

class CMSClient:
    def __init__(self, endpoint: str = None, api_key: str = None):
        self.endpoint = endpoint or os.getenv("CMS_ENDPOINT", "http://cms:8080")
        self.api_key = api_key or os.getenv("CMS_API_KEY")
    
    async def register_firmware_hash(self, firmware_hash: str, version: str, 
                                    hardware_target: str):
        """
        Register firmware hash in CMS blockchain ledger
        Returns: {ledger_hash, timestamp, status}
        """
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.endpoint}/ledger/register",
                headers={"Authorization": f"Bearer {self.api_key}"},
                json={
                    "firmware_hash": firmware_hash,
                    "version": version,
                    "hardware_target": hardware_target,
                    "timestamp": datetime.utcnow().isoformat() + "Z"
                }
            )
            if response.status_code == 200:
                return response.json()  # {ledger_hash, ...}
            else:
                raise Exception(f"CMS registration failed: {response.text}")
    
    async def validate_firmware_hash(self, firmware_hash: str, version: str):
        """
        Validate firmware hash against blockchain ledger
        Returns: {status: "valid"|"invalid"|"rolled_back", ledger_hash}
        """
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.endpoint}/ledger/validate",
                headers={"Authorization": f"Bearer {self.api_key}"},
                json={
                    "firmware_hash": firmware_hash,
                    "version": version
                }
            )
            if response.status_code == 200:
                return response.json()
            else:
                raise Exception(f"CMS validation failed: {response.text}")
    
    async def check_rollback_prevention(self, hardware_target: str, 
                                       current_version: str, new_version: str):
        """
        Check if downgrade is allowed
        Returns: {allowed: true|false, reason}
        """
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.endpoint}/rollback/check",
                headers={"Authorization": f"Bearer {self.api_key}"},
                json={
                    "hardware_target": hardware_target,
                    "current_version": current_version,
                    "new_version": new_version
                }
            )
            return response.json()
```

- [ ] Update `requirements.txt` if needed
- [ ] Add environment variables to docker-compose.yaml:
  ```yaml
  environment:
    - CMS_ENDPOINT=http://cms:8080
    - CMS_API_KEY=${CMS_API_KEY}
  ```

### Phase 3: Integrate CMS into Ledger Validation

- [ ] Modify `/api/v1/ledger/validate-hash` to call CMS
- [ ] Call CMS during firmware upload to register hash
- [ ] Device calls ledger validation endpoint during install check

---

## FOTA Client Integration Points

### What FOTA Client Team Needs From You

- [ ] **Device Certificate Requirements:**
  - [ ] CN format: `device-{device_id}`
  - [ ] How to obtain certificate?
  - [ ] Certificate storage on device?
  - [ ] Certificate renewal process?

- [ ] **API Endpoints to Call:**
  - [ ] `POST /api/v1/devices/register` — register device
  - [ ] `GET /api/v1/firmware?hardware_target={hw}` — list available firmware
  - [ ] `GET /api/v1/firmware/{version}/metadata` — get signature + public key
  - [ ] `GET /api/v1/firmware/{version}/binary` — download binary
  - [ ] `POST /api/v1/ledger/validate-hash` — validate against CMS
  - [ ] `GET /api/v1/mqtt/status` — check notification availability

- [ ] **What They Return:**
  - [ ] Device pulls signature_hex and public_key_hex (from HSM/KMS via your server)
  - [ ] Device verifies signature locally
  - [ ] Device queries ledger validation (CMS through your server)
  - [ ] Device installs if all checks pass

---

## Implementation Roadmap

### Week 1: Setup & Documentation
- [ ] Read COMPLETE_SYSTEM_ARCHITECTURE.md
- [ ] Schedule meetings with each team:
  - [ ] HSM/KMS Team: Understand signing flow
  - [ ] CMS Team: Understand ledger validation
  - [ ] FOTA Client Team: Understand device expectations
- [ ] Document API contracts from each team

### Week 2: HSM/KMS Integration
- [ ] Create `./app/hsm_kms_client.py`
- [ ] Test HSM/KMS endpoint connectivity
- [ ] Modify firmware upload to call HSM for signing
- [ ] Verify signature and public key storage

### Week 3: CMS Integration
- [ ] Create `./app/cms_client.py`
- [ ] Test CMS endpoint connectivity
- [ ] Modify firmware upload to register hash in CMS
- [ ] Modify ledger validation to query CMS
- [ ] Test rollback prevention logic

### Week 4: End-to-End Testing
- [ ] Device registration with HSM/KMS cert
- [ ] Firmware upload with HSM/KMS signing
- [ ] CMS ledger validation
- [ ] Device firmware download and verification
- [ ] FOTA Client integration test

### Week 5: Deployment & Monitoring
- [ ] All integration endpoints working
- [ ] Error handling and logging
- [ ] Audit trail complete
- [ ] Production deployment

---

## API Contract Template

Use this template to document agreements with each team:

### HSM/KMS Team — Firmware Signing Endpoint

**Endpoint:** `POST /sign`

**Request:**
```json
{
  "firmware_binary": "hex-encoded-binary",
  "algorithm": "ECDSA-SHA256",
  "key_id": "firmware-signing-key"
}
```

**Response (Success):**
```json
{
  "signature_hex": "a1b2c3d4...",
  "public_key_hex": "e5f6a7b8...",
  "algorithm": "ECDSA-SHA256",
  "key_id": "firmware-signing-key",
  "timestamp": "2026-06-17T12:00:00Z"
}
```

**Response (Error):**
```json
{
  "error": "Signing failed",
  "reason": "Key not found",
  "status": 400
}
```

---

### CMS Team — Ledger Validation Endpoint

**Endpoint:** `POST /ledger/validate`

**Request:**
```json
{
  "firmware_hash": "abc123def456...",
  "version": "1.0.0",
  "hardware_target": "ESP32-S3"
}
```

**Response (Success):**
```json
{
  "status": "valid",
  "ledger_hash": "blockchain-tx-id",
  "firmware_hash": "abc123def456...",
  "timestamp": "2026-06-17T12:00:00Z",
  "confirmed": true,
  "rollback_allowed": false
}
```

**Response (Rolled Back):**
```json
{
  "status": "rolled_back",
  "reason": "Version rejected by CMS policy",
  "current_approved_version": "0.9.0",
  "requested_version": "1.0.0"
}
```

---

## Testing Checklist

- [ ] HSM/KMS endpoint is reachable
- [ ] Can call HSM sign endpoint successfully
- [ ] Signature and public key are stored correctly
- [ ] CMS endpoint is reachable
- [ ] Can register firmware hash in CMS
- [ ] Can validate firmware hash against CMS
- [ ] Rollback prevention works correctly
- [ ] Device can verify signatures using public key from server
- [ ] Device can query ledger validation endpoint
- [ ] End-to-end firmware update succeeds
- [ ] MQTT notifications work with all components

---

## Success Criteria

✅ **System is complete when:**

1. Admin uploads firmware
   - [ ] HSM/KMS signs it
   - [ ] CMS records hash in ledger
   - [ ] FOTA Server stores everything
   - [ ] MQTT notifies devices

2. Device registers
   - [ ] Certificate validated against HSM/KMS CA
   - [ ] Device identity confirmed

3. Device pulls firmware
   - [ ] Gets metadata with signature (from HSM/KMS)
   - [ ] Downloads binary securely (HTTPS/mTLS)
   - [ ] Verifies signature locally
   - [ ] Queries ledger (CMS)
   - [ ] Installs if all checks pass

4. Audit trail complete
   - [ ] All operations logged
   - [ ] Immutable history
   - [ ] Team accountability

---

## Support & Escalation

If integration fails:

1. **HSM/KMS Issues:**
   - [ ] Check endpoint connectivity: `curl http://<hsm-endpoint>/health`
   - [ ] Verify API key in environment
   - [ ] Check HSM/KMS logs
   - [ ] Contact HSM/KMS team with error message

2. **CMS Issues:**
   - [ ] Check endpoint connectivity: `curl http://<cms-endpoint>/health`
   - [ ] Verify API key in environment
   - [ ] Check CMS logs
   - [ ] Contact CMS team with error message

3. **FOTA Client Issues:**
   - [ ] Verify device certificate is signed by HSM/KMS CA
   - [ ] Check device has correct public key from server
   - [ ] Verify device can query ledger endpoint
   - [ ] Contact FOTA Client team with logs

---

## Documentation to Create

- [ ] API Contract with HSM/KMS Team
- [ ] API Contract with CMS Team
- [ ] API Contract with FOTA Client Team
- [ ] Integration Test Plan
- [ ] Deployment Runbook
- [ ] Troubleshooting Guide
