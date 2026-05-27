# Backend README — 顺路 App MVP 后端

---

## 1. 项目后端一句话说明

这是"顺路 App"黑客松项目的 MVP 阶段后端服务。

**解决的问题：** 大学生在校园里从 A 点到 B 点的路上，想顺路完成取快递、买奶茶、吃饭等任务。用户输入起点、终点和需求（如"买一杯 20 元以内的奶茶，不要绕太远"），系统返回一条顺路路线，包含推荐的中途停留点和对应团购优惠。

**MVP 边界：** 不接入真实高德地图 POI 搜索，不接入真实美团团购 API。POI 数据和团购数据来自人工标注的 SQLite 数据库，路线距离用 Haversine 公式近似计算。后端只负责数据和工具接口，不做 Agent 决策逻辑。

---

## 2. 后端整体架构

```
前端 (Web/App)
    │  POST /api/plan
    ↓
后端 (FastAPI)
    │  校验请求 → 转发给 Agent
    ↓
Agent 服务 (独立进程)
    │  解析用户需求
    │  调用后端内部接口:
    │    POST /internal/pois/search      (查 POI)
    │    POST /internal/deals/search     (查团购)
    │    POST /internal/route/calculate  (算路线)
    │  生成推荐方案
    ↓
后端 → 返回 PlanResponse 给前端
```

**技术栈：**
- **框架**: FastAPI (Python 3.10+)
- **数据库**: SQLite (MVP 阶段，零配置)
- **ORM**: SQLAlchemy 2.0+
- **验证**: Pydantic v2
- **HTTP 客户端**: httpx (调用 Agent 服务)
- **测试**: pytest + pytest-asyncio

**核心文件位置：**
- 后端入口: `app/main.py`
- API 路由: `app/routers/`
- 业务服务: `app/services/`
- 数据模型: `app/models.py`
- 请求/响应模型: `app/schemas.py`
- Seed 数据: `app/seed.py`
- 距离计算: `app/services/distance.py`
- 配置文件: `app/config.py`

---

## 3. 文件结构说明

```
alongway_backend/
├── backend_readme.md          # ← 本文档
├── requirements.txt           # Python 依赖
├── run_server.bat / .sh       # 一键启动脚本
├── verify_mvp.py              # 快速验证脚本
├── app/
│   ├── main.py                # FastAPI 入口，注册路由，启动建表
│   ├── config.py              # 配置（数据库 URL、Agent 服务 URL）
│   ├── database.py            # SQLite 连接 & Session 管理
│   ├── models.py              # SQLAlchemy 模型 (POI 表, Deal 表)
│   ├── schemas.py             # Pydantic 请求/响应模型
│   ├── crud.py                # 基础 CRUD 操作
│   ├── seed.py                # 内置 Mock 数据初始化
│   ├── services/
│   │   ├── distance.py        # Haversine 距离 + 出行速度
│   │   ├── poi_service.py     # POI 查询（同义词匹配 + 距离过滤 + 排序）
│   │   ├── deal_service.py    # 团购查询（分类/价格过滤 + 排序）
│   │   ├── route_service.py   # 路线计算（多段 + polyline + segments）
│   │   └── agent_client.py    # 调用 Agent 服务
│   └── routers/
│       ├── health.py          # GET /health
│       ├── plan.py            # POST /api/plan (前端主接口)
│       ├── internal_pois.py   # POST /internal/pois/search (给 Agent)
│       ├── internal_deals.py  # POST /internal/deals/search (给 Agent)
│       ├── internal_route.py  # POST /internal/route/calculate (给 Agent)
│       ├── poi_admin.py       # POI CRUD (GET/POST/PUT/DELETE /api/pois)
│       ├── deal_admin.py      # Deal CRUD (GET/POST/PUT/DELETE /api/deals)
│       └── admin.py           # 数据导入 (POST /api/admin/seed, /import/pois, /import/deals)
├── tests/
│   ├── conftest.py
│   ├── test_poi_search.py
│   ├── test_deal_search.py
│   ├── test_route_calculate.py
│   └── test_plan_proxy.py
└── archive_unused/            # 归档文件（不含入交付）
    ├── legacy_postgres_backend/  # 旧 PostgreSQL 推荐系统
    └── old_docs/                 # 旧文档草稿
```

---

## 4. 数据部分说明

### 4.1 数据来源

**MVP 阶段：数据来自人工标注，硬编码在 `app/seed.py` 中。**

数据场景设定为武汉某大学校园：
- 6 个 POI（茶百道、瑞幸咖啡、霸王茶姬、菜鸟驿站、快递柜、一食堂）
- 4 个团购（各商家的优惠套餐）
- 经纬度范围：东经 114.123-114.130，北纬 30.456-30.464

**历史数据管道（非 MVP 运行必需，仅供参考）：**
- 原始数据来源于高德地图 Web 服务 API
- 采集脚本位于 `d:\shunluagent\scripts\`（已归档到 `archive_unused/`）
- 团购数据来源于大众点评/美团（根据文件名推断，Excel 导出格式）
- `outputs/processed_hust/` 中有华中科技大学区域清洗后的数据

### 4.2 数据流

```
高德 API 原始 POI             大众点评团购 Excel
      ↓                              ↓
scripts/02_collect_poi.py      (手工导出 xlsx → CSV)
      ↓                              ↓
data/local_life.db             outputs/csv/*.xlsx
      ↓                              ↓
scripts/03_clean_poi.py        scripts/mvp1_data_alignment.py
      ↓                              ↓
clean_poi 表                   团购 items/shops
      ↓                              ↓
      └──────→ 对齐匹配 ←─────────────┘
                    ↓
          match_candidates
                    ↓
          人工审核确认
                    ↓
    写入 seed.py 作为 Mock 数据
                    ↓
         FastAPI 启动时自动建表
         python -m app.seed 导入数据
                    ↓
          前端/Agent 通过 API 查询
```

### 4.3 最终使用的数据文件

| 来源 | 用途 | 是否运行必须 | 主要字段 |
|------|------|:----------:|---------|
| `app/seed.py` 内置数据 | POI 和团购的 Mock 数据 | **是** | poi_id, name, type, source_keyword, longitude, latitude, rating, cost, deal_id, price, category 等 |
| `alongway_mvp.db` (自动生成) | SQLite 数据库文件 | **是** | 两张表: `pois` (6条), `deals` (4条) |
| `outputs/processed_hust/*.csv` | 华中科技大学区域清洗数据 | 否 | 参考用，可供未来扩展数据 |

### 4.4 中间生成文件

| 文件 | 类型 | 说明 | 处理方式 |
|------|------|------|---------|
| `data/local_life.db` (21MB) | 原始采集数据库 | 高德 API 原始 POI + 清洗中间表 | 保留在项目根目录，不纳入交付 zip |
| `outputs/csv/raw_amap_poi.csv` | 原始 POI CSV | 从 SQLite 导出 | 已删除（可从 local_life.db 重新生成） |
| `outputs/csv/clean_poi.csv` | 清洗后 POI | 中间产物 | 已删除 |
| `outputs/processed/*` | 通用清洗结果 | 上海区域数据 | 已删除 |
| `outputs/processed_cug/*` | CUG 清洗结果 | 中国地质大学数据 | 已删除 |
| `outputs/reports/*` | 数据质量报告 | 自动生成 | 已删除 |
| `logs/*` | 采集日志 | 采集过程记录 | 已删除 |
| `outputs/processed_hust/*` | HUST 清洗结果 | 华中科技大学最终数据 | **保留**，供参考 |
| `*.xlsx` (团购 Excel) | 大众点评导出 | 原始团购数据源 | 已删除（数据已提取到 CSV） |

### 4.5 关键字段解释

**POI 表 (`pois`) 字段：**

| 字段 | 含义 | 给前端/Agent 的用途 |
|------|------|-------------------|
| `poi_id` | POI 唯一 ID (如 `poi_001`) | 标识商家，关联团购 |
| `name` | 商家/地点名称 | 展示给用户 |
| `type` | 类型 (drink/express/food/study/park/service/other) | 分类过滤 |
| `source_keyword` | 搜索关键词 (奶茶/咖啡/快递/食堂) | Agent 查询匹配的核心字段 |
| `longitude`, `latitude` | 经纬度 | 路线计算、距离排序 |
| `rating` | 评分 (1-5) | 排序权重 |
| `cost` | 人均消费 | 预算过滤 |

**Deal 表 (`deals`) 字段：**

| 字段 | 含义 | 给前端/Agent 的用途 |
|------|------|-------------------|
| `deal_id` | 团购唯一 ID | 标识团购 |
| `poi_id` | 关联的 POI ID | 关联商家 |
| `category` | 团购分类 (对应 POI 的 source_keyword) | 分类过滤 |
| `deal_title` | 团购标题 | 展示给用户 |
| `price` | 团购价 | 预算过滤、排序 |
| `original_price` | 原价 | 计算折扣力度 |
| `included_items` | 套餐内容 (JSON 数组) | 展示套餐详情 |
| `rating` | 团购评分 | 排序权重 |
| `monthly_sales` | 月销量 | 排序权重 |
| `reviews` | 用户评价 (JSON 数组) | Agent 生成推荐理由 |
| `business_time` | 营业时间 | 可用性判断 |
| `valid_time` | 团购可用时间 | 可用性判断 |

---

## 5. API 接口说明

所有接口均可通过 Swagger UI 交互式测试：`http://127.0.0.1:8000/docs`

### GET /health

**用途:** 健康检查

**返回:**
```json
{"status": "ok"}
```

---

### POST /api/plan

**用途:** 前端主规划接口。接收用户自然语言需求，返回顺路规划方案。

**请求体:**
```json
{
  "request_id": "req_001",
  "user_query": "我从宿舍去图书馆，路上想取快递，再买一杯20元以内的奶茶，最好不要绕太远。",
  "start_location": {
    "name": "学生宿舍",
    "address": "某大学学生宿舍",
    "location": "宿舍区",
    "longitude": 114.123,
    "latitude": 30.456
  },
  "end_location": {
    "name": "图书馆",
    "address": "某大学图书馆",
    "location": "教学区",
    "longitude": 114.128,
    "latitude": 30.462
  },
  "city": "武汉",
  "travel_mode": "walking",
  "budget": 20,
  "preferences": {
    "prefer_less_detour": true,
    "prefer_low_price": true,
    "prefer_high_rating": false,
    "prefer_high_sales": false,
    "prefer_fast_arrival": false
  },
  "constraints": {
    "max_detour_meters": 800,
    "max_extra_time_minutes": 15,
    "search_radius_meters": 1500,
    "max_pois_per_task": 5,
    "max_deals_per_poi": 3,
    "max_route_candidates": 20
  }
}
```

**返回 (成功):** Agent 返回的 PlanResponse（包含 route、stops、recommendation_reason）

**返回 (Agent 不可用):**
```json
{
  "success": false,
  "error_code": "AGENT_SERVICE_UNAVAILABLE",
  "message": "Agent 服务暂时不可用，请稍后重试。"
}
```

---

### POST /internal/pois/search (给 Agent 调用)

**用途:** Agent 用来查询附近的 POI。

**请求体:**
```json
{
  "source_keywords": ["奶茶", "饮品"],
  "center": {"name": "center", "longitude": 114.125, "latitude": 30.459},
  "radius_meters": 1500,
  "limit": 5
}
```

**查询逻辑:**
1. `source_keywords` 通过同义词表扩展匹配 POI 的 `source_keyword`
2. 如果传入 `center` + `radius_meters`，过滤出半径内的 POI
3. 按距离近 → 评分高 → 消费低排序
4. 返回 `limit` 条

**返回:**
```json
{
  "pois": [
    {
      "poi_id": "poi_001",
      "name": "茶百道",
      "type": "drink",
      "address": "学校商业街一楼",
      "location": "商业街",
      "longitude": 114.126,
      "latitude": 30.459,
      "rating": 4.6,
      "cost": 18,
      "source_keyword": "奶茶",
      "distance_meters": 220
    }
  ]
}
```

**同义词表 (内置在 `app/services/poi_service.py`):**
```python
{
  "饮品": ["奶茶", "咖啡", "冷饮", "喝的", "茶"],
  "奶茶": ["饮品", "冷饮", "茶"],
  "咖啡": ["饮品"],
  "快递": ["菜鸟驿站", "快递柜", "驿站"],
  "吃饭": ["食堂", "小吃", "快餐", "餐厅"],
  "饭": ["食堂", "小吃", "快餐", "餐厅"],
}
```

---

### POST /internal/deals/search (给 Agent 调用)

**用途:** Agent 用来查询某个 POI 的团购。

**请求体:**
```json
{
  "poi_id": "poi_001",
  "categories": ["奶茶"],
  "max_price": 20,
  "limit": 3
}
```

**查询逻辑:**
1. 根据 `poi_id` 查询团购
2. 如果 `categories` 不为空，只返回匹配分类的
3. 如果 `max_price` 不为空，只返回 price ≤ max_price 的
4. 按价格低 → 月销高 → 评分高排序

**返回:**
```json
{
  "deals": [
    {
      "poi_id": "poi_001",
      "name": "茶百道",
      "category": "奶茶",
      "deal_id": "deal_001",
      "deal_title": "招牌奶茶单人套餐",
      "price": 16.8,
      "original_price": 22,
      "included_items": ["招牌奶茶1杯", "任选小料1份"],
      "additional_information": "新人可用，部分门店不可用",
      "valid_time": "10:00-21:30",
      "rating": 4.7,
      "monthly_sales": 300,
      "reviews": ["价格划算", "味道不错", "出餐快"],
      "business_time": "10:00-22:00"
    }
  ]
}
```

---

### POST /internal/route/calculate (给 Agent 调用)

**用途:** Agent 用来计算多点路线距离和时间。

**请求体:**
```json
{
  "points": [
    {"name": "学生宿舍", "longitude": 114.123, "latitude": 30.456},
    {"name": "茶百道", "longitude": 114.126, "latitude": 30.459},
    {"name": "图书馆", "longitude": 114.128, "latitude": 30.462}
  ],
  "travel_mode": "walking"
}
```

**计算方式:** Haversine 公式 (地球半径 6371km)

**出行速度:**
- walking: 80 米/分钟
- bicycling: 200 米/分钟
- driving: 500 米/分钟

**返回:**
```json
{
  "distance_meters": 1350,
  "duration_minutes": 18.0,
  "polyline": [
    [114.123, 30.456],
    [114.126, 30.459],
    [114.128, 30.462]
  ],
  "segments": [
    {"from_name": "学生宿舍", "to_name": "茶百道", "distance_meters": 600, "duration_minutes": 7.5},
    {"from_name": "茶百道", "to_name": "图书馆", "distance_meters": 750, "duration_minutes": 10.0}
  ]
}
```

---

### POI 管理接口 (CRUD)

| 方法 | 路径 | 说明 | 查询参数 |
|------|------|------|---------|
| GET | `/api/pois` | 列表查询 | `keyword`, `type`, `source_keyword` |
| POST | `/api/pois` | 新增 POI | (body: POICreate) |
| GET | `/api/pois/{poi_id}` | 查询单个 | - |
| PUT | `/api/pois/{poi_id}` | 更新 POI | (body: POIUpdate) |
| DELETE | `/api/pois/{poi_id}` | 删除 POI | - |

### 团购管理接口 (CRUD)

| 方法 | 路径 | 说明 | 查询参数 |
|------|------|------|---------|
| GET | `/api/deals` | 列表查询 | `poi_id`, `category`, `max_price` |
| POST | `/api/deals` | 新增团购 | (body: DealCreate) |
| GET | `/api/deals/{deal_id}` | 查询单个 | - |
| PUT | `/api/deals/{deal_id}` | 更新团购 | (body: DealUpdate) |
| DELETE | `/api/deals/{deal_id}` | 删除团购 | - |

### 数据管理接口

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/admin/seed` | 导入内置 Mock 数据 |
| POST | `/api/admin/import/pois` | 从 JSON 数组批量导入 POI |
| POST | `/api/admin/import/deals` | 从 JSON 数组批量导入团购 |

---

## 6. 推荐逻辑说明

### 6.1 MVP 阶段的推荐逻辑

MVP 阶段后端**不包含推荐决策逻辑**。推荐由 Agent 服务完成。

**后端提供的能力：**
1. **POI 查询** — Agent 传入关键词，后端返回匹配的 POI 列表（已按距离/评分/价格排序）
2. **团购查询** — Agent 传入 POI ID + 预算，后端返回该商家的团购列表（已按价格/销量/评分排序）
3. **路线计算** — Agent 传入多点，后端返回总距离、时间、分段信息

**Agent 负责：**
- 解析用户自然语言，提取任务（如"取快递"→搜快递；"买奶茶预算20"→搜奶茶+预算≤20）
- 调用后端接口获取候选 POI 和团购
- 组合候选点，调用路线计算评估绕路程度
- 生成最终推荐方案和推荐理由

### 6.2 历史评分公式（已归档，仅供参考）

旧版 PostgreSQL 推荐系统有一套评分公式（位于 `archive_unused/legacy_postgres_backend/score_service.py`）：

```
final_score = 0.50 × along_score + 0.20 × price_score + 0.10 × discount_score + 0.10 × rating_score + 0.10 × sales_score
```

- **along_score**: 基于 POI 到路线的垂直距离 (1 - distance/max_distance) × 100
- **price_score**: (1 - price/reference_price) × 100
- **discount_score**: 基于折扣率
- **rating_score**: rating/5 × 100
- **sales_score**: 基于月销量

这个公式可作参考，但不用于当前 MVP 的 SQLite 后端。

### 6.3 如何判断"顺路"

MVP 中通过路线计算接口评估顺路程度：
- Agent 传入"起点 → 候选POI → 终点"的路线
- 后端返回总距离和分段时间
- Agent 对比直达距离 vs 绕路距离，判断是否在用户的 `max_detour_meters` 约束内

### 6.4 前端展示建议

前端拿到 Agent 返回的 PlanResponse 后：
1. 在**地图**上绘制 `polyline`（坐标数组）
2. 标注**起终点**和**中途停留点**
3. 展示每个停留点的**团购信息**（deal_title, price, 节省金额）
4. 展示**推荐理由**（recommendation_reason）
5. 展示**距离和时间**估算

---

## 7. 数据清洗代码说明

### 7.1 MVP 数据初始化

MVP 阶段的数据直接硬编码在 `app/seed.py` 中，运行即可初始化：

```bash
python -m app.seed
```

这会自动：
1. 创建 SQLite 数据库 (`alongway_mvp.db`)
2. 创建 `pois` 和 `deals` 表
3. 导入 6 个 POI + 4 个团购

**修改数据方式：**
- 直接编辑 `app/seed.py` 中的 `pois_data` 和 `deals_data` 列表，重新运行
- 或通过管理接口 `POST /api/pois` / `POST /api/deals` 在线添加

### 7.2 历史数据清洗管道（已归档）

以下脚本位于项目根目录，属于数据采集阶段，**不属于 MVP 后端运行必需**：

| 脚本 | 作用 |
|------|------|
| `scripts/01_geocode_seed_points.py` | 将种子地点名（华中科技大学、中国地质大学）地理编码为经纬度 |
| `scripts/02_collect_poi.py` | 调用高德周边搜索 API，按关键词采集 POI，存入 SQLite |
| `scripts/03_clean_poi.py` | 清洗原始 POI：去重、标准化、分类、质量评分 |
| `scripts/04_generate_data_report.py` | 生成数据质量报告（JSON + Markdown） |
| `scripts/mvp1_data_alignment.py` | 核心对齐引擎：用模糊匹配将团购店铺与高德 POI 匹配 |
| `scripts/import_to_postgres.py` | 将清洗后的 CSV 导入 PostgreSQL |
| `data_sources/amap_client.py` | 高德地图 API 客户端封装 |

### 如何重新生成最终数据

如果需要从原始高德数据重新生成清洗数据（需要高德 API Key）：

```bash
# 1. 配置高德 API Key
cp .env.example .env   # 编辑填入 AMAP_KEY

# 2. 运行采集管道
python scripts/01_geocode_seed_points.py
python scripts/02_collect_poi.py
python scripts/03_clean_poi.py
python scripts/04_generate_data_report.py

# 3. 对齐团购数据
python scripts/mvp1_data_alignment.py

# 4. 将结果手动更新到 alongway_backend/app/seed.py
```

---

## 8. 如何运行后端

### 最小运行步骤

```bash
# 1. 进入后端目录
cd alongway_backend

# 2. 安装依赖
pip install -r requirements.txt

# 3. 初始化数据库并导入 Mock 数据
python -m app.seed

# 4. 启动服务
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

或者一键启动：

```bash
# Windows
run_server.bat

# Linux/Mac
bash run_server.sh
```

### 访问

- **Swagger API 文档**: http://127.0.0.1:8000/docs
- **健康检查**: http://127.0.0.1:8000/health

### 环境变量 (`.env`)

```env
DATABASE_URL=sqlite:///./alongway_mvp.db
AGENT_SERVICE_URL=http://localhost:8001
AGENT_SERVICE_TIMEOUT=30
```

### 运行测试

```bash
pytest tests/ -v
```

### 快速验证

```bash
python verify_mvp.py
```

---

## 9. 给前端同学的说明

### 前端主要调用的接口

**唯一入口: `POST /api/plan`**

### 请求方式

```javascript
// 示例
const response = await fetch('http://localhost:8000/api/plan', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    user_query: "我从宿舍去图书馆，路上想取快递，再买一杯20元以内的奶茶",
    start_location: {
      name: "学生宿舍",
      address: "某大学学生宿舍",
      location: "宿舍区",
      longitude: 114.123,
      latitude: 30.456
    },
    end_location: {
      name: "图书馆",
      address: "某大学图书馆",
      location: "教学区",
      longitude: 114.128,
      latitude: 30.462
    },
    city: "武汉",
    travel_mode: "walking",
    budget: 20
  })
});
const data = await response.json();
// data.plan.route       → [[lon, lat], ...] 路线坐标
// data.plan.stops       → [{poi_id, deal_id, ...}] 停留点
// data.plan.recommendation_reason → 推荐理由
```

### 返回结果说明

- `data.success` — true/false
- `data.plan.route` — 坐标数组 `[[lon, lat], ...]`，可在地图上绘制 polyline
- `data.plan.stops` — 中途停留点列表，包含 `poi_id` 和 `deal_id`
- `data.plan.recommendation_reason` — 文本推荐理由

### Mock / 真数据边界

- MVP 阶段所有数据为 **人工标注的 Mock 数据**（6 个 POI + 4 个团购）
- 经纬度范围：武汉某大学校园（东经 114.123-114.130，北纬 30.456-30.464）
- 路线距离为 **Haversine 直线近似**，不等于真实步行/骑行距离
- 团购数据字段完整（价格、原价、内容、评价等），但数值为手工设定

### 开发期间的注意事项

- 后端需要 Agent 服务配合才能返回完整的 PlanResponse
- 如果 Agent 不可用，`POST /api/plan` 会返回 `error_code: "AGENT_SERVICE_UNAVAILABLE"`
- Swagger UI (`/docs`) 可以直接测试所有接口，不需要前端

---

## 10. 给 Agent 同学的说明

### Agent 可以调用的接口

| 接口 | 用途 | 请求方式 |
|------|------|---------|
| `/internal/pois/search` | 按关键词查 POI | POST |
| `/internal/deals/search` | 按 POI ID 查团购 | POST |
| `/internal/route/calculate` | 计算多点路线 | POST |

### Agent 工作流程

```
1. 收到 PlanRequest (user_query + start_location + end_location + budget + preferences)

2. 解析 user_query 提取任务:
   - "取快递" → source_keywords=["快递"]
   - "买奶茶" → source_keywords=["奶茶", "饮品"]
   - "20元以内" → max_price=20

3. 对每个任务:
   a. 调用 POST /internal/pois/search (传 source_keywords + center + radius)
      → 获取候选 POI 列表 (已按距离/评分/价格排序)
   b. 对每个候选 POI:
      调用 POST /internal/deals/search (传 poi_id + categories + max_price)
      → 获取符合预算的团购列表

4. 组合候选路线:
   对每个 (起点, POI, 终点) 组合:
     调用 POST /internal/route/calculate
     → 获取 distance_meters, duration_minutes, segments

5. 根据 constraints 过滤:
   - distance_meters - 直达距离 < max_detour_meters ✓
   - duration_minutes < max_extra_time_minutes ✓

6. 按 preferences 排序:
   - prefer_less_detour → 距离短的优先
   - prefer_low_price → 价格低的优先
   - prefer_high_rating → 评分高的优先

7. 生成 PlanResponse:
   - route: polyline 坐标
   - stops: [{poi_id, deal_id, deal_title, price, ...}]
   - recommendation_reason: 推荐理由文本
```

### 适合放进 prompt 的数据字段

Agent 生成推荐理由时可以参考这些字段：

- **POI**: `name`, `type`, `source_keyword`, `rating`, `cost`, `distance_meters`
- **团购**: `deal_title`, `price`, `original_price`, `included_items`, `rating`, `monthly_sales`, `reviews`, `valid_time`
- **路线**: `distance_meters`, `duration_minutes`, `segments[].from_name/ to_name/ distance_meters`

### 推荐理由生成示例

```
顺路推荐：从学生宿舍出发，途经茶百道（商业街，约220米偏离路线），
购买"招牌奶茶单人套餐"仅需16.8元（原价22元，省5.2元），再前往图书馆。
总路程约1350米，步行约18分钟，绕路约350米。
```

---

## 11. 当前限制和后续 TODO

### 当前限制

| 限制 | 详情 |
|------|------|
| **数据是 Mock** | 当前仅 6 个 POI + 4 个团购，硬编码在 seed.py |
| **未接真实 API** | 未接入高德 POI 搜索、高德导航路线、美团团购 |
| **路线是直线近似** | Haversine 公式计算的是大圆距离，不是真实道路距离 |
| **没有走流线路网** | 不支持实际步行/骑行/驾车路线 |
| **Agent 是独立服务** | 后端不包含 Agent 逻辑，需要单独的 Agent 服务运行在 localhost:8001 |
| **无用户认证** | 没有登录、用户偏好存储 |
| **无缓存** | 每次查询都重新计算 |

### 黑客松 Demo 阶段建议优先补

1. **增加 Mock 数据量** — 在 `seed.py` 中加 20-30 个 POI 和对应团购，让 demo 更丰富
2. **实现简单 Mock Agent** — 在 `app/services/agent_client.py` 附近写一个简单的 mock agent，不依赖外部服务也能跑通完整流程
3. **前端联调** — 确认 PlanResponse 的字段格式前端能正确解析和展示
4. **错误处理完善** — 确保边界情况（无结果、超预算、超出绕路限制）有清晰返回

### 后续正式版方向

1. 接入高德 POI 搜索 API 替代本地 SQLite 查询
2. 接入高德导航 API 获取真实路线距离和时间
3. 接入美团团购 API 获取真实团购数据
4. 数据缓存层 (Redis)
5. 用户系统 (偏好学习、历史记录)
6. 迁移到 PostgreSQL (支持空间索引和更复杂的查询)

---

## 附录 A: 归档文件说明

以下文件已从主代码中移除，放在 `archive_unused/` 中：

### archive_unused/legacy_postgres_backend/
旧版 PostgreSQL 推荐系统代码。使用高德采集的真实 POI 数据 + 大众点评团购数据，通过模糊匹配对齐，提供基于评分公式的路线推荐。因依赖 PostgreSQL 且与 MVP 的 Agent 架构不同而归档。

### archive_unused/old_docs/
项目开发过程中的草稿文档（实现总结、完成清单、快速启动指南等）。内容已合并到本文档中。

---

## 附录 B: 未实际运行验证

由于开发环境限制（需要 Python 3.10+ 环境、Agent 服务未启动），以下项目未实际运行验证：
- `uvicorn app.main:app` 后端启动
- pytest 测试套件
- `verify_mvp.py` 快速验证

代码已通过 Python AST 语法检查（`main.py`, `models.py`, `schemas.py` 均通过）。

建议接收方在本地执行 `python verify_mvp.py` 进行完整功能验证。

---

**文档版本**: v1.0  
**最后更新**: 2026-05-27  
**对应代码版本**: Along-way MVP Backend 0.1.0
