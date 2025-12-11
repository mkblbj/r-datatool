# 乐天 店舗カルテ 数据自动化项目方案说明

## 1. 项目目标

新建一个独立服务，专门完成三件事情：

1. **自动登录每个乐天店铺 RMS → 进入 店舗カルテ → 下载 CSV 文件**（例如主要指标、商品排行榜等）。  
2. **将 CSV 解析为 JSON**，并按店铺 / 日期做简单聚合，输出适合前端展示的 `summary.json` 等文件。  
3. **提供一个简单的 HTTP API**，供公司内部 Homepage（gethomepage.dev）调用，显示各店铺关键指标和排行榜。

> 本项目只负责「数据抓取 + 转换 + 提供 API」，所有 UI 展示交给 Homepage。

---

## 2. 推荐技术栈

- 语言：**Python 3.11+**
- 浏览器自动化：**Playwright (Python 版, Chromium)**  
- Web 框架 / API：**FastAPI**
- CSV 解析：
  - Python 标准库 `csv`
  - （可选）`pandas` 做更复杂统计
- 定时任务：
  - 开发阶段可以用 **APScheduler** 内嵌定时器
  - 生产环境推荐直接使用宿主机的 **cron** 定期执行抓取脚本
- 部署：**Docker**（方便挂载数据目录到宿主机 / 其他容器）
- 配置：`shops.yaml` + 环境变量（存放密码等敏感信息）

---

## 3. 项目整体架构

### 3.1 模块拆分

建议把项目拆成 4 个核心模块 + 1 个可选调度模块：

1. **config** – 配置加载
   - 负责读取 `config/shops.yaml`，以及从环境变量中读出密码等。
   - 对外提供「店铺列表」「每个店铺的登录信息和代码」等配置。

2. **fetcher（爬取模块）**
   - 使用 Playwright 完成：
     - 登录 RMS
     - 进入 店舗カルテ 内对应页面（主要指标 / 商品排行榜等）
     - 点击「CSV ダウンロード」，保存到本地
   - 输出目录：`data/csv/{shop_code}/{date}_{type}.csv`

3. **parser（解析与聚合模块）**
   - 负责读取 CSV，进行简单的数据清洗和统计：
     - 解析当日关键指标（売上、注文数、アクセス人数、転換率、客単価 等）
     - 最近 7 / 30 天趋势
     - 当日商品销售排行榜等
   - 输出目录：`data/json/{shop_code}/{type}.json`，例如：
     - `karte_summary.json`
     - `ranking_today.json`

4. **api（对外 HTTP API 模块）**
   - 使用 FastAPI 对外提供只读接口：
     - `GET /rakuten/shops` – 列出所有店铺与最新日期
     - `GET /rakuten/shops/{shop_code}/summary` – 返回该店铺的汇总指标 JSON
     - `GET /rakuten/shops/{shop_code}/ranking` – 返回该店铺当日排行榜 JSON

5. **jobs / scheduler（调度模块，可选）**
   - 提供一个「每天抓一次所有店铺数据」的任务入口：`daily_fetch.py`
   - 可选使用 APScheduler 嵌入到 API 服务中定时触发，或用系统 cron 定时执行。

---

### 3.2 目录结构示例

```bash
rakuten-karte-fetcher/
├─ app/
│  ├─ __init__.py
│  ├─ main.py              # FastAPI 入口
│  ├─ config.py            # 配置加载（shops.yaml + Bitwarden 凭据）
│  ├─ bitwarden_client.py  # Bitwarden API 客户端
│  ├─ models.py            # Pydantic 数据模型（可选）
│  ├─ fetcher/
│  │   ├─ __init__.py
│  │   ├─ login.py         # 登录 RMS 的逻辑
│  │   ├─ karte_main.py    # 店舗カルテ「主要指標」CSV 下载
│  │   ├─ karte_ranking.py # 店舗カルテ「当日売上ランキング」CSV 下载
│  │   └─ utils.py
│  ├─ parser/
│  │   ├─ __init__.py
│  │   ├─ main_metrics.py  # 主要指標 CSV → summary.json
│  │   ├─ ranking.py       # ランキング CSV → ranking_today.json
│  │   └─ utils.py
│  ├─ jobs/
│  │   ├─ daily_fetch.py   # 一次执行所有店铺的抓取 + 解析
│  │   └─ scheduler.py     # APScheduler（如果需要内嵌调度）
│  └─ api/
│      ├─ __init__.py
│      ├─ routers.py       # FastAPI 路由定义
│      └─ deps.py          # 依赖注入（可选）
│
├─ config/
│  ├─ shops.yaml           # 多店铺配置（指向 Bitwarden Item）
│  ├─ bitwarden.yaml       # Bitwarden self-hosted 配置
│  └─ logging.yaml         # 日志配置（可选）
│
├─ data/
│  ├─ csv/                 # 原始 CSV 数据
│  │   └─ {shop_code}/...
│  └─ json/                # 解析后的 JSON 数据
│      └─ {shop_code}/...
│
├─ docker-compose.yml      # 包含 Bitwarden CLI 服务
├─ Dockerfile
├─ requirements.txt
└─ README.md
```

---

## 4. 多店铺配置与安全（Bitwarden CLI 集成）

### 4.1 基本原理

本项目通过 Python 的 `subprocess` 模块直接调用 Bitwarden 官方命令行工具 (`bw`) 来获取店铺凭据。

- **优势**：无需在后台长驻 `bw serve` 进程，无需处理 API Token，直接利用官方 CLI 的能力。
- **前提**：运行环境（开发机或 Docker 容器）必须安装 `bw` CLI，并且处于「已登录」且「已解锁（Unlocked）」状态。

### 4.2 Bitwarden 配置文件 `config/bitwarden.yaml`

```yaml
bitwarden:
  # 在 Bitwarden/Vaultwarden 中自定义的字段名或备注关键字
  # 用于确认获取的是正确的 Item
  match_keyword: "rakuten" 
```

### 4.3 `shops.yaml` 示例

```yaml
shops:
  - code: main_shop              
    # 对应 Bitwarden 中 Item 的名称（Name）或 ID
    bitwarden_item: rakuten-main-shop  

  - code: outlet_shop
    bitwarden_item: rakuten-outlet-shop
```

### 4.4 Python 客户端实现 `app/bitwarden.py`

```python
import json
import subprocess
import shutil
from dataclasses import dataclass
from typing import Optional

@dataclass
class ShopCredential:
    username: str
    password: str

class BitwardenClient:
    def __init__(self):
        # 检查 bw 命令是否存在
        if not shutil.which("bw"):
            raise RuntimeError("未在系统中找到 'bw' 命令，请先安装 Bitwarden CLI。")

    def get_credential(self, item_name_or_id: str) -> ShopCredential:
        """
        通过 `bw get item` 命令获取账号密码。
        要求环境变量 BW_SESSION 已设置，或者已经通过 bw unlock 解锁。
        """
        try:
            # 调用 CLI: bw get item <name_or_id> --raw
            # --raw 返回纯 JSON，无额外 ASCII 装饰
            cmd = ["bw", "get", "item", item_name_or_id, "--raw"]
            
            # 运行命令
            result = subprocess.run(
                cmd, 
                capture_output=True, 
                text=True, 
                check=True
            )
            
            item_json = json.loads(result.stdout)
            
            # 解析 username / password
            login_info = item_json.get("login", {})
            username = login_info.get("username")
            password = login_info.get("password")
            
            if not username or not password:
                raise ValueError(f"Item '{item_name_or_id}' 中未找到完整的 login 信息。")
                
            return ShopCredential(username=username, password=password)
            
        except subprocess.CalledProcessError as e:
            error_msg = e.stderr.strip() if e.stderr else "Unknown error"
            raise RuntimeError(f"调用 Bitwarden CLI 失败: {error_msg}")
        except json.JSONDecodeError:
            raise RuntimeError(f"解析 Bitwarden CLI 返回数据失败: {result.stdout}")

_client = BitwardenClient()

def get_shop_credential(item_name: str) -> ShopCredential:
    return _client.get_credential(item_name)
```

### 4.5 `config.py` 集成

```python
# app/config.py
import yaml
from .bitwarden import get_shop_credential

class Config:
    def load(self):
        with open("config/shops.yaml") as f:
            data = yaml.safe_load(f)
            
        self.shops = []
        for s in data["shops"]:
            # 动态获取密码
            cred = get_shop_credential(s["bitwarden_item"])
            
            self.shops.append({
                "code": s["code"],
                "login_id": cred.username,
                "password": cred.password
            })
```

### 4.6 部署与环境变量

在生产环境（如 Docker）中，推荐使用 **API Key** 进行自动化登录。

1. **安装 Bitwarden CLI**：容器内必须有 `bw` 可执行文件。
2. **环境变量配置**：
   - `BW_CLIENTID`: Vaultwarden 提供的 `client_id` (格式: `user.xxx`)
   - `BW_CLIENTSECRET`: Vaultwarden 提供的 `client_secret`
   - `BW_PASSWORD`: 主密码（Master Password），**用于 `bw unlock` 解锁 Vault**（注意：仅 `bw login` 是不够的，读取密码仍需解锁）
3. **启动流程**：
   - `bw config server <url>`
   - `bw login --apikey` (自动使用环境变量中的 ID 和 Secret)
   - `export BW_SESSION=$(bw unlock --passwordenv BW_PASSWORD --raw)`
   - 启动应用

> **关于 API Key**： Vaultwarden 界面中的 "OAuth 2.0 客户端凭据" 即为这里的 Client ID / Secret。使用它们可以免去交互式输入邮箱和密码的步骤，非常适合 CI/CD 和服务器部署。

---

## 5. 数据目录与文件约定

### 5.1 原始 CSV 文件

路径规则：

```text
data/csv/{shop_code}/{date}_{type}.csv
```

- `{shop_code}`：店铺代号，例如 `main_shop`
- `{date}`：抓取目标日期，例如 `2025-12-10`
- `{type}`：数据类型，例如：
  - `main`     → 店舗カルテ「主要指標」
  - `ranking`  → 店舗カルテ「当日売上ランキング」
  - `traffic`  → 店舗カルテ「流入分析」（如果需要的话）

示例：

```text
data/csv/main_shop/2025-12-10_main.csv
data/csv/main_shop/2025-12-10_ranking.csv
```

### 5.2 聚合后的 JSON 文件

路径规则：

```text
data/json/{shop_code}/{type}.json
```

- `karte_summary.json`：主要指标汇总（KPI + 最近趋势）
- `ranking_today.json`：当日商品排行榜

示例：

```text
data/json/main_shop/karte_summary.json
data/json/main_shop/ranking_today.json
```

API 层只需按约定路径读取 JSON 文件，无需额外数据库即可使用。

---

## 6. 抓取与解析流程

### 6.1 一次完整的「当天抓取」流程

以「抓取某天的数据」为例，流程如下：

1. `jobs/daily_fetch.py` 作为入口：
   - 读取 `shops.yaml` 中配置的所有店铺。
   - 对每个 shop 依次执行：
     - `fetcher.karte_main.download_csv(shop, target_date)`  
       下载「主要指標」CSV。
     - `parser.main_metrics.build_summary(shop, target_date)`  
       解析 CSV，生成 `karte_summary.json`。
     - `fetcher.karte_ranking.download_csv(shop, target_date)`  
       下载「当日売上ランキング」CSV。
     - `parser.ranking.build_ranking(shop, target_date)`  
       解析 CSV，生成 `ranking_today.json`。

2. 整个过程最好加日志（log），便于排查问题：
   - 成功下载哪个店铺的哪个 CSV。
   - CSV 解析是否成功、生成了哪些 JSON 文件。

### 6.2 fetcher 模块（Playwright）关键点

- 抽象 `login_to_rms(page, shop_config)`：
   - 打开 `https://glogin.rms.rakuten.co.jp/`
   - 输入 `login_id` 和 `password`
   - 提交并等待跳转到 RMS 主菜单页面。
- 抽象 `goto_karte_main(page)`：
   - 在已经登录的情况下，跳转到 店舗カルテ 主要指标页面。
   - 可以直接使用固定 URL 或通过菜单点击进入（根据实际情况选择）。
- 在 `download_csv` 内：
   - 根据 DOM 选择器点击「主要指標」「日別」「日期范围」等控件。
   - 使用 `page.wait_for_event("download")` 捕捉下载对象。
   - 将下载的文件保存到 `data/csv/{shop_code}/...`。

> 注意：首次开发时需要在浏览器里通过 F12 / DevTools 查看按钮的 text / data-testid / CSS 选择器，并写死在脚本中。页面如果改版，再调整一次。

### 6.3 parser 模块关键点

以「主要指標 CSV」为例：

- 典型字段：`日付`, `売上`, `売上件数`, `アクセス人数`, `PV数`, `転換率`, `客単価` 等。  
- 解析要点：
   - 编码一般为 `cp932 / Shift-JIS`，读文件时需要指定。
   - 需要把带逗号的数字字符串（例如 `"3,270,998"`）转成整数。
   - `転換率` 一般是带 `%` 的字符串，需要转换为浮点数（0~1）。

输出 `karte_summary.json` 结构建议：

```json
{
  "shop": "main_shop",
  "date": "2025-12-10",
  "kpi": {
    "sales": 3270998,
    "orders": 2456,
    "visitors": 114923,
    "conversion": 0.0214,
    "aov": 1332
  },
  "trend": [
    { "date": "2025-12-04", "sales": 1782111, "visitors": 90000, "conversion": 0.018, "aov": 1260 },
    ...
  ]
}
```

「当日売上ランキング CSV」解析：

- 字段大致包括：`順位`, `商品名`, `売上`, `売上個数`, `商品URL`, `画像URL` 等（以实际为准）。
- 输出 `ranking_today.json` 结构示例：

```json
{
  "shop": "main_shop",
  "date": "2025-12-10",
  "items": [
    {
      "rank": 1,
      "name": "Switch 2 Sports ...",
      "sales": 11000,
      "quantity": 7,
      "imageUrl": "https://...",
      "itemUrl": "https://..."
    },
    ...
  ]
}
```

Homepage 显示排行榜时，只需要读取其中的 `items` 数组即可。

---

## 7. API 设计

使用 FastAPI 提供 REST 风格 API。

### 7.1 路由设计

```http
GET /rakuten/shops
GET /rakuten/shops/{shop_code}/summary
GET /rakuten/shops/{shop_code}/ranking
```

示例实现（简化版）：

```python
# app/api/routers.py
from fastapi import APIRouter, HTTPException
from pathlib import Path
import json

router = APIRouter()
DATA_DIR = Path("data/json")

@router.get("/shops")
def list_shops():
    shops = []
    for shop_dir in DATA_DIR.iterdir():
        if not shop_dir.is_dir():
            continue
        summary_path = shop_dir / "karte_summary.json"
        if summary_path.exists():
            data = json.loads(summary_path.read_text(encoding="utf-8"))
            shops.append({"shop": data["shop"], "latest_date": data["date"]})
    return shops

@router.get("/shops/{shop_code}/summary")
def get_summary(shop_code: str):
    path = DATA_DIR / shop_code / "karte_summary.json"
    if not path.exists():
        raise HTTPException(404, "summary not found")
    return json.loads(path.read_text(encoding="utf-8"))

@router.get("/shops/{shop_code}/ranking")
def get_ranking(shop_code: str):
    path = DATA_DIR / shop_code / "ranking_today.json"
    if not path.exists():
        raise HTTPException(404, "ranking not found")
    return json.loads(path.read_text(encoding="utf-8"))
```

`main.py`：

```python
from fastapi import FastAPI
from .api.routers import router as api_router

app = FastAPI()
app.include_router(api_router, prefix="/rakuten")
```

### 7.2 与 Homepage 对接

在 gethomepage.dev 的配置中，使用 Custom API widget 示例：

```yaml
- Rakuten Main:
    icon: mdi-store
    href: https://rms.rakuten.co.jp/
    description: 乐天主店
    widget:
      type: customapi
      url: http://your-api-server:8000/rakuten/shops/main_shop/summary
      refreshInterval: 600000   # 每 10 分钟刷新一次
```

后续可以根据 `kpi` 和 `trend` 字段，做卡片显示和小型趋势图。

---

## 8. 定时任务

### 8.1 使用 cron（推荐）

- API 服务容器只负责读 JSON，保持稳定。
- 抓取任务由宿主机 cron 或一个单独的任务容器定时执行。

示例 cron 配置：

```cron
# 每天凌晨 3 点执行一次抓取任务
0 3 * * * /usr/bin/docker exec rakuten-karte python -m app.jobs.daily_fetch
```

### 8.2 使用 APScheduler（可选）

如果希望「只跑一个容器」，也可以在 FastAPI 中内嵌调度。

```python
# app/jobs/scheduler.py
from apscheduler.schedulers.background import BackgroundScheduler
from .daily_fetch import run_all_shops

scheduler = BackgroundScheduler()

def start():
    scheduler.add_job(run_all_shops, "cron", hour=3, minute=0)
    scheduler.start()
```

在 `main.py` 中：

```python
from fastapi import FastAPI
from .api.routers import router as api_router
from .jobs.scheduler import start as start_scheduler

app = FastAPI()
app.include_router(api_router, prefix="/rakuten")
start_scheduler()
```

> 两种方式选一种即可，建议先用 cron，简单清晰。

---

## 9. Docker 化与部署

### 9.1 Dockerfile 示例

需要在 Python 镜像基础之上安装 Bitwarden CLI。

```dockerfile
FROM python:3.11-slim

WORKDIR /app

# 安装基础工具
RUN apt-get update && apt-get install -y \
    wget \
    unzip \
    && rm -rf /var/lib/apt/lists/*

# 安装 Bitwarden CLI
RUN wget "https://vault.bitwarden.com/download/?app=cli&platform=linux" -O bw.zip \
    && unzip bw.zip \
    && chmod +x bw \
    && mv bw /usr/local/bin/ \
    && rm bw.zip

# 安装 Playwright 和依赖
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
    && playwright install --with-deps chromium

COPY . .

VOLUME ["/app/data"]

# 默认命令
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### 9.2 启动脚本示例 (run.sh)

```bash
#!/bin/bash
# 宿主机先解锁 Bitwarden
# 确保已安装 bw 并且已执行 bw login

# 获取 Session Key
export BW_SESSION=$(bw unlock --raw)

if [ -z "$BW_SESSION" ]; then
    echo "Bitwarden unlock failed!"
    exit 1
fi

# 启动容器，传入 BW_SESSION
docker run -d \
  --name rakuten-fetcher \
  -e BW_SESSION=$BW_SESSION \
  -v $(pwd)/data:/app/data \
  -v $(pwd)/config:/app/config \
  -p 8000:8000 \
  rakuten-karte-fetcher
```

需要在 Python 镜像基础之上安装 Bitwarden CLI。

```dockerfile
FROM python:3.11-slim

WORKDIR /app

# 安装基础工具
RUN apt-get update && apt-get install -y \
    wget \
    unzip \
    && rm -rf /var/lib/apt/lists/*

# 安装 Bitwarden CLI
RUN wget "https://vault.bitwarden.com/download/?app=cli&platform=linux" -O bw.zip \
    && unzip bw.zip \
    && chmod +x bw \
    && mv bw /usr/local/bin/ \
    && rm bw.zip

# 安装 Playwright 和依赖
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
    && playwright install --with-deps chromium

COPY . .

VOLUME ["/app/data"]

# 默认命令
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### 9.2 启动脚本示例 (start.sh)

此脚本用于在容器启动时自动登录并解锁 Vault。

```bash
#!/bin/bash
set -e

# 1. 配置服务器
# 如果环境变量未设置，使用默认值
export VAULTWARDEN_URL=${VAULTWARDEN_URL:-"https://vaultwarden.your-domain.com"}
bw config server $VAULTWARDEN_URL

# 2. 登录 (使用 API Key)
# 需设置环境变量: BW_CLIENTID, BW_CLIENTSECRET
if [ -n "$BW_CLIENTID" ] && [ -n "$BW_CLIENTSECRET" ]; then
    echo "Logging in with API Key..."
    bw login --apikey
fi

# 3. 解锁 (使用 Master Password)
# 需设置环境变量: BW_PASSWORD
if [ -n "$BW_PASSWORD" ]; then
    echo "Unlocking Vault..."
    export BW_SESSION=$(bw unlock --passwordenv BW_PASSWORD --raw)
else
    echo "Error: BW_PASSWORD not set. Cannot unlock vault."
    exit 1
fi

# 4. 启动应用
exec uvicorn app.main:app --host 0.0.0.0 --port 8000
```

对应的 `docker run` 命令：

```bash
docker run -d \
  --name rakuten-fetcher \
  -e BW_CLIENTID="user.xxxxx" \
  -e BW_CLIENTSECRET="yyyyy" \
  -e BW_PASSWORD="your-master-password" \
  -e VAULTWARDEN_URL="https://vaultwarden.your-domain.com" \
  -v $(pwd)/data:/app/data \
  -v $(pwd)/config:/app/config \
  -p 8000:8000 \
  rakuten-karte-fetcher
```

---

## 10. 建议的实际开发步骤

1. **初始化项目与环境**
   - 新建仓库，按上面的结构创建基本目录。
   - 写 `requirements.txt`：`fastapi`, `uvicorn`, `playwright`, `pyyaml`, `requests`, `apscheduler`（可选）等。
   - 跑通最简单的 FastAPI `GET /health`。

2. **配置 Bitwarden CLI**
   - 确保宿主机和 Docker 镜像中安装了 `bw` CLI。
   - **方式 A (API Key)**：获取 OAuth Client 凭据和 Master Password，配置环境变量 `BW_CLIENTID` / `BW_CLIENTSECRET` / `BW_PASSWORD`。
   - **方式 B (Session)**：在宿主机手动解锁，将 `BW_SESSION` 注入容器（更简单，但重启需重新解锁）。
   - 编写 `app/bitwarden.py` 封装 `subprocess` 调用逻辑。
   - 测试脚本：`python -m app.bitwarden`，确认能打印出密码。

3. **实现「登录 + 下载单店单 CSV」**
   - 写一个独立脚本，使用 `BitwardenClient` 获取凭据：
     - 登录 RMS
     - 进入 店舗カルテ
     - 下载「主要指標」CSV 到本地。
   - 调试好 DOM 选择器与下载逻辑。

4. **抽象 fetcher 模块 + 支持多店铺**
   - 引入 `shops.yaml` 和 `config.py`。
   - 写 `jobs/daily_fetch.py`，遍历所有店铺依次下载 CSV。

5. **实现 parser 模块**
   - 先只解析「主要指標」，生成 `karte_summary.json`。
   - 再解析「当日売上ランキング」，生成 `ranking_today.json`。

6. **完善 API**
   - 实现 `/rakuten/shops`、`/rakuten/shops/{shop}/summary`、`/rakuten/shops/{shop}/ranking`。
   - 用 curl 或浏览器访问确认 JSON 结构正确。

7. **接入定时任务**
   - 在开发机上先用手工执行 `python -m app.jobs.daily_fetch` 看结果。
   - 稳定后接入 cron，观察几天数据是否都能正常更新。

8. **Docker 化部署**
   - 编写 Dockerfile（包含安装 `bw`）。
   - 编写 `run.sh` 启动脚本，处理 Session 注入。
   - 部署并验证。

9. **与 Homepage 对接**
   - 在 Homepage 中增加 custom API widget。
   - 优化 JSON 结构，让展示更方便（字段名 / 单位等）。

10. **后续优化（可选）**
    - 统一日志格式，错误发送通知（邮件 / Slack）。
    - 增加自动重新解锁机制（如果 BW_SESSION 过期，尝试使用 API Key 重新登录解锁）。

---

以上就是整个 csv → json 自动化项目的架构与开发流程整理版，可以直接作为新项目的 README 使用。```

