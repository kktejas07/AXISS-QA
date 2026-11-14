"""
Keeps scans pointed at the public internet.

A scan fetches whatever address it is given. Without this, someone could aim one
at this server's own network (a database, an admin page, the cloud provider's
metadata address) and read the answers in the scan results.
"""
import ipaddress
import socket
from urllib.parse import urlparse

from app.core.config import settings

REFUSED = "That address is on a private network, which Wiseflow does not scan"


def _private(address: str) -> bool:
    ip = ipaddress.ip_address(address)
    return ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast or ip.is_unspecified


def private_target(url: str | None) -> str | None:
    """
    Why this address may not be scanned, or None when it may.
    A name that cannot be looked up is let through: it is not private, and the scan itself will report that it could not be reached.
    Looked up again when the scan starts, so a name cannot be pointed somewhere else between asking and scanning.
    """
    if settings.ALLOW_PRIVATE_TARGETS or not url:
        return None
    host = urlparse(url).hostname
    if not host:
        return None
    if host.lower() == "localhost" or host.lower().endswith((".localhost", ".local", ".internal")):
        return REFUSED
    try:
        return REFUSED if _private(host) else None        # written as a number, such as 10.0.0.5 or [::1]
    except ValueError:
        pass
    try:
        found = {info[4][0] for info in socket.getaddrinfo(host, None, proto=socket.IPPROTO_TCP)}
    except (socket.gaierror, UnicodeError):
        return None
    return REFUSED if any(_private(address) for address in found) else None
