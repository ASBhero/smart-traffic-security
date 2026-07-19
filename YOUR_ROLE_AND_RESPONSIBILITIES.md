# FOTA System: Your Role & Responsibilities

## You Are Building The Central Hub

Your FOTA server is the **orchestrator** connecting four specialized teams:

```
┌─────────────────────────────────┐
│   HSM/KMS Team (Signing)        │
│   (Team #1)                     │
└──────────────┬──────────────────┘
               │ Signs firmware
               │ Issues device certs
               │
┌──────────────▼──────────────────┐
│   FOTA SERVER (YOUR TASK)       │
│   ┌──────────────────────────┐  │
│   │ • Receives signed FW     │  │
│   │ • Stores firmware        │  │
│   │ • Serves to devices      │  │
│   │ • Queries ledger         │  │
│   │ • Notifies via MQTT      │  │
│   └──────────────────────────┘  │
└──────┬──────────────┬────────────┘
       │              │
       │ Registers    │ Validates
       │ hash         │ hash
       │              │
┌──────▼──┐      ┌────▼──────────────┐
│  CMS    │      │  FOTA Client Team  │
│ (Team   │      │  (Team #3)         │
│  #2)    │      │                    │
│ Ledger  │      │ Device pulls FW    │
│Blockch  │      │ Verifies signature │
│ CMS     │      │ Queries ledger     │
│Checks   │      │ Installs           │
└─────────┘      └────────────────────┘
```

---

## What's Already Done ✅

| Component | Status | Details |
|-----------|--------|---------|
| **HTTPS/mTLS Transport Boundary** | ✅ Complete | Devices authenticate with certificates, firmware downloads encrypted |
| **ECDSA-SHA256 Signature Storage** | ✅ Complete | Server stores `signature_hex` and `public_key_hex` for devices |
| **Firmware Management** | ✅ Complete | Upload, store, retrieve firmware binaries |
| **Ledger Query Endpoint** | ✅ Complete | `/api/v1/ledger/validate-hash` ready for CMS integration |
| **MQTT Notifications** | ✅ Complete | Instant notifications to devices when firmware available |
| **Immutable Audit Trail** | ✅ Complete | All operations logged with timestamps and device identity |
| **Device Registration** | ✅ Complete | Certificate-based identity validation |

---

## What Needs Integration ⚠️

### 1. HSM/KMS Integration (Team #1)

**What you need to add:**
- Call HSM/KMS endpoint to sign firmware during upload
- Retrieve public keys from HSM/KMS
- Validate device certificates against HSM/KMS CA

**Files to create:**
- `./app/hsm_kms_client.py` (HTTP client for HSM/KMS)

**Endpoints to call:**
- `POST /hsm/sign` → Returns: `{signature_hex, public_key_hex}`
- `GET /hsm/ca-certificate` → Returns: CA cert for device verification

**Environment variables:**
- `HSM_KMS_ENDPOINT=http://hsm-kms:8080`
- `HSM_KMS_API_KEY=your-key`

### 2. CMS Integration (Team #2)

**What you need to add:**
- Call CMS to register firmware hash in blockchain ledger when firmware uploaded
- Call CMS to validate firmware hash when device queries ledger

**Files to create:**
- `./app/cms_client.py` (HTTP client for CMS)

**Endpoints to call:**
- `POST /cms/ledger/register` → Stores hash in blockchain
- `POST /cms/ledger/validate` → Validates hash, checks rollback prevention

**Environment variables:**
- `CMS_ENDPOINT=http://cms:8080`
- `CMS_API_KEY=your-key`

### 3. FOTA Client Integration (Team #4)

**What you provide:**
- Devices use certificate signed by HSM/KMS
- Devices receive firmware metadata with signature + public key (from HSM/KMS)
- Devices verify signature locally
- Devices query your ledger endpoint to validate against CMS
- Devices install firmware only if all checks pass

**No new code needed** — your current API is sufficient

---

## Integration Flow Summary

```
1. ADMIN UPLOADS FIRMWARE
   └─→ Your server receives firmware
   └─→ Calls HSM/KMS: "Sign this firmware"
   └─→ HSM/KMS returns: signature_hex, public_key_hex
   └─→ Your server stores both
   └─→ Calls CMS: "Register this hash in ledger"
   └─→ CMS returns: ledger_hash (blockchain tx ID)
   └─→ Your server stores ledger_hash
   └─→ Publishes MQTT: "Firmware v1.0.0 available!"

2. DEVICE BOOTS UP (first time)
   └─→ Device has certificate (signed by HSM/KMS)
   └─→ Device connects to your server via HTTPS/mTLS
   └─→ Your server validates device cert against HSM/KMS CA
   └─→ Device registers: POST /api/v1/devices/register

3. DEVICE CHECKS FOR UPDATES
   └─→ Device receives MQTT notification (optional)
   └─→ Or device polls: GET /api/v1/firmware
   └─→ Your server returns list of available firmware

4. DEVICE PULLS FIRMWARE
   └─→ Device pulls metadata: GET /api/v1/firmware/1.0.0/metadata
   └─→ Your server returns: signature_hex, public_key_hex, ledger_hash
   └─→ Device pulls binary: GET /api/v1/firmware/1.0.0/binary
   └─→ Your server streams firmware (HTTPS/mTLS)

5. DEVICE VERIFIES
   └─→ Device verifies signature: verify(signature_hex, binary, public_key_hex)
   └─→ Device queries ledger: POST /api/v1/ledger/validate-hash
   └─→ Your server calls CMS: "Validate this hash"
   └─→ CMS returns: {status: "valid", ledger_hash}

6. DEVICE INSTALLS
   └─→ Device installs firmware
   └─→ Secure boot verifies signature again
   └─→ Flash encryption protects code
```

---

## Key Integration Points

### HSM/KMS Agreement Needed

**Ask HSM/KMS Team:**
- What's your API endpoint?
- How do we authenticate? (API key? OAuth?)
- What format for signing request/response?
- How do you export CA certificate?
- Are device certificates ready, or do we need to request them?

**Your responsibility:**
- Call their `/sign` endpoint during firmware upload
- Load their CA certificate on startup
- Validate device certs during mTLS handshake

### CMS Agreement Needed

**Ask CMS Team:**
- What's your API endpoint?
- How do we authenticate?
- What format for ledger register/validate?
- How does rollback prevention work?
- What does ledger_hash look like? (blockchain tx ID?)

**Your responsibility:**
- Call their `/register` endpoint when firmware uploaded
- Call their `/validate` endpoint when device queries ledger
- Pass ledger_hash back to device for transparency

### FOTA Client Agreement Needed

**Tell FOTA Client Team:**
- Your server provides metadata with signature from HSM/KMS
- Devices must implement signature verification locally
- Devices must query your ledger endpoint to validate CMS
- All verified before installation

---

## Current System State

✅ **Running Services:**
```
docker ps:
- fota_backend (port 8081) — Your FOTA server
- mqtt_broker (port 1883) — Notifications
```

✅ **API Endpoints Ready:**
```
POST   /api/v1/devices/register              (device cert required)
GET    /api/v1/firmware                       (device cert required)
GET    /api/v1/firmware/{version}/metadata    (device cert required)
GET    /api/v1/firmware/{version}/binary      (device cert required)
POST   /api/v1/firmware/upload                (admin endpoint)
POST   /api/v1/ledger/validate-hash           (queries CMS - NEEDS WORK)
GET    /api/v1/audit/pull-events              (device cert required)
GET    /api/v1/mqtt/status                    (status check)
GET    /health                                (system health)
```

✅ **Database Schema:**
```
devices         — Device registration (cert CN, hardware, version)
firmware        — Firmware metadata (version, hash, signature_hex, public_key_hex, ledger_hash)
audit_logs      — Immutable trail (all operations timestamped)
ledger_queries  — CMS interactions
```

⚠️ **Needs HSM/KMS Integration:**
- Firmware signing during upload
- Public key retrieval
- Device cert validation

⚠️ **Needs CMS Integration:**
- Ledger hash registration
- Hash validation
- Rollback prevention checks

---

## Timeline for Full Integration

| Phase | Duration | Tasks |
|-------|----------|-------|
| **1. Kickoff** | 1 week | Meet all teams, agree on APIs, understand requirements |
| **2. HSM/KMS** | 1 week | Implement signing flow, test with test data |
| **3. CMS** | 1 week | Implement ledger validation, test rollback prevention |
| **4. Testing** | 1 week | End-to-end testing, error handling, logging |
| **5. Deploy** | 1 week | Production deployment, monitoring, documentation |
| **Total** | 5 weeks | Complete integrated system |

---

## Your Next Actions

1. **This Week:**
   - [ ] Read `COMPLETE_SYSTEM_ARCHITECTURE.md`
   - [ ] Schedule meetings with each team
   - [ ] Get HSM/KMS endpoint + API docs
   - [ ] Get CMS endpoint + API docs
   - [ ] Create API contracts for both teams

2. **Next Week:**
   - [ ] Create `hsm_kms_client.py`
   - [ ] Create `cms_client.py`
   - [ ] Test HSM/KMS connectivity
   - [ ] Test CMS connectivity

3. **Week 3:**
   - [ ] Integrate HSM/KMS into firmware upload
   - [ ] Integrate CMS into ledger validation
   - [ ] Test full firmware upload flow

4. **Week 4-5:**
   - [ ] End-to-end testing with devices
   - [ ] Production deployment
   - [ ] Documentation complete

---

## You're The Bridge

Remember: You're not doing all four responsibilities. You're **coordinating** between teams:

- **HSM/KMS Team** handles: Private keys, signing, PKI
- **CMS Team** handles: Blockchain ledger, rollback prevention
- **FOTA Client Team** handles: Device verification, installation
- **You handle:** Orchestration, storage, delivery, audit trail

Your job is to connect their work seamlessly so devices can safely update.

---

## Questions to Ask

Before starting HSM/KMS integration:
1. "Can you provide a test endpoint?" → (need to test without production HSM)
2. "What's the exact request/response format?" → (JSON? XML? Binary?)
3. "How often should we refresh public keys?" → (cache? real-time?)
4. "How do device certificates get provisioned?" → (we request, or pre-provisioned?)
5. "What's the recovery if signing fails?" → (retry? alert admin?)

Before starting CMS integration:
1. "What's a sample ledger_hash?" → (transaction ID? hash?)
2. "How long does ledger registration take?" → (instant? eventual consistency?)
3. "What happens on hash mismatch?" → (reject? alert?)
4. "How does rollback prevention work exactly?" → (version numbers? time-based? admin approval?)
5. "Can we test with test blockchain?" → (testnet? mock?)

---

## Support Resources

- `COMPLETE_SYSTEM_ARCHITECTURE.md` — Full system design
- `INTEGRATION_CHECKLIST.md` — Detailed integration steps
- `./app/main.py` — Your current FOTA server code
- `./MQTT_INTEGRATION_APPLIED.md` — MQTT (already done)
- Health endpoint: `http://localhost:8081/health` — Check system status

You have a solid foundation. Integration is straightforward once you understand each team's APIs.

Good luck! 🚀
