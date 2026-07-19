"""
CMS (Certificate Management System) Client for FOTA Server
Handles all operations with CMS API for ledger management and firmware distribution
"""

import httpx
import json
from typing import Optional, Dict, Any
from datetime import datetime
from pathlib import Path

class CMSClient:
    """Client for CMS API operations"""
    
    def __init__(
        self,
        cms_url: str = "http://127.0.0.1:8000",
        api_version: str = "v1",
        timeout: float = 30.0
    ):
        """
        Initialize CMS client
        
        Args:
            cms_url: Base URL of CMS API (default: http://127.0.0.1:8000)
            api_version: API version (default: v1)
            timeout: Request timeout in seconds
        """
        self.cms_url = cms_url.rstrip('/')
        self.api_version = api_version
        self.timeout = timeout
        
        # Headers (no auth required in dev mode)
        self.headers = {
            "Content-Type": "application/json"
        }
        
        print(f"[CMS] Initialized CMS client at {self.cms_url}/api/{self.api_version}", flush=True)
    
    def _build_url(self, path: str) -> str:
        """Build full CMS API URL"""
        return f"{self.cms_url}/api/{self.api_version}/{path.lstrip('/')}"
    
    async def health_check(self) -> bool:
        """
        Check if CMS server is running and accessible
        
        Returns:
            bool: True if CMS is accessible, False otherwise
        """
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                # Try Swagger endpoint as health check
                response = await client.get(f"{self.cms_url}/docs")
            
            if response.status_code == 200:
                print("[CMS] Health check: CMS is running", flush=True)
                return True
            else:
                print(f"[CMS] Health check failed: {response.status_code}", flush=True)
                return False
        
        except Exception as e:
            print(f"[CMS] Health check error: {e}", flush=True)
            return False
    
    async def register_device(
        self,
        device_id: str,
        public_key: str
    ) -> Optional[Dict[str, Any]]:
        """
        Register device in CMS
        
        Args:
            device_id: Unique device identifier
            public_key: Device's public key (PEM format)
        
        Returns:
            dict with device_id and status, or None on error
        """
        try:
            payload = {
                "id": device_id,
                "public_key": public_key
            }
            
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    self._build_url("devices/register"),
                    headers=self.headers,
                    json=payload
                )
            
            if response.status_code not in (200, 201):
                print(f"[CMS] Device registration failed: {response.status_code} - {response.text}", flush=True)
                return None
            
            result = response.json()
            print(f"[CMS] Device {device_id} registered successfully", flush=True)
            return result
        
        except Exception as e:
            print(f"[CMS] Device registration error: {e}", flush=True)
            return None
    
    async def upload_firmware(
        self,
        firmware_name: str,
        firmware_hash: str,
        firmware_signature: str,
        hardware_target: str = "ESP32-S3",
        version: str = "1.0.0"
    ) -> Optional[Dict[str, Any]]:
        """
        Register firmware in CMS blockchain ledger
        
        Args:
            firmware_name: Firmware filename (e.g., "firmware-1.0.0.bin")
            firmware_hash: SHA-256 hash of firmware
            firmware_signature: Vault signature
            hardware_target: Target hardware
            version: Firmware version
        
        Returns:
            dict with firmware metadata and ledger hash, or None on error
        """
        try:
            payload = {
                "firmware": firmware_name,
                "hash": firmware_hash,
                "signature": firmware_signature,
                "hardware_target": hardware_target,
                "version": version
            }
            
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    self._build_url("firmware/upload"),
                    headers=self.headers,
                    json=payload
                )
            
            if response.status_code not in (200, 201):
                print(f"[CMS] Firmware upload failed: {response.status_code} - {response.text}", flush=True)
                return None
            
            result = response.json()
            print(f"[CMS] Firmware {firmware_name} registered in blockchain", flush=True)
            return result
        
        except Exception as e:
            print(f"[CMS] Firmware upload error: {e}", flush=True)
            return None
    
    async def get_latest_firmware(
        self,
        device_id: str
    ) -> Optional[Dict[str, Any]]:
        """
        Get latest approved firmware for device
        
        Args:
            device_id: Device identifier
        
        Returns:
            dict with firmware metadata, or None on error
        """
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(
                    self._build_url(f"firmware/latest/{device_id}"),
                    headers=self.headers
                )
            
            if response.status_code != 200:
                print(f"[CMS] Get latest firmware failed: {response.status_code}", flush=True)
                return None
            
            result = response.json()
            print(f"[CMS] Retrieved latest firmware for {device_id}", flush=True)
            return result
        
        except Exception as e:
            print(f"[CMS] Get latest firmware error: {e}", flush=True)
            return None
    
    async def validate_firmware_hash(
        self,
        firmware_hash: str,
        device_id: str
    ) -> Optional[Dict[str, Any]]:
        """
        Validate firmware hash in blockchain ledger
        
        Args:
            firmware_hash: SHA-256 hash to validate
            device_id: Device making the validation
        
        Returns:
            dict with validation status, or None on error
        """
        try:
            payload = {
                "hash": firmware_hash,
                "device_id": device_id
            }
            
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    self._build_url("ledger/validate"),
                    headers=self.headers,
                    json=payload
                )
            
            if response.status_code != 200:
                print(f"[CMS] Ledger validation failed: {response.status_code}", flush=True)
                return None
            
            result = response.json()
            print(f"[CMS] Ledger validation complete for hash {firmware_hash[:16]}...", flush=True)
            return result
        
        except Exception as e:
            print(f"[CMS] Ledger validation error: {e}", flush=True)
            return None
    
    async def update_firmware_status(
        self,
        device_id: str,
        status: str,
        firmware_version: Optional[str] = None,
        details: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Update FOTA status in CMS
        
        Supported statuses: DOWNLOADING, VERIFYING, INSTALLED, SUCCESS, FAILED, ROLLBACK
        
        Args:
            device_id: Device identifier
            status: Update status
            firmware_version: Firmware version being updated to
            details: Additional details
        
        Returns:
            dict with updated status, or None on error
        """
        try:
            payload = {
                "device_id": device_id,
                "status": status,
                "firmware_version": firmware_version,
                "details": details
            }
            
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    self._build_url("firmware/update-status"),
                    headers=self.headers,
                    json=payload
                )
            
            if response.status_code not in (200, 201):
                print(f"[CMS] Status update failed: {response.status_code}", flush=True)
                return None
            
            result = response.json()
            print(f"[CMS] Device {device_id} status updated to: {status}", flush=True)
            return result
        
        except Exception as e:
            print(f"[CMS] Status update error: {e}", flush=True)
            return None
    
    async def issue_certificate(
        self,
        device_id: str,
        public_key: str,
        ttl: str = "365d"
    ) -> Optional[Dict[str, Any]]:
        """
        Issue certificate for device
        
        Args:
            device_id: Device identifier
            public_key: Device's public key
            ttl: Certificate time-to-live
        
        Returns:
            dict with certificate, or None on error
        """
        try:
            payload = {
                "device_id": device_id,
                "public_key": public_key,
                "ttl": ttl
            }
            
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    self._build_url("certificates/issue"),
                    headers=self.headers,
                    json=payload
                )
            
            if response.status_code not in (200, 201):
                print(f"[CMS] Certificate issuance failed: {response.status_code}", flush=True)
                return None
            
            result = response.json()
            print(f"[CMS] Certificate issued for {device_id}", flush=True)
            return result
        
        except Exception as e:
            print(f"[CMS] Certificate issuance error: {e}", flush=True)
            return None
    
    async def revoke_certificate(
        self,
        device_id: str,
        reason: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Revoke device certificate
        
        Args:
            device_id: Device identifier
            reason: Revocation reason
        
        Returns:
            dict with revocation status, or None on error
        """
        try:
            payload = {"reason": reason} if reason else {}
            
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    self._build_url(f"devices/revoke/{device_id}"),
                    headers=self.headers,
                    json=payload
                )
            
            if response.status_code != 200:
                print(f"[CMS] Certificate revocation failed: {response.status_code}", flush=True)
                return None
            
            result = response.json()
            print(f"[CMS] Certificate revoked for {device_id}", flush=True)
            return result
        
        except Exception as e:
            print(f"[CMS] Certificate revocation error: {e}", flush=True)
            return None
    
    async def get_ledger_status(
        self,
        firmware_hash: str
    ) -> Optional[Dict[str, Any]]:
        """
        Get current ledger status for firmware hash
        
        Args:
            firmware_hash: SHA-256 hash to check
        
        Returns:
            dict with ledger status, or None on error
        """
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(
                    self._build_url(f"ledger/status/{firmware_hash}"),
                    headers=self.headers
                )
            
            if response.status_code == 200:
                return response.json()
            else:
                return None
        
        except Exception as e:
            print(f"[CMS] Get ledger status error: {e}", flush=True)
            return None


# Global CMS client instance (lazy loaded)
cms_client: Optional[CMSClient] = None

def get_cms_client() -> CMSClient:
    """Get or create global CMS client instance"""
    import os
    global cms_client
    
    if cms_client is None:
        cms_url = os.getenv("CMS_URL", "http://127.0.0.1:8000")
        cms_api_version = os.getenv("CMS_API_VERSION", "v1")
        
        cms_client = CMSClient(
            cms_url=cms_url,
            api_version=cms_api_version
        )
    
    return cms_client
