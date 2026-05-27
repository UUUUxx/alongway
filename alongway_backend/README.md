# Along-way MVP Backend Service

## AMap POI Mode

Backend now supports cache-first AMap POI enrichment:

1. Copy `.env.example` to `.env`.
2. Put your key in `.env`:

```env
AMAP_KEY=your_amap_key_here
AMAP_CITY=武汉
```

Do not commit `.env`. The service reads `AMAP_KEY` from environment variables only.

When `/internal/pois/search` is called, the backend searches local SQLite/Postgres first. If there are not enough nearby results and a center point is available, it calls AMap `/v3/place/around`, filters out low-value categories such as parking lots, stores cleaned POIs, and creates deterministic mock deals for dining/entertainment POIs. `/api/plan` also resolves free-text start/end locations through AMap `/v3/geocode/geo` before forwarding the request to the Agent.

一个面向大学生的本地生活顺路规划系统的后端服务。

## 项目概述

本项目是 **Along-way** (顺路) 应用的 MVP（最小可行产品）阶段后端实现。系统支持用户根据起点、终点和顺路需求，智能推荐一条可以完成任务的最优路线。

**用户使用示例：**
```
"我从宿舍去图书馆，路上想取快递，再买一杯20元以内的奶茶，最好不要绕太远。"
```

系统会自动分析需求，推荐一条**既能取快递、又能买奶茶、还不会太绕路**的最佳方案。

## 后端职责

### 核心职责
1. **接收前端请求** - 处理用户的路线规划请求
2. **调用 Agent 服务** - 将请求转发至 AI Agent 进行决策
3. **提供工具接口** - 为 Agent 提供 POI 查询、团购查询、路线计算等能力
4. **管理数据** - 维护 POI（兴趣点）和团购数据的存储和查询
5. **数据管理接口** - 提供 POI 和团购的 CRUD 操作

### 不做的事
- **不做复杂决策** - 路线排序、方案推荐等决策全部由 Agent 完成
- **不接入真实 API** - MVP 阶段使用本地数据库和近似计算
- **不做数据同步** - 高德 POI、美团团购等 API 暂不集成

## 边界说明

### 前端 ↔ 后端
```
前端: 请求路线规划
  ↓ POST /api/plan
后端: 校验 + 转发 Agent
  ↓ POST /agent/plan (调用 Agent)
Agent: 分析需求，调用后端工具接口
  ↓ 调用内部接口
后端: 提供查询、计算服务
  ↓ 返回结果
Agent: 生成方案和推荐理由
  ↓ 返回 PlanResponse
后端: 转发给前端
  ↓ 响应前端
前端: 展示推荐方案
```

### Agent ↔ 后端
Agent 可以调用以下后端内部接口：

1. `POST /internal/pois/search` - 查询附近 POI
2. `POST /internal/deals/search` - 查询团购信息
3. `POST /internal/route/calculate` - 计算路线距离和时间

这些接口只供 Agent 使用，不暴露给前端。

## 技术栈

- **框架**: FastAPI (Python 3.10+)
- **数据库**: SQLite3 (MVP 阶段)
- **ORM**: SQLAlchemy + SQLModel
- **验证**: Pydantic v2
- **HTTP 客户端**: httpx
- **测试**: pytest

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 初始化数据库并导入 Mock 数据

```bash
python -m app.seed
```

这会自动：
- 创建 SQLite 数据库 (`alongway_mvp.db`)
- 创建 `pois` 和 `deals` 表
- 导入内置的 6 个 POI 和 4 个团购数据

### 3. 启动服务

```bash
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

服务会在 `http://127.0.0.1:8000` 启动。

### 4. 访问 API 文档

- **交互式 API 文档**: http://127.0.0.1:8000/docs (Swagger UI)
- **API 备选文档**: http://127.0.0.1:8000/redoc (ReDoc)

## API 接口

### 1. 健康检查 ✅

```http
GET /health
```

**响应**:
```json
{
  "status": "ok"
}
```

---

### 2. 前端主规划接口 🔑

```http
POST /api/plan
```

这是前端调用的主接口。后端会：
1. 校验请求
2. 如果缺少 `request_id`，自动生成
3. 调用 Agent 服务 `POST /agent/plan`
4. 将 Agent 返回结果原样转发给前端

**请求体** (example):
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

**响应** (成功):
```json
{
  "success": true,
  "request_id": "req_001",
  "plan": {
    "route": [...],
    "stops": [...],
    "recommendation_reason": "..."
  }
}
```

**响应** (Agent 不可用):
```json
{
  "success": false,
  "error_code": "AGENT_SERVICE_UNAVAILABLE",
  "message": "Agent 服务暂时不可用，请稍后重试。"
}
```

---

### 3. POI 查询接口 (给 Agent 调用)

```http
POST /internal/pois/search
```

**请求体**:
```json
{
  "source_keywords": ["奶茶", "饮品"],
  "center": {
    "name": "中心点",
    "longitude": 114.125,
    "latitude": 30.459
  },
  "radius_meters": 1500,
  "limit": 5
}
```

**查询逻辑**:
- 根据 `source_keywords` 匹配 POI 表的 `source_keyword`
- 支持**模糊匹配**和**同义词扩展** (例如搜"饮品"可匹配"奶茶""咖啡"等)
- 如果指定 `center` 和 `radius_meters`，只返回半径内的 POI
- 按距离近 → 评分高 → 消费低排序

**响应**:
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

---

### 4. 团购查询接口 (给 Agent 调用)

```http
POST /internal/deals/search
```

**请求体**:
```json
{
  "poi_id": "poi_001",
  "categories": ["奶茶", "饮品"],
  "max_price": 20,
  "limit": 3
}
```

**查询逻辑**:
- 根据 `poi_id` 查询该商家的所有团购
- 如果提供 `categories`，只返回匹配的分类
- 如果提供 `max_price`，只返回价格 ≤ max_price 的团购
- 按价格低 → 月销高 → 评分高排序

**响应**:
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

### 5. 路线计算接口 (给 Agent 调用)

```http
POST /internal/route/calculate
```

**请求体**:
```json
{
  "points": [
    {
      "name": "学生宿舍",
      "longitude": 114.123,
      "latitude": 30.456
    },
    {
      "name": "茶百道",
      "longitude": 114.126,
      "latitude": 30.459
    },
    {
      "name": "图书馆",
      "longitude": 114.128,
      "latitude": 30.462
    }
  ],
  "travel_mode": "walking"
}
```

**计算逻辑**:
- 按顺序逐段计算，使用 **Haversine 公式**
- 支持三种出行模式：
  - `walking`: 80 m/min
  - `bicycling`: 200 m/min
  - `driving`: 500 m/min

**响应**:
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
    {
      "from_name": "学生宿舍",
      "to_name": "茶百道",
      "distance_meters": 600,
      "duration_minutes": 7.5
    },
    {
      "from_name": "茶百道",
      "to_name": "图书馆",
      "distance_meters": 750,
      "duration_minutes": 10.0
    }
  ]
}
```

---

### 6. POI 管理接口 (管理员)

#### 查询 POI 列表
```http
GET /api/pois?keyword=茶&type=drink&source_keyword=奶茶
```

#### 创建 POI
```http
POST /api/pois
```

#### 查询单个 POI
```http
GET /api/pois/{poi_id}
```

#### 更新 POI
```http
PUT /api/pois/{poi_id}
```

#### 删除 POI
```http
DELETE /api/pois/{poi_id}
```

---

### 7. 团购管理接口 (管理员)

#### 查询团购列表
```http
GET /api/deals?poi_id=poi_001&category=奶茶&max_price=20
```

#### 创建团购
```http
POST /api/deals
```

#### 查询单个团购
```http
GET /api/deals/{deal_id}
```

#### 更新团购
```http
PUT /api/deals/{deal_id}
```

#### 删除团购
```http
DELETE /api/deals/{deal_id}
```

---

## 数据库设计

### POI 表 (`pois`)

| 字段 | 类型 | 描述 | 示例 |
|------|------|------|------|
| `poi_id` | TEXT (PK) | 唯一ID | `poi_001` |
| `name` | TEXT | 商家名称 | `茶百道` |
| `type` | TEXT | 类型 | `drink`, `express`, `food` |
| `address` | TEXT | 地址 | `学校商业街一楼` |
| `location` | TEXT | 位置描述 | `商业街` |
| `longitude` | FLOAT | 经度 | `114.126` |
| `latitude` | FLOAT | 纬度 | `30.459` |
| `rating` | FLOAT (NULL) | 评分 | `4.6` |
| `cost` | FLOAT (NULL) | 人均消费 | `18` |
| `source_keyword` | TEXT | 搜索关键词 | `奶茶`, `咖啡`, `快递` |
| `created_at` | DATETIME | 创建时间 | |
| `updated_at` | DATETIME | 更新时间 | |

### Deal 表 (`deals`)

| 字段 | 类型 | 描述 | 示例 |
|------|------|------|------|
| `deal_id` | TEXT (PK) | 团购ID | `deal_001` |
| `poi_id` | TEXT (FK) | 关联 POI | `poi_001` |
| `name` | TEXT | 商家名称 | `茶百道` |
| `category` | TEXT | 分类 | `奶茶`, `咖啡` |
| `deal_title` | TEXT | 团购标题 | `招牌奶茶单人套餐` |
| `price` | FLOAT | 团购价 | `16.8` |
| `original_price` | FLOAT (NULL) | 原价 | `22` |
| `included_items` | TEXT (JSON) | 包含内容 | `["奶茶1杯", "小料1份"]` |
| `additional_information` | TEXT | 补充信息 | `新人可用` |
| `valid_time` | TEXT | 可用时间 | `10:00-21:30` |
| `rating` | FLOAT (NULL) | 评分 | `4.7` |
| `monthly_sales` | INT (NULL) | 月销量 | `300` |
| `reviews` | TEXT (JSON) | 用户评价 | `["好喝", "划算"]` |
| `business_time` | TEXT | 营业时间 | `10:00-22:00` |
| `created_at` | DATETIME | 创建时间 | |
| `updated_at` | DATETIME | 更新时间 | |

## 关键词匹配规则

### 内置同义词表

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

### 匹配逻辑

1. **完全匹配优先** - 用户关键词与 `source_keyword` 完全相同
2. **同义词扩展** - 自动扩展同义词表中的相关词汇
3. **双向匹配** - 如果某词是其他词的同义词，也会被匹配

**示例**:
- 搜索 "饮品" 可以匹配: 奶茶、咖啡、冷饮、喝的、茶、饮品
- 搜索 "奶茶" 可以匹配: 饮品、冷饮、茶、奶茶

## 距离计算

### Haversine 公式

```python
def haversine_distance_meters(lon1, lat1, lon2, lat2) -> float:
    R = 6371000  # 地球半径(米)
    φ1 = radians(lat1)
    φ2 = radians(lat2)
    Δφ = radians(lat2 - lat1)
    Δλ = radians(lon2 - lon1)
    
    a = sin²(Δφ/2) + cos(φ1)·cos(φ2)·sin²(Δλ/2)
    c = 2·atan2(√a, √(1−a))
    distance = R·c
    return distance
```

### 时间计算

根据出行模式的速度和距离计算时间：

```
duration_minutes = distance_meters / (speed_m_per_min)
```

## 测试

### 运行所有测试

```bash
pytest
```

### 运行特定测试

```bash
# POI 查询测试
pytest test_poi_search.py

# 团购查询测试
pytest test_deal_search.py

# 路线计算测试
pytest test_route_calculate.py
```

### 测试覆盖范围

- ✅ POI 查询 - 关键词匹配、距离过滤、排序
- ✅ 团购查询 - 分类过滤、价格过滤、排序
- ✅ 路线计算 - Haversine 公式、时间计算、多段路线
- ✅ 前端代理 - Agent 服务调用、超时处理、错误返回

## 如何修改人工标注数据

### 方式 1: 直接修改 seed.py

编辑 `app/seed.py` 中的 `pois_data` 和 `deals_data` 列表，然后重新运行：

```bash
python -m app.seed
```

### 方式 2: 使用管理接口

**创建新 POI:**
```bash
curl -X POST http://localhost:8000/api/pois \
  -H "Content-Type: application/json" \
  -d '{
    "name": "新奶茶店",
    "type": "drink",
    "address": "某地址",
    "location": "某区域",
    "longitude": 114.125,
    "latitude": 30.460,
    "rating": 4.5,
    "cost": 20,
    "source_keyword": "奶茶"
  }'
```

**更新 POI:**
```bash
curl -X PUT http://localhost:8000/api/pois/poi_001 \
  -H "Content-Type: application/json" \
  -d '{"name": "新名称", "rating": 4.8}'
```

**创建新团购:**
```bash
curl -X POST http://localhost:8000/api/deals \
  -H "Content-Type: application/json" \
  -d '{
    "poi_id": "poi_001",
    "name": "茶百道",
    "category": "奶茶",
    "deal_title": "新团购",
    "price": 15.9,
    "original_price": 20,
    "included_items": ["产品1", "产品2"],
    "rating": 4.6,
    "monthly_sales": 250,
    "reviews": ["好评"],
    "business_time": "10:00-22:00"
  }'
```

### 方式 3: 使用 Swagger UI

访问 http://localhost:8000/docs，使用 "Try it out" 功能直接测试接口。

## 后续接入真实 API 的扩展指南

### 接入高德地图 POI API

1. **修改 POI 数据源**
   - 在 `services/mvp_poi_service.py` 中添加高德 API 调用
   - 使用高德 POI 搜索 API 替代本地数据库查询
   - 缓存结果以提高性能

2. **更新数据模型**
   ```python
   # 添加高德特定字段
   class POI(Base):
       amap_poi_id: str  # 高德 ID
       amap_type: str    # 高德分类
       # ...
   ```

### 接入美团团购 API

1. **添加美团数据爬取**
   - 实现美团 API 调用逻辑
   - 定期同步团购数据到本地数据库
   - 使用异步任务定期刷新

2. **更新团购模型**
   ```python
   class Deal(Base):
       meituan_deal_id: str  # 美团 ID
       meituan_shop_id: str  # 美团店铺 ID
       # ...
   ```

### 接入真实路线规划 API

1. **替换 Haversine 计算**
   - 在 `services/mvp_route_service.py` 中调用高德导航 API
   - 获得真实的距离和时间估计

2. **缓存策略**
   ```python
   # 缓存常用路线
   @cache
   def get_real_route(start, end, mode):
       return amap_api.calculate_route(start, end, mode)
   ```

### 平滑迁移策略

```python
# 配置开关
USE_REAL_AMAP = os.getenv("USE_REAL_AMAP", "false").lower() == "true"
USE_REAL_MEITUAN = os.getenv("USE_REAL_MEITUAN", "false").lower() == "true"

# POI 查询逻辑
if USE_REAL_AMAP:
    results = amap_search_pois(keywords)
else:
    results = db_search_pois(keywords)
```

这样可以在不影响现有功能的前提下逐步接入真实 API。

## 环境变量配置

创建 `.env` 文件（可选，有默认值）:

```bash
# 数据库
DATABASE_URL=sqlite:///./alongway_mvp.db

# Agent 服务
AGENT_SERVICE_URL=http://localhost:8001
AGENT_SERVICE_TIMEOUT=30

# 服务器
HOST=127.0.0.1
PORT=8000
DEBUG=False
```

## 常见问题

### Q: 数据库文件在哪里？
A: 默认在项目根目录，文件名为 `alongway_mvp.db`。可在 `.env` 文件中修改 `DATABASE_URL`。

### Q: 如何清空并重新初始化数据库？
A: 
```bash
rm alongway_mvp.db
python -m app.seed
```

### Q: Agent 服务如何调用后端？
A: Agent 获得后端 base URL（如 `http://localhost:8000`），然后调用：
- `POST http://localhost:8000/internal/pois/search`
- `POST http://localhost:8000/internal/deals/search`
- `POST http://localhost:8000/internal/route/calculate`

### Q: 如何调试？
A: 在 `.env` 中设置 `DEBUG=True`，SQLAlchemy 会打印 SQL 日志。

## 项目结构

```
alongway_backend/
├── app/
│   ├── __init__.py
│   ├── main.py                  # FastAPI 应用入口
│   ├── config.py                # 配置管理
│   ├── database.py              # 数据库连接
│   ├── models.py                # SQLAlchemy 模型 (POI, Deal)
│   ├── schemas.py               # Pydantic 请求/响应模型
│   ├── seed.py                  # Mock 数据初始化
│   ├── crud.py                  # 基础 CRUD 操作
│   ├── services/
│   │   ├── distance.py          # Haversine 距离计算
│   │   ├── poi_service.py       # POI 查询逻辑
│   │   ├── deal_service.py      # 团购查询逻辑
│   │   ├── route_service.py     # 路线计算逻辑
│   │   └── agent_client.py      # Agent 服务调用
│   └── routers/
│       ├── health.py            # 健康检查
│       ├── plan.py              # 前端主接口
│       ├── internal_pois.py     # POI 查询接口
│       ├── internal_deals.py    # 团购查询接口
│       ├── internal_route.py    # 路线计算接口
│       ├── poi_admin.py         # POI 管理接口
│       ├── deal_admin.py        # 团购管理接口
│       └── admin.py             # 数据导入接口
├── tests/
│   ├── conftest.py
│   ├── test_poi_search.py       # POI 查询测试
│   ├── test_deal_search.py      # 团购查询测试
│   ├── test_route_calculate.py  # 路线计算测试
│   └── test_plan_proxy.py       # Plan 代理测试
├── requirements.txt             # 依赖清单
└── README.md                    # 本文档
```

## 贡献指南

### 添加新的 POI 类型

1. 在 POI 表中添加新类型示例
2. 更新同义词表
3. 添加对应的测试用例

### 扩展查询功能

1. 在 service 层添加新的查询逻辑
2. 在 schemas 中定义新的请求/响应
3. 在 router 中暴露新的端点
4. 补充测试覆盖

## 许可证

MIT

## 联系方式

For issues and questions, please open an issue on the project repository.

---

**最后更新**: 2024
**MVP 版本**: 0.1.0
