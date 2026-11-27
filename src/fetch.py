"""下载器：带重试、UA 轮换、编码自适应。"""
from __future__ import annotations

import gzip
import io
import time
import urllib.error
import urllib.request

from . import config


def fetch(url: str, timeout: int = None, retries: int = None) -> str:
    timeout = timeout or config.HTTP_TIMEOUT
    retries = config.HTTP_RETRIES if retries is None else retries
    last_err = ""
    for attempt in range(retries + 1):
        ua = config.UA_POOL[attempt % len(config.UA_POOL)]
        req = urllib.request.Request(url, headers={
            "User-Agent": ua,
            "Accept": "*/*",
            "Accept-Encoding": "gzip",
        })
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                raw = r.read()
                if r.headers.get("Content-Encoding") == "gzip":
                    raw = gzip.decompress(raw)
                return raw.decode("utf-8", "ignore")
        except urllib.error.HTTPError as e:
            last_err = f"HTTP {e.code}"
        except urllib.error.URLError as e:
            last_err = f"URLError {e.reason}"
        except Exception as e:
            last_err = f"{type(e).__name__} {e}"
        time.sleep(1.5 * (attempt + 1))
    raise RuntimeError(f"{url} -> {last_err}")
