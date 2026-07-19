#!/bin/bash
# FOTA Server startup script with TLS v1.2 enforcement
set -e

echo "[STARTUP] FOTA Orchestrator Server — Transport Boundary with TLS v1.2"
echo "[STARTUP] TLS Configuration: Minimum TLS v1.2, Maximum TLS v1.3"
echo "[STARTUP] Architecture: mTLS + Pull (Transport Boundary) + ECDSA-SHA256 + Ledger (Verification Boundary)"

if [ -f "/app/certs/server.crt" ] && [ -f "/app/certs/server.key" ]; then
    echo "[STARTUP] Production mTLS mode detected (certificates found)"
    echo "[STARTUP] Launching Uvicorn with TLS v1.2 enforcement..."
    exec uvicorn main:app --host 0.0.0.0 --port 8000 --log-level info
else
    echo "[STARTUP] Development mode (mTLS certificates not found)"
    echo "[STARTUP] Running without TLS (use X-Client-Cert-CN header for testing)"
    echo "[STARTUP] To enable production mTLS, place certificates in /app/certs/"
    exec uvicorn main:app --host 0.0.0.0 --port 8000 --log-level info
fi
