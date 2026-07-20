"""
Vault KMS Client for FOTA Server
Handles all operations with HashiCorp Vault for firmware signing and certificate management
"""

import httpx
import base64
import json
import os
from typing import Optional, Tuple
from datetime import datetime
from pathlib import Path

class VaultKMSClient:
    """Client for HashiCorp Vault KMS operations"""
    
    def __init__(
        self,
        vault_url: str = "http://127.0.0.1:8200",
        vault_token: str = "root",
        vault_namespace: str = "v1",
        transit_key_name: str = "fota-key",
        pki_role: str = "fota-devices",
        ca_cert_path: str = "./shared/certs/root_ca.crt",
        timeout: float = 30.0
    ):
        """
        Initialize Vault KMS client
        
        Args:
            vault_url: Base URL of Vault API (default: http://127.0.0.1:8200)
            vault_token: Authentication token (default: root)
            vault_namespace: Vault namespace (default: v1)
            transit_key_name: Name of transit encryption key (default: fota-key)
            pki_role: PKI role for device certificates (default: fota-devices)
            ca_cert_path: Path to store root CA certificate
            timeout: Request timeout in seconds
        """
        self.vault_url = vault_url.rstrip('/')
        self.vault_token = vault_token
        self.vault_namespace = vault_namespace
        self.transit_key_name = transit_key_name
        self.pki_role = pki_role
        self.ca_cert_path = ca_cert_path
        self.timeout = timeout
        
        # HTTP client with Vault token header
        self.headers = {
            "X-Vault-Token": self.vault_token,
            "Content-Type": "application/json"
        }
        
        # Create CA cert directory if it doesn't exist
        cert_dir = Path(self.ca_cert_path).parent
        cert_dir.mkdir(parents=True, exist_ok=True)
        
        print(f"[VAULT] Initialized Vault KMS client at {self.vault_url}", flush=True)
        print(f"[VAULT] Transit key: {self.transit_key_name}", flush=True)
        print(f"[VAULT] PKI role: {self.pki_role}", flush=True)
    
    def _build_url(self, path: str) -> str:
        """Build full Vault API URL"""
        return f"{self.vault_url}/{self.vault_namespace}/{path.lstrip('/')}"
    
    async def health_check(self) -> bool:
        """
        Check if Vault server is running and accessible
        
        Returns:
            bool: True if Vault is accessible, False otherwise
        """
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(
                    self._build_url("sys/seal-status"),
                    headers=self.headers
                )
            
            if response.status_code in (200, 400, 473):  # 473 = sealed, 400 = unsealed, 200 = ok
                print("[VAULT] Health check: Vault is running", flush=True)
                return True
            else:
                print(f"[VAULT] Health check failed: {response.status_code}", flush=True)
                return False
        
        except Exception as e:
            print(f"[VAULT] Health check error: {e}", flush=True)
            return False
    
    async def sign_firmware(self, firmware_hash: str) -> Optional[str]:
        """
        Sign firmware hash using Vault Transit engine
        
        Args:
            firmware_hash: SHA-256 hash of firmware (hex string)
        
        Returns:
            Vault signature string (e.g., "vault:v1:MEUCIQDxK3kH...") or None on error
        """
        try:
            # Encode firmware hash to base64 as required by Vault
            hash_b64 = base64.b64encode(bytes.fromhex(firmware_hash)).decode('utf-8')
            
            payload = {
                "input": hash_b64
            }
            
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    self._build_url(f"transit/sign/{self.transit_key_name}"),
                    headers=self.headers,
                    json=payload
                )
            
            if response.status_code != 200:
                print(f"[VAULT] Sign failed: {response.status_code} - {response.text}", flush=True)
                return None
            
            data = response.json()
            signature = data.get("data", {}).get("signature")
            
            if signature:
                print(f"[VAULT] Firmware signed successfully", flush=True)
                return signature
            else:
                print("[VAULT] No signature in response", flush=True)
                return None
        
        except Exception as e:
            print(f"[VAULT] Sign error: {e}", flush=True)
            return None
    
    async def verify_signature(self, firmware_hash: str, signature: str) -> bool:
        """
        Verify firmware signature using Vault Transit engine
        
        Args:
            firmware_hash: SHA-256 hash of firmware (hex string)
            signature: Vault signature string
        
        Returns:
            bool: True if signature is valid, False otherwise
        """
        try:
            # Encode firmware hash to base64
            hash_b64 = base64.b64encode(bytes.fromhex(firmware_hash)).decode('utf-8')
            
            payload = {
                "input": hash_b64,
                "signature": signature
            }
            
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    self._build_url(f"transit/verify/{self.transit_key_name}"),
                    headers=self.headers,
                    json=payload
                )
            
            if response.status_code != 200:
                print(f"[VAULT] Verify failed: {response.status_code}", flush=True)
                return False
            
            data = response.json()
            is_valid = data.get("data", {}).get("valid", False)
            
            print(f"[VAULT] Signature verification: {'valid' if is_valid else 'invalid'}", flush=True)
            return is_valid
        
        except Exception as e:
            print(f"[VAULT] Verify error: {e}", flush=True)
            return False
    
    async def get_public_key(self) -> Optional[str]:
        """
        Get the public key from Vault Transit engine
        
        Returns:
            Public key hex string or None on error
        """
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(
                    self._build_url(f"transit/keys/{self.transit_key_name}"),
                    headers=self.headers
                )
            
            if response.status_code != 200:
                print(f"[VAULT] Get public key failed: {response.status_code}", flush=True)
                return None
            
            data = response.json()
            # Extract public key from Vault response
            public_key = data.get("data", {}).get("keys", {})
            
            if public_key:
                print("[VAULT] Public key retrieved successfully", flush=True)
                return json.dumps(public_key)
            else:
                print("[VAULT] No public key in response", flush=True)
                return None
        
        except Exception as e:
            print(f"[VAULT] Get public key error: {e}", flush=True)
            return None
    
    async def get_root_ca(self) -> Optional[str]:
        """
        Get Root CA certificate from Vault PKI engine
        
        Returns:
            PEM-encoded CA certificate string or None on error
        """
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(
                    self._build_url("pki/cert/ca"),
                    headers=self.headers
                )
            
            if response.status_code != 200:
                print(f"[VAULT] Get Root CA failed: {response.status_code}", flush=True)
                return None
            
            ca_cert = response.text
            
            if ca_cert:
                print(f"[VAULT] Root CA certificate retrieved successfully", flush=True)
                # Save to disk for future use
                self._save_ca_cert(ca_cert)
                return ca_cert
            else:
                print("[VAULT] No CA certificate in response", flush=True)
                return None
        
        except Exception as e:
            print(f"[VAULT] Get Root CA error: {e}", flush=True)
            return None
    
    def _save_ca_cert(self, ca_cert: str) -> bool:
        """Save CA certificate to disk"""
        try:
            cert_path = Path(self.ca_cert_path)
            cert_path.parent.mkdir(parents=True, exist_ok=True)
            cert_path.write_text(ca_cert)
            print(f"[VAULT] CA certificate saved to {self.ca_cert_path}", flush=True)
            return True
        except Exception as e:
            print(f"[VAULT] Failed to save CA cert: {e}", flush=True)
            return False
    
    def get_ca_cert_local(self) -> Optional[str]:
        """Get locally cached CA certificate"""
        try:
            cert_path = Path(self.ca_cert_path)
            if cert_path.exists():
                return cert_path.read_text()
            else:
                return None
        except Exception as e:
            print(f"[VAULT] Failed to read local CA cert: {e}", flush=True)
            return None
    
    async def issue_device_certificate(
        self,
        device_id: str,
        common_name: str,
        ttl: str = "87600h"  # 10 years
    ) -> Optional[Tuple[str, str, str]]:
        """
        Issue a device certificate from Vault PKI
        
        Args:
            device_id: Unique device identifier
            common_name: Certificate CN (typically device-id)
            ttl: Certificate time-to-live
        
        Returns:
            Tuple of (certificate, private_key, ca_chain) or None on error
        """
        try:
            payload = {
                "common_name": common_name,
                "ttl": ttl,
                "exclude_cn_from_sans": True
            }
            
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    self._build_url(f"pki/issue/{self.pki_role}"),
                    headers=self.headers,
                    json=payload
                )
            
            if response.status_code != 200:
                print(f"[VAULT] Issue device cert failed: {response.status_code}", flush=True)
                return None
            
            data = response.json().get("data", {})
            certificate = data.get("certificate")
            private_key = data.get("private_key")
            ca_chain = data.get("ca_chain", [])
            
            if certificate and private_key:
                print(f"[VAULT] Device certificate issued for {device_id}", flush=True)
                return (certificate, private_key, "\n".join(ca_chain) if ca_chain else "")
            else:
                print("[VAULT] Missing certificate or private key in response", flush=True)
                return None
        
        except Exception as e:
            print(f"[VAULT] Issue device cert error: {e}", flush=True)
            return None
    
    async def revoke_certificate(self, certificate_serial: str) -> bool:
        """
        Revoke a device certificate
        
        Args:
            certificate_serial: Certificate serial number
        
        Returns:
            bool: True if revocation succeeded, False otherwise
        """
        try:
            payload = {
                "serial_number": certificate_serial
            }
            
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.put(
                    self._build_url("pki/revoke"),
                    headers=self.headers,
                    json=payload
                )
            
            if response.status_code != 200:
                print(f"[VAULT] Revoke cert failed: {response.status_code}", flush=True)
                return False
            
            print(f"[VAULT] Certificate revoked: {certificate_serial}", flush=True)
            return True
        
        except Exception as e:
            print(f"[VAULT] Revoke cert error: {e}", flush=True)
            return False
    
    async def get_seal_status(self) -> dict:
        """
        Get Vault seal status
        
        Returns:
            dict with seal status information
        """
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(
                    self._build_url("sys/seal-status"),
                    headers=self.headers
                )
            
            if response.status_code in (200, 400, 473):
                return response.json()
            else:
                return {"error": f"HTTP {response.status_code}"}
        
        except Exception as e:
            return {"error": str(e)}


# Global Vault client instance (lazy loaded)
vault_client: Optional[VaultKMSClient] = None

def get_vault_client() -> VaultKMSClient:
    """Get or create global Vault client instance"""
    global vault_client
    
    if vault_client is None:
        vault_url = os.getenv("VAULT_URL", "http://127.0.0.1:8200")
        vault_token = os.getenv("VAULT_TOKEN", "root")
        vault_namespace = os.getenv("VAULT_NAMESPACE", "v1")
        transit_key_name = os.getenv("VAULT_TRANSIT_KEY", "fota-key")
        pki_role = os.getenv("VAULT_PKI_ROLE", "fota-devices")
        ca_cert_path = os.getenv("VAULT_CA_CERT_PATH", "./shared/certs/root_ca.crt")
        
        vault_client = VaultKMSClient(
            vault_url=vault_url,
            vault_token=vault_token,
            vault_namespace=vault_namespace,
            transit_key_name=transit_key_name,
            pki_role=pki_role,
            ca_cert_path=ca_cert_path
        )
    
    return vault_client
