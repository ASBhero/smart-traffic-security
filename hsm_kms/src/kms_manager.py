#!/usr/bin/env python3
"""
kms_manager.py - Key Management System
Key lifecycle management for smart traffic system
"""

import os
import secrets
import time
import json
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.backends import default_backend


class KeyManagementSystem:
    """Key Management System"""
    
    def __init__(self, storage_path="./keys"):
        self.storage_path = storage_path
        self.master_key = None
        self.key_metadata = {}
        self.audit_log = []
        os.makedirs(storage_path, exist_ok=True)
        self._log("KMS Initialized")
    
    def _log(self, message):
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        self.audit_log.append(f"[{timestamp}] {message}")
        print(f"[{timestamp}] {message}")
    
    def generate_master_key(self):
        self._log("Generating master key")
        self.master_key = secrets.token_bytes(32)
        self.key_metadata = {
            "key_id": hash(self.master_key) & 0xFFFFFFFF,
            "created": time.time(),
            "status": "active"
        }
        self._save_metadata()
        return self.master_key
    
    def _save_metadata(self):
        with open(f"{self.storage_path}/metadata.json", "w") as f:
            json.dump(self.key_metadata, f)
    
    def derive_child_key(self, purpose, length=32):
        hkdf = HKDF(
            algorithm=hashes.SHA256(),
            length=length,
            salt=None,
            info=purpose.encode(),
            backend=default_backend()
        )
        return hkdf.derive(self.master_key)
    
    def encrypt_key(self, key_bytes):
        iv = secrets.token_bytes(16)
        cipher = Cipher(algorithms.AES(self.master_key), modes.CFB(iv), backend=default_backend())
        encryptor = cipher.encryptor()
        encrypted = encryptor.update(key_bytes) + encryptor.finalize()
        return encrypted, iv
    
    def decrypt_key(self, encrypted_key, iv):
        cipher = Cipher(algorithms.AES(self.master_key), modes.CFB(iv), backend=default_backend())
        decryptor = cipher.decryptor()
        return decryptor.update(encrypted_key) + decryptor.finalize()
    
    def get_audit_log(self):
        return self.audit_log


if __name__ == "__main__":
    kms = KeyManagementSystem("./test_keys")
    kms.generate_master_key()
    print("✅ KMS initialized")
    child = kms.derive_child_key("CMS_DB")
    print(f"Child key: {child[:8].hex()}...")
