# 节点订阅（自动更新）

一个跑在 GitHub 上的免费节点采集 + 订阅服务：
每 3 小时自动抓公开节点 → 真连一次筛掉死的 → 按美国 / 家宽 / 原生排好 → 生成订阅。

**订阅地址永远不变**，手机上的 Clash 类 App 设好一次就不用再管。

---

## 一、三步上线

### 1. 传到 GitHub

先在网页上建一个**空仓库**（Public，不要勾 Add a README file），然后：

- **Windows**：双击 `setup.bat`，按提示输入用户名和仓库名
- **Mac / Linux**：`bash setup.sh`

> 网页上传也行：仓库首页 → Add file → Upload files，把解压后的文件全选拖进去。
> `.github` 是隐藏文件夹，Windows 里要开「显示隐藏项目」才看得到，别漏了它。

### 2. 开权限（少这一步必定失败）

| 位置 | 要改的地方 |
|---|---|
| Settings → Actions → General | 最下面 **Workflow permissions** 选 **Read and write** → Save |
| Settings → Pages | **Source** 选 **GitHub Actions** |

### 3. 手动跑第一次

顶部 **Actions** → 左边「更新节点订阅」→ 右边 **Run workflow** → 绿色按钮。

约 3–6 分钟跑完，`docs/` 和 `output/` 会有提交。之后每 3 小时自己跑，不用管。

面板地址：

```
https://<你的用户名>.github.io/<仓库名>/
```

---

## 二、订阅地址

跑完之后，路径固定是这些（把 `<用户名>/<仓库名>` 换成你的）：

| 用途 | 地址 |
|---|---|
| **完整版**（推荐） | `https://<用户名>.github.io/<仓库名>/sub/clash.yaml` |
| 精简版（老客户端 / 加载慢） | `.../sub/clash-lite.yaml` |
| 兼容版（节点名纯英文，不认 emoji 时用） | `.../sub/clash-ascii.yaml` |
| sing-box / NekoBox | `.../sub/singbox.json` |
| v2rayN（链接列表） | `.../sub/base64.txt` |

每份都同时存在于 4 个通道，哪个通用哪个：

```
GitHub Pages : https://<用户>.github.io/<仓库>/sub/clash.yaml
jsDelivr     : https://cdn.jsdelivr.net/gh/<用户>/<仓库>@main/docs/sub/clash.yaml
ghproxy      : https://ghproxy.net/https://raw.githubusercontent.com/<用户>/<仓库>/main/docs/sub/clash.yaml
raw          : https://raw.githubusercontent.com/<用户>/<仓库>/main/docs/sub/clash.yaml
```

面板页面上有按钮，点一下就能复制，不用手打。

---

## 三、在手机上导入

**Clash Verge / FlClash / Mihomo / Stash**
1. 复制「完整版」地址
2. App → 订阅 / Profiles → **+** → 从链接导入 → 粘贴
3. 启用这份订阅 → 首页节点选择选「🚀 节点选择」

**NekoBox / Hiddify**
1. 复制 sing-box 地址
2. 菜单 → 订阅 → 新建 → 粘贴 → 保存 → 点一下更新

**把「自动更新间隔」设成 6 小时**（默认一般就是）。

---

## 四、关于"会不会被封"

说清楚，不吹：

- **GitHub Pages 域名（`*.github.io`）在国内经常打不开** —— 这是最常见的"订阅拉不到"，不是你的项目坏了。换 jsDelivr 那条地址通常就好。
- **想彻底稳，自己搭一条中转**：`tools/worker.js` 是一段 Cloudflare Worker 代码，免费，粘进去改一行仓库名就能用，它会自动在 4 条线路里挑能通的。教程见 `使用教程.txt` 第 7 节。
- **免费节点本身寿命短**：几小时到几天就死一批，这是免费源的通病，不是项目问题。订阅每 3 小时换一批，客户端下次更新就换成能用的。
- **仓库不会被每小时几十次提交撑爆**：每周日会自动把提交历史压成一个（文件全留，只丢旧历史）。

这个项目为你做了四件防呆的事：

1. **本轮节点太少、或比上轮暴跌 → 直接不覆盖**，宁可数据旧，也不让订阅变空。
2. **先写临时文件、自检通过才替换正式文件** —— 客户端永远拉不到半截 YAML。
3. **三条 Clash 订阅都做重名检测**（重名会让客户端整份拒绝）。
4. **主定时 + 每天兜底一次**，单轮失败不影响下一轮。

---

## 五、常见问题

**Q：Actions 跑完是红的，报 `Resource not accessible by integration`**
→ 第 2 步的 Workflow permissions 没设成 Read and write。

**Q：Actions 里一直排队 / 不触发**
→ 免费仓库长时间没活动会被暂停定时任务，去 Actions 点一次 Run workflow 就恢复。

**Q：跑完了但节点很少 / 是 0**
→ 看 Actions 那一轮的摘要（Summary），会写明是"跳过覆盖"还是"探活失败"。免费源集体失效是常有的事，下一轮会自己好。

**Q：手机导入报"格式错误"**
→ 换「精简版」或「兼容版」；还不行说明拉到的是错误页（多半是网络断了 GitHub Pages），换成 jsDelivr 地址。

**Q：仓库能不能设 Private**
→ 不建议。Private 仓库的 Actions 每月只有 2000 分钟免费额度（本项目每月约 1400 分钟），而且 Private 仓库的 Pages 要付费。**设 Public**。

**Q：会不会被封号**
→ 项目只做公开数据聚合，不挖矿、不刷接口、低频运行。真正会出问题的是把仓库搞成公开代理服务对外卖 —— 别那么干。

---

## 六、目录结构

```
main.py                 主流程：采集 → 去重 → 探活 → 判定 → 输出
src/
  config.py             源清单、并发、上限（想加减源改这里）
  fetch.py              下载（重试 + UA 轮换）
  parse.py              解析 clash / sing-box / 各种分享链接
  probe.py              TCP 探活
  geo.py                归属地 + 家宽 / 原生判定
  emit.py               输出三种 Clash + sing-box + base64
tools/
  verify.py             交付前自检
  summary.py            Actions 页面里的中文摘要
  worker.js             Cloudflare 中转（可选，强烈建议）
docs/
  index.html            面板
  sub/                  订阅文件（客户端拉的就是这里）
output/                 同 sub，兼容老地址
.github/workflows/      定时任务
setup.bat / setup.sh    一键上传
```

## 七、本地调试

```bash
pip install -r requirements.txt

python main.py --quick                 # 只跑前 8 个源，快速看链路通不通
python main.py --no-geo                # 跳过归属查询，快一倍
python main.py --no-probe              # 跳过探活（本机不能直连 TCP 时用）
python main.py                         # 完整跑一轮
python tools/verify.py                 # 检查产物
```

`--offline` 会用 `.cache/nodes.json` 重放上一轮数据，用来调输出格式最方便。
