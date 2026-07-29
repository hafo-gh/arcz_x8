"""Online detection: a cheap TCP connect to decide whether to attempt upload."""
import socket
from urllib.parse import urlparse


def endpoint_host_port(endpoint, default_port=443):
    """Extract (host, port) from an upload endpoint URL."""
    parsed = urlparse(endpoint)
    host = parsed.hostname
    port = parsed.port or (443 if parsed.scheme == 'https' else 80) or default_port
    return host, port


def is_online(host, port, timeout_s=3.0):
    """Return True if a TCP connection to host:port succeeds within timeout."""
    if not host:
        return False
    try:
        with socket.create_connection((host, int(port)), timeout=timeout_s):
            return True
    except OSError:
        return False
