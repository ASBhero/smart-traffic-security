# HSM + KMS Module

## Owner
Ahmed (HSM + KMS team)

## What this module provides
- SoftHSM emulator (`hsm_emulator.py`)
- Vault KMS manager (`kms_manager.py`)
- Root CA + Intermediate CA certificates

## How other teams use this
1. Import `root_ca.crt` and `intermediate.crt` from `shared/certs/`
2. Use `hsm_emulator.py` for signing operations
3. Use `kms_manager.py` for key lifecycle management

## Integration points
- CMS team: uses certificates to sign device certificates
- FOTA team: uses certificates to sign firmware updates
- Traffic team: uses certificates for secure boot
