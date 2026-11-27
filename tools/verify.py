#!/usr/bin/env python3
"""交付前自检：订阅文件是否齐全、能否被客户端解析。

Actions 里跑在 main.py 之后。这里只做只读检查，不改任何文件。
全部通过退出 0；有问题退出 1（这一轮不部署，上一轮订阅继续服务）。
"""
from __future__ import annotations

import base64
import json
import os
import sys

REQ = ("clash.yaml", "clash-lite.yaml", "clash-ascii.yaml", "singbox.json",
       "base64.txt", "meta.json")


def main() -> int:
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    sub = os.path.join(root, "docs", "sub")
    errors: list[str] = []

    if not os.path.isdir(sub):
        print("FAIL: docs/sub 不存在")
        return 1

    for fn in REQ:
        p = os.path.join(sub, fn)
        if not os.path.exists(p):
            errors.append(f"缺文件 {fn}")
        elif os.path.getsize(p) < 80:
            errors.append(f"{fn} 内容过小（{os.path.getsize(p)} 字节）")

    try:
        import yaml
    except ImportError:
        print("FAIL: 缺少 PyYAML")
        return 1

    counts = {}
    for fn in ("clash.yaml", "clash-lite.yaml", "clash-ascii.yaml"):
        p = os.path.join(sub, fn)
        if not os.path.exists(p):
            continue
        try:
            doc = yaml.safe_load(open(p, encoding="utf-8")) or {}
        except Exception as e:
            errors.append(f"{fn} YAML 解析失败: {e}")
            continue
        proxies = doc.get("proxies") or []
        groups = doc.get("proxy-groups") or []
        counts[fn] = len(proxies)
        if not proxies:
            errors.append(f"{fn} 没有任何节点")
        names = [x.get("name") for x in proxies]
        if len(set(names)) != len(names):
            errors.append(f"{fn} 有重名节点（客户端会整份拒绝）")
        if not groups:
            errors.append(f"{fn} 没有 proxy-groups")
        allowed_types = {"ss", "ssr", "vmess", "vless", "trojan", "hysteria", "hysteria2", "tuic", "anytls", "socks5", "http"}
        for x in proxies:
            if not x.get("type") or not x.get("server") or not x.get("port"):
                errors.append(f"{fn} 有节点缺 type/server/port")
                break
            if str(x.get("type")).lower() not in allowed_types:
                errors.append(f"{fn} 含 Clash 不支持的代理类型: {x.get('type')}")
                break
            if str(x.get("type")).lower() == "ssr" and not x.get("protocol"):
                errors.append(f"{fn} 含缺少 protocol 的 SSR 节点: {x.get('name', '')}")
                break

    p = os.path.join(sub, "singbox.json")
    if os.path.exists(p):
        try:
            sb = json.load(open(p, encoding="utf-8"))
            outs = sb.get("outbounds") or []
            if not outs:
                errors.append("singbox.json 没有 outbounds")
            tags = [o.get("tag") for o in outs]
            if len(set(tags)) != len(tags):
                errors.append("singbox.json 有重复 tag")
            if not sb.get("route", {}).get("final"):
                errors.append("singbox.json 缺 route.final")
        except Exception as e:
            errors.append(f"singbox.json 解析失败: {e}")

    p = os.path.join(sub, "base64.txt")
    if os.path.exists(p):
        try:
            raw = open(p, encoding="utf-8").read().strip()
            dec = base64.b64decode(raw + "=" * (-len(raw) % 4)).decode("utf-8", "ignore")
            if dec.count("://") < 1:
                errors.append("base64.txt 解码后没有有效链接")
        except Exception as e:
            errors.append(f"base64.txt 解码失败: {e}")

    p = os.path.join(sub, "meta.json")
    if os.path.exists(p):
        try:
            meta = json.load(open(p, encoding="utf-8"))
            if not meta.get("generated_at"):
                errors.append("meta.json 缺 generated_at")
        except Exception as e:
            errors.append(f"meta.json 解析失败: {e}")

    for k, v in counts.items():
        print(f"  {k}: {v} 个节点")

    if errors:
        print("FAIL")
        for e in errors:
            print("  - " + e)
        return 1

    print("OK: 订阅自检全部通过")
    return 0


if __name__ == "__main__":
    sys.exit(main())
