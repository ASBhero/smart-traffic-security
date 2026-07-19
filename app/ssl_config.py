"""
SSL/TLS Configuration for FOTA Server
Enforces TLS v1.2 minimum for all device communication (Transport Boundary)
"""
import ssl
import os

def create_ssl_context():
    """
    Create SSL context enforcing TLS v1.2 minimum.
    This is used for mTLS endpoints where devices authenticate with client certificates.
    """
    context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
    
    # Enforce TLS v1.2 minimum (disable TLS 1.0, 1.1)
    context.minimum_version = ssl.TLSVersion.TLSv1_2
    context.maximum_version = ssl.TLSVersion.TLSv1_3  # Allow TLS 1.3 for forward compatibility
    
    # Require client certificate for mTLS
    context.verify_mode = ssl.CERT_REQUIRED
    context.load_verify_locations(os.environ.get('CLIENT_CA_CERT', '/app/certs/ca.crt'))
    
    # Load server certificate and key
    context.load_cert_chain(
        certfile=os.environ.get('SERVER_CERT', '/app/certs/server.crt'),
        keyfile=os.environ.get('SERVER_KEY', '/app/certs/server.key')
    )
    
    # Cipher suites recommended for TLS 1.2 (ECDSA preferred for IoT devices)
    # These are strong, modern ciphers suitable for embedded systems
    context.set_ciphers('ECDHE+AESGCM:ECDHE+CHACHA20:DHE+AESGCM:DHE+CHACHA20:!aNULL:!eNULL:!EXPORT:!DSS:!DES:!RC4:!3DES:!MD5:!PSK')
    
    return context

def get_tls_version_string():
    """Return human-readable TLS version requirement"""
    return "TLS v1.2 minimum (TLS v1.3 supported)"
