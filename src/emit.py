"""输出：Clash(mihomo) / sing-box(NekoBox/Hiddify) / 通用 base64 / 站点元数据。

输出三份 Clash 订阅，适配不同客户端：
  clash.yaml       完整版（分组 + DNS + 分流规则）—— Clash Verge / FlClash / Stash
  clash-lite.yaml  极简版（只有节点 + 两个选择组）—— 老内核 / 想用自己的规则
  clash-ascii.yaml 纯 ASCII 命名版（无 emoji 无中文）—— 老客户端不认 emoji 时用这个
"""
from __future__ import annotations

import base64
import json
import os
import re

import yaml

from . import config

FLAGS = {
    "US": "🇺🇸", "HK": "🇭🇰", "TW": "🇹🇼", "JP": "🇯🇵", "SG": "🇸🇬", "KR": "🇰🇷",
    "GB": "🇬🇧", "DE": "🇩🇪", "NL": "🇳🇱", "FR": "🇫🇷", "CA": "🇨🇦", "AU": "🇦🇺",
    "RU": "🇷🇺", "IN": "🇮🇳", "TR": "🇹🇷", "BR": "🇧🇷", "VN": "🇻🇳", "TH": "🇹🇭",
    "MY": "🇲🇾", "ID": "🇮🇩", "PH": "🇵🇭", "IT": "🇮🇹", "ES": "🇪🇸", "SE": "🇸🇪",
    "CH": "🇨🇭", "PL": "🇵🇱", "UA": "🇺🇦", "AE": "🇦🇪", "IL": "🇮🇱", "ZA": "🇿🇦",
    "MX": "🇲🇽", "AR": "🇦🇷", "CL": "🇨🇱", "FI": "🇫🇮", "NO": "🇳🇴", "DK": "🇩🇰",
    "IE": "🇮🇪", "AT": "🇦🇹", "BE": "🇧🇪", "CZ": "🇨🇿", "RO": "🇷🇴", "HU": "🇭🇺",
    "CN": "🇨🇳", "MO": "🇲🇴", "KZ": "🇰🇿", "SA": "🇸🇦", "IR": "🇮🇷", "PK": "🇵🇰",
}

# Clash 节点允许保留的字段白名单（其余自定义键会被 mihomo 严格模式拒绝）
CLASH_KEEP = {
    "name", "type", "server", "port", "uuid", "username", "password", "cipher", "alterId",
    "network", "tls", "udp", "sni", "servername", "skip-cert-verify", "flow",
    "client-fingerprint", "alpn", "ws-opts", "grpc-opts", "h2-opts", "reality-opts",
    "plugin", "plugin-opts", "obfs", "obfs-password", "protocol", "protocol-param", "obfs-param", "up", "down", "ports",
    "auth", "disable-sni", "reduce-rtt", "heartbeat-interval", "congestion-controller",
    "udp-relay-mode", "fingerprint", "ip-version", "packet-encoding",
}

BAD_NAME_CHARS = re.compile(r"[,\"'\\\n\r\t]")


def _g(node: dict) -> dict:
    return node.get("geo") or {}


def _tags(node: dict) -> list[str]:
    g = _g(node)
    tags = []
    if g.get("residential"):
        tags.append("家宽")
    elif g.get("suspected_home"):
        tags.append("疑似家宽")
    if g.get("native"):
        tags.append("原生")
    if g.get("mobile"):
        tags.append("移动")
    if not tags and g.get("hosting"):
        tags.append("机房")
    return tags


def label(node: dict, idx: int) -> str:
    """可读名：🇺🇸 US · 家宽·原生 | FiberState | 01"""
    g = _g(node)
    cc = g.get("country")
    if cc:
        flag = FLAGS.get(cc, "🏳")
        base = f"{flag} {cc}"
    else:
        base = "🌐 节点"
    tags = "·".join(_tags(node)) or (node.get("type") or "")
    isp = (g.get("isp") or "")[:18]
    if tags:
        base += f" · {tags}"
    if isp:
        base += f" | {isp}"
    return _clean_name(f"{base} | {idx:02d}")


def ascii_label(node: dict, idx: int) -> str:
    """纯 ASCII 名：US-HOME-01 —— 老客户端 / 中间盒不认 emoji 时用。"""
    g = _g(node)
    cc = re.sub(r"[^A-Z]", "", (g.get("country") or "XX").upper()) or "XX"
    if g.get("residential") or g.get("suspected_home"):
        kind = "HOME"
    elif g.get("native"):
        kind = "NAT"
    elif g.get("hosting"):
        kind = "DC"
    else:
        kind = "N"
    return f"{cc}-{kind}-{idx:03d}"


def _clean_name(s: str) -> str:
    s = BAD_NAME_CHARS.sub(" ", s).strip()
    return re.sub(r"\s{2,}", " ", s)[:80]


# ------------------------------------------------------------------ Clash
def to_clash_node(node: dict, name: str) -> dict:
    out = {}
    for k, v in node.items():
        if k in CLASH_KEEP and v is not None and v != "":
            out[k] = v
    out["name"] = name
    if out.get("type") == "socks":
        out["type"] = "socks5"
    t = out.get("type")
    if t in ("hysteria", "hysteria2", "tuic"):
        out.setdefault("skip-cert-verify", True)
    if t == "vmess":
        out["cipher"] = out.get("cipher") or "auto"
        out["alterId"] = out.get("alterId", 0)
    if out.get("network") == "ws" and not out.get("ws-opts"):
        out["ws-opts"] = {"path": "/"}
    return out


def write_clash(nodes: list[dict], path: str, meta: dict, *,
                lite: bool = False, ascii_names: bool = False) -> int:
    proxies = []
    flags: list[dict] = []
    for i, n in enumerate(nodes, 1):
        name = ascii_label(n, i) if ascii_names else label(n, i)
        g = _g(n)
        flags.append({
            "name": name,
            "us": g.get("country") == "US",
            "us_home": g.get("country") == "US" and bool(g.get("residential") or g.get("suspected_home")),
            "home": bool(g.get("residential") or g.get("suspected_home")),
            "native": bool(g.get("native")),
        })
        proxies.append(to_clash_node(n, name))

    if not proxies:
        return 0

    names = [p["name"] for p in proxies]

    def pick(*keys) -> list[str]:
        out = []
        for f in flags:
            if any(f.get(k) for k in keys):
                out.append(f["name"])
        return out

    home = pick("us_home") or pick("home")
    us = pick("us")
    native = pick("native")
    if ascii_names:
        G_SEL, G_HOME, G_US, G_ALL, G_AD, auto = (
            "NODE-SELECT", "US-HOME", "US-ALL", "ALL-NODES", "AD-BLOCK", "AUTO")
    else:
        G_SEL, G_HOME, G_US, G_ALL, G_AD, auto = (
            "🚀 节点选择", "🏠 美国家宽", "🇺🇸 美国节点", "🌍 全部节点", "🛑 广告拦截", "♻️ 自动选择")

    groups = []
    if lite:
        groups = [
            {"name": auto, "type": "url-test", "url": "http://www.gstatic.com/generate_204",
             "interval": 300, "tolerance": 80, "proxies": names},
            {"name": G_SEL, "type": "select", "proxies": [auto] + names + ["DIRECT"]},
        ]
        doc = {
            "mixed-port": 7890,
            "allow-lan": False,
            "mode": "rule",
            "log-level": "warning",
            "proxies": proxies,
            "proxy-groups": groups,
            "rules": [f"MATCH,{G_SEL}"],
        }
    else:
        groups = [
            {"name": G_SEL, "type": "select",
             "proxies": [auto, G_HOME, G_US, G_ALL, "DIRECT"]},
            {"name": auto, "type": "url-test", "url": "http://www.gstatic.com/generate_204",
             "interval": 300, "tolerance": 80, "proxies": names},
            {"name": G_HOME, "type": "select", "proxies": home + [auto, "DIRECT"]},
            {"name": G_US, "type": "select", "proxies": us + [auto, "DIRECT"]},
            {"name": G_ALL, "type": "select", "proxies": names},
        ]
        if native:
            groups.append({"name": "🎯 原生 IP" if not ascii_names else "NATIVE-IP",
                           "type": "select", "proxies": native + [auto]})
        groups.append({"name": G_AD, "type": "select", "proxies": ["REJECT", "DIRECT"]})
        doc = {
            "mixed-port": 7890,
            "allow-lan": False,
            "mode": "rule",
            "log-level": "warning",
            "ipv6": False,
            "external-controller": "127.0.0.1:9090",
            "profile": {"store-selected": True, "store-fake-ip": True},
            "dns": {
                "enable": True,
                "ipv6": False,
                "enhanced-mode": "fake-ip",
                "fake-ip-range": "198.18.0.1/16",
                "fake-ip-filter": ["*.lan", "*.local", "*.localdomain", "+.msftconnecttest.com",
                                   "+.msftncsi.com", "localhost.ptlogin2.qq.com"],
                "default-nameserver": ["223.5.5.5", "119.29.29.29"],
                "nameserver": ["https://223.5.5.5/dns-query", "https://doh.pub/dns-query"],
                "fallback": ["https://1.1.1.1/dns-query", "https://8.8.4.4/dns-query"],
                "fallback-filter": {"geoip": True, "geoip-code": "CN",
                                    "ipcidr": ["240.0.0.0/4"]},
            },
            "proxies": proxies,
            "proxy-groups": groups,
            "rules": [
                "DOMAIN-SUFFIX,local,DIRECT",
                "IP-CIDR,127.0.0.0/8,DIRECT,no-resolve",
                "IP-CIDR,192.168.0.0/16,DIRECT,no-resolve",
                "IP-CIDR,10.0.0.0/8,DIRECT,no-resolve",
                "IP-CIDR,172.16.0.0/12,DIRECT,no-resolve",
                "GEOIP,CN,DIRECT",
                f"MATCH,{G_SEL}",
            ],
        }

    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(f"# {meta.get('title', 'node-sub')} | 更新 {meta['generated_at']} | "
                f"{len(proxies)} 个节点\n")
        yaml.safe_dump(doc, f, allow_unicode=True, sort_keys=False,
                       width=4096, default_flow_style=False)
    os.replace(tmp, path)
    return len(proxies)


# ------------------------------------------------------------------ sing-box
def to_singbox(node: dict, name: str) -> dict | None:
    t = node.get("type")
    base = {"tag": name, "server": node["server"], "server_port": int(node["port"])}

    def tls_block(sni_key="sni"):
        sni = node.get(sni_key) or node.get("servername") or ""
        tls = {"enabled": True}
        if sni:
            tls["server_name"] = sni
        ro = node.get("reality-opts")
        if ro and ro.get("public-key"):
            tls["reality"] = {"enabled": True, "public_key": ro["public-key"],
                              "short_id": ro.get("short-id", "")}
            tls["utls"] = {"enabled": True, "fingerprint": node.get("client-fingerprint") or "chrome"}
        elif node.get("client-fingerprint"):
            tls["utls"] = {"enabled": True, "fingerprint": node["client-fingerprint"]}
        if node.get("alpn"):
            tls["alpn"] = node["alpn"]
        if node.get("skip-cert-verify"):
            tls["insecure"] = True
        return tls

    if t == "vmess":
        o = dict(base, type="vmess", uuid=node.get("uuid", ""),
                 security=node.get("cipher") or "auto",
                 alter_id=int(node.get("alterId") or 0))
        if node.get("tls"):
            o["tls"] = tls_block()
    elif t == "vless":
        o = dict(base, type="vless", uuid=node.get("uuid", ""))
        if node.get("flow"):
            o["flow"] = node["flow"]
        if node.get("tls") or node.get("reality-opts"):
            o["tls"] = tls_block()
    elif t == "ss":
        o = dict(base, type="shadowsocks", method=node.get("cipher", ""),
                 password=node.get("password", ""))
        if node.get("plugin"):
            o["plugin"] = node["plugin"]
            if node.get("plugin-opts"):
                o["plugin_opts"] = node["plugin-opts"]
    elif t == "trojan":
        o = dict(base, type="trojan", password=node.get("password", ""))
        o["tls"] = tls_block()
    elif t in ("hysteria2", "hy2"):
        o = dict(base, type="hysteria2", password=node.get("password", ""))
        tls = {"enabled": True}
        if node.get("sni"):
            tls["server_name"] = node["sni"]
        if node.get("skip-cert-verify"):
            tls["insecure"] = True
        o["tls"] = tls
        if node.get("obfs"):
            o["obfs"] = {"type": node["obfs"], "password": node.get("obfs-password", "")}
        if node.get("up"):
            o["up_mbps"] = int(node["up"])
        if node.get("down"):
            o["down_mbps"] = int(node["down"])
    elif t == "tuic":
        o = dict(base, type="tuic", uuid=node.get("uuid", ""),
                 password=node.get("password", ""))
        o["tls"] = {"enabled": True,
                    "server_name": node.get("sni") or "",
                    "alpn": node.get("alpn") or ["h3"],
                    "insecure": bool(node.get("skip-cert-verify"))}
    else:
        return None

    net = node.get("network")
    if net == "ws":
        tr = {"type": "ws", "path": (node.get("ws-opts") or {}).get("path", "/")}
        hdrs = (node.get("ws-opts") or {}).get("headers") or {}
        if hdrs.get("Host"):
            tr["headers"] = {"Host": hdrs["Host"]}
        o["transport"] = tr
    elif net == "grpc":
        o["transport"] = {"type": "grpc",
                          "service_name": (node.get("grpc-opts") or {}).get("grpc-service-name", "")}
    elif net == "h2":
        o["transport"] = {"type": "http",
                          "path": (node.get("h2-opts") or {}).get("path", "/")}
    return o


def write_singbox(nodes: list[dict], path: str, meta: dict) -> int:
    outs: list[dict] = []
    us_all, home = [], []
    for i, n in enumerate(nodes, 1):
        name = label(n, i)
        o = to_singbox(n, name)
        if not o:
            continue
        outs.append(o)
        g = _g(n)
        if g.get("country") == "US":
            us_all.append(name)
            if g.get("residential") or g.get("suspected_home"):
                home.append(name)

    if not outs:
        return 0

    tags = [o["tag"] for o in outs]
    groups: list[dict] = [
        {"type": "selector", "tag": "🚀 节点选择",
         "outbounds": ["♻️ 自动选择", "🏠 美国家宽", "🇺🇸 美国节点", "🌍 全部节点", "DIRECT"],
         "default": "♻️ 自动选择"},
        {"type": "urltest", "tag": "♻️ 自动选择", "outbounds": tags,
         "url": "http://www.gstatic.com/generate_204", "interval": "5m", "tolerance": 80},
        {"type": "selector", "tag": "🏠 美国家宽",
         "outbounds": (home or ["♻️ 自动选择"]) + ["DIRECT"],
         "default": (home or ["♻️ 自动选择"])[0]},
        {"type": "selector", "tag": "🇺🇸 美国节点",
         "outbounds": (us_all or ["♻️ 自动选择"]) + ["DIRECT"],
         "default": (us_all or ["♻️ 自动选择"])[0]},
        {"type": "selector", "tag": "🌍 全部节点", "outbounds": tags + ["DIRECT"],
         "default": tags[0]},
    ]
    doc = {
        "log": {"level": "warn", "timestamp": True},
        "dns": {
            "servers": [
                {"tag": "cf", "address": "https://1.1.1.1/dns-query", "detour": "DIRECT"},
                {"tag": "local", "address": "223.5.5.5", "detour": "DIRECT"},
            ],
            "rules": [{"outbound": "any", "server": "cf"}],
        },
        "inbounds": [
            {"type": "mixed", "tag": "mixed-in", "listen": "127.0.0.1", "listen_port": 2080},
        ],
        "outbounds": groups + outs + [
            {"type": "direct", "tag": "DIRECT"},
            {"type": "block", "tag": "REJECT"},
        ],
        "route": {
            "rules": [
                {"ip_is_private": True, "outbound": "DIRECT"},
            ],
            "final": "🚀 节点选择",
            "auto_detect_interface": True,
        },
    }
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, indent=1)
    os.replace(tmp, path)
    return len(outs)


# ------------------------------------------------------------------ base64 / URI
def _b64url(s: str) -> str:
    return base64.urlsafe_b64encode(s.encode()).decode().rstrip("=")


def _uri_for(node: dict) -> str | None:
    """把节点还原成标准分享链接（v2rayN / NekoBox 通用）。"""
    raw = node.get("raw_uri")
    if raw:
        return raw
    t = node.get("type")
    host, port = node.get("server"), node.get("port")
    if not host or not port:
        return None
    name = (node.get("name") or f"{host}:{port}")
    q = []

    def add(k, v):
        if v not in (None, "", False):
            q.append(f"{k}={v}")

    if t == "vmess":
        obj = {
            "v": "2", "ps": name, "add": host, "port": str(port),
            "id": node.get("uuid", ""), "aid": str(node.get("alterId") or 0),
            "scy": node.get("cipher") or "auto", "net": node.get("network") or "tcp",
            "type": "none", "host": "", "path": "", "tls": "tls" if node.get("tls") else "",
            "sni": node.get("sni") or node.get("servername") or "",
        }
        if node.get("network") == "ws":
            wo = node.get("ws-opts") or {}
            obj["path"] = wo.get("path", "/")
            obj["host"] = (wo.get("headers") or {}).get("Host", "")
        if node.get("network") == "grpc":
            obj["path"] = (node.get("grpc-opts") or {}).get("grpc-service-name", "")
        return "vmess://" + base64.b64encode(
            json.dumps(obj, ensure_ascii=False).encode()).decode()

    if t == "vless":
        add("encryption", "none")
        add("security", "tls" if (node.get("tls") or node.get("reality-opts")) else "none")
        add("sni", node.get("sni") or node.get("servername"))
        add("type", node.get("network") or "tcp")
        if node.get("flow"):
            add("flow", node["flow"])
        if node.get("network") == "ws":
            wo = node.get("ws-opts") or {}
            add("path", wo.get("path", "/"))
            add("host", (wo.get("headers") or {}).get("Host"))
        ro = node.get("reality-opts") or {}
        if ro.get("public-key"):
            add("pbk", ro["public-key"])
            add("sid", ro.get("short-id"))
            add("fp", node.get("client-fingerprint") or "chrome")
        add("allowInsecure", "1" if node.get("skip-cert-verify") else None)
        return f"vless://{node.get('uuid','')}@{host}:{port}?{'&'.join(q)}#{name}"

    if t == "ss":
        userinfo = base64.urlsafe_b64encode(
            f"{node.get('cipher','')}:{node.get('password','')}".encode()).decode().rstrip("=")
        return f"ss://{userinfo}@{host}:{port}#{name}"

    if t == "trojan":
        add("security", "tls")
        add("sni", node.get("sni") or node.get("servername"))
        add("type", node.get("network") or "tcp")
        add("allowInsecure", "1" if node.get("skip-cert-verify") else None)
        return f"trojan://{node.get('password','')}@{host}:{port}?{'&'.join(q)}#{name}"

    if t in ("hysteria2", "hy2"):
        add("sni", node.get("sni"))
        add("insecure", "1" if node.get("skip-cert-verify") else None)
        return f"hysteria2://{node.get('password','')}@{host}:{port}?{'&'.join(q)}#{name}"

    if t == "tuic":
        add("sni", node.get("sni"))
        add("alpn", "h3")
        return f"tuic://{node.get('uuid','')}:{node.get('password','')}@{host}:{port}?{'&'.join(q)}#{name}"

    return None


def write_base64(nodes: list[dict], path: str) -> int:
    lines = []
    for n in nodes:
        for i, u in ((0, _uri_for(n)),):
            if u:
                lines.append(u.replace("\n", ""))
                break
    blob = "\n".join(lines)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(base64.b64encode(blob.encode()).decode())
    os.replace(tmp, path)
    return len(lines)


def write_meta(meta: dict, path: str) -> None:
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)
