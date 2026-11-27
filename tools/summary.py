#!/usr/bin/env python3
"""把本轮结果汇总成 Actions 页面上的中文摘要（写 stdout）。"""
from __future__ import annotations

import json
import os

root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
p = os.path.join(root, "docs", "status.json")

print("## 本轮结果")
if not os.path.exists(p):
    print("- 没有生成状态文件（看上面的日志）")
    raise SystemExit(0)

try:
    s = json.load(open(p, encoding="utf-8"))
except Exception as e:
    print(f"- 状态文件读不出来：{e}")
    raise SystemExit(0)

ok = bool(s.get("ok"))
reason = s.get("reason") or ""

reason_cn = {
    "no_alive_nodes": "一个可用节点都没探到（源站集体失效或被挡）",
    "too_few_nodes": "可用节点太少",
    "sharp_drop": "节点数比上一轮暴跌",
}.get(reason, reason)

print(f"- 状态：{'已更新订阅' if ok else '本轮跳过覆盖（' + reason_cn + '）'}")
print(f"- 时间：{s.get('updated_at') or s.get('checked_at') or '-'}")
print(f"- 节点数：{s.get('count', 0)}")
print(f"- 源成功率：{s.get('sources_ok', 0)}/{s.get('sources_total', 0)}")
print(f"- 耗时：{s.get('elapsed_s', 0)} 秒")

c = s.get("counts") or {}
if c:
    print(f"- 产物：Clash {c.get('clash', 0)} / 精简 {c.get('clash_lite', 0)} / "
          f"sing-box {c.get('singbox', 0)} / base64 {c.get('base64', 0)}")

if not ok:
    print("\n> 数据异常时不会覆盖上一轮订阅，手机上的订阅照常能用。"
          "如果连续几轮都是这个状态，去 README 的「排错」一节对照处理。")
else:
    print("\n> 订阅地址没变，客户端下次自动更新即可。")
