#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
socket_proxy.py - Flash-to-DmEnter TCP proxy for Pockie Ninja offline server.

Listens on PROXY_PORT (7001).
  - Flash policy requests  -> reply with cross-domain XML, close.
  - Game traffic            -> relay bidirectionally to DmEnter on DMENTER_PORT (7101).

Usage:  python socket_proxy.py [--proxy-port 7001] [--dmenter-port 7101] [--verbose]
"""

import socket
import sys
import os
import threading
import argparse
import time
import traceback

# ---------------------------------------------------------------------------
# Configuration (overridable via CLI or env)
# ---------------------------------------------------------------------------
PROXY_HOST  = os.environ.get("PROXY_HOST", "127.0.0.1")
PROXY_PORT  = int(os.environ.get("PROXY_PORT", "7001"))
DMENTER_HOST = os.environ.get("DMENTER_HOST", "127.0.0.1")
DMENTER_PORT = int(os.environ.get("DMENTER_PORT", "7101"))
BUFFER_SIZE  = 8192
CONNECT_TIMEOUT = 10.0
FIRST_READ_TIMEOUT = 15.0

POLICY_MAGIC = b"<policy-file-request/>"

POLICY_RESPONSE = (
    b'<?xml version="1.0"?>\n'
    b'<!DOCTYPE cross-domain-policy SYSTEM '
    b'"http://www.adobe.com/xml/dtds/cross-domain-policy.dtd">\n'
    b'<cross-domain-policy>\n'
    b'  <allow-access-from domain="*" to-ports="*"/>\n'
    b'</cross-domain-policy>\x00'
)

# ---------------------------------------------------------------------------
# Logging helpers  (no external deps)
# ---------------------------------------------------------------------------
_log_lock = threading.Lock()
LOG_FILE = None

def _ts():
    return time.strftime("%Y-%m-%d %H:%M:%S")

def log(level, msg):
    line = f"[{_ts()}] [{level}] {msg}"
    with _log_lock:
        print(line, flush=True)
        if LOG_FILE:
            try:
                LOG_FILE.write(line + "\n")
                LOG_FILE.flush()
            except Exception:
                pass

def log_info(msg):  log("INFO", msg)
def log_debug(msg): log("DEBUG", msg)
def log_warn(msg):  log("WARN", msg)
def log_error(msg): log("ERROR", msg)

def hexpreview(data, maxlen=64):
    preview = data[:maxlen]
    hex_str = " ".join(f"{b:02x}" for b in preview)
    ascii_str = "".join(chr(b) if 32 <= b < 127 else "." for b in preview)
    suffix = f" ... ({len(data)} total)" if len(data) > maxlen else ""
    return f"[{hex_str}] [{ascii_str}]{suffix}"

# ---------------------------------------------------------------------------
# Connection counter
# ---------------------------------------------------------------------------
_conn_counter = 0
_conn_lock = threading.Lock()

def next_conn_id():
    global _conn_counter
    with _conn_lock:
        _conn_counter += 1
        return _conn_counter

# ---------------------------------------------------------------------------
# Relay thread
# ---------------------------------------------------------------------------
def relay(src, dst, label, stop_event):
    """Copy bytes from src to dst until EOF or error."""
    try:
        while not stop_event.is_set():
            try:
                data = src.recv(BUFFER_SIZE)
            except socket.timeout:
                continue
            except OSError:
                break
            if not data:
                log_info(f"{label}: remote closed (EOF)")
                break
            log_debug(f"{label}: {len(data)} bytes")
            try:
                dst.sendall(data)
            except OSError as e:
                log_info(f"{label}: send failed: {e}")
                break
    except Exception as e:
        log_warn(f"{label}: relay exception: {e}")
    finally:
        stop_event.set()
        safe_close(src)
        safe_close(dst)

def safe_close(sock):
    try:
        sock.shutdown(socket.SHUT_RDWR)
    except OSError:
        pass
    try:
        sock.close()
    except OSError:
        pass

# ---------------------------------------------------------------------------
# Client handler
# ---------------------------------------------------------------------------
def handle_client(client_sock, addr):
    cid = next_conn_id()
    tag = f"C{cid}|{addr[0]}:{addr[1]}"
    log_info(f"{tag}: new connection")

    client_sock.settimeout(FIRST_READ_TIMEOUT)

    try:
        first_data = client_sock.recv(BUFFER_SIZE)
    except socket.timeout:
        log_warn(f"{tag}: timeout waiting for first packet")
        safe_close(client_sock)
        return
    except OSError as e:
        log_warn(f"{tag}: error reading first packet: {e}")
        safe_close(client_sock)
        return

    if not first_data:
        log_info(f"{tag}: empty first packet, closing")
        safe_close(client_sock)
        return

    log_info(f"{tag}: first packet ({len(first_data)} bytes): {hexpreview(first_data)}")

    # --- Flash policy request ---
    if first_data.startswith(POLICY_MAGIC):
        log_info(f"{tag}: -> policy request, sending policy XML")
        try:
            client_sock.sendall(POLICY_RESPONSE)
        except OSError:
            pass
        safe_close(client_sock)
        return

    # --- Game traffic -> forward to DmEnter ---
    log_info(f"{tag}: -> game data, connecting to DmEnter {DMENTER_HOST}:{DMENTER_PORT}")
    dmenter_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    dmenter_sock.settimeout(CONNECT_TIMEOUT)

    try:
        dmenter_sock.connect((DMENTER_HOST, DMENTER_PORT))
    except Exception as e:
        log_error(f"{tag}: cannot connect to DmEnter: {e}")
        safe_close(client_sock)
        safe_close(dmenter_sock)
        return

    log_info(f"{tag}: connected to DmEnter, forwarding first packet")
    try:
        dmenter_sock.sendall(first_data)
    except OSError as e:
        log_error(f"{tag}: failed to send first packet to DmEnter: {e}")
        safe_close(client_sock)
        safe_close(dmenter_sock)
        return

    client_sock.settimeout(1.0)
    dmenter_sock.settimeout(1.0)

    stop = threading.Event()
    t1 = threading.Thread(
        target=relay,
        args=(client_sock, dmenter_sock, f"{tag}:Flash->DmEnter", stop),
        daemon=True,
    )
    t2 = threading.Thread(
        target=relay,
        args=(dmenter_sock, client_sock, f"{tag}:DmEnter->Flash", stop),
        daemon=True,
    )
    t1.start()
    t2.start()
    t1.join()
    t2.join()
    log_info(f"{tag}: session ended")

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    global PROXY_HOST, PROXY_PORT, DMENTER_HOST, DMENTER_PORT, LOG_FILE

    parser = argparse.ArgumentParser(description="Flash-to-DmEnter TCP proxy")
    parser.add_argument("--proxy-host", default=PROXY_HOST)
    parser.add_argument("--proxy-port", type=int, default=PROXY_PORT)
    parser.add_argument("--dmenter-host", default=DMENTER_HOST)
    parser.add_argument("--dmenter-port", type=int, default=DMENTER_PORT)
    parser.add_argument("--logfile", default=None)
    parser.add_argument("--verbose", "-v", action="store_true")
    args = parser.parse_args()

    PROXY_HOST = args.proxy_host
    PROXY_PORT = args.proxy_port
    DMENTER_HOST = args.dmenter_host
    DMENTER_PORT = args.dmenter_port

    if args.logfile:
        os.makedirs(os.path.dirname(args.logfile) or ".", exist_ok=True)
        LOG_FILE = open(args.logfile, "a", encoding="utf-8")

    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        server.bind((PROXY_HOST, PROXY_PORT))
    except OSError as e:
        log_error(f"Cannot bind {PROXY_HOST}:{PROXY_PORT}: {e}")
        sys.exit(1)

    server.listen(50)
    log_info(f"Proxy listening on {PROXY_HOST}:{PROXY_PORT}  ->  DmEnter {DMENTER_HOST}:{DMENTER_PORT}")
    log_info("Waiting for Flash connections...")

    try:
        while True:
            client_sock, addr = server.accept()
            t = threading.Thread(target=handle_client, args=(client_sock, addr), daemon=True)
            t.start()
    except KeyboardInterrupt:
        log_info("Proxy shutting down (Ctrl+C)")
    finally:
        server.close()
        if LOG_FILE:
            LOG_FILE.close()


if __name__ == "__main__":
    main()
