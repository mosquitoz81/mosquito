#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
flash_policy.py - Flash cross-domain policy server on port 843.

Flash Player connects to port 843 first to request the master policy file.
This tiny server responds with an allow-all policy and closes the connection.

Usage:  python flash_policy.py [--port 843]
"""

import socket
import sys
import os
import threading
import argparse
import time

HOST = "0.0.0.0"
PORT = 843

POLICY_RESPONSE = (
    b'<?xml version="1.0"?>\n'
    b'<!DOCTYPE cross-domain-policy SYSTEM '
    b'"http://www.adobe.com/xml/dtds/cross-domain-policy.dtd">\n'
    b'<cross-domain-policy>\n'
    b'  <site-control permitted-cross-domain-policies="master-only"/>\n'
    b'  <allow-access-from domain="*" to-ports="*"/>\n'
    b'</cross-domain-policy>\x00'
)

def _ts():
    return time.strftime("%Y-%m-%d %H:%M:%S")

def handle(conn, addr):
    try:
        conn.settimeout(5.0)
        data = conn.recv(256)
        print(f"[{_ts()}] {addr}: recv {len(data) if data else 0} bytes", flush=True)
        conn.sendall(POLICY_RESPONSE)
    except Exception as e:
        print(f"[{_ts()}] {addr}: error: {e}", flush=True)
    finally:
        try:
            conn.close()
        except OSError:
            pass

def main():
    parser = argparse.ArgumentParser(description="Flash policy server")
    parser.add_argument("--port", type=int, default=PORT)
    parser.add_argument("--host", default=HOST)
    args = parser.parse_args()

    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        srv.bind((args.host, args.port))
    except OSError as e:
        print(f"Cannot bind {args.host}:{args.port}: {e}", file=sys.stderr)
        sys.exit(1)

    srv.listen(20)
    print(f"[{_ts()}] Flash policy server listening on {args.host}:{args.port}", flush=True)

    try:
        while True:
            conn, addr = srv.accept()
            threading.Thread(target=handle, args=(conn, addr), daemon=True).start()
    except KeyboardInterrupt:
        print(f"\n[{_ts()}] Policy server shutting down")
    finally:
        srv.close()

if __name__ == "__main__":
    main()
