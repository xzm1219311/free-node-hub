"""源清单与采集参数。

kind 说明：
  clash   -> Clash/mihomo YAML（proxies 列表）
  uri     -> 明文节点 URI（vmess:// vless:// ss:// trojan:// ...），可能整体 base64
  base64  -> 明确是 base64 包裹的 uri 列表
  singbox -> sing-box JSON（outbounds）
  vpngate -> VPNGate CSV（OpenVPN/SSL-VPN，单独产出）
"""

from __future__ import annotations

# ---- 采集行为 ----
HTTP_TIMEOUT = 20
HTTP_RETRIES = 2
FETCH_WORKERS = 12          # 并发拉取的源数量
UA_POOL = [
    "clash-verge/v2.0.0",
    "mihomo/1.18.0",
    "sing-box/1.10.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0 Safari/537.36",
]

# ---- 仅保留这些国家/地区（None = 全保留）----
# 需求是「美国家宽 / 原生」优先，其余国家仍然采集但单独归档
FOCUS_COUNTRIES = {"US"}

# ---- 探测参数 ----
TCP_TIMEOUT = 3.5
TCP_WORKERS = 128
MAX_GEO_PER_RUN = 1200          # 每轮最多查询多少 IP 的归属信息
GEO_BATCH = 100                # ip-api batch 单次条数
MAX_OUTPUT_NODES = 600         # 最终输出节点上限（订阅别太大，手机加载快）
MAX_PROBE_NODES = 2600         # 每轮最多探测多少个节点

# ---- 输出保护（这四项是「不把好订阅搞坏」的保险，别乱改）----
MIN_OUTPUT_NODES = 25          # 本轮可用节点少于这个数 -> 视为失败，不覆盖旧订阅
MIN_KEEP_RATIO = 0.30          # 本轮数量低于上一轮的 30% -> 视为异常，不覆盖
SUB_DIR = "sub"                # docs/sub/ 下的稳定订阅路径
TITLE = "node-sub"

# ---- 采集开关（Actions 里用默认值即可）----
QUICK_SOURCES = 8              # --quick 模式只跑前几个源，用于排错

# ---- 判定「机房 ASN」的关键词（命中即视为 IDC / 云厂商，不算家宽）----
IDC_KEYWORDS = (
    "amazon", "aws", "google", "microsoft", "azure", "oracle", "alibaba", "aliyun",
    "tencent", "huawei", "cloud", "digitalocean", "vultr", "linode", "akamai",
    "hetzner", "ovh", "contabo", "leaseweb", "choopa", "constant", "psychz",
    "colocation", "colocrossing", "datacenter", "data center", "hosting", "server",
    "vps", "dedicated", "cdn", "fastly", "cloudflare", "quadranet", "multacom",
    "zenlayer", "gcore", "upcloud", "scaleway", "kamatera", "ionos", "cogent",
    "equinix", "limelight", "stackpath", "hostwinds", "hosthatch", "buyvm",
    "frantech", "nexus", "servarica", "greencloud", "racknerd", "colocrossing",
    "sharktech", "fdcservers", "he.net", "hurricane electric", "dmit", "bandwagon",
    "cloudsigma", "netcup", "time4vps", "m247", "datacamp", "serverhub", "hostus",
)

# ---- 居民宽带 / 移动运营商关键词（「疑似家宽」兜底判定）----
ISP_KEYWORDS = (
    "comcast", "xfinity", "verizon", "at&t", "charter", "spectrum", "cox ",
    "centurylink", "lumen", "frontier", "windstream", "mediacom", "suddenlink",
    "optimum", "cablevision", "rcn", "cableone", "wideopenwest",
    "t-mobile", "tmobile", "sprint", "us cellular", "hughes", "viasat", "starlink",
    "bell canada", "telus", "rogers", "shaw ", "videotron", "cogeco", "eastlink",
    "kddi", "ntt", "softbank", "docomo", "biglobe", "so-net", "plala",
    "china telecom", "china unicom", "china mobile", "chunghwa", "hinet", "seednet",
    "sk broadband", "kornet", "lg u+", "kt corp", "singtel", "starhub", "m1 limited",
    "true internet", "ais fibre", "3bb", "viettel", "vnpt", "fpt telecom",
    "telkom", "indosat", "biznet", "myrepublic", "viewqwest", "exetel",
    "aussie broadband", "iinet", "optus", "vodafone", "telefonica", "orange s.a",
    "deutsche telekom", "1&1", "kabel deutschland", "virgin media",
    "sky broadband", "talktalk", "ziggo", "kpn", "xs4all", "proximus", "telenet",
)

# ---- 来源清单 ----
# 说明：全部为公开、无需登录的订阅/节点列表。失效的会在运行日志里标出，不影响整体。
SOURCES: list[dict] = [
    # ===== GitHub 聚合（clash yaml）=====
    {"name": "Pawdroid-Free-servers",  "kind": "clash",   "url": "https://raw.githubusercontent.com/Pawdroid/Free-servers/main/sub"},
    {"name": "aiboboxx-clashfree",     "kind": "clash",   "url": "https://raw.githubusercontent.com/aiboboxx/clashfree/main/sub.yml"},
    {"name": "mfuu-v2ray-clash",       "kind": "clash",   "url": "https://raw.githubusercontent.com/mfuu/v2ray/master/sub.yaml"},
    {"name": "ripaojiedian-clash",     "kind": "clash",   "url": "https://raw.githubusercontent.com/ripaojiedian/freenode/main/clash"},
    {"name": "ermaozi-clash",          "kind": "clash",   "url": "https://raw.githubusercontent.com/ermaozi/get_subscribe/main/subscribe/clash.yml"},
    {"name": "mahdibland-Eternity",    "kind": "clash",   "url": "https://raw.githubusercontent.com/mahdibland/ShadowsocksAggregator/master/Eternity.yml"},
    {"name": "mahdibland-merge",       "kind": "clash",   "url": "https://raw.githubusercontent.com/mahdibland/V2RayAggregator/master/sub/sub_merge_yaml.yml"},
    {"name": "Barabama-FreeNodes",     "kind": "clash",   "url": "https://raw.githubusercontent.com/Barabama/FreeNodes/main/nodes/merged.yaml"},
    {"name": "anaer-Sub-clash",        "kind": "clash",   "url": "https://raw.githubusercontent.com/anaer/Sub/main/clash.yaml"},
    {"name": "peasoft-NoMoreWalls",    "kind": "clash",   "url": "https://raw.githubusercontent.com/peasoft/NoMoreWalls/master/list.yml"},
    {"name": "chengaopan-AutoMerge",   "kind": "clash",   "url": "https://raw.githubusercontent.com/chengaopan/AutoMergePublicNodes/master/list.yml"},
    {"name": "a2470982985-getNode",    "kind": "clash",   "url": "https://raw.githubusercontent.com/a2470982985/getNode/main/clash.yaml"},
    {"name": "free18-v2ray",           "kind": "clash",   "url": "https://raw.githubusercontent.com/free18/v2ray/main/c.yaml"},
    {"name": "ts-sf-fly",              "kind": "clash",   "url": "https://raw.githubusercontent.com/ts-sf/fly/main/clash"},
    {"name": "vxiaov-free_proxies",    "kind": "clash",   "url": "https://raw.githubusercontent.com/vxiaov/free_proxies/main/clash/clash.provider.yaml"},
    {"name": "Ruk1ng001-clash",        "kind": "clash",   "url": "https://raw.githubusercontent.com/Ruk1ng001/freeSub/main/clash.yaml"},
    {"name": "w1770946466-sub1",       "kind": "clash",   "url": "https://raw.githubusercontent.com/w1770946466/Auto_proxy/main/Long_term_subscription1.yaml"},
    {"name": "w1770946466-sub3",       "kind": "clash",   "url": "https://raw.githubusercontent.com/w1770946466/Auto_proxy/main/Long_term_subscription3.yaml"},
    {"name": "w1770946466-sub4",       "kind": "clash",   "url": "https://raw.githubusercontent.com/w1770946466/Auto_proxy/main/Long_term_subscription4.yaml"},
    {"name": "learnhard-config",       "kind": "clash",   "url": "https://raw.githubusercontent.com/learnhard-cn/free_proxy_ss/main/config.yaml"},
    {"name": "awesome-vpn-clash",      "kind": "clash",   "url": "https://raw.githubusercontent.com/awesome-vpn/awesome-vpn/master/clash.yaml"},
    {"name": "zhangkaiitugithub-meta", "kind": "clash",   "url": "https://raw.githubusercontent.com/zhangkaiitugithub/passcro/main/meta.yaml"},
    {"name": "zhangkaiitugithub-speed","kind": "clash",   "url": "https://raw.githubusercontent.com/zhangkaiitugithub/passcro/main/speednodes.yaml"},

    # ===== GitHub 聚合（明文 URI / base64）=====
    {"name": "aiboboxx-v2rayfree",     "kind": "uri",     "url": "https://raw.githubusercontent.com/aiboboxx/v2rayfree/main/sub"},
    {"name": "mfuu-v2ray-uri",         "kind": "uri",     "url": "https://raw.githubusercontent.com/mfuu/v2ray/master/sub"},
    {"name": "ripaojiedian-sub",       "kind": "uri",     "url": "https://raw.githubusercontent.com/ripaojiedian/freenode/main/sub"},
    {"name": "freefq-free",            "kind": "uri",     "url": "https://raw.githubusercontent.com/freefq/free/master/v2"},
    {"name": "ermaozi-v2ray",          "kind": "uri",     "url": "https://raw.githubusercontent.com/ermaozi/get_subscribe/main/subscribe/v2ray.txt"},
    {"name": "peasoft-NoMoreWalls-t",  "kind": "uri",     "url": "https://raw.githubusercontent.com/peasoft/NoMoreWalls/master/list.txt"},
    {"name": "Flik6-getNode",          "kind": "uri",     "url": "https://raw.githubusercontent.com/Flik6/getNode/main/v2ray.txt"},
    {"name": "Kwinshadow-TG",          "kind": "uri",     "url": "https://raw.githubusercontent.com/Kwinshadow/TelegramV2rayCollector/main/sublinks/mix.txt"},
    {"name": "MatinGhanbari-super",    "kind": "uri",     "url": "https://raw.githubusercontent.com/MatinGhanbari/v2ray-configs/main/subscriptions/v2ray/super-sub.txt"},
    {"name": "roosterkid-V2RAY_RAW",   "kind": "uri",     "url": "https://raw.githubusercontent.com/roosterkid/openproxylist/main/V2RAY_RAW.txt"},
    {"name": "ALIILAPRO-v2rayNG",      "kind": "uri",     "url": "https://raw.githubusercontent.com/ALIILAPRO/v2rayNG-Config/main/server.txt"},
    {"name": "Surfboardv2ray-TGParse", "kind": "uri",     "url": "https://raw.githubusercontent.com/Surfboardv2ray/TGParse/main/configtg.txt"},
    {"name": "Ruk1ng001-v2ray",        "kind": "uri",     "url": "https://raw.githubusercontent.com/Ruk1ng001/freeSub/main/v2ray"},
    {"name": "Jsnzkpg-nodes",          "kind": "uri",     "url": "https://raw.githubusercontent.com/Jsnzkpg/Jsnzkpg/Jsnzkpg/Jsnzkpg"},
    {"name": "ZywChannel-sub",         "kind": "uri",     "url": "https://raw.githubusercontent.com/ZywChannel/free/main/sub"},
    {"name": "learnhard-free",         "kind": "uri",     "url": "https://raw.githubusercontent.com/learnhard-cn/free_proxy_ss/main/free"},
    {"name": "xiaoji235-airport-free", "kind": "uri",     "url": "https://raw.githubusercontent.com/xiaoji235/airport-free/main/v2ray.txt"},
    {"name": "awesome-vpn-all",        "kind": "uri",     "url": "https://raw.githubusercontent.com/awesome-vpn/awesome-vpn/master/all"},

    # ===== sing-box 原生格式 =====
    {"name": "Ruk1ng001-singbox",      "kind": "singbox", "url": "https://raw.githubusercontent.com/Ruk1ng001/freeSub/main/singBox.json"},
    {"name": "zhangkaiitugithub-singbox", "kind": "singbox", "url": "https://raw.githubusercontent.com/zhangkaiitugithub/passcro/main/sing-box.json"},

    # ===== 补充聚合（2026-11 追加，失效不影响整体）=====
    {"name": "barry-far-All",          "kind": "uri",     "url": "https://raw.githubusercontent.com/barry-far/V2ray-Configs/main/All_Configs_Sub.txt"},
    {"name": "Epodonios-All",          "kind": "uri",     "url": "https://raw.githubusercontent.com/Epodonios/v2ray-configs/main/All_Configs_Sub.txt"},
    {"name": "mahdibland-merge-txt",   "kind": "uri",     "url": "https://raw.githubusercontent.com/mahdibland/V2RayAggregator/master/sub/sub_merge.txt"},
    {"name": "soroush-mixed",          "kind": "uri",     "url": "https://raw.githubusercontent.com/soroushmirzaei/telegram-configs-collector/main/splitted/mixed"},
    {"name": "ALIILAPRO-sub",          "kind": "uri",     "url": "https://raw.githubusercontent.com/ALIILAPRO/v2rayNG-Config/main/sub.txt"},
    {"name": "free18-v",               "kind": "uri",     "url": "https://raw.githubusercontent.com/free18/v2ray/main/v.txt"},

    # ===== VPNGate（OpenVPN / SSL-VPN，单独产出）=====
    {"name": "VPNGate-API",            "kind": "vpngate", "url": "https://www.vpngate.net/api/iphone/"},
]

# ur.io（URnetwork）说明：官方为闭源客户端 + 需注册的分布式网络，没有公开订阅端点。
# 这里保留其公开信息页用于 README 说明，不参与自动采集，避免产出无效节点。
REFERENCE_ONLY = [
    {
        "name": "URnetwork (ur.io)",
        "url": "https://ur.io/",
        "note": "闭源分布式 VPN，需注册账号并安装官方客户端，无公开订阅接口，无法直接转为 clash/sing-box 订阅。",
    },
    {
        "name": "VPNGate",
        "url": "https://www.vpngate.net/",
        "note": "公开学术实验项目，提供 OpenVPN/SSL-VPN，非 clash 协议；本项目单独产出 .ovpn 包。",
    },
]
