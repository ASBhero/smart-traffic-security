<< 'EOF'
#!/usr/bin/env python3
"""
Integration Test Script for Smart Traffic Security System
Run this to test all components are working together
"""

import requests
import json
import time
import sys
import os

# Load configuration
CONFIG_FILE = os.path.join(os.path.dirname(__file__), '..', '..', 'shared', 'config', 'team_ips.json')

def load_config():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE) as f:
            return json.load(f)
    else:
        return {
            "hsm_kms": {"ip": "127.0.0.1", "port": 8200},
            "cms": {"ip": "127.0.0.1", "port": 8442},
            "fota": {"ip": "127.0.0.1", "port": 5000},
            "traffic": {"ip": "127.0.0.1", "port": 8080},
            "wokwi": {"ip": "127.0.0.1", "port": 8081}
        }

def test_component(name, url, method="GET", data=None, timeout=5):
    try:
        if method == "GET":
            response = requests.get(url, timeout=timeout, verify=False)
        elif method == "POST":
            response = requests.post(url, json=data, timeout=timeout, verify=False)
        else:
            response = requests.request(method, url, timeout=timeout, verify=False)
        
        if response.status_code in [200, 201, 204]:
            print(f"✅ {name}: Connected (Status: {response.status_code})")
            return True
        else:
            print(f"⚠️ {name}: Responded with {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ {name}: Not reachable - {str(e)}")
        return False

def main():
    print("=" * 60)
    print("   INTEGRATION TEST - Smart Traffic Security System")
    print("=" * 60)
    
    config = load_config()
    
    print("\n1. Testing HSM + KMS (Vault)...")
    test_component("HSM/KMS", f"http://{config['hsm_kms']['ip']}:{config['hsm_kms']['port']}/v1/sys/seal-status")
    
    print("\n2. Testing CMS (EJBCA)...")
    test_component("CMS", f"https://{config['cms']['ip']}:{config['cms']['port']}/ejbca/health")
    
    print("\n3. Testing FOTA Server...")
    test_component("FOTA", f"http://{config['fota']['ip']}:{config['fota']['port']}/api/health")
    
    print("\n4. Testing Traffic Controller...")
    test_component("Traffic", f"http://{config['traffic']['ip']}:{config['traffic']['port']}/api/health")
    
    print("\n5. Testing Wokwi (ATECC608A)...")
    test_component("Wokwi", f"http://{config['wokwi']['ip']}:{config['wokwi']['port']}/api/health")
    
    print("\n" + "=" * 60)
    print("   INTEGRATION TEST COMPLETE")
    print("=" * 60)

if __name__ == "__main__":
    main()
EOF

