"""节点连通性探测（TCP 握手，不发起真实代理请求）。"""
from __future__ import annotations

import socket
from concurrent.futures import ThreadPoolExecutor, as_completed

from . import config


def tcp_ok(host: str, port: int, timeout: float = None) -> bool:
    timeout = timeout or config.TCP_TIMEOUT
    try:
        with socket.create_connection((host, int(port)), timeout=timeout):
            return True
    except (OSError, ValueError):
        return False


def probe(nodes: list[dict], workers: int = None) -> list[dict]:
    """返回能建立 TCP 连接的节点；同时写入 _tcp_ms 延迟。"""
    workers = workers or config.TCP_WORKERS
    alive: list[dict] = []
    if not nodes:
        return alive

    def _one(n):
        import time
        t0 = time.time()
        ok = tcp_ok(n["server"], n["port"])
        return n, ok, int((time.time() - t0) * 1000)

    with ThreadPoolExecutor(max_workers=workers) as ex:
        futs = [ex.submit(_one, n) for n in nodes]
        for f in as_completed(futs):
            try:
                n, ok, ms = f.result()
            except Exception:
                continue
            if ok:
                n["_tcp_ms"] = ms
                alive.append(n)
    alive.sort(key=lambda x: x.get("_tcp_ms", 9999))
    return alive
