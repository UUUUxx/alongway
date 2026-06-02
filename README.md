# 顺路购 · Along-way

> AI 驱动的顺路团购推荐系统 — 美团黑客松 Demo

输入你的行程（起点 → 终点 + 顺路需求），AI 自动扫描沿途好店、匹配团购优惠，生成最优顺路方案。

---

## 架构总览

```
┌──────────────────────────────────────────────────────────────────┐
│                        Frontend (React)                          │
│              alongway-frontend/alongway-demo/index.html          │
│                 用户输入 → 展示路线 + 团购卡片                      │
└────────────────────────────┬─────────────────────────────────────┘
                             │ POST /api/plan
                             ▼
┌──────────────────────────────────────────────────────────────────┐
│                      Backend (FastAPI :8000)                     │
│                     alongway_backend/app/                        │
│        请求校验 → 代理转发 → 历史缓存 → 日志记录                     │
│        提供 internal tools: POI搜索 / 团购搜索 / 路线计算           │
│        高德API集成：地理编码 / 周边POI / 真路网路线                   │
└────────────────────────────┬─────────────────────────────────────┘
                             │ POST /agent/plan
                             ▼
┌──────────────────────────────────────────────────────────────────┐
│                       Agent (FastAPI :8001)                      │
│                     alongway_agent/agent/                        │
│    意图解析 → 候选生成 → 路线组合 → 约束过滤 → 评分排序 → 推荐理由    │
│         LLM 优先解析 + 规则兜底 / 确定性评分 / Mock 全链路           │
└──────────────────────────────────────────────────────────────────┘
```

---

## 项目结构

```
shunlu/
├── alongway-frontend/alongway-demo/   # 前端 SPA
│   └── index.html                     # React + Tailwind 单文件应用
│
├── alongway_backend/                  # FastAPI 后端 (:8000)
│   ├── app/
│   │   ├── main.py                    # FastAPI 入口 + CORS + 路由注册
│   │   ├── config.py                  # 环境变量配置管理
│   │   ├── database.py                # SQLAlchemy engine/session
│   │   ├── models.py                  # ORM 模型 (POI + Deal)
│   │   ├── schemas.py                 # Pydantic 请求/响应模型
│   │   ├── seed.py                    # 种子数据 (18 POI + 26 Deal)
│   │   ├── routers/
│   │   │   ├── plan.py                # POST /api/plan — 主入口代理
│   │   │   ├── health.py              # GET /health — 健康检查
│   │   │   ├── geocode.py             # POST /api/geocode — 地址→坐标
│   │   │   ├── internal_route.py      # POST /internal/route/calculate
│   │   │   ├── internal_pois.py       # POST /internal/pois/search
│   │   │   ├── internal_deals.py      # POST /internal/deals/search
│   │   │   ├── poi_admin.py           # POI CRUD 管理
│   │   │   ├── deal_admin.py          # Deal CRUD 管理
│   │   │   └── admin.py               # POST /api/admin/seed
│   │   └── services/
│   │       ├── route_service.py       # 高德真路网路线计算
│   │       ├── amap_route_service.py  # Amap 路由服务兼容层
│   │       ├── distance.py            # Haversine 直线距离估算
│   │       ├── poi_service.py         # POI 搜索 (缓存+高德补拉)
│   │       ├── deal_service.py        # Deal 搜索 (过滤+排序)
│   │       ├── agent_client.py        # Agent 服务 HTTP 客户端
│   │       └── call_logger.py         # 调用日志记录
│   ├── tests/                         # 27 个单元测试
│   ├── docs/                          # 技术文档
│   ├── verify_mvp.py                  # 手动验证脚本
│   ├── run_server.bat                 # Windows 启动脚本
│   └── run_server.sh                  # Linux/Mac 启动脚本
│
├── alongway_agent/                    # Agent 编排层 (:8001)
│   ├── agent/
│   │   ├── models.py                  # 数据模型 (Pydantic)
│   │   ├── config.py                  # 配置管理
│   │   ├── exceptions.py              # 错误码定义
│   │   ├── backend_client.py          # 后端工具 HTTP/Mock 客户端
│   │   ├── llm_client.py              # LLM 客户端 (Mock/真实)
│   │   ├── prompts.py                 # LLM Prompt 模板
│   │   ├── intent_parser.py           # 意图解析 (LLM+规则)
│   │   ├── candidate_generator.py     # 候选 POI + Deal 生成
│   │   ├── filters.py                 # 候选过滤 (预算/时间)
│   │   ├── route_evaluator.py         # 路线组合与评估
│   │   ├── scorer.py                  # 确定性多维评分
│   │   ├── explainer.py               # 推荐理由生成
│   │   └── planner_agent.py           # 主编排流程 PlanAgent
│   ├── app/
│   │   └── main.py                    # FastAPI 服务入口
│   └── tests/                         # Agent 单元测试
│
└── README.md                          # 本文件
```

---

## 各模块功能详解

### 🖥️ 前端 (Frontend)

单文件 React + Tailwind CSS 应用，美团风格 UI 设计：

| 功能 | 说明 |
|------|------|
| **自然语言输入** | 支持 `从A到B，顺路找C` 句式，自动识别地名和需求 |
| **偏好设置** | 5 种偏好：低价优先 / 高分优先 / 销量优先 / 尽快到达 / 少绕路 |
| **示例引导** | 预设热搜卡片，一键填入查询 |
| **路线示意图** | SVG 地图展示起点→途经点→终点，带路线动画和粒子效果 |
| **路线小票** | 距离/耗时/团购花费三大指标卡片 |
| **途经推荐** | POI 卡片 + 可展开团购券列表（美团票券风格） |
| **路线详情** | 时间线样式展示每段路程的导航指令 |
| **省钱看板** | 深色主题展示本次预计节省金额 |
| **分享路线** | 支持 Web Share API 和剪贴板复制 |
| **Toast 通知** | 操作反馈提示 |
| **粒子背景** | 动态粒子场（降低动画偏好时自动关闭） |
| **响应式** | 适配手机和桌面端 |

### ⚙️ 后端 (Backend)

FastAPI 后端，负责数据管理、高德 API 集成和 Agent 代理：

| 功能 | 说明 |
|------|------|
| **Plan 代理** | 接收前端请求 → 转发 Agent → 适配响应 → 返回前端 |
| **历史缓存** | 最近 10 条规划记录，前端可召回 |
| **请求日志** | DEBUG 模式完整日志；生产模式仅记录 request_id |
| **POI 搜索** | 本地 DB 优先 → 结果不足时调用高德周边搜索 → 清洗入库 |
| **Deal 搜索** | 按类别/预算/销量排序；餐饮/娱乐 POI 自动生成 Mock 团购 |
| **路线计算** | 高德真路网 API（步行/骑行/驾车）→ Haversine 兜底 |
| **地理编码** | 地址→坐标代理，保护 AMAP_KEY 不暴露前端 |
| **高德 POI 清洗** | 保留餐饮/娱乐/生活服务；过滤停车场/公司/住宅等 |
| **Mock 团购** | 确定性模板生成（非随机），同一 POI 每次结果一致 |
| **双城数据** | 武汉(华科) 12 POI + 上海(复旦/五角场) 6 POI |
| **CRUD 管理** | POI 和 Deal 的完整 CRUD API |
| **Seed 初始化** | 一键初始化数据库种子数据 |

### 🧠 Agent (编排层)

核心智能编排引擎，11 步完成从自然语言到推荐方案的完整流程：

| 步骤 | 模块 | 功能 |
|------|------|------|
| **Step 0** | 输入校验 | 检查 query/起终点/坐标完整性 |
| **Step 1** | IntentParser | LLM 优先解析意图 → 规则兜底；识别任务类型、预算、偏好 |
| **Step 2** | 搜索中心 | 起终点中点作为 POI 搜索中心 |
| **Step 3** | 基础路线 | 计算起点→终点直线距离和耗时 |
| **Step 4** | CandidateGenerator | 按任务关键词并发查询 POI |
| **Step 5** | 团购匹配 | 对餐饮/饮品任务查询 Deal；取快递/到访不查 |
| **Step 6** | Filters | 预算过滤 + 营业时间检查 + 团购可用性 |
| **Step 7** | RouteEvaluator | 任务顺序组合起点→候选→候选→终点 |
| **Step 8** | 路线计算 | 并发计算所有候选路线距离/耗时/绕路 |
| **Step 9** | Scorer | 6 维确定性评分：绕路(35%)+时间(20%)+价格(20%)+评分(10%)+销量(10%)+营业(5%) |
| **Step 10** | Explainer | LLM/模板生成推荐理由和备选方案对比 |
| **Step 11** | 返回结果 | 结构化 PlanResponse，含 selected_plan + alternatives |

**支持的任务类型：**

| 类型 | 触发词 | 搜索词 | 团购 |
|------|--------|--------|------|
| `pickup_express` | 快递/驿站/菜鸟 | 快递,菜鸟驿站,快递柜 | ❌ |
| `buy_drink` | 奶茶/咖啡/饮品 | 奶茶,饮品,咖啡 | ✅ |
| `eat_meal` | 吃饭/午饭/食堂 | 食堂,小吃,快餐,餐厅 | ✅ |
| `visit_place` | 公园/操场/图书馆 | 地点名 | ❌ |

**评分维度权重**（可根据偏好动态调整）：

```
默认权重:
  detour (绕路)    35%
  time   (时间)    20%
  price  (价格)    20%
  rating (评分)    10%
  sales  (销量)    10%
  open   (营业)     5%

偏好调整:
  prefer_less_detour  → 提高 detour 权重
  prefer_low_price    → 提高 price 权重
  prefer_high_rating  → 提高 rating 权重
  prefer_high_sales   → 提高 sales 权重
  prefer_fast_arrival → 提高 time 权重
```

---

## 数据流

```
用户输入 "从宿舍去图书馆，取快递+买20元以内的奶茶"
       │
       ▼
┌─ Frontend ──────────────────────────────────────────┐
│  submitPlan({ userQuery, preferences })             │
│  → 解析地名 → 构造 LocationInput                    │
│  → POST /api/plan                                  │
└────────────────────┬────────────────────────────────┘
                     │
                     ▼
┌─ Backend (:8000) ───────────────────────────────────┐
│  plan.py: 校验 + 生成 request_id + 日志              │
│  agent_client.py: 转发 POST /agent/plan             │
└────────────────────┬────────────────────────────────┘
                     │
                     ▼
┌─ Agent (:8001) ────────────────────────────────────┐
│  PlanAgent.plan()                                  │
│    → IntentParser: "取快递"→pickup_express,        │
│                    "买20元奶茶"→buy_drink(budget=20) │
│    → 并发: 基础路线 + POI候选搜索                    │
│    → BackendClient.search_pois(["快递","菜鸟"...])  │
│    → BackendClient.search_pois(["奶茶","饮品"...])  │
│    → BackendClient.search_deals(poi_id, max=20)    │
│    → RouteEvaluator: 组合 2×2=4 条候选路线          │
│    → BackendClient.calculate_route(每条路线)        │
│    → Scorer: 评分排序 → 选出最优方案                │
│    → Explainer: 生成推荐理由                        │
│    → 返回 PlanResponse                             │
└────────────────────┬────────────────────────────────┘
                     │
                     ▼
┌─ Backend ───────────────────────────────────────────┐
│  plan.py: 适配 Agent 响应 → 前端 PlanResponse       │
│  缓存历史记录                                       │
└────────────────────┬────────────────────────────────┘
                     │
                     ▼
┌─ Frontend ──────────────────────────────────────────┐
│  展示: 路线示意图 + 距离/时间/费用摘要               │
│       + 途经POI卡片 + 可展开团购券                   │
│       + 路线详情时间线 + 省钱看板                     │
└─────────────────────────────────────────────────────┘
```

---

## API 端点总览

### 前端可见

| 方法 | 路径 | 用途 |
|------|------|------|
| GET | `/health` | 健康检查 |
| POST | `/api/plan` | **主入口**: 路线+团购规划 |
| GET | `/api/plan/history` | 历史记录缓存 |
| POST | `/api/geocode` | 地址→坐标代理 |

### Agent 调用的 Internal Tools

| 方法 | 路径 | 用途 |
|------|------|------|
| POST | `/internal/pois/search` | POI 搜索 (缓存+高德补拉) |
| POST | `/internal/deals/search` | Deal 搜索 (过滤+排序) |
| POST | `/internal/route/calculate` | 路线计算 (真路网/Haversine) |

### 管理接口

| 方法 | 路径 | 用途 |
|------|------|------|
| GET/POST | `/api/pois` | POI 列表/创建 |
| GET/PUT/DELETE | `/api/pois/{id}` | POI 查/改/删 |
| GET/POST | `/api/deals` | Deal 列表/创建 |
| GET/PUT/DELETE | `/api/deals/{id}` | Deal 查/改/删 |
| POST | `/api/admin/seed` | 初始化数据库 |

---

## 快速启动

需要三个终端窗口：

### 1. 启动 Backend (端口 8000)

```bash
cd alongway_backend
pip install -r requirements.txt
python -m app.seed              # 首次运行：初始化数据库
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

验证:
- http://127.0.0.1:8000/health → `{"status": "ok"}`
- http://127.0.0.1:8000/docs → Swagger UI

### 2. 启动 Agent (端口 8001)

```bash
cd alongway_agent
pip install -r requirements.txt
uvicorn app.main:app --host 127.0.0.1 --port 8001 --reload
```

验证:
- POST http://127.0.0.1:8001/agent/plan

### 3. 启动 Frontend (端口 5173)

```bash
cd alongway-frontend/alongway-demo
python -m http.server 5173
```

访问: http://127.0.0.1:5173

---

## 环境变量

在 `alongway_backend/.env` 中配置：

```env
# 高德 Web Service API Key（可选，不填则使用 Haversine 近似路线）
AMAP_KEY=your_amap_api_key

# 数据库（默认 SQLite）
DATABASE_URL=sqlite:///./alongway_mvp.db

# Agent 服务地址
AGENT_SERVICE_URL=http://localhost:8001
AGENT_SERVICE_TIMEOUT=180

# 调试模式
DEBUG=true
```

在 `alongway_agent/.env` 中配置：

```env
# 使用 Mock 后端（不依赖真实 Backend）
ALONGWAY_USE_MOCK_BACKEND=false

# Backend 服务地址
ALONGWAY_BACKEND_URL=http://localhost:8000
ALONGWAY_BACKEND_TIMEOUT=30
```

---

## 测试

### Backend 测试

```bash
cd alongway_backend
set PYTHONPATH=.
pytest tests/ -v
# 27 tests passed

# 手动验证
python verify_mvp.py
# 4/4 checks passed
```

### Agent 测试

```bash
cd alongway_agent
pytest tests/ -v
# 4 tests passed (intent_parser, scorer, planner_agent, backend_client)
```

---

## 推荐测试输入

以下输入可稳定跑通 demo：

```text
从武大去光谷，顺路找点吃的
```

```text
从汉口火车站到江汉路，想喝杯咖啡
```

```text
从武汉大学到光谷广场，预算100以内
```

```text
从街道口到光谷步行街，找点甜品
```

---

## 数据概览

| 维度 | 数值 |
|------|------|
| Mock POI 总数 | 18 (武汉 12 + 上海 6) |
| Mock Deal 总数 | 26 (武汉 18 + 上海 8) |
| POI 类别 | 咖啡/日料/茶饮/食堂/便利店/快递/超市/快餐/娱乐/美发 |
| 价格区间 | ¥5.9 ~ ¥39.9 |
| 覆盖场景 | 价格高但近、价格低但远、价格高且远、价格低且近、无团购 |

---

## 当前限制

- 路线计算优先使用 Haversine 近似，配置 AMAP_KEY 后可启用真路网
- 团购数据是 Mock 模板生成，非真实美团 API
- 前端地图是 SVG 示意图，非高德地图 SDK
- Agent 的 LLM 模块默认使用 Mock（模板/规则），可接入真实 LLM
- 意图解析仅稳定支持快递/饮品/吃饭/到访四类任务
- 数据库使用 SQLite，生产部署应切换 Postgres

---

## 技术栈

| 层 | 技术 |
|----|------|
| Frontend | React 18 (UMD), Tailwind CSS (CDN), Babel Standalone |
| Backend | FastAPI, SQLAlchemy, SQLite, httpx, Pydantic |
| Agent | FastAPI, Pydantic, asyncio |
| External | 高德 Web Service API (v3) |
| Tests | pytest (Backend 27 + Agent 4) |

---

## 变更记录

| 日期 | 变更 |
|------|------|
| 2026-06-02 | 前端升级：美团风格 UI（票券卡片/时间线/Toast/粒子场） |
| 2026-06-02 | 后端同步：shunlu 版本为最新，含 geocode fallback + call_logger |
| 2026-05-30 | Agent Mock 全链路可跑通 |
| 2026-05-21 | MVP Backend 完成 4 个 Task (Mock数据/位置获取/真路网/前端验证) |
