#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
debug_connection.py - Debug tool for Pockie Ninja connection issues.

Tests each component of the connection chain:
  1. MySQL (3306)
  2. Flash Policy (843)
  3. Web Server (8080) - CAS, xrconfig endpoints
  4. Game01 (8001)
  5. DmEnter (7101)
  6. Socket Proxy (7001)
  7. Full flow simulation

Usage: python debug_connection.py [--fix]
"""

import socket
import sys
import time
import json
import os

try:
    from urllib.request import urlopen, Request
    from urllib.error import URLError
except ImportError:
    from urllib2 import urlopen, Request, URLError

HOST = "127.0.0.1"

def test_tcp(port, name, timeout=3):
    """Test if a TCP port is listening."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(timeout)
        s.connect((HOST, port))
        s.close()
        return True, f"{name} :{port} OK"
    except Exception as e:
        return False, f"{name} :{port} FAIL - {e}"


def test_http(url, name, expect_in=None):
    """Test an HTTP endpoint."""
    try:
        req = Request(url)
        resp = urlopen(req, timeout=5)
        body = resp.read().decode("utf-8", errors="replace")
        code = resp.getcode()
        if expect_in and expect_in not in body:
            return False, f"{name} {url} -> {code} but missing '{expect_in}' in response:\n  {body[:200]}"
        return True, f"{name} {url} -> {code} OK ({len(body)} bytes)"
    except Exception as e:
        return False, f"{name} {url} FAIL - {e}"


def test_flash_policy(port=843):
    """Test Flash policy server response."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(5)
        s.connect((HOST, port))
        s.sendall(b"<policy-file-request/>\x00")
        data = s.recv(4096)
        s.close()
        if b"cross-domain-policy" in data:
            return True, f"Flash policy :{port} OK - got valid policy XML ({len(data)} bytes)"
        return False, f"Flash policy :{port} unexpected response: {data[:100]}"
    except Exception as e:
        return False, f"Flash policy :{port} FAIL - {e}"


def test_proxy_policy(port=7001):
    """Test that the proxy handles policy requests."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(5)
        s.connect((HOST, port))
        s.sendall(b"<policy-file-request/>\x00")
        data = s.recv(4096)
        s.close()
        if b"cross-domain-policy" in data:
            return True, f"Proxy policy :{port} OK - got valid policy XML"
        return False, f"Proxy policy :{port} unexpected response: {data[:100]}"
    except Exception as e:
        return False, f"Proxy policy :{port} FAIL - {e}"


def test_proxy_relay(port=7001):
    """Test that the proxy can connect to DmEnter and relay data."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(5)
        s.connect((HOST, port))
        # Send some non-policy data to trigger relay to DmEnter
        s.sendall(b"\x00\x00\x00\x04TEST")
        s.settimeout(3)
        try:
            data = s.recv(4096)
            s.close()
            if data:
                return True, f"Proxy relay :{port} OK - DmEnter responded with {len(data)} bytes: {data[:60]}"
            return True, f"Proxy relay :{port} OK - connected to DmEnter (no immediate response, may need game protocol)"
        except socket.timeout:
            s.close()
            return True, f"Proxy relay :{port} PARTIAL - connected to DmEnter but no response (may need proper handshake)"
    except Exception as e:
        return False, f"Proxy relay :{port} FAIL - {e}"


def test_cas_login():
    """Test CAS login endpoint."""
    try:
        url = f"http://{HOST}:8080/cas.php?action=login&username=localadmin@local&password=localadmin"
        req = Request(url)
        resp = urlopen(req, timeout=5)
        body = resp.read().decode("utf-8", errors="replace")
        try:
            data = json.loads(body)
            if "ticket" in data:
                return True, f"CAS login OK - ticket: {data['ticket']}", data["ticket"]
        except json.JSONDecodeError:
            pass
        return False, f"CAS login - unexpected response: {body[:200]}", None
    except Exception as e:
        return False, f"CAS login FAIL - {e}", None


def test_cas_validate(ticket):
    """Test CAS validation endpoint (what DmEnter calls)."""
    try:
        url = f"http://{HOST}:8080/cas.php?server=s1&ticket={ticket}"
        req = Request(url)
        resp = urlopen(req, timeout=5)
        body = resp.read().decode("utf-8", errors="replace")
        if body and len(body) > 0:
            return True, f"CAS validate OK - response: {body[:200]}"
        return False, f"CAS validate - empty response"
    except Exception as e:
        return False, f"CAS validate FAIL - {e}"


def main():
    print("=" * 60)
    print("  Pockie Ninja Connection Debugger")
    print("=" * 60)
    print()

    results = []

    # 1. Port checks
    print("--- Port Connectivity ---")
    for port, name in [(3306, "MySQL"), (843, "Flash Policy"), (8080, "Web Server"),
                        (8001, "Game01"), (7101, "DmEnter"), (7001, "Socket Proxy")]:
        ok, msg = test_tcp(port, name)
        results.append((ok, msg))
        print(f"  {'OK' if ok else 'FAIL':4s}  {msg}")

    print()

    # 2. Flash policy
    print("--- Flash Policy ---")
    ok, msg = test_flash_policy(843)
    results.append((ok, msg))
    print(f"  {'OK' if ok else 'FAIL':4s}  {msg}")

    ok, msg = test_proxy_policy(7001)
    results.append((ok, msg))
    print(f"  {'OK' if ok else 'FAIL':4s}  {msg}")

    print()

    # 3. Web endpoints
    print("--- Web Server Endpoints ---")
    tests = [
        (f"http://{HOST}:8080/game/xrconfig", "xrconfig", "ServerPort"),
        (f"http://{HOST}:8080/game/xrconfig/{HOST}:8080.js", "xrconfig JS", "ServerPort"),
        (f"http://{HOST}:8080/admin.html", "Admin panel", "Admin Panel"),
    ]
    for url, name, expect in tests:
        ok, msg = test_http(url, name, expect)
        results.append((ok, msg))
        print(f"  {'OK' if ok else 'FAIL':4s}  {msg}")

    print()

    # 4. CAS flow
    print("--- CAS Authentication Flow ---")
    ok, msg, ticket = test_cas_login()
    results.append((ok, msg))
    print(f"  {'OK' if ok else 'FAIL':4s}  {msg}")

    if ticket:
        ok, msg = test_cas_validate(ticket)
        results.append((ok, msg))
        print(f"  {'OK' if ok else 'FAIL':4s}  {msg}")

    print()

    # 5. Proxy relay
    print("--- Socket Proxy Relay ---")
    ok, msg = test_proxy_relay(7001)
    results.append((ok, msg))
    print(f"  {'OK' if ok else 'FAIL':4s}  {msg}")

    print()

    # Summary
    total = len(results)
    passed = sum(1 for ok, _ in results if ok)
    failed = total - passed
    print("=" * 60)
    print(f"  Results: {passed}/{total} passed, {failed} failed")
    print("=" * 60)

    if failed > 0:
        print()
        print("Failures:")
        for ok, msg in results:
            if not ok:
                print(f"  - {msg}")
        print()
        print("Troubleshooting:")
        print("  1. Run .\\local\\stop-local.bat then .\\local\\start-local.bat")
        print("  2. Check logs in local\\logs\\")
        print("  3. Check DmEnter ERROR*.log in work\\Pockie\\app\\bin\\")
        print("  4. Try changing CAS format: open admin.html -> CAS Format")


if __name__ == "__main__":
    main()
