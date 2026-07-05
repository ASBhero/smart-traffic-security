#!/usr/bin/env python3
"""
hsm_emulator.py - Hardware Security Module Emulator
Root of trust for smart traffic system
"""

import hashlib
import time
import os
import secrets
from typing import Tuple


class HSMEmulator:
    """Hardware Security Module Emulator - Root of Trust"""
    
    def __init__(self, device_id: str = None):
        self.audit_log = []
        self.lockout_until = 0
        self.failed_attempts = 0
        self.max_failed_attempts = 5
        self.sequence_counter = 0
        self.used_nonces = set()
        self.firmware_version = 1
        
        if device_id:
            self.device_id = device_id
        else:
            self.device_id = self._generate_device_id()
        
        self.master_key = self._get_master_key()
        self.device_key = self._derive_device_key()
        
        self._log(f"HSM Initialized - Device ID: {self.device_id[:16]}...")
    
    def _generate_device_id(self) -> str:
        system_info = f"{os.uname().nodename}_{os.getpid()}_{time.time()}"
        unique_hash = hashlib.sha256(system_info.encode()).hexdigest()
        random_component = secrets.token_hex(16)
        return hashlib.sha256(f"{unique_hash}_{random_component}".encode()).hexdigest()
    
    def _get_master_key(self) -> str:
        master_key = os.environ.get("HSM_MASTER_KEY")
        if not master_key:
            master_key = secrets.token_hex(32)
            self._log("New Master Key Generated")
        return master_key
    
    def _derive_device_key(self) -> str:
        combined = f"{self.master_key}_{self.device_id}"
        device_key = hashlib.sha256(combined.encode()).hexdigest()
        self._log("Device Key Derived")
        return device_key
    
    def _log(self, message: str):
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        log_entry = f"[{timestamp}] [{self.device_id[:8]}...] {message}"
        self.audit_log.append(log_entry)
        print(log_entry)
    
    def calculate_signature(self, data: str, nonce: int = None) -> Tuple[str, int]:
        if nonce is None:
            nonce = int(time.time() * 1000) + self.sequence_counter
        
        if nonce in self.used_nonces:
            self._log(f"❌ REPLAY ATTACK DETECTED")
            return None, None
        
        self.used_nonces.add(nonce)
        self.sequence_counter += 1
        
        signed_data = f"{data}|nonce={nonce}|seq={self.sequence_counter}|device={self.device_id}"
        signature = hashlib.sha256(f"{signed_data}_{self.device_key}".encode()).hexdigest()
        
        self._log(f"✅ Signature created - Nonce: {nonce}")
        return signature, nonce
    
    def verify_signature(self, data: str, signature: str, nonce: int) -> bool:
        if nonce in self.used_nonces:
            self._log(f"❌ REPLAY ATTACK DETECTED")
            return False
        
        signed_data = f"{data}|nonce={nonce}|device={self.device_id}"
        expected = hashlib.sha256(f"{signed_data}_{self.device_key}".encode()).hexdigest()
        
        if signature != expected:
            self._log(f"❌ Invalid signature")
            return False
        
        self.used_nonces.add(nonce)
        self.sequence_counter += 1
        self._log(f"✅ Signature verified")
        return True
    
    def get_device_id(self) -> str:
        return self.device_id
    
    def get_audit_log(self) -> list:
        return self.audit_log
    
    def update_version(self, new_version: int) -> bool:
        if new_version > self.firmware_version:
            self.firmware_version = new_version
            return True
        return False


if __name__ == "__main__":
    hsm = HSMEmulator()
    print(f"Device ID: {hsm.get_device_id()[:32]}...")
    sig, nonce = hsm.calculate_signature("test")
    print(f"Signature: {sig[:32]}...")
