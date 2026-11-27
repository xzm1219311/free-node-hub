"""解析各类订阅格式，统一成内部节点表示（字段名对齐 Clash/mihomo）。"""
from __future__ import annotations

import base64
import binascii
import json
import re
import urllib.parse as up

import yaml

URI_SCHEMES = ("vmess://", "vless://", "ss://", "ssr://", "trojan://",
               "hysteria2://", "hy2://", "hysteria://", "tuic://")


# ---------------------------------------------------------------- helpers
def b64d(s: str) -> str:
    """宽松 base64 解码（兼容 url-safe、缺 padding、带换行）。"""
    s = s.strip().replace("\n", "").replace("\r", "").replace(" ", "")
    if not s:
        return ""
    s += "=" * (-len(s) % 4)
    for fn in (base64.b64decode, base64.urlsafe_b64decode):
        try:
            return fn(s).decode("utf-8", "ignore")
        except (binascii.Error, ValueError):
            continue
    return ""


def _int(v, default=0) -> int:
    try:
        return int(str(v).strip())
    except (TypeError, ValueError):
        return default


def _b(v) -> bool:
    if isinstance(v, bool):
        return v
    return str(v).strip().lower() in ("1", "true", "yes", "on")


def _first(d: dict, *keys, default=None):
    for k in keys:
        if k in d and d[k] not in (None, ""):
            return d[k]
    return default


# ---------------------------------------------------------------- URI 解析
def parse_vmess(uri: str) -> dict | None:
    body = uri[len("vmess://"):].strip()
    txt = b64d(body)
    if not txt:
        return None
    try:
        j = json.loads(txt)
    except json.JSONDecodeError:
        return None
    host = str(_first(j, "add", "host", default="")).strip()
    port = _int(_first(j, "port", default=0))
    uuid = str(_first(j, "id", default="")).strip()
    if not host or not port or not uuid:
        return None
    net = str(_first(j, "net", default="tcp")).lower()
    tls = str(_first(j, "tls", default="")).lower()
    node = {
        "type": "vmess", "name": str(_first(j, "ps", default=f"{host}:{port}")),
        "server": host, "port": port, "uuid": uuid,
        "cipher": str(_first(j, "scy", "security", default="auto")) or "auto",
        "alterId": _int(_first(j, "aid", "alterId", default=0)),
        "network": net,
        "tls": tls in ("tls", "reality", "true", "1"),
        "udp": True,
    }
    sni = _first(j, "sni", "peer", "host")
    if sni and node["tls"]:
        node["servername"] = str(sni)
        node["sni"] = str(sni)
    if net == "ws":
        node["ws-opts"] = {"path": str(_first(j, "path", default="/")) or "/"}
        h = _first(j, "host")
        if h:
            node["ws-opts"]["headers"] = {"Host": str(h)}
    elif net == "grpc":
        node["grpc-opts"] = {"grpc-service-name": str(_first(j, "path", default=""))}
    elif net == "h2":
        node["h2-opts"] = {"path": str(_first(j, "path", default="/")) or "/"}
    return node


def parse_vless(uri: str) -> dict | None:
    u = up.urlsplit(uri)
    if not u.hostname:
        return None
    q = dict(up.parse_qsl(u.query, keep_blank_values=True))
    node = {
        "type": "vless", "name": up.unquote(u.fragment) or f"{u.hostname}:{u.port}",
        "server": u.hostname, "port": _int(u.port), "uuid": up.unquote(u.username or ""),
        "udp": True, "network": (q.get("type") or "tcp").lower(),
    }
    sec = (q.get("security") or "").lower()
    if sec in ("tls", "reality", "xtls"):
        node["tls"] = True
    if q.get("sni"):
        node["servername"] = q["sni"]
        node["sni"] = q["sni"]
    if q.get("flow"):
        node["flow"] = q["flow"]
    if sec == "reality":
        node["reality-opts"] = {
            "public-key": q.get("pbk", ""),
            "short-id": q.get("sid", ""),
        }
        node["client-fingerprint"] = q.get("fp", "chrome")
    if q.get("fp") and sec != "reality":
        node["client-fingerprint"] = q["fp"]
    if q.get("alpn"):
        node["alpn"] = [a for a in q["alpn"].split(",") if a]
    if node["network"] == "ws":
        node["ws-opts"] = {"path": q.get("path", "/") or "/"}
        if q.get("host"):
            node["ws-opts"]["headers"] = {"Host": q["host"]}
    elif node["network"] == "grpc":
        node["grpc-opts"] = {"grpc-service-name": q.get("serviceName", "")}
    elif node["network"] in ("http", "h2"):
        node["network"] = "h2"
        node["h2-opts"] = {"path": q.get("path", "/") or "/"}
        if q.get("host"):
            node["h2-opts"]["host"] = [h for h in q["host"].split(",") if h]
    if not node["port"] or not node["uuid"]:
        return None
    return node


def parse_ss(uri: str) -> dict | None:
    body = uri[len("ss://"):]
    frag = ""
    if "#" in body:
        body, frag = body.split("#", 1)
    frag = up.unquote(frag)
    body = body.split("?")[0]
    method = password = None
    host = port = None
    if "@" in body:
        userinfo, hostport = body.rsplit("@", 1)
        dec = b64d(userinfo)
        if ":" in dec:
            method, password = dec.split(":", 1)
        elif ":" in up.unquote(userinfo):
            method, password = up.unquote(userinfo).split(":", 1)
        if hostport.startswith("["):
            host, _, port_s = hostport.rpartition(":")
            host = host.strip("[]")
            port = _int(port_s)
        else:
            host, _, port_s = hostport.rpartition(":")
            port = _int(port_s)
    else:
        dec = b64d(body)
        if "@" not in dec:
            return None
        userinfo, hostport = dec.rsplit("@", 1)
        if ":" not in userinfo:
            return None
        method, password = userinfo.split(":", 1)
        host, _, port_s = hostport.rpartition(":")
        port = _int(port_s)
    if not method or not password or not host or not port:
        return None
    return {
        "type": "ss", "name": frag or f"{host}:{port}", "server": host, "port": port,
        "cipher": method, "password": password, "udp": True,
    }


def parse_trojan(uri: str) -> dict | None:
    u = up.urlsplit(uri)
    if not u.hostname:
        return None
    q = dict(up.parse_qsl(u.query, keep_blank_values=True))
    node = {
        "type": "trojan", "name": up.unquote(u.fragment) or f"{u.hostname}:{u.port}",
        "server": u.hostname, "port": _int(u.port), "password": up.unquote(u.username or ""),
        "udp": True, "skip-cert-verify": _b(q.get("allowInsecure", "0")),
    }
    if q.get("sni") or q.get("peer"):
        node["sni"] = q.get("sni") or q.get("peer")
    if q.get("type") == "ws":
        node["network"] = "ws"
        node["ws-opts"] = {"path": q.get("path", "/") or "/"}
        if q.get("host"):
            node["ws-opts"]["headers"] = {"Host": q["host"]}
    elif q.get("type") == "grpc":
        node["network"] = "grpc"
        node["grpc-opts"] = {"grpc-service-name": q.get("serviceName", "")}
    if not node["port"] or not node["password"]:
        return None
    return node


def parse_hy2(uri: str) -> dict | None:
    u = up.urlsplit(uri)
    if not u.hostname:
        return None
    q = dict(up.parse_qsl(u.query, keep_blank_values=True))
    node = {
        "type": "hysteria2", "name": up.unquote(u.fragment) or f"{u.hostname}:{u.port}",
        "server": u.hostname, "port": _int(u.port),
        "password": up.unquote(u.username or "") or up.unquote(u.netloc.split("@")[0] if "@" in u.netloc else ""),
        "udp": True, "skip-cert-verify": _b(q.get("insecure", "0")),
    }
    if q.get("sni"):
        node["sni"] = q["sni"]
    if q.get("obfs"):
        node["obfs"] = q["obfs"]
        node["obfs-password"] = q.get("obfs-password", "")
    if not node["port"] or not node["password"]:
        return None
    return node


def parse_tuic(uri: str) -> dict | None:
    u = up.urlsplit(uri)
    if not u.hostname or not u.username:
        return None
    q = dict(up.parse_qsl(u.query, keep_blank_values=True))
    node = {
        "type": "tuic", "name": up.unquote(u.fragment) or f"{u.hostname}:{u.port}",
        "server": u.hostname, "port": _int(u.port), "uuid": up.unquote(u.username),
        "password": up.unquote(u.password or ""), "udp": True,
        "skip-cert-verify": _b(q.get("allow_insecure", "0")),
    }
    if q.get("sni"):
        node["sni"] = q["sni"]
    if q.get("alpn"):
        node["alpn"] = [a for a in q["alpn"].split(",") if a]
    if not node["port"]:
        return None
    return node


PARSERS = {
    "vmess://": parse_vmess,
    "vless://": parse_vless,
    "ss://": parse_ss,
    "trojan://": parse_trojan,
    "hysteria2://": parse_hy2,
    "hy2://": parse_hy2,
    "tuic://": parse_tuic,
}


def parse_uri(uri: str) -> dict | None:
    uri = uri.strip()
    for scheme, fn in PARSERS.items():
        if uri.startswith(scheme):
            try:
                node = fn(uri)
            except Exception:
                return None
            if node:
                node["raw_uri"] = uri
            return node
    return None


# ---------------------------------------------------------------- 订阅整体解析
def parse_uri_blob(text: str, source: str = "") -> list[dict]:
    """从任意文本里抽取所有节点 URI（自动判断是否 base64）。"""
    text = text.strip()
    nodes: list[dict] = []
    if not text:
        return nodes
    # 先看明文是否直接含 scheme
    if any(s in text[:4000] for s in URI_SCHEMES):
        lines = re.split(r"[\r\n]+", text)
    else:
        dec = b64d(text)
        lines = re.split(r"[\r\n]+", dec) if dec else []
    for line in lines:
        line = line.strip()
        if not line or len(line) < 20:
            continue
        if not line.startswith(URI_SCHEMES):
            # 有些源每行是 base64 包着的单条
            dec = b64d(line)
            if dec.startswith(URI_SCHEMES):
                line = dec.strip()
            else:
                continue
        n = parse_uri(line)
        if n:
            n["source"] = source
            nodes.append(n)
    return nodes


def parse_clash_yaml(text: str, source: str = "") -> list[dict]:
    try:
        doc = yaml.safe_load(text)
    except Exception:
        return []
    if not isinstance(doc, dict):
        return []
    proxies = doc.get("proxies") or doc.get("Proxy") or []
    if not isinstance(proxies, list):
        return []
    out = []
    for p in proxies:
        if not isinstance(p, dict):
            continue
        ptype = str(p.get("type", "")).lower()
        server = p.get("server") or p.get("servername")
        port = _int(p.get("port"))
        if not server or not port:
            continue
        if ptype not in ("vmess", "vless", "ss", "trojan", "hysteria2", "hysteria",
                         "tuic", "ssr", "anytls"):
            continue
        node = dict(p)
        node["type"] = ptype
        node["server"] = str(server)
        node["port"] = port
        node["name"] = str(p.get("name") or f"{server}:{port}")
        node["source"] = source
        out.append(node)
    return out


def parse_singbox_json(text: str, source: str = "") -> list[dict]:
    try:
        doc = json.loads(text)
    except json.JSONDecodeError:
        return []
    if isinstance(doc, dict):
        outs = doc.get("outbounds") or []
    elif isinstance(doc, list):
        outs = doc
    else:
        return []
    out = []
    for o in outs:
        if not isinstance(o, dict):
            continue
        t = str(o.get("type", "")).lower()
        if t in ("direct", "block", "dns", "selector", "urltest"):
            continue
        server = o.get("server")
        port = _int(o.get("server_port") or o.get("port"))
        if not server or not port:
            continue
        node = {
            "type": "vless" if t == "vless" else ("vmess" if t == "vmess" else t),
            "name": str(o.get("tag") or f"{server}:{port}"),
            "server": str(server), "port": port, "source": source,
        }
        if o.get("uuid"):
            node["uuid"] = o["uuid"]
        if o.get("password"):
            node["password"] = o["password"]
        if o.get("method"):
            node["cipher"] = o["method"]
        tls = o.get("tls") or {}
        if isinstance(tls, dict):
            if tls.get("server_name"):
                node["sni"] = tls["server_name"]
            if tls.get("reality", {}).get("public_key"):
                node["reality-opts"] = {
                    "public-key": tls["reality"]["public_key"],
                    "short-id": tls["reality"].get("short_id", ""),
                }
                node["tls"] = True
        out.append(node)
    return out


def parse_vpngate_csv(text: str) -> list[dict]:
    """VPNGate CSV -> 只是元信息（协议为 OpenVPN/SSL-VPN，不能进 clash）。"""
    rows = []
    lines = [l for l in text.splitlines() if l and not l.startswith("*")]
    if not lines:
        return rows
    header = lines[0].lstrip("#").split(",")
    for line in lines[1:]:
        parts = line.split(",")
        if len(parts) < len(header):
            continue
        rec = dict(zip(header, parts))
        rows.append({
            "host": rec.get("HostName", ""),
            "ip": rec.get("IP", ""),
            "country": rec.get("CountryShort", ""),
            "sessions": _int(rec.get("NumVpnSessions", 0)),
            "ping": _int(rec.get("Ping", 0)),
            "speed": _int(rec.get("Speed", 0)),
            "ovpn_b64": rec.get("OpenVPN_ConfigData_Base64", ""),
            "operator": rec.get("Operator", ""),
        })
    return rows
