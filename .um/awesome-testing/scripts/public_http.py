"""Bounded, unauthenticated HTTP(S), pinned to a validated public address.

Do not use ambient proxies, cookies, GitHub auth, or credential-bearing URLs.
Resolve each redirect separately and connect to the inspected IP, not the hostname.
"""
import base64
import json
import os
from pathlib import Path
import subprocess
import sys
import http.client
import ipaddress
import socket
import ssl
import time
from urllib.parse import urljoin, urlsplit

MAX_BYTES = 512 * 1024
MAX_REDIRECTS = 5
TIMEOUT = 10


def destination(url):
    if len(url) > 4096 or any(ord(c) < 33 or ord(c) == 127 for c in url) or "\\" in url:
        raise ValueError("Malformed or oversized URL")
    parsed = urlsplit(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username is not None or parsed.password is not None:
        raise ValueError("Only public HTTP(S) URLs without credentials are allowed")
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    if port != (443 if parsed.scheme == "https" else 80):
        raise ValueError("Nonstandard destination port")
    host = parsed.hostname.encode("idna").decode("ascii")
    addresses = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    if not addresses:
        raise ValueError("No destination addresses")
    for item in addresses:
        ip = ipaddress.ip_address(item[4][0])
        # IPv6 transition addresses may reach private IPv4 networks.
        if not ip.is_global or ip.is_multicast or getattr(ip, "is_site_local", False) or (ip.version == 6 and (ip.ipv4_mapped or ip.sixtofour or ip.teredo)):
            raise ValueError("Non-public network destination")
    return parsed, host, port, addresses


def _connect(addresses):
    last = None
    for family, kind, protocol, _, address in addresses[:4]:
        sock = socket.socket(family, kind, protocol)
        sock.settimeout(TIMEOUT)
        try:
            sock.connect(address)
            return sock
        except OSError as error:
            sock.close()
            last = error
    raise last or OSError("No destination addresses")


def _fetch(url, limit=MAX_BYTES):
    started = time.monotonic()
    current = url
    for hop in range(MAX_REDIRECTS + 1):
        if time.monotonic() - started > 30:
            raise TimeoutError("Total fetch time exceeded")
        parsed, host, port, addresses = destination(current)
        connection = http.client.HTTPConnection(host, port, timeout=TIMEOUT)
        sock = _connect(addresses)
        try:
            if parsed.scheme == "https":
                sock = ssl.create_default_context().wrap_socket(sock, server_hostname=host)
            connection.sock = sock
            target = parsed.path or "/"
            if parsed.query:
                target += "?" + parsed.query
            connection.request("GET", target, headers={"User-Agent": "awesome-testing-review/1.0", "Accept-Encoding": "identity"})
            response = connection.getresponse()
            location = response.getheader("Location")
            if response.status in {301, 302, 303, 307, 308} and location:
                if hop == MAX_REDIRECTS:
                    raise ValueError("Redirect limit exceeded")
                current = urljoin(current, location)
                continue
            content = bytearray()
            while len(content) <= limit:
                if time.monotonic() - started > 30:
                    raise TimeoutError("Total fetch time exceeded")
                chunk = response.read1(min(16384, limit + 1 - len(content)))
                if not chunk:
                    break
                content.extend(chunk)
            return {"status": response.status, "finalUrl": current,
                    "contentType": response.getheader("Content-Type", ""),
                    "truncated": len(content) > limit, "content": bytes(content[:limit])}
        finally:
            connection.close()
            sock.close()
    raise ValueError("Redirect limit exceeded")


def fetch(url, limit=MAX_BYTES):
    """A killable process bounds DNS, connect, TLS, headers, and body to 35 seconds."""
    if type(limit) is not int or not 1 <= limit <= 1024 * 1024:
        raise ValueError("Invalid response size limit")
    environment = {key: os.environ[key] for key in ("PATH", "LANG", "SSL_CERT_FILE", "NIX_SSL_CERT_FILE") if key in os.environ}
    try:
        result = subprocess.run([sys.executable, str(Path(__file__).resolve())],
                                input=json.dumps({"url": url, "limit": limit}), text=True,
                                capture_output=True, timeout=35, env=environment, check=True)
    except subprocess.TimeoutExpired as error:
        raise TimeoutError("Public fetch exceeded the 35-second process deadline") from error
    response = json.loads(result.stdout)
    if "error" in response:
        raise ValueError(response["error"])
    response["content"] = base64.b64decode(response.pop("contentBase64"), validate=True)
    return response


if __name__ == "__main__":
    try:
        request = json.loads(sys.stdin.read(8192))
        response = _fetch(request["url"], request["limit"])
        response["contentBase64"] = base64.b64encode(response.pop("content")).decode("ascii")
    except Exception as error:
        response = {"error": str(error)[:300]}
    print(json.dumps(response))
