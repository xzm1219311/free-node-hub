#!/usr/bin/env python3
"""节点聚合：采集 -> 解析 -> 去重 -> 连通性 -> 归属判定 -> 输出订阅。

用法：
    python main.py                 # 完整跑一轮（Actions 里用这个）
    python main.py --quick         # 快速自检：只跑前几个源、少量节点
    python main.py --no-geo        # 跳过归属查询
    python main.py --offline       # 用 .cache/nodes.json 重放（不联网）

设计原则（这套保险比功能更重要）：
  1. 先写临时目录，全部校验通过才替换正式文件 —— 客户端永远拉不到半截文件
  2. 本轮节点太少 / 比上轮暴跌，直接放弃覆盖 —— 宁可数据旧，也不让订阅变空
  3. 任何一步异常都不动已有产物
"""
from __future__ import annotations

import base64
import json
import os
import shutil
import sys
import time
import traceback

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src import config, emit, fetch, geo, parse, probe  # noqa: E402

ROOT = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(ROOT, "output")
DOCS = os.path.join(ROOT, "docs")
SUB = os.path.join(DOCS, "sub")
CACHE = os.path.join(ROOT, ".cache")
STAGE = os.path.join(ROOT, ".staging")
REPO = os.environ.get("GITHUB_REPOSITORY", "your-name/free-node-hub")


def log(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


# ------------------------------------------------------------------ 采集
def _one_source(s: dict):
    """拉取并解析单个源，返回 (name, nodes, vpngate_rows, err)。"""
    name, url, kind = s["name"], s["url"], s["kind"]
    try:
        text = fetch.fetch(url)
    except Exception as e:
        return name, [], [], str(e)[:150]
    try:
        if kind == "clash":
            return name, parse.parse_clash_yaml(text, name), [], None
        if kind == "singbox":
            return name, parse.parse_singbox_json(text, name), [], None
        if kind in ("uri", "base64"):
            return name, parse.parse_uri_blob(text, name), [], None
        if kind == "vpngate":
            return name, [], parse.parse_vpngate_csv(text), None
        return name, [], [], "未知 kind"
    except Exception as e:
        return name, [], [], f"解析异常 {type(e).__name__}: {e}"[:150]


def collect(no_geo: bool = False, quick: bool = False):
    from concurrent.futures import ThreadPoolExecutor, as_completed

    sources = config.SOURCES[:config.QUICK_SOURCES] if quick else config.SOURCES
    all_nodes: list[dict] = []
    vpngate: list[dict] = []
    stats = {"sources_total": len(sources), "sources_ok": 0, "sources_fail": 0,
             "raw_nodes": 0, "errors": []}

    with ThreadPoolExecutor(max_workers=config.FETCH_WORKERS) as ex:
        futs = {ex.submit(_one_source, s): s for s in sources}
        for f in as_completed(futs):
            s = futs[f]
            try:
                name, nodes, vg, err = f.result()
            except Exception as e:
                name = s["name"]
                nodes, vg, err = [], [], f"任务异常 {e}"
            if vg:
                vpngate = vg
                stats["sources_ok"] += 1
                log(f"OK  {name}: VPNGate {len(vg)} 台（单独产出 .ovpn）")
            elif nodes:
                all_nodes += nodes
                stats["sources_ok"] += 1
                stats["raw_nodes"] = len(all_nodes)
                log(f"OK  {name}: +{len(nodes)}")
            else:
                stats["sources_fail"] += 1
                stats["errors"].append({"source": name, "url": s["url"],
                                        "error": err or "解析出 0 个节点"})
                log(f"--  {name}: {(err or '0 节点')[:80]}")

    return all_nodes, vpngate, stats


# ------------------------------------------------------------------ 去重 / 排序
def dedupe(nodes: list[dict]) -> list[dict]:
    seen = set()
    out = []
    for n in nodes:
        key = (n.get("type"), str(n.get("server", "")).lower(), int(n.get("port") or 0),
               n.get("uuid") or n.get("password") or "")
        if key in seen:
            continue
        seen.add(key)
        out.append(n)
    return out


def rank(nodes: list[dict]) -> list[dict]:
    def score(n):
        g = n.get("geo") or {}
        s = 0
        if g.get("country") == "US":
            s += 1000
        if g.get("residential"):
            s += 500
        elif g.get("suspected_home"):
            s += 250
        if g.get("native"):
            s += 300
        if g.get("mobile"):
            s += 50
        if g.get("hosting"):
            s -= 200
        return (-s, n.get("_tcp_ms", 3000))

    return sorted(nodes, key=score)


def _count_by(nodes, key, top_level=False) -> dict:
    from collections import Counter
    c = Counter()
    for n in nodes:
        if top_level:
            c[n.get(key) or "?"] += 1
        else:
            c[(n.get("geo") or {}).get(key) or "?"] += 1
    return dict(c.most_common(30))


# ------------------------------------------------------------------ 输出（原子）
def build_outputs(nodes: list[dict], meta: dict) -> dict:
    """全部写进 .staging，返回每个文件的字节数 / 条数。"""
    shutil.rmtree(STAGE, ignore_errors=True)
    os.makedirs(STAGE, exist_ok=True)

    def p(name):
        return os.path.join(STAGE, name)

    counts = {}
    counts["clash"] = emit.write_clash(nodes, p("clash.yaml"), meta)
    counts["clash_lite"] = emit.write_clash(nodes, p("clash-lite.yaml"), meta, lite=True)
    counts["clash_ascii"] = emit.write_clash(nodes, p("clash-ascii.yaml"), meta, ascii_names=True)
    counts["singbox"] = emit.write_singbox(nodes, p("singbox.json"), meta)
    counts["base64"] = emit.write_base64(nodes, p("base64.txt"))
    emit.write_meta(meta, p("meta.json"))
    return counts


def validate(counts: dict) -> tuple[bool, str]:
    """交付前自检：能不能被客户端解析、有没有重复名、数量对不对。"""
    import yaml

    if counts.get("clash", 0) < 1:
        return False, "clash 订阅为空"

    for fn in ("clash.yaml", "clash-lite.yaml", "clash-ascii.yaml"):
        path = os.path.join(STAGE, fn)
        if not os.path.exists(path) or os.path.getsize(path) < 200:
            return False, f"{fn} 缺失或过小"
        try:
            doc = yaml.safe_load(open(path, encoding="utf-8"))
        except Exception as e:
            return False, f"{fn} 不是合法 YAML: {e}"
        proxies = (doc or {}).get("proxies") or []
        if len(proxies) != counts["clash"]:
            return False, f"{fn} 节点数不符 {len(proxies)} != {counts['clash']}"
        names = [x.get("name") for x in proxies]
        if len(set(names)) != len(names):
            return False, f"{fn} 有重名节点（客户端会拒绝整个订阅）"
        allowed_types = {"ss", "ssr", "vmess", "vless", "trojan", "hysteria", "hysteria2", "tuic", "anytls", "socks5", "http"}
        for x in proxies:
            if not x.get("server") or not x.get("port") or not x.get("type"):
                return False, f"{fn} 有节点缺 server/port/type"
            if str(x.get("type")).lower() not in allowed_types:
                return False, f"{fn} 含 Clash 不支持的代理类型: {x.get('type')}"

    try:
        sb = json.load(open(os.path.join(STAGE, "singbox.json"), encoding="utf-8"))
    except Exception as e:
        return False, f"singbox.json 非法: {e}"
    tags = [o.get("tag") for o in sb.get("outbounds", [])]
    if len(tags) != len(set(tags)):
        return False, "singbox 有重复 tag"

    if counts.get("base64", 0) < 1:
        return False, "base64 订阅为空"
    return True, "ok"


def publish(counts: dict, meta: dict) -> None:
    """校验通过后，原子替换到 output/ 和 docs/sub/。"""
    os.makedirs(OUT, exist_ok=True)
    os.makedirs(SUB, exist_ok=True)

    for fn in os.listdir(STAGE):
        src = os.path.join(STAGE, fn)
        if not os.path.isfile(src):
            continue
        for dest in (os.path.join(OUT, fn), os.path.join(SUB, fn)):
            tmp = dest + ".tmp"
            shutil.copyfile(src, tmp)
            os.replace(tmp, dest)

    # 旧路径兼容：之前导入过 docs/output/clash.yaml 的客户端不用改地址
    docs_out = os.path.join(DOCS, "output")
    shutil.rmtree(docs_out, ignore_errors=True)
    shutil.copytree(STAGE, docs_out)
    shutil.copyfile(os.path.join(STAGE, "meta.json"), os.path.join(DOCS, "meta.json"))

    status = {
        "ok": True,
        "updated_at": meta["generated_at"],
        "updated_ts": int(time.time()),
        "count": meta["count"],
        "counts": {k: counts.get(k, 0) for k in ("clash", "clash_lite", "clash_ascii", "singbox", "base64")},
        "sources_ok": meta["sources_ok"],
        "sources_total": meta["sources_total"],
        "repo": meta["repo"],
        "elapsed_s": meta["elapsed_s"],
    }
    emit.write_meta(status, os.path.join(DOCS, "status.json"))

    # VPNGate 附件
    vg = os.path.join(STAGE, "vpngate")
    if os.path.isdir(vg):
        for base in (os.path.join(OUT, "vpngate"), os.path.join(SUB, "vpngate")):
            shutil.rmtree(base, ignore_errors=True)
            shutil.copytree(vg, base)


def _write_vpngate(rows: list[dict]) -> None:
    if not rows:
        return
    d = os.path.join(STAGE, "vpngate")
    os.makedirs(d, exist_ok=True)
    us = [r for r in rows if r.get("country") == "US"]
    us.sort(key=lambda r: (-r.get("speed", 0), r.get("ping", 9999)))
    picked = (us or rows)[:40]
    idx = []
    for i, r in enumerate(picked, 1):
        if not r.get("ovpn_b64"):
            continue
        try:
            cfg = base64.b64decode(r["ovpn_b64"]).decode("utf-8", "ignore")
        except Exception:
            continue
        fn = f"vpngate-{r.get('country', 'XX')}-{i:02d}.ovpn"
        with open(os.path.join(d, fn), "w", encoding="utf-8") as f:
            f.write(cfg)
        idx.append({"file": fn, "host": r.get("host"), "ip": r.get("ip"),
                    "country": r.get("country"),
                    "speed_mbps": round(r.get("speed", 0) / 1e6, 2),
                    "ping_ms": r.get("ping")})
    with open(os.path.join(d, "index.json"), "w", encoding="utf-8") as f:
        json.dump(idx, f, ensure_ascii=False, indent=2)
    log(f"VPNGate：导出 {len(idx)} 个 .ovpn")


# ------------------------------------------------------------------ 上一轮对比
def prev_count() -> int:
    """上一轮节点数。老版本留下的 meta（没有 generated_ts）不算数，
    否则第一次跑会被旧数据误判成「暴跌」而一直不更新。"""
    for p in (os.path.join(DOCS, "meta.json"), os.path.join(OUT, "meta.json")):
        try:
            m = json.load(open(p, encoding="utf-8"))
        except Exception:
            continue
        if not m.get("generated_ts"):
            continue
        return int(m.get("count") or 0)
    return 0


# ------------------------------------------------------------------ 主流程
def main() -> int:
    quick = "--quick" in sys.argv
    offline = "--offline" in sys.argv
    no_probe = "--no-probe" in sys.argv
    force = "--force" in sys.argv
    no_geo = "--no-geo" in sys.argv or quick

    os.makedirs(OUT, exist_ok=True)
    os.makedirs(DOCS, exist_ok=True)
    os.makedirs(CACHE, exist_ok=True)

    t0 = time.time()
    log(f"开始采集{'（快速模式）' if quick else ''}…")
    if offline:
        p = os.path.join(CACHE, "nodes.json")
        if not os.path.exists(p):
            log("离线模式但缺少 .cache/nodes.json")
            return 1
        raw = json.load(open(p, encoding="utf-8"))
        nodes, vpngate, stats = raw["nodes"], raw.get("vpngate", []), raw.get("stats", {})
    else:
        nodes, vpngate, stats = collect(no_geo, quick)

    log(f"采集完成：{len(nodes)} 原始 / {len(vpngate)} VPNGate")
    nodes = dedupe(nodes)
    nodes = [n for n in nodes if n.get("server") and n.get("port")]
    log(f"去重后：{len(nodes)}")

    cap = 400 if quick else config.MAX_PROBE_NODES
    nodes = nodes[:cap]
    if no_probe:
        log("跳过 TCP 探测（--no-probe）")
        for n in nodes:
            n.setdefault("_tcp_ms", 999)
    else:
        log(f"TCP 探测 {len(nodes)} 个…")
        nodes = probe.probe(nodes)
        log(f"可连通：{len(nodes)}")

    if not nodes:
        log("本轮 0 个可用节点 —— 保留上一轮订阅不覆盖")
        emit.write_meta({"ok": False, "reason": "no_alive_nodes",
                         "checked_at": time.strftime("%Y-%m-%d %H:%M:%S")},
                        os.path.join(DOCS, "status.json"))
        return 0

    if not no_geo:
        log("归属 / 家宽判定…")
        geo.enrich(nodes, 200 if quick else config.MAX_GEO_PER_RUN)
        geo.asn_country_for_nodes(nodes)
        log("判定完成")

    nodes = rank(nodes)[: (120 if quick else config.MAX_OUTPUT_NODES)]
    us = [n for n in nodes if (n.get("geo") or {}).get("country") == "US"]
    home = [n for n in us if (n.get("geo") or {}).get("residential")]
    susp = [n for n in us if (n.get("geo") or {}).get("suspected_home")]
    native = [n for n in us if (n.get("geo") or {}).get("native")]

    meta = {
        "title": config.TITLE,
        "repo": REPO,
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime()),
        "generated_ts": int(time.time()),
        "tz": "UTC",
        "count": len(nodes),
        "us": len(us),
        "us_home": len(home),
        "us_suspected": len(susp),
        "us_native": len(native),
        "vpngate": len(vpngate),
        "sources_ok": stats.get("sources_ok", 0),
        "sources_total": stats.get("sources_total", len(config.SOURCES)),
        "by_country": _count_by(nodes, "country"),
        "by_type": _count_by(nodes, "type", top_level=True),
        "top": [{
            "name": emit.label(n, i),
            "type": n.get("type"),
            "server": n.get("server"),
            "country": (n.get("geo") or {}).get("country"),
            "isp": (n.get("geo") or {}).get("isp"),
            "residential": (n.get("geo") or {}).get("residential"),
            "suspected": (n.get("geo") or {}).get("suspected_home"),
            "native": (n.get("geo") or {}).get("native"),
            "ms": n.get("_tcp_ms"),
        } for i, n in enumerate(nodes[:60], 1)],
        "errors": stats.get("errors", [])[:40],
        "reference": config.REFERENCE_ONLY,
        "elapsed_s": round(time.time() - t0, 1),
    }

    counts = build_outputs(nodes, meta)
    counts["clash"] = counts["clash"]
    meta["count"] = counts["clash"]
    _write_vpngate(vpngate)

    ok, why = validate(counts)
    if not ok:
        log(f"自检失败：{why} —— 保留上一轮订阅不覆盖")
        emit.write_meta({"ok": False, "reason": f"validate: {why}",
                         "checked_at": time.strftime("%Y-%m-%d %H:%M:%S")},
                        os.path.join(DOCS, "status.json"))
        return 0

    prev = prev_count()
    if len(nodes) < config.MIN_OUTPUT_NODES and not (quick or force):
        log(f"只拿到 {len(nodes)} 个节点（< {config.MIN_OUTPUT_NODES}）—— 保留上一轮订阅")
        emit.write_meta({"ok": False, "reason": "too_few_nodes", "count": len(nodes),
                         "checked_at": time.strftime("%Y-%m-%d %H:%M:%S")},
                        os.path.join(DOCS, "status.json"))
        return 0
    if prev and len(nodes) < prev * config.MIN_KEEP_RATIO and not (quick or force):
        log(f"节点数从 {prev} 暴跌到 {len(nodes)}（< {int(prev * config.MIN_KEEP_RATIO)}）—— 保留上一轮订阅")
        emit.write_meta({"ok": False, "reason": "sharp_drop", "prev": prev, "count": len(nodes),
                         "checked_at": time.strftime("%Y-%m-%d %H:%M:%S")},
                        os.path.join(DOCS, "status.json"))
        return 0

    meta["count"] = len(nodes)
    emit.write_meta(meta, os.path.join(STAGE, "meta.json"))
    publish(counts, meta)

    json.dump({"nodes": nodes, "vpngate": vpngate, "stats": stats},
              open(os.path.join(CACHE, "nodes.json"), "w", encoding="utf-8"),
              ensure_ascii=False)
    log(f"完成：{len(nodes)} 节点（美国 {len(us)} / 家宽 {len(home)} / 疑似 {len(susp)} / "
        f"原生 {len(native)}），耗时 {meta['elapsed_s']}s")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        traceback.print_exc()
        sys.exit(1)
