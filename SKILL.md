---
name: 1688-supplier-finder
description: 用一句话（关键词）或一张产品照片在 1688 上找供应商/工厂，抓主图、价格、起批量、工厂名片与链接，直接输出带图片的 Excel。当用户要「在 1688 找做 X 的工厂」「拿这张图去 1688 找同款供应商」「整理一份 1688 供应商报价表」时使用；只处理 1688 平台，不做阿里国际站/淘宝/拼多多，不代替用户谈价下单。
---

# 1688-supplier-finder

两条入口，同样的输出：`关键词 → 供应商表`，或`产品照片 → 图搜结果 → 供应商表`。每张表都嵌真实主图，链接可直接点开。

本目录即技能本体（`SKILL.md` + `run.py` + `finder/` + `scripts/`），可以被任何读取 `SKILL.md` 的 agent 客户端安装：DSH、WorkBuddy，或自行调用 `run.py`。

## 何时用

- 手里只有一个品类词（"硅胶折叠水杯"），要一批候选工厂做初筛。
- 手里有一张产品图（竞品图、客户来图、自己拍的样），要反查 1688 上谁在做。
- 需要一份能直接发给老板/客户的 Excel：工厂名、产地、年限、回头率、起批量、主图、链接。

## 何时不用

- 要的是**商品**清单而不是**供应商**清单 → 用 `1688 search`（本技能已按店铺聚合）。
- 要下单、询价、看物流 → 用 `1688 cart` / `1688 inbox` / `1688 order`，不归这里。
- 没有登录态、也不打算扫码 → 本技能所有数据都来自登录后可见页面，未登录直接失败。

## 安装

三种客户端都靠"把本目录放进它的 skills 目录"来生效。

```powershell
# 方式 1：仓库自带脚本（DSH + WorkBuddy 一起装，会检查依赖）
git clone https://github.com/G2E-Michael/1688-sourcing.git
cd 1688-sourcing
pwsh -File .\install.ps1 -Target both          # PowerShell 7
powershell -File .\install.ps1 -Target both    # Windows PowerShell 5.1

# 方式 2：直接克隆到目标目录（目录名必须是 1688-supplier-finder）
git clone https://github.com/G2E-Michael/1688-sourcing.git "$env:USERPROFILE\.dsh\skills\1688-supplier-finder"
git clone https://github.com/G2E-Michael/1688-sourcing.git "$env:USERPROFILE\.workbuddy\skills\1688-supplier-finder"
```

macOS / Linux 用 `bash install.sh`。装完在客户端刷新/重开会话，技能列表里出现 `1688-supplier-finder` 即生效。

## 前置（只需做一次）

1. Node 20+、Python 3.10+。
2. 本机有真实 Chrome（Playwright 走 `channel: 'chrome'`，用真实浏览器指纹，不下载额外 Chromium）。
3. 全局安装执行层 CLI 并装 Python 依赖：

```powershell
npm i -g 1688-cli
python -m pip install -r requirements.txt
```

4. 登录一次，登录态落在 `~/.1688/profiles/default`：

```powershell
& "$env:APPDATA\npm\1688.cmd" login --headed --timeout 300   # Windows
npx 1688 login --headed --timeout 300                        # macOS / Linux
```

登录态失效时任何命令都会返回 `NOT_LOGGED_IN`，重跑上面这条扫码即可。

## 跑法

先自检（10 秒），确认 node / CLI / Chrome / 登录四项：

```powershell
python run.py check
```

### 关键词找工厂

```powershell
python run.py keyword "硅胶折叠水杯" --max 20 --top 10 --offers 12 --enrich 5 `
  --province 广东 --min-years 3 --min-repeat-rate 0.4 --out "D:\采购\硅胶杯.xlsx"
```

### 照片找同款

```powershell
python run.py image "C:\path\to\cup.jpg" --max 30 --top 8 --offers 8 --enrich 3
```

`--enrich` 是"再进工厂名片页补员工数、详细地址、是否验厂"，每行约 3–5 秒，按需开。不开也能出表，只是省份/类型/工厂标签会空着。

### 常用参数

| 参数 | 作用 |
| --- | --- |
| `--max` | 关键词：每个词取多少家（默认 20）；图搜：抓多少条商品（默认 40） |
| `--top` | 表里最终保留多少行 |
| `--offers` | 为前 N 条商品查详情，补起批量/阶梯价（默认 12） |
| `--enrich` | 为前 N 家查工厂名片（默认 0） |
| `--include-traders` | 连贸易商一起要（默认只看工厂） |
| `--no-images` | 不下载图片（快，但表里没图） |
| `--no-offer-detail` | 跳过详情请求（最快，只有店铺级信息） |

## 输出

一个 `.xlsx`，两张表：

- **供应商**（18 列）：序号 / 主图 / 供应商名称 / 省份 / 城市 / 入驻年限 / 回头率% / 响应率% / 类型 / 工厂标签 / 综合评分 / 主营产品 / 主推产品 / 价格 / 起批 / 产品链接 / 店铺链接 / 工厂名片
- **产品明细**（9 列）：序号 / 供应商 / 产品标题 / 价格 / 起批 / 阶梯价 / 产品图 / 产品链接 / offerId

默认输出到 `./out/1688_<关键词或图名>_<时间戳>.xlsx`，用 `--out` 指定绝对路径。表头冻结、带筛选、链接可点。

## 实现要点（改代码前先看）

- `finder/cli1688.py`：调 CLI 并解析 JSON。CLI 会在 stdout 混进度行（`[1/2] collecting ...`），所以 `_parse_json` 走"整体 → 截 `[...]` → 截 `{...}`"三档回退。
- `scripts/imgsearch.cjs`：**CLI 自带 `1688 image-search` 已失效**（定位器 `.image-upload-button-container` 过期，且 `s.1688.com/youyuan/index.htm` 会被 `x5secdata` 惩罚页拦）。本技能改为打开 `s.1688.com/selloffer/offer_search.htm` → 直接 `setInputFiles` 到 `input[type=file]` → 等"已上传1张图片" → 点"搜索图片" → 抓卡片。headless 可用。
- `finder/keyword.py:enrich()`：`offer.supplier.memberId` 常为 null，所以 inspect 的入参优先 memberId，退化为首条 offerId（CLI 支持 `supplier inspect <offerId>` 并回填 memberId）。
- `finder/excel.py`：图片走 requests + Pillow 转 JPEG（长边 ≤300px），`add_image` 锚在 B/G 列。

## 坑

- **风控**：图搜一次约 30 条就停；连续跑同一张图、或短时间高频请求会落 `x5secdata` 惩罚页。出现 `RISK_CONTROL` 时用 `--headed` 手工浏览器过一次滑块，再复用登录态，别硬刷。
- **daemon 与 profile 锁**：`imgsearch.cjs` 会先 `1688 daemon stop` 释放 `~/.1688/profiles/default` 的锁；CLI 命令随后会自动重启 daemon。两条路径不要同时跑。
- **起批/阶梯价可能空**：部分 offer 页面本身不返回 `minOrderQty`，是数据缺失，不是解析 bug。
- **图搜只给店铺名，不给省份**：省份/城市/是否工厂要靠 `--enrich` 从工厂名片补，所以图搜默认信息比关键词路径薄。
- **图片下载失败**留空不报错；alicdn 偶发 403 时重跑一次即可。

## 合规

只抓登录后自己能看到的页面，控制频率，不做数据转售。批量抓取前确认用途符合 1688 用户协议。
