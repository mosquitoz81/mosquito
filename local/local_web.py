#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
local_web.py - Pockie Ninja offline web server.

Serves game resources and handles:
  /littleninjasclient.html  - game client page
  /cas.php                  - CAS authentication (login + validate)
  /game/xrconfig            - server configuration (JS)
  /game/xrconfig/...        - server configuration (JS)
  /sendgift.php             - gift endpoint stub
  /gmcmd.php                - GM command endpoint
  /admin.html               - admin panel
  /UI_*, /JS_*              - resource URL mapping
  everything else           - static files from GAME_ROOT

Usage:  python local_web.py [--port 8080] [--game-root ../work/Pockie]
"""

import http.server
import socketserver
import urllib.parse
import json
import os
import sys
import hashlib
import time
import argparse
import mimetypes
import subprocess
import re
import traceback

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
HOST = "127.0.0.1"
PORT = 8080
GAME_ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "work", "Pockie")
SERVER_IP = "127.0.0.1"
SERVER_PORT = 7001
MYSQL_HOST = "127.0.0.1"
MYSQL_PORT = 3306
MYSQL_USER = "root"
MYSQL_PASS = ""
MYSQL_DB   = "webgamedb"

# In-memory ticket store:  ticket_str -> { uid, username, email, gmlevel, ts }
_tickets = {}

# CAS response format for DmEnter validation.
# Try: "pipe", "json", "simple_uid", "simple_ok", "xml_cas"
# Change this if DmEnter does not accept the response.
CAS_VALIDATE_FORMAT = os.environ.get("CAS_FORMAT", "pipe")

# Resource URL -> file path mapping (relative to GAME_ROOT)
RESOURCE_MAP = {
    "/UI_FirstLoading":     "source/movieclip/ui/sceneui/firstloading.s28805.swf",
    "/JS_Fight.js":         "source/script/fight.s33747.j",
    "/JS_HomeNpcAction.js": "source/script/homenpcaction.s14453.j",
}

# Extra resource mappings will be loaded from resource_map.json if it exists
EXTRA_RESOURCE_MAP = {}

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
LOG_FILE = None

def _ts():
    return time.strftime("%Y-%m-%d %H:%M:%S")

def log(msg):
    line = f"[{_ts()}] {msg}"
    print(line, flush=True)
    if LOG_FILE:
        try:
            LOG_FILE.write(line + "\n")
            LOG_FILE.flush()
        except Exception:
            pass

# ---------------------------------------------------------------------------
# CAS helpers
# ---------------------------------------------------------------------------
def make_ticket(uid, username, email="", gmlevel=0):
    raw = f"{uid}:{username}:{time.time()}"
    ticket = hashlib.md5(raw.encode()).hexdigest()
    _tickets[ticket] = {
        "uid": uid,
        "username": username,
        "email": email,
        "gmlevel": gmlevel,
        "ts": int(time.time()),
    }
    return ticket

def validate_ticket(ticket):
    return _tickets.get(ticket)

def cas_validate_response(info):
    """Build CAS validation response in the configured format."""
    uid = info["uid"]
    username = info["username"]
    email = info.get("email", "")
    gmlevel = info.get("gmlevel", 0)

    fmt = CAS_VALIDATE_FORMAT.lower()

    if fmt == "pipe":
        # uid|username|email|gmlevel|timestamp|ok
        return f"{uid}|{username}|{email}|{gmlevel}|{int(time.time())}|ok"

    elif fmt == "json":
        return json.dumps({
            "result": 1,
            "uid": uid,
            "username": username,
            "email": email,
            "gmlevel": gmlevel,
        })

    elif fmt == "simple_uid":
        return str(uid)

    elif fmt == "simple_ok":
        return "ok"

    elif fmt == "xml_cas":
        return (
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            '<cas:serviceResponse xmlns:cas="http://www.yale.edu/tp/cas">\n'
            '  <cas:authenticationSuccess>\n'
            f'    <cas:user>{username}</cas:user>\n'
            '    <cas:attributes>\n'
            f'      <cas:uid>{uid}</cas:uid>\n'
            f'      <cas:email>{email}</cas:email>\n'
            f'      <cas:gmlevel>{gmlevel}</cas:gmlevel>\n'
            '    </cas:attributes>\n'
            '  </cas:authenticationSuccess>\n'
            '</cas:serviceResponse>'
        )

    # fallback: pipe
    return f"{uid}|{username}|{email}|{gmlevel}|{int(time.time())}|ok"

# Pre-generate a default ticket for localadmin so Flash can use it immediately
_default_ticket = make_ticket(1, "localadmin", "localadmin@local", 1)

# ---------------------------------------------------------------------------
# MySQL helper (uses CLI to avoid extra Python deps)
# ---------------------------------------------------------------------------
def mysql_query(sql, fetch=True):
    """Run a SQL query via mysql CLI. Returns list of rows (tab-separated)."""
    cmd = [
        "mysql",
        f"-h{MYSQL_HOST}",
        f"-P{MYSQL_PORT}",
        f"-u{MYSQL_USER}",
        f"-D{MYSQL_DB}",
        "--batch",
        "--skip-column-names",
        "-e", sql,
    ]
    if MYSQL_PASS:
        cmd.insert(4, f"-p{MYSQL_PASS}")
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        if r.returncode != 0:
            log(f"MySQL error: {r.stderr.strip()}")
            return None
        if not fetch:
            return []
        return [line.split("\t") for line in r.stdout.strip().split("\n") if line]
    except FileNotFoundError:
        log("mysql CLI not found; GM commands that need DB will fail")
        return None
    except Exception as e:
        log(f"MySQL exception: {e}")
        return None

# ---------------------------------------------------------------------------
# xrconfig builder
# ---------------------------------------------------------------------------
def build_xrconfig_js():
    """Build the JavaScript configuration that Flash loads."""
    return f"""\
var xrconfig = {{
    "serverId": 1,
    "serverName": "Local Server",
    "serverIp": "{SERVER_IP}",
    "serverPort": {SERVER_PORT},
    "serverState": 1,
    "loginUrl": "http://{SERVER_IP}:{PORT}/cas.php",
    "resourceUrl": "http://{SERVER_IP}:{PORT}/",
    "cdnUrl": "http://{SERVER_IP}:{PORT}/",
    "version": "1.0.0",
    "notice": "Pockie Ninja Offline"
}};

var ServerList = [{{
    "id": 1,
    "name": "Local",
    "ip": "{SERVER_IP}",
    "port": {SERVER_PORT},
    "state": 1,
    "recommend": 1
}}];

var ServerConfig = {{
    "ServerId": 1,
    "ServerName": "Local",
    "ServerHost": "{SERVER_IP}",
    "ServerPort": {SERVER_PORT},
    "ResUrl": "http://{SERVER_IP}:{PORT}/",
    "CdnUrl": "http://{SERVER_IP}:{PORT}/",
    "CasUrl": "http://{SERVER_IP}:{PORT}/cas.php",
    "LoginUrl": "http://{SERVER_IP}:{PORT}/cas.php",
    "Version": "1.0.0"
}};
"""

# ---------------------------------------------------------------------------
# Admin panel HTML
# ---------------------------------------------------------------------------
ADMIN_HTML = """\
<!DOCTYPE html>
<html lang="th">
<head>
<meta charset="UTF-8">
<title>Pockie Ninja - Admin Panel</title>
<style>
  body { font-family: 'Segoe UI', Tahoma, sans-serif; background: #1a1a2e; color: #e0e0e0; margin: 0; padding: 20px; }
  h1 { color: #ff6b35; border-bottom: 2px solid #ff6b35; padding-bottom: 10px; }
  h2 { color: #ffa500; margin-top: 30px; }
  .card { background: #16213e; border-radius: 8px; padding: 20px; margin: 15px 0; border: 1px solid #0f3460; }
  .info { background: #0f3460; padding: 10px 15px; border-radius: 4px; margin: 5px 0; font-family: monospace; }
  input, select { background: #1a1a2e; color: #e0e0e0; border: 1px solid #0f3460; padding: 8px 12px; border-radius: 4px; margin: 4px; }
  button { background: #ff6b35; color: white; border: none; padding: 10px 20px; border-radius: 4px; cursor: pointer; margin: 4px; font-weight: bold; }
  button:hover { background: #ff8c5a; }
  button.danger { background: #c0392b; }
  button.danger:hover { background: #e74c3c; }
  .result { background: #0d1117; color: #58a6ff; padding: 15px; border-radius: 4px; margin-top: 10px; white-space: pre-wrap; font-family: monospace; max-height: 400px; overflow-y: auto; }
  table { border-collapse: collapse; width: 100%%; }
  th, td { padding: 8px 12px; text-align: left; border-bottom: 1px solid #0f3460; }
  th { background: #0f3460; color: #ffa500; }
  .flex { display: flex; gap: 10px; flex-wrap: wrap; align-items: center; }
  .status-ok { color: #2ecc71; }
  .status-err { color: #e74c3c; }
</style>
</head>
<body>

<h1>Pockie Ninja - Admin Panel (Offline)</h1>

<div class="card">
  <h2>Server Status</h2>
  <div id="status">Loading...</div>
  <button onclick="checkStatus()">Refresh</button>
</div>

<div class="card">
  <h2>Account Info</h2>
  <div class="flex">
    <label>Account: <input id="acc-email" value="localadmin@local" size="25"></label>
    <button onclick="getAccountInfo()">Query</button>
  </div>
  <div id="acc-result" class="result" style="display:none"></div>
</div>

<div class="card">
  <h2>GM Commands</h2>
  <p>Commands are sent to the game server. Account must be logged in with gmlevel >= 1.</p>
  <div class="flex">
    <select id="gm-cmd">
      <option value="addgold">Add Gold</option>
      <option value="addcoin">Add Coin</option>
      <option value="addexp">Add EXP</option>
      <option value="additem">Add Item</option>
      <option value="setlevel">Set Level</option>
      <option value="custom">Custom SQL</option>
    </select>
    <input id="gm-arg1" placeholder="value / item_id" size="12">
    <input id="gm-arg2" placeholder="amount (optional)" size="12">
    <label>Target UID: <input id="gm-uid" value="1" size="5"></label>
    <button onclick="sendGmCmd()">Execute</button>
  </div>
  <div id="gm-result" class="result" style="display:none"></div>
</div>

<div class="card">
  <h2>Quick Actions</h2>
  <div class="flex">
    <button onclick="quickAction('max_gold')">Max Gold (999999)</button>
    <button onclick="quickAction('max_level')">Max Level</button>
    <button onclick="quickAction('unlock_all')">Unlock All GM</button>
    <button onclick="quickAction('list_accounts')">List Accounts</button>
  </div>
  <div id="quick-result" class="result" style="display:none"></div>
</div>

<div class="card">
  <h2>Login Ticket</h2>
  <p>Current default ticket (for localadmin): <code id="ticket-val">loading...</code></p>
  <div class="flex">
    <label>Email: <input id="tk-email" value="localadmin@local" size="25"></label>
    <label>Password: <input id="tk-pass" value="localadmin" size="20"></label>
    <button onclick="getTicket()">Generate Ticket</button>
  </div>
  <div id="tk-result" class="result" style="display:none"></div>
</div>

<div class="card">
  <h2>CAS Format</h2>
  <p>If DmEnter rejects login, try changing the CAS validation response format:</p>
  <div class="flex">
    <select id="cas-fmt">
      <option value="pipe">pipe (uid|user|email|gmlevel|ts|ok)</option>
      <option value="json">JSON</option>
      <option value="simple_uid">simple_uid (just uid number)</option>
      <option value="simple_ok">simple_ok (just "ok")</option>
      <option value="xml_cas">XML CAS 2.0</option>
    </select>
    <button onclick="setCasFormat()">Apply</button>
  </div>
  <div id="cas-result" class="result" style="display:none"></div>
</div>

<script>
function api(url, cb) {
  fetch(url).then(r => r.text()).then(cb).catch(e => cb('Error: ' + e));
}
function showResult(id, text) {
  var el = document.getElementById(id);
  el.style.display = 'block';
  el.textContent = text;
}
function checkStatus() {
  api('/admin_api?action=status', function(t) {
    document.getElementById('status').innerHTML = t;
  });
}
function getAccountInfo() {
  var email = document.getElementById('acc-email').value;
  api('/admin_api?action=account_info&email=' + encodeURIComponent(email), function(t) {
    showResult('acc-result', t);
  });
}
function sendGmCmd() {
  var cmd = document.getElementById('gm-cmd').value;
  var arg1 = document.getElementById('gm-arg1').value;
  var arg2 = document.getElementById('gm-arg2').value;
  var uid = document.getElementById('gm-uid').value;
  api('/gmcmd.php?cmd=' + cmd + '&arg1=' + encodeURIComponent(arg1) + '&arg2=' + encodeURIComponent(arg2) + '&uid=' + uid, function(t) {
    showResult('gm-result', t);
  });
}
function quickAction(act) {
  api('/gmcmd.php?cmd=' + act + '&uid=' + document.getElementById('gm-uid').value, function(t) {
    showResult('quick-result', t);
  });
}
function getTicket() {
  var email = document.getElementById('tk-email').value;
  var pass = document.getElementById('tk-pass').value;
  api('/cas.php?action=login&username=' + encodeURIComponent(email) + '&password=' + encodeURIComponent(pass), function(t) {
    showResult('tk-result', t);
  });
}
function setCasFormat() {
  var fmt = document.getElementById('cas-fmt').value;
  api('/admin_api?action=set_cas_format&format=' + fmt, function(t) {
    showResult('cas-result', t);
  });
}

checkStatus();
api('/admin_api?action=get_ticket', function(t) {
  document.getElementById('ticket-val').textContent = t;
});
</script>

</body>
</html>
"""

# ---------------------------------------------------------------------------
# HTTP Handler
# ---------------------------------------------------------------------------
class GameHTTPHandler(http.server.BaseHTTPRequestHandler):

    def log_message(self, fmt, *args):
        log(f"HTTP {self.address_string()} {fmt % args}")

    # ----- routing --------------------------------------------------------

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        qs = urllib.parse.parse_qs(parsed.query)

        log(f"GET {self.path}")

        # --- dynamic endpoints ---
        if path == "/cas.php":
            return self.handle_cas(qs)
        if path.startswith("/game/xrconfig"):
            return self.handle_xrconfig(qs)
        if path == "/admin.html":
            return self.send_html(ADMIN_HTML)
        if path == "/admin_api":
            return self.handle_admin_api(qs)
        if path == "/gmcmd.php":
            return self.handle_gmcmd(qs)
        if path == "/sendgift.php":
            return self.send_json({"result": 1, "msg": "ok"})

        # --- resource URL mapping ---
        # Strip query string for mapping lookup
        mapped = RESOURCE_MAP.get(path) or EXTRA_RESOURCE_MAP.get(path)
        if mapped:
            return self.serve_mapped(mapped)

        # Broad pattern: /UI_* or /JS_* might need lookup
        if path.startswith("/UI_") or path.startswith("/JS_"):
            return self.handle_resource_guess(path)

        # --- static file ---
        self.serve_static(path)

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        content_len = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_len) if content_len > 0 else b""
        qs = urllib.parse.parse_qs(parsed.query)
        post_qs = urllib.parse.parse_qs(body.decode("utf-8", errors="replace"))
        qs.update(post_qs)

        log(f"POST {self.path}  body={body[:200]}")

        if path == "/cas.php":
            return self.handle_cas(qs)
        if path == "/gmcmd.php":
            return self.handle_gmcmd(qs)
        if path == "/sendgift.php":
            return self.send_json({"result": 1, "msg": "ok"})

        self.send_text("OK", 200)

    # ----- CAS endpoint ---------------------------------------------------

    def handle_cas(self, qs):
        action = _qs_first(qs, "action", "")
        ticket = _qs_first(qs, "ticket", "")
        username = _qs_first(qs, "username", "")
        password = _qs_first(qs, "password", "")
        server = _qs_first(qs, "server", "")

        log(f"CAS: action={action} ticket={ticket} username={username} server={server} "
            f"ALL_QS={dict(qs)}")

        # --- Login ---
        if action == "login" or (username and password and not ticket):
            log(f"CAS LOGIN: {username}")
            # For offline, always succeed. Look up uid from DB or use default.
            uid = 1
            email = username
            gmlevel = 1
            rows = mysql_query(
                f"SELECT id, gmlevel FROM accounts WHERE email='{_sql_escape(username)}' LIMIT 1"
            )
            if rows and rows[0]:
                try:
                    uid = int(rows[0][0])
                    gmlevel = int(rows[0][1]) if len(rows[0]) > 1 else 0
                except (ValueError, IndexError):
                    pass

            tk = make_ticket(uid, username.split("@")[0] if "@" in username else username, username, gmlevel)
            resp = json.dumps({
                "result": 1,
                "uid": uid,
                "username": username,
                "ticket": tk,
                "server": server or "s1",
            })
            log(f"CAS LOGIN response: {resp}")
            return self.send_json_raw(resp)

        # --- Validate (called by DmEnter) ---
        if ticket:
            info = validate_ticket(ticket)
            if info:
                resp = cas_validate_response(info)
                log(f"CAS VALIDATE ok: ticket={ticket} -> {resp}")
                return self.send_text(resp, 200)
            else:
                # Ticket unknown - might be DmEnter using a ticket we don't know.
                # Try to accept it anyway for offline mode.
                log(f"CAS VALIDATE: unknown ticket={ticket}, returning default user")
                resp = cas_validate_response({
                    "uid": 1, "username": "localadmin",
                    "email": "localadmin@local", "gmlevel": 1,
                })
                return self.send_text(resp, 200)

        # --- Unknown CAS request - log everything and return success ---
        log(f"CAS UNKNOWN request, returning default success. QS={dict(qs)}")
        # Return the default ticket info
        resp = cas_validate_response({
            "uid": 1, "username": "localadmin",
            "email": "localadmin@local", "gmlevel": 1,
        })
        return self.send_text(resp, 200)

    # ----- xrconfig -------------------------------------------------------

    def handle_xrconfig(self, qs):
        js = build_xrconfig_js()
        self.send_response(200)
        self.send_header("Content-Type", "application/javascript; charset=utf-8")
        self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
        self.send_header("Pragma", "no-cache")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(js.encode("utf-8"))

    # ----- GM commands ----------------------------------------------------

    def handle_gmcmd(self, qs):
        cmd = _qs_first(qs, "cmd", "")
        uid = _qs_first(qs, "uid", "1")
        arg1 = _qs_first(qs, "arg1", "")
        arg2 = _qs_first(qs, "arg2", "")
        log(f"GMCMD: cmd={cmd} uid={uid} arg1={arg1} arg2={arg2}")

        result = "Unknown command"

        if cmd == "addgold" and arg1:
            result = self._gm_sql(f"UPDATE purse SET gold = gold + {int(arg1)} WHERE uid = {int(uid)}")
        elif cmd == "addcoin" and arg1:
            result = self._gm_sql(f"UPDATE purse SET coin = coin + {int(arg1)} WHERE uid = {int(uid)}")
        elif cmd == "addexp" and arg1:
            result = self._gm_sql(f"UPDATE player SET exp = exp + {int(arg1)} WHERE uid = {int(uid)}")
        elif cmd == "setlevel" and arg1:
            result = self._gm_sql(f"UPDATE player SET level = {int(arg1)} WHERE uid = {int(uid)}")
        elif cmd == "additem" and arg1:
            amt = int(arg2) if arg2 else 1
            result = self._gm_sql(
                f"INSERT INTO bag (uid, item_id, amount) VALUES ({int(uid)}, {int(arg1)}, {amt}) "
                f"ON DUPLICATE KEY UPDATE amount = amount + {amt}"
            )
        elif cmd == "max_gold":
            result = self._gm_sql(f"UPDATE purse SET gold = 999999, coin = 999999 WHERE uid = {int(uid)}")
        elif cmd == "max_level":
            result = self._gm_sql(f"UPDATE player SET level = 100, exp = 99999999 WHERE uid = {int(uid)}")
        elif cmd == "unlock_all":
            result = self._gm_sql(f"UPDATE accounts SET gmlevel = 1 WHERE id = {int(uid)}")
        elif cmd == "list_accounts":
            rows = mysql_query("SELECT id, email, gmlevel FROM accounts LIMIT 50")
            if rows:
                result = "ID\tEmail\t\tGMLevel\n" + "\n".join("\t".join(r) for r in rows)
            else:
                result = "No accounts found or mysql error"
        elif cmd == "custom" and arg1:
            rows = mysql_query(arg1)
            result = "\n".join("\t".join(r) for r in rows) if rows else "OK (no output)"
        else:
            result = f"Unknown command or missing args: cmd={cmd}"

        log(f"GMCMD result: {result[:200]}")
        return self.send_text(result, 200)

    def _gm_sql(self, sql):
        log(f"GM SQL: {sql}")
        rows = mysql_query(sql, fetch=False)
        return "OK" if rows is not None else "SQL Error (check logs)"

    # ----- Admin API ------------------------------------------------------

    def handle_admin_api(self, qs):
        action = _qs_first(qs, "action", "")

        if action == "status":
            html = '<table><tr><th>Service</th><th>Port</th><th>Status</th></tr>'
            services = [
                ("MySQL", 3306), ("Flash Policy", 843), ("Socket Proxy", 7001),
                ("DmEnter", 7101), ("Game01", 8001), ("Web Server", 8080),
            ]
            for name, port in services:
                ok = self._check_port(port)
                cls = "status-ok" if ok else "status-err"
                status = "LISTENING" if ok else "DOWN"
                html += f'<tr><td>{name}</td><td>{port}</td><td class="{cls}">{status}</td></tr>'
            html += '</table>'
            return self.send_html_fragment(html)

        elif action == "account_info":
            email = _qs_first(qs, "email", "")
            rows = mysql_query(
                f"SELECT id, email, gmlevel FROM accounts WHERE email LIKE '%{_sql_escape(email)}%' LIMIT 10"
            )
            if rows:
                return self.send_text("\n".join("\t".join(r) for r in rows), 200)
            return self.send_text("Not found or mysql error", 200)

        elif action == "get_ticket":
            return self.send_text(_default_ticket, 200)

        elif action == "set_cas_format":
            global CAS_VALIDATE_FORMAT
            fmt = _qs_first(qs, "format", "pipe")
            CAS_VALIDATE_FORMAT = fmt
            return self.send_text(f"CAS format set to: {fmt}", 200)

        self.send_text("unknown action", 400)

    def _check_port(self, port):
        import socket as _sock
        try:
            s = _sock.socket(_sock.AF_INET, _sock.SOCK_STREAM)
            s.settimeout(0.5)
            s.connect(("127.0.0.1", port))
            s.close()
            return True
        except Exception:
            return False

    # ----- Resource guess -------------------------------------------------

    def handle_resource_guess(self, path):
        """Try to find a resource file that matches the URL pattern."""
        name = path.lstrip("/").replace(".js", ".j").replace(".swf", ".swf")
        # Search in common directories
        search_dirs = ["source/script", "source/movieclip", "source"]
        for d in search_dirs:
            full_dir = os.path.join(GAME_ROOT, d)
            if not os.path.isdir(full_dir):
                continue
            for root, dirs, files in os.walk(full_dir):
                for f in files:
                    if name.lower().replace("_", "").replace("js_", "") in f.lower().replace("_", ""):
                        rel = os.path.relpath(os.path.join(root, f), GAME_ROOT)
                        log(f"Resource guess: {path} -> {rel}")
                        return self.serve_mapped(rel)
        log(f"Resource not found: {path}")
        self.send_error(404, f"Resource not found: {path}")

    # ----- Static file serving --------------------------------------------

    def serve_mapped(self, rel_path):
        full = os.path.join(GAME_ROOT, rel_path.replace("\\", "/"))
        if os.path.isfile(full):
            return self._send_file(full)
        log(f"Mapped file not found: {full}")
        self.send_error(404, f"File not found: {rel_path}")

    def serve_static(self, url_path):
        # Security: prevent directory traversal
        clean = urllib.parse.unquote(url_path).lstrip("/")
        if ".." in clean:
            self.send_error(403, "Forbidden")
            return
        full = os.path.join(GAME_ROOT, clean)
        if os.path.isfile(full):
            return self._send_file(full)
        # Try with index.html
        idx = os.path.join(full, "index.html")
        if os.path.isdir(full) and os.path.isfile(idx):
            return self._send_file(idx)
        self.send_error(404, f"Not found: {url_path}")

    def _send_file(self, filepath):
        ctype, _ = mimetypes.guess_type(filepath)
        if not ctype:
            ext = os.path.splitext(filepath)[1].lower()
            ctype = {
                ".swf": "application/x-shockwave-flash",
                ".j": "application/javascript",
                ".js": "application/javascript",
                ".json": "application/json",
                ".xml": "application/xml",
                ".html": "text/html",
                ".htm": "text/html",
                ".css": "text/css",
                ".png": "image/png",
                ".jpg": "image/jpeg",
                ".gif": "image/gif",
            }.get(ext, "application/octet-stream")

        try:
            with open(filepath, "rb") as f:
                data = f.read()
            self.send_response(200)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(data)
        except Exception as e:
            log(f"Error serving {filepath}: {e}")
            self.send_error(500, str(e))

    # ----- Response helpers -----------------------------------------------

    def send_text(self, text, code=200):
        data = text.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(data)

    def send_json(self, obj):
        return self.send_json_raw(json.dumps(obj, ensure_ascii=False))

    def send_json_raw(self, text):
        data = text.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(data)

    def send_html(self, html):
        data = html.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(data)

    def send_html_fragment(self, html):
        self.send_html(html)

# ---------------------------------------------------------------------------
# Utility
# ---------------------------------------------------------------------------
def _qs_first(qs, key, default=""):
    v = qs.get(key, [default])
    return v[0] if isinstance(v, list) else v

def _sql_escape(s):
    return s.replace("'", "''").replace("\\", "\\\\")

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
class ThreadedHTTPServer(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads = True
    allow_reuse_address = True

def main():
    global HOST, PORT, GAME_ROOT, SERVER_IP, SERVER_PORT, LOG_FILE
    global MYSQL_HOST, MYSQL_PORT, MYSQL_USER, MYSQL_PASS, MYSQL_DB, CAS_VALIDATE_FORMAT

    parser = argparse.ArgumentParser(description="Pockie Ninja offline web server")
    parser.add_argument("--host", default=HOST)
    parser.add_argument("--port", type=int, default=PORT)
    parser.add_argument("--game-root", default=GAME_ROOT)
    parser.add_argument("--server-ip", default=SERVER_IP)
    parser.add_argument("--server-port", type=int, default=SERVER_PORT)
    parser.add_argument("--mysql-host", default=MYSQL_HOST)
    parser.add_argument("--mysql-port", type=int, default=MYSQL_PORT)
    parser.add_argument("--mysql-user", default=MYSQL_USER)
    parser.add_argument("--mysql-pass", default=MYSQL_PASS)
    parser.add_argument("--mysql-db", default=MYSQL_DB)
    parser.add_argument("--cas-format", default=CAS_VALIDATE_FORMAT)
    parser.add_argument("--logfile", default=None)
    args = parser.parse_args()

    HOST = args.host
    PORT = args.port
    GAME_ROOT = os.path.abspath(args.game_root)
    SERVER_IP = args.server_ip
    SERVER_PORT = args.server_port
    MYSQL_HOST = args.mysql_host
    MYSQL_PORT = args.mysql_port
    MYSQL_USER = args.mysql_user
    MYSQL_PASS = args.mysql_pass
    MYSQL_DB = args.mysql_db
    CAS_VALIDATE_FORMAT = args.cas_format

    if args.logfile:
        os.makedirs(os.path.dirname(args.logfile) or ".", exist_ok=True)
        LOG_FILE = open(args.logfile, "a", encoding="utf-8")

    # Load extra resource map if exists
    map_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "resource_map.json")
    if os.path.isfile(map_file):
        try:
            with open(map_file, "r", encoding="utf-8") as f:
                EXTRA_RESOURCE_MAP.update(json.load(f))
            log(f"Loaded {len(EXTRA_RESOURCE_MAP)} extra resource mappings")
        except Exception as e:
            log(f"Failed to load resource_map.json: {e}")

    log(f"Game root: {GAME_ROOT}")
    log(f"Server: {SERVER_IP}:{SERVER_PORT}")
    log(f"CAS format: {CAS_VALIDATE_FORMAT}")
    log(f"Default ticket: {_default_ticket}")

    server = ThreadedHTTPServer((HOST, PORT), GameHTTPHandler)
    log(f"Web server listening on http://{HOST}:{PORT}")
    log(f"Admin panel: http://{HOST}:{PORT}/admin.html")
    log(f"Game:        http://{HOST}:{PORT}/littleninjasclient.html?nocache={int(time.time())}")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        log("Web server shutting down")
    finally:
        server.server_close()
        if LOG_FILE:
            LOG_FILE.close()


if __name__ == "__main__":
    main()
