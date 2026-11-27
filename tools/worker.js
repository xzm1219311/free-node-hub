/**
 * 节点订阅中转（Cloudflare Worker）
 *
 * 作用：给手机上的 Clash / FlClash / Stash / NekoBox 一个稳定、快的订阅地址，
 *      内部自动在 GitHub 的几条线路之间挑一条能通的，客户端只用记一个网址。
 *
 * 部署（网页版，5 分钟）：
 *   1. 打开 https://dash.cloudflare.com  → 左侧 Workers & Pages → Create → Worker
 *   2. 把本文件全部内容粘进去，替换掉原来的示例代码
 *   3. 只改下面 REPO 那一行，填成你的「用户名/仓库名」
 *   4. Deploy，然后访问 https://<你的worker名>.workers.dev/clash 查看结果
 *
 * 之后订阅地址就是：
 *   https://<你的worker名>.workers.dev/clash        完整版
 *   https://<你的worker名>.workers.dev/clash-lite   精简版
 *   https://<你的worker名>.workers.dev/singbox      sing-box 版
 *   https://<你的worker名>.workers.dev/base64       通用 base64
 */

// ======== 只改这一行 ========
const REPO = "你的用户名/你的仓库名";   // 例如 "zhangsan/free-node-hub"
// ===========================

const USER = REPO.split("/")[0];
const NAME = REPO.split("/")[1] || "";
const PREFIX = "docs/sub";

const FILES = {
  "/clash": { file: "clash.yaml", type: "text/yaml; charset=utf-8" },
  "/clash-lite": { file: "clash-lite.yaml", type: "text/yaml; charset=utf-8" },
  "/clash-ascii": { file: "clash-ascii.yaml", type: "text/yaml; charset=utf-8" },
  "/singbox": { file: "singbox.json", type: "application/json; charset=utf-8" },
  "/base64": { file: "base64.txt", type: "text/plain; charset=utf-8" },
  "/meta": { file: "meta.json", type: "application/json; charset=utf-8" },
};

const UPSTREAMS = [
  // 1. GitHub 官方 raw（海外最快，国内常被墙）
  (f) => `https://raw.githubusercontent.com/${REPO}/main/${PREFIX}/${f}`,
  // 2. jsDelivr（国内通常能通，有缓存）
  (f) => `https://cdn.jsdelivr.net/gh/${REPO}@main/${PREFIX}/${f}`,
  // 3. ghproxy 加速
  (f) => `https://ghproxy.net/https://raw.githubusercontent.com/${REPO}/main/${PREFIX}/${f}`,
  // 4. GitHub Pages
  (f) => `https://${USER}.github.io/${NAME}/sub/${f}`,
];

const CACHE_TTL = 300; // 5 分钟，够新也不至于每请求都回源

export default {
  async fetch(request) {
    const url = new URL(request.url);
    let path = url.pathname.replace(/\/+$/, "") || "/";

    // 随便什么后缀都能用，避免有人按路径屏蔽
    if (path.startsWith("/sub/")) path = "/" + path.slice(5);

    if (path === "/" || path === "") {
      return json({
        ok: true,
        repo: REPO,
        endpoints: Object.keys(FILES).concat(["/health", "/status"]),
        usage: "把 /clash 加到本域名后面就是订阅地址",
      });
    }

    if (path === "/status") {
      return proxyFile("meta.json", "application/json; charset=utf-8", true);
    }

    if (path === "/health") {
      const results = await Promise.all(
        UPSTREAMS.map(async (fn, i) => {
          const t0 = Date.now();
          try {
            const r = await fetch(fn("meta.json"), {
              headers: { "user-agent": "sub-worker/1.0" },
              cf: { cacheTtl: 60 },
            });
            return { order: i + 1, ok: r.ok, ms: Date.now() - t0, status: r.status };
          } catch (e) {
            return { order: i + 1, ok: false, ms: Date.now() - t0, error: String(e) };
          }
        })
      );
      return json({ repo: REPO, upstreams: results });
    }

    const hit = FILES[path];
    if (!hit) {
      return json({ ok: false, error: "未知路径", endpoints: Object.keys(FILES) }, 404);
    }
    return proxyFile(hit.file, hit.type, false);
  },
};

async function proxyFile(file, type, noCache) {
  const cache = caches.default;
  const cacheKey = new Request(`https://cache.local/${REPO}/${file}`, { method: "GET" });
  if (!noCache) {
    const cached = await cache.match(cacheKey);
    if (cached) return cached;
  }

  let last = "未知错误";
  for (const fn of UPSTREAMS) {
    const target = fn(file);
    try {
      const resp = await fetch(target, {
        headers: { "user-agent": "sub-worker/1.0", accept: "*/*" },
        cf: { cacheTtl: CACHE_TTL, cacheEverything: true },
      });
      if (!resp.ok) {
        last = `HTTP ${resp.status} @ ${new URL(target).host}`;
        continue;
      }
      const body = await resp.text();
      // 空内容 / 半截文件都不算成功，继续试下一条线路
      if (!body || body.length < 50) {
        last = `内容为空 @ ${new URL(target).host}`;
        continue;
      }
      const out = new Response(body, {
        headers: {
          "content-type": type,
          "cache-control": `public, max-age=${CACHE_TTL}`,
          "profile-update-interval": "6",
          "access-control-allow-origin": "*",
          "x-source": new URL(target).host,
        },
      });
      if (!noCache) {
        try {
          await cache.put(cacheKey, out.clone());
        } catch (e) { /* 缓存失败不影响返回 */ }
      }
      return out;
    } catch (e) {
      last = `${new URL(target).host}: ${e}`;
    }
  }

  return json({ ok: false, error: "所有上游线路都不通", last }, 502);
}

function json(obj, status = 200) {
  return new Response(JSON.stringify(obj, null, 2), {
    status,
    headers: { "content-type": "application/json; charset=utf-8", "access-control-allow-origin": "*" },
  });
}
