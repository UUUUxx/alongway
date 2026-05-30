# Along-way Backend v0.2.0

路线+团购推荐系统的 FastAPI 后端。支持武汉（华科）和上海（复旦/五角场）双城 mock 数据。

## 快速启动

```bash
cd alongway_backend
pip install -r ../requirements.txt
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

或直接初始化数据库种子脚本：
```bash
python -m app.seed
```

---

## 目录结构与文件说明

```
alongway_backend/
│
├── verify_mvp.py                  # 手动验证脚本（18 POI + 26 Deal + Amap路由）
├── requirements.txt               # (项目根目录) Python 依赖
│
├── docs/
│   └── user_location_acquisition.md   # 【Task 2】用户位置获取调研文档
│       # 浏览器 / 微信小程序 / React Native / Flutter 的定位方案
│       # 电脑 vs 手机精度对比，前端→后端数据流说明
│
└── app/
    │
    ├── main.py                    # FastAPI 入口 + 日志配置 + CORS + 路由注册
    │   # 注册了 9 个 router: health, plan, geocode, internal_*, admin_*
    │   # DEBUG 模式下完整日志；生产模式下只记录 request_id
    │
    ├── config.py                  # 配置管理（Settings 类）
    │   # 读取 .env 中的 AMAP_KEY, DATABASE_URL, AGENT_SERVICE_URL 等
    │   # 新增: debug 模式（从 DEBUG 环境变量读取）
    │   # 新增: amap_key, amap_base_url, amap_timeout_seconds
    │
    ├── database.py                # SQLAlchemy engine/session 工厂
    ├── models.py                  # ORM 模型（POI + Deal 两个表）
    │
    ├── schemas.py                 # Pydantic 请求/响应模型
    │   # PlanRequest: 包含 PreferencesInput（低价优先/高分优先等5个偏好）
    │   #            包含 ConstraintsInput（绕路/时间/搜索半径限制）
    │   # LocationInput: 新增 accuracy_meters, source 字段【Task 2】
    │   # RouteCalculateRequest: 新增 use_real_route 字段【Task 3】
    │   # 新增: GeocodeRequest/GeocodeResponse/GeocodeResult【Task 2】
    │   # 新增: PlanHistoryEntry/PlanHistoryResponse【Task 4】
    │
    ├── seed.py                    # 【Task 1】Mock 数据模板
    │   # 18 POIs: 12 武汉(华科) + 6 上海(复旦/五角场)
    │   # 26 Deals: 18 武汉 + 8 上海
    │   # 覆盖场景:
    │   #   - 价格高但近 (东九咖啡角 26-39, 百景园 19.9)
    │   #   - 价格低但远 (西十二轻食 13.9, 东操饮品 7.9, 南一门鲜果 8.8)
    │   #   - 价格高且远 (青年园咖啡车 31, 五角场星巴克 38, 万达影城 39.9)
    │   #   - 价格低且近 (图书馆水果切 15.9, 江湾便利店 5.9)
    │   #   - 服务类无团购 (poi_005/poi_017/poi_015)
    │   # 每个 deal 均有独立的 deal_title 无重合
    │
    ├── routers/
    │   ├── __init__.py            # Router 聚合导出
    │   │
    │   ├── health.py              # GET /health — 健康检查
    │   │
    │   ├── plan.py                # 【Task 4】POST /api/plan — 前端代理端点
    │   │   # DEBUG 模式下记录完整请求体（含 coordinates + preferences + constraints）
    │   │   # 生产模式下只记录 request_id + user_query + city
    │   │   # GET /api/plan/history — 缓存最近 10 条历史记录(前端可召回)
    │   │
    │   ├── geocode.py             # 【Task 2】POST /api/geocode — 地址→坐标代理
    │   │   # 保护 AMAP_KEY 不暴露到前端
    │   │
    │   ├── internal_route.py      # 【Task 3】POST /internal/route/calculate
    │   │   # use_real_route=True → Amap 真路网 API（默认）
    │   │   # use_real_route=False → Haversine 直线近似（兜底）
    │   │   # Amap 失败时自动 fallback 到 Haversine
    │   │
    │   ├── internal_pois.py       # POST /internal/pois/search — POI 搜索
    │   ├── internal_deals.py      # POST /internal/deals/search — Deal 搜索
    │   ├── poi_admin.py           # POI CRUD (GET/POST/PUT/DELETE /api/pois)
    │   ├── deal_admin.py          # Deal CRUD (GET/POST/PUT/DELETE /api/deals)
    │   └── admin.py               # POST /api/admin/seed — 数据库初始化
    │
    ├── services/
    │   ├── route_service.py       # 【Task 3】Amap 真路网路线计算
    │   │   # AmapRouteClient 类（步行/骑行/驾车三种模式）
    │   │   # 使用 httpx 同步调用高德 Web Service API，解析 polyline
    │   │
    │   ├── amap_route_service.py  # 【Task 3】Amap 路由服务包装（兼容层）
    │   │
    │   ├── distance.py            # Haversine 直线距离 + 速度估算
    │   ├── poi_service.py         # POI 搜索（关键词+同义词+距离过滤）
    │   ├── deal_service.py        # Deal 搜索（按价格/类别/月销量排序）
    │   └── agent_client.py        # Agent 服务 HTTP 客户端
    │
    └── tests/
        ├── conftest.py            # pytest 配置（内存 SQLite）
        ├── test_seed_data.py      # 种子数据测试（数量范围+去重+场景覆盖）
        ├── test_deal_search.py    # Deal 搜索测试
        ├── test_poi_search.py     # POI 搜索测试
        ├── test_route_calculate.py # 路线计算测试
        └── test_plan_proxy.py     # Plan 代理测试（含前端选项传入验证）
```

---

## 四个后端任务完成情况

### Task 1: Mock 数据模板（10-20条，多样化场景）✅

| 维度 | 详情 |
|------|------|
| POI 数量 | 18（12 武汉 + 6 上海） |
| Deal 数量 | 26（18 武汉 + 8 上海） |
| 地理范围 | 武汉华科校园 ~3km + 上海复旦/五角场 ~2km |
| 类别覆盖 | drink/coffee/food/express/service/convenience/supermarket/entertainment/hair |
| **价格高但近** | deal_003(26), deal_004(39), deal_009(19.9) |
| **价格低但远** | deal_005(13.9), deal_013(7.9), deal_016(8.8) |
| **价格高且远** | deal_015(31), deal_021(38), deal_026(39.9) |
| **价格低且近** | deal_007(15.9), deal_024(5.9) |
| 无团购POI | poi_005(紫菘快递站), poi_015(街道口美发沙龙), poi_017(复旦北区快递站) |
| 无重合 | 26 个 deal_title 各不相同（测试验证通过） |

### Task 2: 用户当前位置信息获取 ✅

- **文档**: `docs/user_location_acquisition.md`
  - 浏览器 `navigator.geolocation` API（含权限处理+fallback）
  - 微信小程序 `wx.getLocation`（含 app.json 配置）
  - React Native / Flutter 方案
  - 电脑 vs 手机精度对比表
  - 坐标系统说明（WGS-84/GCJ-02/BD-09）
- **端点**: `POST /api/geocode` — 地址→坐标代理（保护 AMAP_KEY）
- **Schema**: `LocationInput` 新增 `accuracy_meters` 和 `source` 字段

### Task 3: 高德 API 真路网路线规划 ✅

- `route_service.py`: `AmapRouteClient` 类
  - 支持 walking / driving / bicycling 三种出行方式
  - 解析高德 API 返回的 polyline 生成真实路线坐标点
- `internal_route.py`: `use_real_route` 参数控制
  - True（默认）→ 调用 Amap API，获取真实路网距离
  - False → Haversine 直线近似
  - Amap 失败时自动 fallback 到 Haversine
- `data_sources/amap_client.py`: 新增 driving_route, transit_route, bicycling_route
- 验证：华科校内路线 = **949m, 48个路线点**（真API结果）

### Task 4: 前端选项传入验证 + 历史缓存 ✅

- **DEBUG 日志**: `plan.py` 在 DEBUG 模式下记录完整请求体
  - `preferences`: prefer_less_detour / prefer_low_price / prefer_high_rating / prefer_high_sales / prefer_fast_arrival
  - `constraints`: max_detour_meters / max_extra_time_minutes / search_radius_meters 等
  - 生产模式只记录 request_id + query + city
- **前端历史缓存**: `GET /api/plan/history` — 返回最近 10 条记录
  - 每条记录含完整 preferences + constraints + 响应结果
  - 前端可以召回"之前问过的问题"
- **测试验证**: `test_plan_forwards_frontend_options_to_agent` 确认所有字段完整传输

---

## API 端点总览

| 方法 | 路径 | 用途 | 模块 |
|------|------|------|------|
| GET | `/health` | 健康检查 | health.py |
| POST | `/api/plan` | **主入口**: 路线+团购规划 | plan.py |
| GET | `/api/plan/history` | 历史记录缓存 | plan.py |
| POST | `/api/geocode` | 地址→坐标（代理） | geocode.py |
| POST | `/internal/route/calculate` | 路线计算 | internal_route.py |
| POST | `/internal/pois/search` | POI 搜索 | internal_pois.py |
| POST | `/internal/deals/search` | Deal 搜索 | internal_deals.py |
| GET/POST | `/api/pois` | POI 列表/创建 | poi_admin.py |
| GET/PUT/DELETE | `/api/pois/{id}` | POI 查/改/删 | poi_admin.py |
| GET/POST | `/api/deals` | Deal 列表/创建 | deal_admin.py |
| GET/PUT/DELETE | `/api/deals/{id}` | Deal 查/改/删 | deal_admin.py |
| POST | `/api/admin/seed` | 初始化数据库 | admin.py |

---

## 关键数据结构

### PlanRequest（前端 → 后端）

```json
{
  "request_id": "req_001",
  "user_query": "我从宿舍去图书馆，路上取快递+买奶茶",
  "start_location": {
    "name": "我的位置",
    "longitude": 114.415,
    "latitude": 30.515,
    "accuracy_meters": 10,
    "source": "browser_gps"
  },
  "end_location": { "name": "图书馆", "longitude": 114.414, "latitude": 30.513 },
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

### Mock 数据场景矩阵

| 场景 | 示例 | POI | 价格 | 距离 | 城市 |
|------|------|-----|------|------|------|
| 价格高但近 | 精品美式早课券 | 东九咖啡角 | ¥26 | ~300m | 武汉 |
| 价格高但近 | 燕麦拿铁点心券 | 东九咖啡角 | ¥39 | ~300m | 武汉 |
| 价格低但远 | 鸡胸肉谷物碗 | 西十二轻食窗口 | ¥13.9 | ~900m | 武汉 |
| 价格低但远 | 运动电解质水 | 东操能量饮品 | ¥7.9 | ~1.2km | 武汉 |
| 价格低但远 | 香蕉酸奶杯券 | 南一门鲜果铺 | ¥8.8 | ~1.5km | 武汉 |
| 价格高且远 | 手冲咖啡体验券 | 青年园咖啡车 | ¥31 | ~800m | 武汉 |
| 价格高且远 | 拿铁下午茶 | 五角场星巴克 | ¥38 | ~1km | 上海 |
| 价格高且远 | 单人电影票 | 万达影城 | ¥39.9 | ~1km | 上海 |
| 价格低且近 | 鲜切果盒补给券 | 图书馆水果切 | ¥15.9 | ~100m | 武汉 |
| 价格低且近 | 早餐饭团套餐 | 江湾便利店 | ¥5.9 | ~300m | 上海 |
| 无团购 | — | 紫菘快递站 | — | ~500m | 武汉 |

---

## 测试

```bash
# 单元测试（27 个）
cd alongway_backend
python -m pytest tests/ -v

# 手动验证（4 个）
python verify_mvp.py
```

测试结果：**27/27 pytest 通过 + 4/4 verify_mvp 通过**

---

## 环境变量 (.env)

```env
AMAP_KEY=your_amap_api_key        # 高德 Web Service API Key
DATABASE_URL=sqlite:///./alongway_mvp.db
AGENT_SERVICE_URL=http://localhost:8001
AGENT_SERVICE_TIMEOUT=30
DEBUG=true                         # true=完整请求日志, false=仅记录ID
```
