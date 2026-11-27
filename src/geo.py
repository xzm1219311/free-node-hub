"""IP 归属 / 家宽 / 原生 IP 判定。

数据来源（公开免费，失败即降级，不阻断主流程）：
  1. ip-api.com   批量接口 —— country / asn / isp / org / hosting / proxy / mobile
  2. ipwho.is     —— 第二 GeoIP 源，用于「原生 IP」交叉验证
"""
from __future__ import annotations

import json
import socket
import time
import urllib.request

from . import config

_IP_CACHE: dict[str, str] = {}


def _http(url: str, data: bytes | None = None, timeout: int = 25) -> str:
    req = urllib.request.Request(url, data=data, headers={
        "User-Agent": config.UA_POOL[3],
        "Content-Type": "application/json",
        "Accept": "application/json",
    })
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8", "ignore")


# ---------------------------------------------------------------- ip-api batch
def ip_api_batch(ips: list[str]) -> dict[str, dict]:
    """批量查询，单次最多 100 个。返回 {ip: info}。"""
    out: dict[str, dict] = {}
    fields = "status,country,countryCode,asn,as,isp,org,mobile,proxy,hosting,query"
    for i in range(0, len(ips), config.GEO_BATCH):
        chunk = ips[i:i + config.GEO_BATCH]
        payload = json.dumps(chunk).encode()
        url = f"http://ip-api.com/batch?fields={fields}"
        for attempt in range(3):
            try:
                arr = json.loads(_http(url, payload))
                if isinstance(arr, list):
                    for item in arr:
                        ip = item.get("query")
                        if ip and item.get("status") == "success":
                            out[ip] = item
                break
            except Exception:
                time.sleep(2 + attempt * 2)
    return out


# ---------------------------------------------------------------- 判定
def _is_idc(isp: str, org: str, asname: str) -> bool:
    blob = " ".join([isp or "", org or "", asname or ""]).lower()
    return any(k in blob for k in config.IDC_KEYWORDS)


def _is_isp(isp: str, org: str, asname: str) -> bool:
    blob = " ".join([isp or "", org or "", asname or ""]).lower()
    return any(k in blob for k in config.ISP_KEYWORDS)


def _build_geo(info: dict) -> dict:
    cc = (info.get("countryCode") or "").upper()
    asn_s = info.get("asn") or ""
    asnum = 0
    if isinstance(asn_s, str) and asn_s.upper().startswith("AS"):
        try:
            asnum = int(asn_s[2:])
        except ValueError:
            asnum = 0
    asname = info.get("as") or ""
    isp, org = info.get("isp", ""), info.get("org", "")
    hosting = bool(info.get("hosting"))
    proxy = bool(info.get("proxy"))
    mobile = bool(info.get("mobile"))
    idc = _is_idc(isp, org, asname)
    isp_like = _is_isp(isp, org, asname)

    residential = bool(cc) and (not proxy) and (not hosting) and (not idc)
    # 疑似家宽：被标成 hosting，但 ISP/ASN 名明显是居民宽带运营商
    suspected = bool(cc) and (not residential) and isp_like and (not proxy) and (not mobile)

    return {
        "country": cc,
        "asn": f"AS{asnum}" if asnum else "",
        "isp": isp,
        "org": org,
        "hosting": hosting,
        "proxy": proxy,
        "mobile": mobile,
        "residential": residential,
        "suspected_home": suspected,
        "native": False,
        "native_known": False,
    }


_EMPTY = {"country": "", "asn": "", "isp": "", "org": "", "hosting": True,
          "proxy": False, "mobile": False, "residential": False,
          "suspected_home": False, "native": False, "native_known": False}


def classify(ip: str) -> dict:
    raw = ip_api_batch([ip]).get(ip)
    return _build_geo(raw) if raw else dict(_EMPTY)


def enrich(nodes: list[dict], limit: int) -> None:
    """给节点批量附加 geo 信息（就地修改）。"""
    order, seen = [], set()
    for n in nodes:
        ip = _resolve_ip(n.get("server", ""))
        n["_ip"] = ip
        if ip and ip not in seen:
            seen.add(ip)
            order.append(ip)
    order = order[:limit]
    if not order:
        return
    raw = ip_api_batch(order)
    for n in nodes:
        info = raw.get(n.get("_ip", ""))
        n["geo"] = _build_geo(info) if info else dict(_EMPTY)


# ---------------------------------------------------------------- 原生：双源交叉
def ipwho_country(ip: str) -> str:
    if not ip:
        return ""
    try:
        j = json.loads(_http(f"https://ipwho.is/{ip}", timeout=15))
        if j.get("success"):
            return (j.get("country_code") or "").upper()
    except Exception:
        pass
    return ""


def asn_country_for_nodes(nodes: list[dict]) -> None:
    """「原生 IP」判定：两个独立 GeoIP 库给出同一国家 → 位置可信。

    反例：1.1.1.1 在 ip-api 是 US、在 ipwho.is 是 AU，Anycast 漂移，不算原生。
    """
    from concurrent.futures import ThreadPoolExecutor

    targets = [n for n in nodes
               if (n.get("geo") or {}).get("residential")
               or (n.get("geo") or {}).get("suspected_home")
               or (n.get("geo") or {}).get("country") == "US"]
    if not targets:
        return

    def _q(n):
        time.sleep(0.15)
        return n, ipwho_country(n.get("_ip", ""))

    try:
        with ThreadPoolExecutor(max_workers=5) as ex:
            for n, cc2 in ex.map(_q, targets):
                g = n.get("geo") or {}
                g["geo2"] = cc2
                same = bool(cc2 and cc2 == g.get("country"))
                # 原生 = 两源国家一致 + 属于本地居民宽带/运营商网络（排除机房与广播 IP）
                local_net = bool(g.get("residential") or g.get("suspected_home"))
                g["native"] = bool(same and local_net)
                g["native_known"] = bool(cc2)
    except Exception:
        pass


# ---------------------------------------------------------------- 工具
def _is_ipv4(s: str) -> bool:
    p = s.split(".")
    if len(p) != 4:
        return False
    return all(x.isdigit() and 0 <= int(x) <= 255 for x in p)


def _resolve_ip(host: str) -> str:
    if not host:
        return ""
    if _is_ipv4(host):
        return host
    if host in _IP_CACHE:
        return _IP_CACHE[host]
    try:
        ip = socket.gethostbyname(host)
    except OSError:
        ip = ""
    _IP_CACHE[host] = ip
    return ip
