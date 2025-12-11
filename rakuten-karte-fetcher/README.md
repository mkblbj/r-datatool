# Rakuten Karte Fetcher

乐天店舗カルテ数据自动化抓取与API服务。

## 功能

1. **自动登录** - 使用 Playwright 自动登录乐天 RMS
2. **CSV 下载** - 从店舗カルテ下载主要指标和排行榜 CSV
3. **数据解析** - 将 CSV 解析为 JSON 格式
4. **REST API** - 提供数据查询接口

## 快速开始

### 1. 安装依赖

```bash
# 创建虚拟环境
python -m venv .venv
source .venv/bin/activate

# 安装 Python 依赖
pip install -r requirements.txt

# 安装 Playwright 浏览器
playwright install chromium
```

### 2. 配置

编辑 `config/shops.yaml` 配置店铺信息。

### 3. 启动服务

```bash
uvicorn app.main:app --reload
```

### 4. 访问 API

- 健康检查: http://localhost:8000/health
- API 文档: http://localhost:8000/docs

## 项目结构

```
rakuten-karte-fetcher/
├── app/
│   ├── main.py          # FastAPI 入口
│   ├── bitwarden.py     # Bitwarden CLI 集成
│   ├── config.py        # 配置加载
│   ├── api/             # API 路由
│   ├── fetcher/         # RMS 数据抓取
│   ├── parser/          # CSV 解析
│   └── jobs/            # 定时任务
├── config/
│   ├── shops.yaml       # 店铺配置
│   └── bitwarden.yaml   # Bitwarden 配置
├── data/
│   ├── csv/             # 原始 CSV 文件
│   └── json/            # 解析后的 JSON
├── requirements.txt
└── Dockerfile
```

## 环境变量

| 变量名 | 说明 | 必须 |
|--------|------|------|
| `BW_SESSION` | Bitwarden Session Key | ✓ |
| `BW_CLIENTID` | Bitwarden API Client ID | 可选 |
| `BW_CLIENTSECRET` | Bitwarden API Client Secret | 可选 |
| `BW_PASSWORD` | Bitwarden Master Password | 可选 |

## 文档

详细文档请参考 `docs/` 目录：
- [项目方案说明](../docs/rakuten_karte_project_plan.md)
- [实施阶段清单](../docs/implementation_checklist.md)
