#!/usr/bin/env python3
"""
ACDC - Advanced Control & Deployment Console
Backend Flask - Un Fantasma en el Sistema
"""

import os
import re
import json
import time
import shutil
import hashlib
import subprocess
import threading
from pathlib import Path
from datetime import datetime, timedelta
from functools import wraps

import psutil
from flask import Flask, render_template, request, jsonify, session, redirect, url_for

# ─── Config ───────────────────────────────────────────────────────────────────

CONFIG_FILE = Path(__file__).parent / "config.json"

def load_config():
    default = {
        "username": "admin",
        "password_hash": hashlib.sha256("admin".encode()).hexdigest(),
        "port": 8080,
        "host": "0.0.0.0",
        "session_timeout_minutes": 60,
        "site_url": "https://www.unfantasmaenelsistema.com"
    }
    if CONFIG_FILE.exists():
        with open(CONFIG_FILE) as f:
            return {**default, **json.load(f)}
    return default

CONFIG = load_config()

app = Flask(__name__)
app.secret_key = os.urandom(32)
app.config["SEND_FILE_MAX_AGE_DEFAULT"] = 0
app.config["TEMPLATES_AUTO_RELOAD"] = True

@app.after_request
def no_cache(response):
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response

# ─── Auth ──────────────────────────────────────────────────────────────────────

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if "user" not in session:
            if request.path.startswith("/api/"):
                return jsonify({"error": "unauthorized"}), 401
            return redirect(url_for("login_page"))
        return f(*args, **kwargs)
    return decorated

def check_session_timeout():
    if "login_time" in session:
        elapsed = datetime.now() - datetime.fromisoformat(session["login_time"])
        if elapsed > timedelta(minutes=CONFIG["session_timeout_minutes"]):
            session.clear()
            return False
    return True

# ─── Routes: Pages ─────────────────────────────────────────────────────────────

@app.route("/")
def index():
    if "user" not in session:
        return redirect(url_for("login_page"))
    return render_template("index.html", config=CONFIG)

@app.route("/login")
def login_page():
    if "user" in session:
        return redirect(url_for("index"))
    return render_template("login.html", config=CONFIG)

# ─── API: Auth ─────────────────────────────────────────────────────────────────

@app.route("/api/login", methods=["POST"])
def api_login():
    data = request.get_json()
    username = data.get("username", "")
    password = data.get("password", "")
    ph = hashlib.sha256(password.encode()).hexdigest()
    if username == CONFIG["username"] and ph == CONFIG["password_hash"]:
        session["user"] = username
        session["login_time"] = datetime.now().isoformat()
        return jsonify({"ok": True})
    return jsonify({"ok": False, "error": "Credenciales incorrectas"}), 401

@app.route("/api/logout", methods=["POST"])
def api_logout():
    session.clear()
    return jsonify({"ok": True})

# ─── API: Dashboard ────────────────────────────────────────────────────────────

@app.route("/api/dashboard")
@login_required
def api_dashboard():
    cpu = psutil.cpu_percent(interval=0.5)
    mem = psutil.virtual_memory()
    disk = psutil.disk_usage("/")
    net = psutil.net_io_counters()
    boot = datetime.fromtimestamp(psutil.boot_time())
    uptime = datetime.now() - boot
    days = uptime.days
    hours = uptime.seconds // 3600
    minutes = (uptime.seconds % 3600) // 60

    try:
        with open("/etc/os-release") as f:
            os_info = {}
            for line in f:
                if "=" in line:
                    k, v = line.strip().split("=", 1)
                    os_info[k] = v.strip('"')
        os_name = os_info.get("PRETTY_NAME", "Linux")
    except Exception:
        os_name = "Linux"

    import platform
    return jsonify({
        "cpu": {"percent": cpu, "cores": psutil.cpu_count(), "freq": round(psutil.cpu_freq().current / 1000, 1) if psutil.cpu_freq() else 0},
        "memory": {"percent": mem.percent, "used_gb": round(mem.used / 1e9, 1), "total_gb": round(mem.total / 1e9, 1)},
        "disk": {"percent": disk.percent, "used_gb": round(disk.used / 1e9, 1), "total_gb": round(disk.total / 1e9, 1)},
        "network": {"bytes_sent": net.bytes_sent, "bytes_recv": net.bytes_recv},
        "uptime": f"{days}d {hours}h {minutes}m",
        "os": os_name,
        "hostname": platform.node(),
        "kernel": platform.release()
    })

# ─── API: Processes ────────────────────────────────────────────────────────────

@app.route("/api/processes")
@login_required
def api_processes():
    procs = []
    for p in psutil.process_iter(["pid", "name", "username", "cpu_percent", "memory_percent", "status", "cmdline"]):
        try:
            info = p.info
            procs.append({
                "pid": info["pid"],
                "name": info["name"],
                "user": info["username"] or "",
                "cpu": round(info["cpu_percent"] or 0, 1),
                "mem": round(info["memory_percent"] or 0, 1),
                "status": info["status"]
            })
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    procs.sort(key=lambda x: x["cpu"], reverse=True)
    return jsonify(procs[:100])

@app.route("/api/processes")
@login_required
def api_processes():
    procs = []
    for p in psutil.process_iter(["pid", "name", "username", "cpu_percent", "memory_percent", "status", "cmdline"]):
        try:
            info = p.info
            procs.append({
                "pid": info["pid"],
                "name": info["name"],
                "user": info["username"] or "",
                "cpu": round(info["cpu_percent"] or 0, 1),
                "mem": round(info["memory_percent"] or 0, 1),
                "status": info["status"]
            })
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    procs.sort(key=lambda x: x["cpu"], reverse=True)
    return jsonify(procs[:200])

@app.route("/api/processes/<int:pid>/kill", methods=["POST"])
@login_required
def api_kill_process(pid):
    data = request.get_json() or {}
    force = data.get("force", False)
    try:
        p = psutil.Process(pid)
        pname = p.name()
        if force:
            # SIGKILL - forzado, no ignorable
            out, rc = run_cmd(f"sudo kill -9 {pid} 2>&1")
            if rc != 0:
                # fallback sin sudo
                p.kill()
        else:
            # SIGTERM primero, luego SIGKILL si no responde
            try:
                p.terminate()
                p.wait(timeout=3)
            except psutil.TimeoutExpired:
                p.kill()
            except psutil.AccessDenied:
                # proceso de otro usuario, usar sudo
                out, rc = run_cmd(f"sudo kill -15 {pid} 2>&1")
                if rc != 0:
                    out, rc = run_cmd(f"sudo kill -9 {pid} 2>&1")
                    if rc != 0:
                        return jsonify({"ok": False, "error": f"Sin permisos para matar PID {pid} ({pname}). Intenta forzar."}), 403
        return jsonify({"ok": True, "name": pname})
    except psutil.NoSuchProcess:
        return jsonify({"ok": True, "name": "ya no existe"})
    except psutil.AccessDenied:
        # último recurso con sudo
        out, rc = run_cmd(f"sudo kill -9 {pid} 2>&1")
        return jsonify({"ok": rc == 0, "error": out if rc != 0 else None})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

# ─── API: Services (systemd) ───────────────────────────────────────────────────

def run_cmd(cmd, timeout=10):
    try:
        r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout)
        return r.stdout.strip(), r.returncode
    except subprocess.TimeoutExpired:
        return "timeout", 1

@app.route("/api/services")
@login_required
def api_services():
    out, _ = run_cmd("systemctl list-units --type=service --all --no-pager --no-legend --plain 2>/dev/null | head -80")
    services = []
    for line in out.splitlines():
        parts = line.split()
        if len(parts) >= 4:
            services.append({
                "name": parts[0],
                "load": parts[1],
                "active": parts[2],
                "sub": parts[3],
                "description": " ".join(parts[4:]) if len(parts) > 4 else ""
            })
    return jsonify(services)

@app.route("/api/services/<service>/<action>", methods=["POST"])
@login_required
def api_service_action(service, action):
    service = re.sub(r"[^a-zA-Z0-9._@-]", "", service)
    if action not in ("start", "stop", "restart", "enable", "disable", "status"):
        return jsonify({"ok": False, "error": "Acción no permitida"}), 400
    out, rc = run_cmd(f"systemctl {action} {service} 2>&1")
    return jsonify({"ok": rc == 0, "output": out})

# ─── API: Logs ─────────────────────────────────────────────────────────────────

@app.route("/api/logs")
@login_required
def api_logs():
    source = request.args.get("source", "syslog")
    lines = int(request.args.get("lines", 100))
    lines = min(lines, 500)

    sources = {
        "syslog": "journalctl -n {n} --no-pager 2>/dev/null",
        "kernel": "journalctl -k -n {n} --no-pager 2>/dev/null",
        "auth": "journalctl -u ssh -n {n} --no-pager 2>/dev/null",
        "nginx": "journalctl -u nginx -n {n} --no-pager 2>/dev/null",
        "docker": "journalctl -u docker -n {n} --no-pager 2>/dev/null",
    }
    cmd = sources.get(source, sources["syslog"]).format(n=lines)
    out, _ = run_cmd(cmd, timeout=15)
    return jsonify({"lines": out.splitlines()})

# ─── API: Packages (apt) ───────────────────────────────────────────────────────

@app.route("/api/packages/upgradable")
@login_required
def api_packages_upgradable():
    out, _ = run_cmd("apt list --upgradable 2>/dev/null | grep -v '^Listing'")
    pkgs = []
    for line in out.splitlines():
        if "/" in line:
            name = line.split("/")[0]
            parts = line.split()
            version = parts[1] if len(parts) > 1 else ""
            pkgs.append({"name": name, "version": version})
    return jsonify(pkgs)

@app.route("/api/packages/search")
@login_required
def api_packages_search():
    query = re.sub(r"[^a-zA-Z0-9+._-]", "", request.args.get("q", ""))
    if len(query) < 2:
        return jsonify([])
    out, _ = run_cmd(f"apt-cache search --names-only {query} 2>/dev/null | head -30")
    pkgs = []
    for line in out.splitlines():
        if " - " in line:
            name, desc = line.split(" - ", 1)
            pkgs.append({"name": name.strip(), "description": desc.strip()})
    return jsonify(pkgs)

@app.route("/api/packages/<action>/<package>", methods=["POST"])
@login_required
def api_package_action(action, package):
    package = re.sub(r"[^a-zA-Z0-9+._-]", "", package)
    if action not in ("install", "remove", "upgrade"):
        return jsonify({"ok": False, "error": "Acción no permitida"}), 400
    cmd_map = {
        "install": f"apt-get install -y {package} 2>&1",
        "remove": f"apt-get remove -y {package} 2>&1",
        "upgrade": f"apt-get upgrade -y {package} 2>&1"
    }
    out, rc = run_cmd(cmd_map[action], timeout=120)
    return jsonify({"ok": rc == 0, "output": out})

# ─── API: Firewall (ufw) ───────────────────────────────────────────────────────

@app.route("/api/firewall/status")
@login_required
def api_firewall_status():
    # Check if ufw is installed
    out_check, rc_check = run_cmd("which ufw 2>/dev/null")
    if rc_check != 0:
        return jsonify({"enabled": False, "rules": [], "raw": "", "error": "ufw no está instalado. Instálalo con: sudo apt install ufw"})
    out, _ = run_cmd("sudo ufw status verbose 2>&1")
    enabled = "Status: active" in out
    rules = []
    for line in out.splitlines():
        if "ALLOW" in line or "DENY" in line or "REJECT" in line:
            rules.append(line.strip())
    return jsonify({"enabled": enabled, "rules": rules, "raw": out})

@app.route("/api/firewall/<action>", methods=["POST"])
@login_required
def api_firewall_action(action):
    data = request.get_json() or {}
    if action == "enable":
        out, rc = run_cmd("sudo ufw --force enable 2>&1")
    elif action == "disable":
        out, rc = run_cmd("sudo ufw --force disable 2>&1")
    elif action == "allow":
        port = re.sub(r"[^0-9/a-zA-Z]", "", data.get("port", ""))
        if not port:
            return jsonify({"ok": False, "error": "Puerto requerido"}), 400
        out, rc = run_cmd(f"sudo ufw allow {port} 2>&1")
    elif action == "deny":
        port = re.sub(r"[^0-9/a-zA-Z]", "", data.get("port", ""))
        if not port:
            return jsonify({"ok": False, "error": "Puerto requerido"}), 400
        out, rc = run_cmd(f"sudo ufw deny {port} 2>&1")
    elif action == "delete":
        rule = re.sub(r"[^0-9]", "", data.get("rule_number", ""))
        out, rc = run_cmd(f"sudo ufw --force delete {rule} 2>&1")
    else:
        return jsonify({"ok": False, "error": "Acción no permitida"}), 400
    return jsonify({"ok": rc == 0, "output": out, "error": out if rc != 0 else None})

# ─── API: Cron ─────────────────────────────────────────────────────────────────

@app.route("/api/cron")
@login_required
def api_cron():
    out, _ = run_cmd("crontab -l 2>/dev/null")
    jobs = []
    for line in out.splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            parts = line.split(None, 5)
            if len(parts) >= 6:
                jobs.append({
                    "schedule": " ".join(parts[:5]),
                    "command": parts[5],
                    "raw": line
                })
            elif len(parts) >= 1:
                jobs.append({"schedule": "", "command": line, "raw": line})
    return jsonify(jobs)

@app.route("/api/cron", methods=["POST"])
@login_required
def api_cron_add():
    data = request.get_json()
    entry = data.get("entry", "").strip()
    if not entry:
        return jsonify({"ok": False, "error": "Entrada vacía"}), 400
    out, _ = run_cmd("crontab -l 2>/dev/null")
    new_cron = out + "\n" + entry + "\n"
    proc = subprocess.run("crontab -", input=new_cron, shell=True, text=True, capture_output=True)
    return jsonify({"ok": proc.returncode == 0})

@app.route("/api/cron/delete", methods=["POST"])
@login_required
def api_cron_delete():
    data = request.get_json()
    raw = data.get("raw", "")
    out, _ = run_cmd("crontab -l 2>/dev/null")
    lines = [l for l in out.splitlines() if l.strip() != raw.strip()]
    new_cron = "\n".join(lines) + "\n"
    proc = subprocess.run("crontab -", input=new_cron, shell=True, text=True, capture_output=True)
    return jsonify({"ok": proc.returncode == 0})

# ─── API: Network ──────────────────────────────────────────────────────────────

@app.route("/api/network")
@login_required
def api_network():
    interfaces = []
    for name, stats in psutil.net_if_stats().items():
        addrs = psutil.net_if_addrs().get(name, [])
        ipv4 = next((a.address for a in addrs if a.family.name == "AF_INET"), "")
        ipv6 = next((a.address for a in addrs if a.family.name == "AF_INET6"), "")
        mac = next((a.address for a in addrs if a.family.name == "AF_PACKET"), "")
        io = psutil.net_io_counters(pernic=True).get(name)
        interfaces.append({
            "name": name,
            "up": stats.isup,
            "speed": stats.speed,
            "mtu": stats.mtu,
            "ipv4": ipv4,
            "ipv6": ipv6,
            "mac": mac,
            "bytes_sent": io.bytes_sent if io else 0,
            "bytes_recv": io.bytes_recv if io else 0,
        })
    return jsonify(interfaces)

# ─── API: Files ────────────────────────────────────────────────────────────────

@app.route("/api/files")
@login_required
def api_files():
    path = request.args.get("path", "/")
    path = os.path.realpath(path)
    if not os.path.exists(path):
        return jsonify({"error": "Ruta no existe"}), 404
    items = []
    try:
        for entry in sorted(os.scandir(path), key=lambda e: (not e.is_dir(), e.name.lower())):
            try:
                stat = entry.stat(follow_symlinks=False)
                items.append({
                    "name": entry.name,
                    "type": "dir" if entry.is_dir() else "file",
                    "size": stat.st_size,
                    "modified": datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M"),
                    "permissions": oct(stat.st_mode)[-4:]
                })
            except PermissionError:
                items.append({"name": entry.name, "type": "?", "size": 0, "modified": "", "permissions": "----"})
    except PermissionError:
        return jsonify({"error": "Sin permiso"}), 403
    parent = str(Path(path).parent) if path != "/" else None
    return jsonify({"path": path, "parent": parent, "items": items})

@app.route("/api/files/read")
@login_required
def api_files_read():
    path = request.args.get("path", "")
    path = os.path.realpath(path)
    if not os.path.isfile(path):
        return jsonify({"error": "No es un archivo"}), 404
    size = os.path.getsize(path)
    if size > 1_000_000:
        return jsonify({"error": "Archivo demasiado grande (>1MB)"}), 413
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()
        return jsonify({"content": content, "path": path})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/files/delete", methods=["POST"])
@login_required
def api_files_delete():
    data = request.get_json()
    path = os.path.realpath(data.get("path", ""))
    if not os.path.exists(path):
        return jsonify({"ok": False, "error": "No existe"}), 404
    try:
        if os.path.isdir(path):
            shutil.rmtree(path)
        else:
            os.remove(path)
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

# ─── API: Users ────────────────────────────────────────────────────────────────

def _user_locked(username):
    """Returns True if the user's password is locked (! or * prefix in shadow)."""
    out, _ = run_cmd(f"passwd -S {username} 2>/dev/null")
    return " L " in out or out.split()[1:2] == ["L"] if out else False

def _user_last_login(username):
    out, _ = run_cmd(f"lastlog -u {username} 2>/dev/null | tail -1")
    if out and "Never logged in" not in out and username not in out.split()[0:1]:
        parts = out.split()
        if len(parts) >= 5:
            return " ".join(parts[3:])
    return None

@app.route("/api/users")
@login_required
def api_users():
    import pwd
    users = []
    for u in pwd.getpwall():
        groups_out, _ = run_cmd(f"id -Gn {u.pw_name} 2>/dev/null")
        groups = groups_out.split() if groups_out else []
        users.append({
            "name": u.pw_name,
            "uid": u.pw_uid,
            "gid": u.pw_gid,
            "home": u.pw_dir,
            "shell": u.pw_shell,
            "comment": u.pw_gecos,
            "groups": groups,
            "locked": _user_locked(u.pw_name),
        })
    return jsonify(users)

@app.route("/api/users/create", methods=["POST"])
@login_required
def api_user_create():
    data = request.get_json()
    username = re.sub(r"[^a-z0-9_\-]", "", data.get("username", "").lower())
    password = data.get("password", "")
    shell    = data.get("shell", "/bin/bash")
    home     = data.get("home", f"/home/{username}")
    comment  = re.sub(r"[^a-zA-Z0-9 .,_\-]", "", data.get("comment", ""))
    create_home = data.get("create_home", True)

    if not username or len(username) < 2:
        return jsonify({"ok": False, "error": "Nombre de usuario inválido"}), 400
    if not password or len(password) < 4:
        return jsonify({"ok": False, "error": "Contraseña demasiada corta (mín. 4 caracteres)"}), 400

    flags = "-m" if create_home else "-M"
    shell = shell if shell in ("/bin/bash", "/bin/sh", "/bin/zsh", "/usr/bin/zsh", "/sbin/nologin", "/usr/sbin/nologin") else "/bin/bash"
    cmd = f"useradd {flags} -s {shell} -c '{comment}' {username} 2>&1"
    out, rc = run_cmd(cmd)
    if rc != 0:
        return jsonify({"ok": False, "error": out}), 500

    # Set password via chpasswd
    proc = subprocess.run("chpasswd", input=f"{username}:{password}", shell=True, text=True, capture_output=True)
    if proc.returncode != 0:
        return jsonify({"ok": False, "error": f"Usuario creado pero error al poner contraseña: {proc.stderr}"}), 500

    return jsonify({"ok": True})

@app.route("/api/users/<username>/passwd", methods=["POST"])
@login_required
def api_user_passwd(username):
    username = re.sub(r"[^a-z0-9_\-]", "", username)
    data = request.get_json()
    password = data.get("password", "")
    if not password or len(password) < 4:
        return jsonify({"ok": False, "error": "Contraseña demasiado corta (mín. 4 caracteres)"}), 400
    proc = subprocess.run("chpasswd", input=f"{username}:{password}", shell=True, text=True, capture_output=True)
    if proc.returncode != 0:
        return jsonify({"ok": False, "error": proc.stderr}), 500
    return jsonify({"ok": True})

@app.route("/api/users/<username>/lock", methods=["POST"])
@login_required
def api_user_lock(username):
    username = re.sub(r"[^a-z0-9_\-]", "", username)
    out, rc = run_cmd(f"passwd -l {username} 2>&1")
    return jsonify({"ok": rc == 0, "output": out})

@app.route("/api/users/<username>/unlock", methods=["POST"])
@login_required
def api_user_unlock(username):
    username = re.sub(r"[^a-z0-9_\-]", "", username)
    out, rc = run_cmd(f"passwd -u {username} 2>&1")
    return jsonify({"ok": rc == 0, "output": out})

@app.route("/api/users/<username>/delete", methods=["POST"])
@login_required
def api_user_delete(username):
    username = re.sub(r"[^a-z0-9_\-]", "", username)
    data = request.get_json() or {}
    remove_home = data.get("remove_home", False)
    flag = "-r" if remove_home else ""
    out, rc = run_cmd(f"userdel {flag} {username} 2>&1")
    return jsonify({"ok": rc == 0, "output": out})

@app.route("/api/users/<username>/groups", methods=["POST"])
@login_required
def api_user_set_groups(username):
    username = re.sub(r"[^a-z0-9_\-]", "", username)
    data = request.get_json()
    groups = [re.sub(r"[^a-z0-9_\-]", "", g) for g in data.get("groups", [])]
    groups = [g for g in groups if g]
    if not groups:
        return jsonify({"ok": False, "error": "Sin grupos"}), 400
    primary = groups[0]
    extra   = ",".join(groups[1:]) if len(groups) > 1 else ""
    out, rc = run_cmd(f"usermod -g {primary} {username} 2>&1")
    if rc != 0:
        return jsonify({"ok": False, "error": out}), 500
    if extra:
        out2, rc2 = run_cmd(f"usermod -G {extra} {username} 2>&1")
        if rc2 != 0:
            return jsonify({"ok": False, "error": out2}), 500
    return jsonify({"ok": True})

@app.route("/api/users/<username>/shell", methods=["POST"])
@login_required
def api_user_shell(username):
    username = re.sub(r"[^a-z0-9_\-]", "", username)
    data = request.get_json()
    shell = data.get("shell", "/bin/bash")
    allowed = ("/bin/bash", "/bin/sh", "/bin/zsh", "/usr/bin/zsh", "/sbin/nologin", "/usr/sbin/nologin", "/bin/false")
    if shell not in allowed:
        return jsonify({"ok": False, "error": "Shell no permitida"}), 400
    out, rc = run_cmd(f"chsh -s {shell} {username} 2>&1")
    return jsonify({"ok": rc == 0, "output": out})

@app.route("/api/groups")
@login_required
def api_groups():
    import grp
    groups = []
    for g in grp.getgrall():
        groups.append({
            "name": g.gr_name,
            "gid": g.gr_gid,
            "members": g.gr_mem
        })
    return jsonify(groups)

@app.route("/api/groups/create", methods=["POST"])
@login_required
def api_group_create():
    data = request.get_json()
    name = re.sub(r"[^a-z0-9_\-]", "", data.get("name", "").lower())
    if not name or len(name) < 2:
        return jsonify({"ok": False, "error": "Nombre de grupo inválido"}), 400
    out, rc = run_cmd(f"groupadd {name} 2>&1")
    return jsonify({"ok": rc == 0, "output": out})

@app.route("/api/groups/delete", methods=["POST"])
@login_required
def api_group_delete():
    data = request.get_json() or {}
    groupname = re.sub(r"[^a-z0-9_-]", "", data.get("name", ""))
    if not groupname:
        return jsonify({"ok": False, "error": "Nombre requerido"}), 400
    out, rc = run_cmd(f"groupdel {groupname} 2>&1")
    return jsonify({"ok": rc == 0, "output": out})

# ─── Main ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print(f"\n  AC⚡DC Console arrancando en http://{CONFIG['host']}:{CONFIG['port']}")
    print(f"  Usuario: {CONFIG['username']}")
    print(f"  Web: {CONFIG['site_url']}\n")
    app.run(
        host=CONFIG["host"],
        port=CONFIG["port"],
        debug=False,
        threaded=True
    )
