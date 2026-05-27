# 顺路购 Along-way MVP

顺路购是一个面向校园生活场景的智能顺路规划 demo。用户用自然语言输入起点、终点和路上需求，例如“从学生宿舍到教学区，顺路吃个午饭，预算 15 元以内”，系统会解析任务、查找沿途 POI、匹配团购/优惠信息，并生成一条可展示的路线方案。

当前项目由三个部分组成：

```text
shunlu/
├── alongway_backend/                 # FastAPI 后端，负责数据、工具接口、高德 POI 接入
├── alongway_agent/                   # Agent 编排层，负责意图解析、候选生成、路线评分
└── alongway-frontend/alongway-demo/   # 单页前端 demo
```

## 核心能力

- 自然语言行程输入：从一句话中识别起点、终点、预算、顺路任务和偏好。
- 高德 POI 接入：后端支持用高德 Web API 地理编码和周边 POI 搜索。
- 缓存优先：优先查本地数据库，结果不足时再调用高德，清洗后入库。
- POI 清洗：保留餐饮、娱乐、快递/打印/便利店等轻量生活服务，过滤停车场、公司、住宅、公共设施等低价值点位。
- 团购 mock：餐饮和娱乐类 POI 会自动生成稳定的演示团购数据。
- 路线评分：Agent 组合候选点，按绕路距离、时间、预算、评分等因素选出推荐方案。
- 前端展示：展示路线示意图、距离/时间/费用、推荐点和团购卡片。

## 数据流

```text
Frontend
  -> POST /api/plan
Backend
  -> 解析/补全起终点坐标
  -> 调用 Agent /agent/plan
Agent
  -> 调用 Backend internal tools
     - /internal/pois/search
     - /internal/deals/search
     - /internal/route/calculate
Backend
  -> 本地 DB 优先，不足时拉取高德 POI 并入库
Agent
  -> 生成 selected_plan
Backend
  -> 适配成前端 plan 结构
Frontend
  -> 展示结果
```

## 技术栈

- Backend: FastAPI, SQLAlchemy, SQLite/Postgres-compatible `DATABASE_URL`, httpx, pytest
- Agent: FastAPI, Pydantic, pytest
- Frontend: React UMD + Tailwind CDN, 单文件 `index.html`
- External API: 高德 Web 服务 API `/v3/geocode/geo`, `/v3/place/around`

## 快速启动

建议打开三个终端，分别启动 backend、agent 和 frontend。

### 1. Backend

```bash
cd alongway_backend
pip install -r requirements.txt
python -m app.seed
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

检查：

```text
http://127.0.0.1:8000/health
http://127.0.0.1:8000/docs
```

### 2. Agent

```bash
cd alongway_agent
pip install -r requirements.txt
uvicorn app.main:app --host 127.0.0.1 --port 8001 --reload
```

Agent 默认应使用真实 backend 工具接口。若要纯 mock 调试，可在 `.env` 中设置：

```env
ALONGWAY_USE_MOCK_BACKEND=true
```

### 3. Frontend

```bash
cd alongway-frontend/alongway-demo
python -m http.server 5173
```

然后访问：

```text
http://127.0.0.1:5173
```

## 推荐测试输入

这些输入贴合当前 seed 数据和校园 demo 场景：

```text
从学生宿舍去图书馆，路上想取快递，再买一杯20元以内的奶茶，最好不要绕太远。
```

```text
从学生宿舍到教学区，顺路吃个午饭，预算15元以内，不要绕太远。
```

开启 `AMAP_KEY` 后，也可以尝试更自由的地点和需求，例如：

```text
从华中科技大学主校区到光谷广场，路上想喝奶茶，预算20元以内，少绕路。
```

## 当前允许的用户输入

当前 MVP 不是通用自然语言理解系统。为了稳定跑通 demo，前端输入建议遵守下面的句式和关键词范围。

### 1. 必须包含明确起点和终点

推荐句式：

```text
从{起点}到{终点}，{顺路需求}
从{起点}去{终点}，{顺路需求}
从{起点}前往{终点}，{顺路需求}
从{起点}→{终点}，{顺路需求}
```

也可以写成：

```text
自{起点}到{终点}，{顺路需求}
由{起点}到{终点}，{顺路需求}
```

地点要求：

- 如果未配置 `AMAP_KEY`，起点/终点应尽量使用内置地点：`学生宿舍`、`宿舍`、`图书馆`、`教学区`、`商业街`、`生活区`、`学生服务中心`、`一食堂`。
- 如果已配置 `AMAP_KEY`，可输入高德能解析的武汉地点，例如 `光谷步行街`、`华中科技大学紫菘学生公寓`、`华中科技大学明德楼`、`华中科技大学主图书馆`。
- 不建议只写“从 A 出发，去吃饭/买奶茶”这种没有明确终点的句式；当前 Agent 仍要求最终有起点和终点坐标。

### 2. 当前可识别的顺路任务

当前 Agent 通过规则词表解析任务，只稳定支持以下几类。

取快递：

```text
取快递、拿快递、快递、驿站、菜鸟、快递柜
```

实际触发关键词中只要包含 `快递`、`驿站`、`菜鸟`、`快递柜` 即可。系统会搜索：

```text
快递、菜鸟驿站、快递柜
```

买饮品：

```text
奶茶、饮品、咖啡、喝的、买杯喝的、冷饮
```

系统会搜索：

```text
奶茶、饮品、咖啡
```

吃饭：

```text
吃饭、午饭、晚饭、小吃、快餐、食堂、餐厅
```

系统会搜索：

```text
食堂、小吃、快餐、餐厅
```

途经地点/访问：

```text
公园、操场、图书馆、教学楼、活动中心
```

注意：如果这些词已经出现在终点里，例如“到图书馆”，不会额外当作顺路任务。

### 3. 当前支持的预算和偏好表达

预算可写：

```text
20元以内
15块以下
预算20
不超过30
低于25
控制在18
```

偏好可写：

```text
便宜、省钱、低价、划算
不要绕、少绕、顺路、绕太远
快一点、尽快、赶时间
```

### 4. 当前不稳定或暂不支持的输入

这些输入可能无法解析出任务，或结果不稳定：

- 只有出发地，没有明确终点：`从明德楼出发，去吃韩餐`
- 细分菜系但不含通用吃饭词：`吃韩餐`、`吃火锅`、`吃日料`
- 饮品细分类但不含当前饮品词：`酸奶`、`果茶`、`豆浆`
- 购物类泛需求：`买东西`、`买文具`、`买药`
- 多城市、跨城、非武汉范围的地点
- 复杂时间条件：`晚上九点后还开门的店`
- 需要真实道路导航的表达：当前路线仍是近似直线距离，不是高德导航路线

### 5. 推荐可跑通样例

```text
从学生宿舍去图书馆，路上想取快递，再买一杯20元以内的奶茶，最好不要绕太远。
```

```text
从学生宿舍到教学区，顺路吃个午饭，预算15元以内，不要绕太远。
```

```text
从光谷步行街到华中科技大学紫菘学生公寓，中途拿快递。
```

```text
从华中科技大学明德楼到华中科技大学主图书馆，中间买杯奶茶。
```

## 高德 POI 和本地缓存

Backend 的 POI 搜索策略是：

1. 先查本地数据库。
2. 如果结果不足、请求里有中心点，并且配置了 `AMAP_KEY`，再调用高德周边搜索。
3. 清洗高德返回的 POI，只保留项目需要的字段。
4. 用高德 POI `id` 作为 `source_id` 去重，写入本地数据库。
5. 对餐饮/娱乐 POI 生成稳定 mock 团购。
6. 再次查询同区域时优先命中本地缓存，减少延迟和 API 调用。

当前保留类型：

- 餐饮：餐厅、食堂、快餐、小吃、奶茶、咖啡、冷饮等。
- 娱乐：棋牌、桌游、游戏厅、影剧院、运动/健身等。
- 轻量生活服务：快递、菜鸟驿站、打印、便利店、超市等。

当前默认剔除：

- 停车场、交通设施、汽车服务/维修、政府机构、公司企业、住宅、公共设施、道路附属设施、地名地址、出入口、加油站等。

## Mock 团购规则

mock 团购是确定性模板生成，不是随机数据：

- `drink` 生成饮品券，例如单人饮品、双杯下午茶。
- `food` 生成餐饮券，例如午餐套餐、轻食简餐。
- `entertainment` 生成娱乐体验券。
- `express/life` 默认不生成团购，只作为顺路点。

价格、销量、评分会根据 `poi_id` 做稳定变化，因此同一个 POI 每次生成结果一致，便于演示和调试。

## 测试

Backend：

```bash
cd alongway_backend
set PYTHONPATH=.
pytest
```

PowerShell：

```powershell
cd alongway_backend
$env:PYTHONPATH='.'
pytest
```

Agent：

```bash
cd alongway_agent
pytest
```

当前已验证：

- Backend 测试通过：`24 passed`
- Agent 测试通过：`4 passed`
- Backend 编译检查通过
- SQLite 旧库 schema 补齐通过

## API 摘要

对前端开放：

- `POST /api/plan`：规划主入口。
- `GET /health`：健康检查。

Backend 给 Agent 的 internal tools：

- `POST /internal/pois/search`：查 POI，缓存不足时可补拉高德。
- `POST /internal/deals/search`：查团购，必要时生成 mock deal。
- `POST /internal/route/calculate`：计算近似路线距离和时间。

管理接口：

- `/api/pois...`：POI CRUD。
- `/api/deals...`：Deal CRUD。

## 当前限制

- 路线计算仍是 Haversine 近似，不是真实道路导航。
- 团购数据是 mock，不是真实美团/大众点评 API。
- 高德 POI 搜索受 API key、QPS 和网络状态影响。
- 前端地图是示意图，不是高德真实地图 SDK。

## 后续优化方向

- 接入真实步行/骑行路径规划。
- 扩充 mock 团购模板池，让结果更自然。
- 给 POI 增加 TTL 和后台刷新任务。
- 增加城市/校园范围配置。
- 将生产环境数据库切换为 Postgres。
