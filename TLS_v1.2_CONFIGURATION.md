# FOTA Server TLS v1.2 Configuration

## Overview

The FOTA Orchestrator Server enforces **TLS v1.2 minimum** for all device communication. This document describes:

1. TLS requirements for FOTA clients
2. How to configure the server for mTLS production deployment
3. Certificate generation and rotation procedures
4. Cipher suite policies

---

## TLS Version Requirement

**Minimum Version:** TLS v1.2  
**Maximum Version:** TLS v1.3 (forward compatible)  
**Deprecated Versions:** TLS 1.0, TLS 1.1 (not supported)

### Why TLS v1.2?

- **Hardware Compatibility:** ESP32, STM32, and other embedded devices widely support TLS 1.2
- **Security:** TLS 1.2 provides strong encryption (AES-GCM, ChaCha20-Poly1305)
- **Forward Compatibility:** TLS 1.3 supported for devices that implement it
- **Industry Standard:** Most IoT security frameworks mandate TLS 1.2 minimum (e.g., AWS IoT, Azure IoT)

---

## FOTA Client Requirements

All FOTA clients (devices) must:

1. **Support TLS v1.2** — Minimum protocol version
2. **Provide Client Certificate** — Unique certificate with CN = device_id
3. **Verify Server Certificate** — Validate server identity (hostname/CA chain)
4. **Use Strong Ciphers** — Support ECDHE+AESGCM or DHE+AESGCM

### Recommended Client TLS Configuration

```c
// Example: mbedTLS (common on ESP32)
mbedtls_ssl_config_set_min_version(&conf, MBEDTLS_SSL_MINOR_VERSION_3);  // TLS 1.2
mbedtls_ssl_config_set_max_version(&conf, MBEDTLS_SSL_MINOR_VERSION_4);  // TLS 1.3

// Load client certificate and key
mbedtls_ssl_conf_own_cert(&conf, &client_cert, &client_key);

// Load CA certificate for server verification
mbedtls_ssl_conf_ca_chain(&conf, &ca_chain, NULL);
```

---

## Server Configuration

### Development Mode (Testing)

In development, the server runs **without TLS** for easy testing. Use the `X-Client-Cert-CN` header to simulate device identity:

```bash
curl -X POST "http://localhost:8081/api/v1/devices/register" \
  -H "X-Client-Cert-CN: device-001" \
  -H "Content-Type: application/json" \
  -d '{...}'
```

### Production Mode (mTLS Enforcement)

To enable production mTLS with TLS v1.2 enforcement:

#### 1. Generate Server Certificate and Key

```bash
# Generate server private key
openssl genrsa -out ./app/certs/server.key 2048

# Generate server certificate (self-signed or CA-signed)
openssl req -new -x509 -key ./app/certs/server.key \
  -out ./app/certs/server.crt \
  -subj "/CN=fota-server/O=YourOrg"
```

#### 2. Generate CA Certificate (for client verification)

```bash
# Generate CA private key
openssl genrsa -out ./app/certs/ca.key 2048

# Generate CA certificate
openssl req -new -x509 -key ./app/certs/ca.key \
  -out ./app/certs/ca.crt \
  -subj "/CN=FOTA-CA/O=YourOrg"
```

#### 3. Generate Client Certificates (for each device)

```bash
# Generate client private key
openssl genrsa -out ./app/certs/device-001.key 2048

# Generate client certificate signing request (CSR)
openssl req -new -key ./app/certs/device-001.key \
  -out ./app/certs/device-001.csr \
  -subj "/CN=device-001"

# Sign CSR with CA (creates device certificate)
openssl x509 -req -in ./app/certs/device-001.csr \
  -CA ./app/certs/ca.crt -CAkey ./app/certs/ca.key \
  -CAcreateserial -out ./app/certs/device-001.crt \
  -days 365
```

#### 4. Environment Variables

Set these when running the container:

```bash
export SERVER_CERT=/app/certs/server.crt
export SERVER_KEY=/app/certs/server.key
export CLIENT_CA_CERT=/app/certs/ca.crt
```

Or in docker-compose.yaml:

```yaml
environment:
  - SERVER_CERT=/app/certs/server.crt
  - SERVER_KEY=/app/certs/server.key
  - CLIENT_CA_CERT=/app/certs/ca.crt
```

#### 5. Restart Container

```bash
docker compose down
docker compose up -d
```

---

## Cipher Suite Policy

The server enforces strong cipher suites suitable for TLS v1.2 + embedded devices:

```
ECDHE+AESGCM          # Elliptic Curve + AES-GCM (preferred for IoT)
ECDHE+CHACHA20        # Elliptic Curve + ChaCha20
DHE+AESGCM            # Diffie-Hellman + AES-GCM
DHE+CHACHA20          # Diffie-Hellman + ChaCha20
!aNULL !eNULL         # Reject null ciphers
!EXPORT !DSS          # Reject export-grade and DSS
!DES !RC4 !3DES       # Reject weak algorithms
!MD5 !PSK             # Reject MD5 and pre-shared key
```

### Why ECDHE for IoT?

- **Key Exchange:** ECDHE (Elliptic Curve) is faster and uses less CPU than DHE
- **Battery Efficiency:** Critical for battery-powered IoT devices
- **Small Code Size:** ESP32/STM32 can implement ECDHE in less flash memory than DHE

---

## Testing TLS v1.2 Enforcement

### Test Server Accepts TLS 1.2

```bash
# Test with TLS 1.2
openssl s_client -tls1_2 -connect localhost:8443 \
  -cert ./app/certs/device-001.crt \
  -key ./app/certs/device-001.key \
  -CAfile ./app/certs/ca.crt
```

### Test Server Rejects TLS 1.1 and Below

```bash
# This should fail (TLS 1.1 not supported)
openssl s_client -tls1_1 -connect localhost:8443 \
  -cert ./app/certs/device-001.crt \
  -key ./app/certs/device-001.key \
  -CAfile ./app/certs/ca.crt
# Expected: connection refused or protocol error
```

---

## Certificate Rotation

To rotate certificates without downtime:

1. Generate new certificate with same CN (device_id)
2. Update `/app/certs/` directory with new certificate
3. No server restart required — certificate is validated per-request

---

## Troubleshooting

### "Unsupported Protocol Version" Error

**Cause:** Device using TLS < 1.2  
**Solution:** Update device firmware to support TLS 1.2

### "Certificate Verification Failed"

**Cause:** Client certificate not signed by CA  
**Solution:** Regenerate client certificate and sign with correct CA

### "Bad Certificate" Error

**Cause:** Certificate CN doesn't match device_id in registration  
**Solution:** Ensure certificate CN equals the device_id you register

---

## Compliance

- ✅ NIST SP 800-52 Rev. 2 (TLS 1.2 recommended for Federal systems)
- ✅ OWASP Secure Coding Practices (TLS 1.2 minimum)
- ✅ IETF RFC 5246 (TLS 1.2 specification)
- ✅ IoT Security Foundation Recommendations

---

## References

- [TLS 1.2 RFC 5246](https://tools.ietf.org/html/rfc5246)
- [mbedTLS Documentation](https://mbed-tls.readthedocs.io/)
- [OpenSSL Certificate Commands](https://www.openssl.org/docs/manmaster/man1/)
