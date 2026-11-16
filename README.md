# 1688-sourcing

**一句话或一张产品照片 → 1688 上的工厂 → 带图片的 Excel。** 一个可被任何 agent 客户端安装的技能（DSH / WorkBuddy / 自建 agent）。

![status](https://img.shields.io/badge/status-working-brightgreen)

## 它解决什么问题

在 1688 找供应商，手工路径是：搜关键词 → 翻一屏商品 → 逐个点进店铺看是不是工厂 → 复制主图 → 粘贴到 Excel。图搜更麻烦：上传图、认结果、再回到店铺维度。

本技能把这条路径压成一个命令，并把"商品 → 店铺 → 工厂名片"三级串联起来：

```text
关键词  ┐
        ├─→ 1688-cli（真实 Chrome 登录态）─→ 供应商/工厂 + 商品 ─→ 下载主图 ─→ xlsx（图已嵌入）
产品图  ┘
```

- **关键词路径**：`supplier search` 直接给公司级结果（含回头率、响应率、入驻年限、是否工厂）。
- **照片路径**：CLI 自带的 `image-search` 已失效，本仓库用自研的 `scripts/imgsearch.cjs` 驱动现行"以图搜款"组件，再把商品按店铺聚合成供应商。
- **补细节**：`supplier inspect` 可按 memberId **或 offerId** 拉工厂名片（地址、员工规模、是否验厂），这正是图搜结果补"省份/类型"的入口。

## 快速开始

```powershell
git clone https://github.com/G2E-Michael/1688-sourcing.git
cd 1688-sourcing

npm i -g 1688-cli                    # 执行层
python -m pip install -r requirements.txt
& "$env:APPDATA\npm\1688.cmd" login --headed   # 扫码一次，登录态持久化

pwsh -File .\install.ps1 -Target both          # PowerShell 7
powershell -File .\install.ps1 -Target both    # Windows PowerShell 5.1
python run.py check                            # 自检
python run.py keyword "硅胶折叠水杯" --max 12 --top 6 --enrich 3
python run.py image "C:\path\to\cup.jpg" --max 30 --top 8 --enrich 3
```

macOS / Linux：`npx 1688 login --headed`，其余相同，安装用 `bash install.sh`。

## 安装到各客户端

技能不需要编译，就是"一个目录"：`SKILL.md` 负责描述，`run.py` 负责执行。

| 客户端 | 安装位置 | 触发方式 |
| --- | --- | --- |
| DeepSeek Harness (DSH) | `~/.dsh/skills/1688-supplier-finder/` | 刷新页面/重开会话后进技能目录 |
| WorkBuddy | `~/.workbuddy/skills/1688-supplier-finder/` | 重启或刷新技能列表（`.skill-list-cache.json` 会重建） |
| 其他 agent | 任意目录 | 直接把 `SKILL.md` 喂给模型，或让它调 `run.py` |

`install.ps1` / `install.sh` 会完成三件事：拷目录（排除 `.git`、`out/`、`__pycache__`）、检查 node/python/Chrome/1688-cli、打印还差哪一步。

```powershell
powershell -File .\install.ps1 -Target dsh         # 只装 DSH
powershell -File .\install.ps1 -Target workbuddy   # 只装 WorkBuddy
powershell -File .\install.ps1 -Target both -Force # 覆盖已有安装
```

## 输出结构

一个 xlsx，两张表，图片以 JPEG 300px 长边嵌入单元格：

**表 1 供应商（18 列）**：序号 / 主图 / 供应商名称 / 省份 / 城市 / 入驻年限 / 回头率% / 响应率% / 类型 / 工厂标签 / 综合评分 / 主营产品 / 主推产品 / 价格 / 起批 / 产品链接 / 店铺链接 / 工厂名片

**表 2 产品明细（9 列）**：序号 / 供应商 / 产品标题 / 价格 / 起批 / 阶梯价 / 产品图 / 产品链接 / offerId

## 参数

| 参数 | 说明 |
| --- | --- |
| `--max` | 关键词：每个词的供应商数（默认 20）；图搜：抓取商品数（默认 40） |
| `--top` | 最终保留行数 |
| `--offers N` | 前 N 条商品查详情，补起批量/阶梯价（默认 12） |
| `--enrich N` | 前 N 家查工厂名片，补员工规模/详细地址/验厂（默认 0，每行 3–5 秒） |
| `--province/--city/--min-years/--min-repeat-rate` | 供应商侧筛选，直接下推给 1688 |
| `--include-traders` | 连贸易商一起要（默认只看工厂） |
| `--no-images` / `--no-offer-detail` | 跳图 / 跳详情，换速度 |

## 诚实的能力边界

| 限制 | 原因 | 影响 |
| --- | --- | --- |
| 图搜单次约 30 条，不做翻页 | 翻页显著抬高 `x5secdata` 风控概率 | 冷门品类可能召回不足，需要换更干净的产品图 |
| 高频请求会落惩罚页 | 1688 账号/设备/行为风控 | 出现 `RISK_CONTROL` 须 `--headed` 人工过滑块一次 |
| 图搜默认没有省份/类型 | 图搜卡片只给店铺名 | 需 `--enrich` 才会补 |
| 部分行起批为空 | offer 页面本身不返回 `minOrderQty` | 数据缺失，非解析 bug |
| 必须登录 | 只抓登录后可见页面 | `NOT_LOGGED_IN` 时扫码即可，无需重装 |

## 合规

本工具只访问**你自己账号登录后可见**的页面，不绕过验证码、不调用未授权接口、不做数据转售。请自行确认批量抓取用途符合 1688 用户协议与当地法律。风控是平台的权利，出现滑块就停手，不要用指纹伪装或代理池硬闯。

## 目录

```text
1688-sourcing/
├─ SKILL.md              # 技能描述（客户端读这个）
├─ run.py                # 入口：check / keyword / image
├─ finder/
│  ├─ cli1688.py         # 定位并驱动全局 1688-cli
│  ├─ keyword.py         # 公司搜索 → 行规范化 → 工厂名片补全
│  ├─ image.py           # 图搜结果 → 按店铺聚合
│  ├─ offers.py          # 批量 offer 详情 → 起批量/阶梯价
│  └─ excel.py           # 两表 xlsx + 图片下载与嵌入
├─ scripts/imgsearch.cjs # 自研图搜驱动（Playwright，headless 可用）
├─ install.ps1 / install.sh
└─ requirements.txt
```

## License

MIT © Michael Yang
