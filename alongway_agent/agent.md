你是一个资深 AI Agent 工程师，请帮我实现一个“顺路 App”的 Agent 编排层。

这是 MVP 阶段，不接入真实高德地图 POI 搜索，也不接入真实美团团购 API。

MVP 阶段所有 POI 信息和团购信息都来自后端维护的人工标注数据库。

==================================================
一、项目背景
============

我们要做一个面向大学生的本地生活顺路规划 Agent。

用户输入示例：

“我从宿舍去图书馆，路上想取快递，再买一杯20元以内的奶茶，最好不要绕太远。”

系统需要完成：

1. 理解用户自然语言需求；
2. 拆解成多个顺路任务；
3. 根据任务类型生成 source_keyword；
4. 调用后端人工标注 POI 数据库，查询候选 POI；
5. 调用后端人工标注团购数据库，查询候选团购套餐；
6. 根据预算、营业时间、评分、销量等字段筛选候选；
7. 组合起点、候选 POI、终点；
8. 调用后端路线计算接口，得到近似距离、耗时、绕路距离；
9. 使用确定性的评分函数排序；
10. 最后用大模型生成自然语言推荐理由；
11. 返回结构化 JSON 给后端和前端。

注意：
Agent 不直接读取数据库。
Agent 不直接调用高德地图。
Agent 不直接调用美团 API。
Agent 只调用后端提供的内部接口。

Agent 负责：

- 理解用户需求；
- 拆任务；
- 生成搜索关键词 source_keyword；
- 调用后端工具；
- 组合方案；
- 评分排序；
- 生成推荐理由。

后端负责：

- 管理人工标注 POI 数据；
- 管理人工标注团购数据；
- 提供 POI 查询接口；
- 提供团购查询接口；
- 提供路线距离和时间计算接口；
- 提供统一的数据格式。

==================================================
二、MVP 阶段人工标注数据字段
============================

1. 商家基础信息 POI 表

字段如下：

poi_id:

- POI 唯一 ID。
- 示例：poi_001

name:

- 商家或地点名称。
- 示例：茶百道、菜鸟驿站、瑞幸咖啡、图书馆

type:

- POI 类型。
- 示例：drink、express、food、study、park、service

address:

- 地址。
- 示例：学校商业街一楼

location:

- 位置描述。
- 示例：商业街、宿舍区、图书馆附近

longitude:

- 经度。
- float 类型。

latitude:

- 纬度。
- float 类型。

rating:

- 商家评分。
- float 类型。
- 示例：4.6

cost:

- 人均消费。
- float 类型。
- 示例：18

source_keyword:

- 人工标注的搜索关键词。
- 用于和 Agent 解析出的任务类型匹配。
- 示例：
  - 奶茶
  - 饮品
  - 咖啡
  - 快递
  - 菜鸟驿站
  - 食堂
  - 小吃
  - 公园
  - 图书馆

POI 示例：

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
  "source_keyword": "奶茶"
}

2. 团购信息 Deal 表

字段如下：

poi_id:

- 对应 POI 表中的 poi_id。

name:

- 商家名称。
- 示例：茶百道

category:

- 对应 POI 表中的 source_keyword。
- 用于匹配任务类型。
- 示例：奶茶、饮品、咖啡、小吃、快餐

deal_id:

- 团购套餐 ID。
- 示例：deal_001

deal_title:

- 团购标题。
- 示例：招牌奶茶单人套餐

price:

- 团购价。
- float 类型。
- 示例：16.8

original_price:

- 原价。
- float 类型。
- 示例：22

included_items:

- 包含内容。
- 可以是字符串，也可以是字符串数组。
- 示例：["招牌奶茶1杯", "任选小料1份"]

additional_information:

- 补充信息。
- 例如：新人可用、限工作日、部分门店不可用。

valid_time:

- 可用时间。
- 示例：10:00-21:30

rating:

- 团购或商家在团购平台上的评分。
- float 类型。

monthly_sales:

- 月销量。
- int 类型。

reviews:

- 评价。
- MVP 可以先用字符串数组。
- 示例：["味道不错", "出餐快", "价格划算"]

business_time:

- 商家营业时间。
- 示例：10:00-22:00

Deal 示例：

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

==================================================
三、Agent 层输入数据结构
========================

后端调用 Agent 层时，请传入 PlanRequest。

请在 agent/models.py 中使用 Pydantic 定义以下结构。

Location:

class Location(BaseModel):
    name: Optional[str] = None
    address: Optional[str] = None
    location: Optional[str] = None
    longitude: Optional[float] = None
    latitude: Optional[float] = None

说明：

- name 是地点名称。
- address 是详细地址。
- location 是位置描述，例如“商业街”“宿舍区”。
- longitude 是经度。
- latitude 是纬度。

UserPreferences:

class UserPreferences(BaseModel):
    prefer_less_detour: bool = True
    prefer_low_price: bool = False
    prefer_high_rating: bool = False
    prefer_high_sales: bool = False
    prefer_fast_arrival: bool = False

PlanConstraints:

class PlanConstraints(BaseModel):
    max_detour_meters: int = 800
    max_extra_time_minutes: int = 15
    search_radius_meters: int = 1500
    max_pois_per_task: int = 5
    max_deals_per_poi: int = 3
    max_route_candidates: int = 20

PlanRequest:

class PlanRequest(BaseModel):
    request_id: str
    user_query: str
    start_location: Optional[Location] = None
    end_location: Optional[Location] = None
    current_location: Optional[Location] = None
    city: Optional[str] = None
    travel_mode: Literal["walking", "bicycling", "driving"] = "walking"
    budget: Optional[float] = None
    departure_time: Optional[datetime] = None
    preferences: UserPreferences = UserPreferences()
    constraints: PlanConstraints = PlanConstraints()

前端传给后端的数据示例：

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

==================================================
四、Agent 层内部数据模型
========================

请定义以下模型。

TaskType 枚举：

- pickup_express
- buy_drink
- eat_meal
- visit_place
- study
- custom

StopType 枚举：

- start
- task
- deal
- end

POI 模型：

class POI(BaseModel):
    poi_id: str
    name: str
    type: str
    address: Optional[str] = None
    location: Optional[str] = None
    longitude: float
    latitude: float
    rating: Optional[float] = None
    cost: Optional[float] = None
    source_keyword: str

Deal 模型：

class Deal(BaseModel):
    poi_id: str
    name: str
    category: str
    deal_id: str
    deal_title: str
    price: float
    original_price: Optional[float] = None
    included_items: List[str] = []
    additional_information: Optional[str] = None
    valid_time: Optional[str] = None
    rating: Optional[float] = None
    monthly_sales: Optional[int] = None
    reviews: List[str] = []
    business_time: Optional[str] = None

TaskSpec 模型：

class TaskSpec(BaseModel):
    task_id: str
    type: TaskType
    raw_text: str
    source_keywords: List[str]
    budget: Optional[float] = None
    required: bool = True

说明：
source_keywords 是 Agent 解析出来的关键词，用于查询 POI 表中的 source_keyword 和 Deal 表中的 category。

例如：
用户说“买杯奶茶”
source_keywords = ["奶茶", "饮品"]

用户说“取快递”
source_keywords = ["快递", "菜鸟驿站", "快递柜"]

UserIntent 模型：

class UserIntent(BaseModel):
    start_text: Optional[str] = None
    end_text: Optional[str] = None
    tasks: List[TaskSpec]
    budget: Optional[float] = None
    preferences: UserPreferences

EnrichedCandidate 模型：

class EnrichedCandidate(BaseModel):
    task_id: str
    task_type: TaskType
    poi: POI
    deal: Optional[Deal] = None
    is_open: bool = True
    filter_reasons: List[str] = []

RouteSegment 模型：

class RouteSegment(BaseModel):
    from_name: str
    to_name: str
    distance_meters: int
    duration_minutes: float

RouteResult 模型：

class RouteResult(BaseModel):
    distance_meters: int
    duration_minutes: float
    polyline: List[List[float]]
    segments: List[RouteSegment] = []

PlanStop 模型：

class PlanStop(BaseModel):
    order: int
    stop_type: StopType
    task_id: Optional[str] = None
    name: str
    location: Location
    poi: Optional[POI] = None
    deal: Optional[Deal] = None
    reason: Optional[str] = None

ScoreDetail 模型：

class ScoreDetail(BaseModel):
    detour_score: float
    time_score: float
    price_score: float
    rating_score: float
    sales_score: float
    open_score: float

CandidatePlan 模型：

class CandidatePlan(BaseModel):
    plan_id: str
    stops: List[PlanStop]
    route: RouteResult
    base_distance_meters: int
    base_duration_minutes: float
    detour_distance_meters: int
    extra_time_minutes: float
    estimated_cost: float
    score: float
    score_detail: ScoreDetail
    recommendation_reason: Optional[str] = None

AlternativePlanSummary 模型：

class AlternativePlanSummary(BaseModel):
    plan_id: str
    score: float
    total_distance_meters: int
    total_duration_minutes: float
    detour_distance_meters: int
    extra_time_minutes: float
    estimated_cost: float
    brief_reason: str

DebugTrace 模型：

class DebugTrace(BaseModel):
    parsed_task_count: int
    poi_candidate_count: int
    deal_candidate_count: int
    route_candidate_count: int

PlanResponse 模型：

class PlanResponse(BaseModel):
    success: bool
    request_id: str
    summary: Optional[str] = None
    intent: Optional[UserIntent] = None
    selected_plan: Optional[CandidatePlan] = None
    alternative_plans: List[AlternativePlanSummary] = []
    warnings: List[str] = []
    debug_trace: Optional[DebugTrace] = None
    error_code: Optional[str] = None
    message: Optional[str] = None
    missing_fields: List[str] = []
    fallback_suggestions: List[str] = []

==================================================
五、Agent 需要调用后端的功能
============================

Agent 只通过 BackendClient 调用后端。

请实现 BackendClient 抽象类，并实现 HttpBackendClient 和 MockBackendClient。

1. 查询 POI

函数：

async def search_pois(
    source_keywords: List[str],
    center: Optional[Location],
    radius_meters: int,
    limit: int
) -> List[POI]

对应后端接口：

POST /internal/pois/search

请求示例：

{
  "source_keywords": ["奶茶", "饮品"],
  "center": {
    "longitude": 114.125,
    "latitude": 30.459
  },
  "radius_meters": 1500,
  "limit": 5
}

返回示例：

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
      "source_keyword": "奶茶"
    }
  ]
}

2. 查询团购

函数：

async def search_deals(
    poi_id: str,
    categories: List[str],
    max_price: Optional[float],
    limit: int
) -> List[Deal]

对应后端接口：

POST /internal/deals/search

请求示例：

{
  "poi_id": "poi_001",
  "categories": ["奶茶", "饮品"],
  "max_price": 20,
  "limit": 3
}

返回示例：

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

3. 计算路线

MVP 阶段不要求真实地图路径规划。
后端可以根据经纬度使用 Haversine 或欧氏距离近似计算距离。

函数：

async def calculate_route(
    points: List[Location],
    travel_mode: str
) -> RouteResult

对应后端接口：

POST /internal/route/calculate

请求示例：

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

返回示例：

{
  "distance_meters": 1350,
  "duration_minutes": 18,
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
      "duration_minutes": 8
    },
    {
      "from_name": "茶百道",
      "to_name": "图书馆",
      "distance_meters": 750,
      "duration_minutes": 10
    }
  ]
}

==================================================
六、Agent 编排流程
==================

请实现 PlanAgent 类：

class PlanAgent:
    async def plan(self, request: PlanRequest) -> PlanResponse:
        ...

完整流程如下。

Step 0：输入校验

检查：

- user_query 是否为空；
- 是否有起点；
- 是否有终点；
- 如果没有 start_location，但有 current_location，则用 current_location 作为起点；
- 起点和终点必须有 longitude 和 latitude；
- 如果起点或终点缺少经纬度，MVP 阶段直接返回 MISSING_LOCATION，不做真实地理编码。

错误返回：

success=false
error_code="MISSING_LOCATION"
message="缺少起点或终点经纬度，请先在前端选择地点。"

Step 1：解析用户意图

调用 IntentParser。

输入：

- request.user_query
- request.budget
- request.preferences

输出 UserIntent。

任务映射规则：

1. 取快递

如果用户输入包含：

- 取快递
- 快递
- 驿站
- 菜鸟
- 快递柜

生成任务：

{
  "type": "pickup_express",
  "source_keywords": ["快递", "菜鸟驿站", "快递柜"],
  "budget": null
}

2. 买饮品

如果用户输入包含：

- 奶茶
- 饮品
- 咖啡
- 喝的
- 买杯喝的
- 冷饮

生成任务：

{
  "type": "buy_drink",
  "source_keywords": ["奶茶", "饮品", "咖啡"],
  "budget": 从用户文本中提取，例如20
}

3. 吃饭

如果用户输入包含：

- 吃饭
- 午饭
- 晚饭
- 小吃
- 快餐
- 食堂
- 餐厅

生成任务：

{
  "type": "eat_meal",
  "source_keywords": ["食堂", "小吃", "快餐", "餐厅"],
  "budget": 从用户文本中提取
}

4. 去某个地点

如果用户输入包含：

- 公园
- 操场
- 图书馆
- 教学楼
- 活动中心

生成任务：

{
  "type": "visit_place",
  "source_keywords": 根据用户文本提取
}

IntentParser 应优先调用 LLMClient 解析 JSON。
如果 LLM 调用失败或输出不合法，则使用规则解析兜底。

LLM 解析结果只能用于生成任务结构，不允许直接生成最终推荐方案。

Step 2：计算搜索中心

MVP 计算搜索中心：

center.longitude = (start.longitude + end.longitude) / 2
center.latitude = (start.latitude + end.latitude) / 2

搜索半径使用：

request.constraints.search_radius_meters

Step 3：计算基础路线

调用后端 route 工具：

start -> end

得到 base_route：

- base_distance_meters
- base_duration_minutes

Step 4：根据每个任务查询 POI

对每个 TaskSpec：

调用：

search_pois(
  source_keywords=task.source_keywords,
  center=center,
  radius_meters=request.constraints.search_radius_meters,
  limit=request.constraints.max_pois_per_task
)

得到 POI 候选。

去重规则：

- 按 poi_id 去重。

如果某个 required 任务没有 POI：

返回：
success=false
error_code="NO_POI_FOR_REQUIRED_TASK"
message="没有找到可以完成该任务的地点。"

Step 5：根据 POI 查询团购

对于 buy_drink、eat_meal 任务：

对每个 POI 调用：

search_deals(
  poi_id=poi.poi_id,
  categories=task.source_keywords,
  max_price=task.budget or request.budget,
  limit=request.constraints.max_deals_per_poi
)

如果找到团购：

- 每个 deal 都可以生成一个 EnrichedCandidate。

如果没有找到团购：

- 如果用户明确说“团购”“优惠券”“套餐”“20元以内”等价格约束，则该 POI 降权或过滤；
- MVP 中对于 buy_drink/eat_meal，如果有预算但没有团购，先过滤；
- 如果没有预算，则可以保留无团购 POI，但 deal=None。

对于 pickup_express、visit_place：

- 不需要查询团购；
- 直接生成 EnrichedCandidate，deal=None。

Step 6：过滤候选

过滤规则：

1. 预算过滤

如果 deal.price > task.budget 或 request.budget，则过滤。

2. 营业时间过滤

使用 deal.business_time 或 poi 营业信息。
但 POI 表没有 business_time，所以优先使用 deal.business_time。

如果无法判断营业状态：

- is_open=True；
- warnings 添加 "部分商家缺少营业时间信息"。

如果能判断：

- 解析 "10:00-22:00" 或 "08:00-21:30"；
- 判断 request.departure_time 是否在范围内；
- 不在营业时间内则过滤或降权。
  MVP 中可以先降权，不直接过滤。

3. 团购可用时间过滤

解析 deal.valid_time。
如果当前时间不在 valid_time 内，降权或过滤。
MVP 中先降权。

Step 7：组合路线

如果用户有多个任务，则按用户任务顺序组合。

例如：
任务1：取快递，有候选 A1、A2
任务2：买奶茶，有候选 B1、B2

生成路线：

start -> A1 -> B1 -> end
start -> A1 -> B2 -> end
start -> A2 -> B1 -> end
start -> A2 -> B2 -> end

MVP 不需要优化任务顺序，不做排列组合。
只保持用户说出的任务顺序。

组合数量不能超过：

request.constraints.max_route_candidates

如果组合太多：

- 先按候选的 POI rating、deal price、monthly_sales 粗排；
- 截断到 max_route_candidates。

Step 8：调用路线计算

对每条候选路线调用：

calculate_route(points, travel_mode)

points 格式：

[
  start_location,
  candidate_1.poi 转成 Location,
  candidate_2.poi 转成 Location,
  end_location
]

得到 candidate_route。

计算：

detour_distance_meters =
candidate_route.distance_meters - base_route.distance_meters

extra_time_minutes =
candidate_route.duration_minutes - base_route.duration_minutes

estimated_cost =
所有 deal.price 之和

过滤：

- detour_distance_meters > max_detour_meters 时过滤；
- extra_time_minutes > max_extra_time_minutes 时过滤；
- estimated_cost > budget 时过滤。

Step 9：评分排序

不要让大模型决定哪条路线最优。
使用确定性评分函数。

请在 scorer.py 中实现。

默认权重：

score =
0.35 * detour_score

+ 0.20 * time_score
+ 0.20 * price_score
+ 0.10 * rating_score
+ 0.10 * sales_score
+ 0.05 * open_score

如果 prefer_less_detour=True：
提高 detour_score 权重。

如果 prefer_low_price=True：
提高 price_score 权重。

如果 prefer_high_rating=True：
提高 rating_score 权重。

如果 prefer_high_sales=True：
提高 sales_score 权重。

如果 prefer_fast_arrival=True：
提高 time_score 权重。

权重调整后必须归一化，保证总和为 1。

子分计算：

detour_score:
detour_score = max(0, 1 - detour_distance_meters / max_detour_meters)

time_score:
time_score = max(0, 1 - extra_time_minutes / max_extra_time_minutes)

price_score:
如果没有预算：
price_score = 0.7

如果有预算且 estimated_cost <= budget：
price_score = 1 - 0.5 * estimated_cost / budget

如果 estimated_cost > budget：
price_score = 0

rating_score:
综合 POI.rating 和 Deal.rating。
如果都有：
rating_score = ((poi_rating + deal_rating) / 2) / 5
如果只有一个：
rating_score = rating / 5
如果都没有：
rating_score = 0.6

sales_score:
根据 monthly_sales 计算。
MVP 简单规则：

- monthly_sales >= 500: 1.0
- monthly_sales >= 200: 0.8
- monthly_sales >= 50: 0.6
- monthly_sales > 0: 0.4
- 缺失: 0.5

open_score:

- 明确营业：1.0
- 时间未知：0.8
- 当前不可用：0.3

排序规则：

- score 降序；
- score 相同时，detour_distance_meters 小的优先；
- 再相同，estimated_cost 小的优先；
- 再相同，monthly_sales 高的优先；
- 再相同，duration_minutes 小的优先。

Step 10：生成推荐理由

选出分数最高的 CandidatePlan 作为 selected_plan。

然后调用 Explainer。

Explainer 可以使用 LLM，也可以使用模板。

LLM 输入必须只包含：

- 用户原始需求；
- selected_plan 的距离、耗时、绕路、价格；
- selected_plan 中每个 stop 的 POI 和 deal；
- alternative_plans 的简要对比；
- score_detail。

LLM 不能修改：

- 距离；
- 时间；
- 价格；
- score；
- POI；
- deal。

LLM 只负责生成：

- summary
- recommendation_reason
- 每个 stop.reason
- alternative brief_reason

如果 LLM 失败，使用模板生成。

Step 11：返回 PlanResponse

成功返回：

{
  "success": true,
  "request_id": "req_001",
  "summary": "推荐你先去菜鸟驿站取快递，再顺路去茶百道购买16.8元团购奶茶，最后到达图书馆。",
  "intent": {
    "start_text": "宿舍",
    "end_text": "图书馆",
    "tasks": [
      {
        "task_id": "task_1",
        "type": "pickup_express",
        "raw_text": "取快递",
        "source_keywords": ["快递", "菜鸟驿站", "快递柜"],
        "budget": null,
        "required": true
      },
      {
        "task_id": "task_2",
        "type": "buy_drink",
        "raw_text": "买一杯20元以内的奶茶",
        "source_keywords": ["奶茶", "饮品", "咖啡"],
        "budget": 20,
        "required": true
      }
    ],
    "budget": 20,
    "preferences": {
      "prefer_less_detour": true,
      "prefer_low_price": true,
      "prefer_high_rating": false,
      "prefer_high_sales": false,
      "prefer_fast_arrival": false
    }
  },
  "selected_plan": {
    "plan_id": "plan_001",
    "score": 0.86,
    "total_distance_meters": 1350,
    "total_duration_minutes": 18,
    "base_distance_meters": 1000,
    "base_duration_minutes": 12,
    "detour_distance_meters": 350,
    "extra_time_minutes": 6,
    "estimated_cost": 16.8,
    "score_detail": {
      "detour_score": 0.82,
      "time_score": 0.75,
      "price_score": 0.91,
      "rating_score": 0.86,
      "sales_score": 0.8,
      "open_score": 1.0
    },
    "stops": [
      {
        "order": 1,
        "stop_type": "start",
        "task_id": null,
        "name": "学生宿舍",
        "location": {
          "name": "学生宿舍",
          "address": "某大学学生宿舍",
          "location": "宿舍区",
          "longitude": 114.123,
          "latitude": 30.456
        },
        "poi": null,
        "deal": null,
        "reason": "出发点"
      },
      {
        "order": 2,
        "stop_type": "task",
        "task_id": "task_1",
        "name": "菜鸟驿站",
        "location": {
          "name": "菜鸟驿站",
          "address": "学生服务中心一楼",
          "location": "宿舍区附近",
          "longitude": 114.125,
          "latitude": 30.458
        },
        "poi": {
          "poi_id": "poi_002",
          "name": "菜鸟驿站",
          "type": "express",
          "address": "学生服务中心一楼",
          "location": "宿舍区附近",
          "longitude": 114.125,
          "latitude": 30.458,
          "rating": 4.5,
          "cost": null,
          "source_keyword": "快递"
        },
        "deal": null,
        "reason": "该快递点位于宿舍到图书馆的路线附近，绕路较少。"
      },
      {
        "order": 3,
        "stop_type": "deal",
        "task_id": "task_2",
        "name": "茶百道",
        "location": {
          "name": "茶百道",
          "address": "学校商业街一楼",
          "location": "商业街",
          "longitude": 114.126,
          "latitude": 30.459
        },
        "poi": {
          "poi_id": "poi_001",
          "name": "茶百道",
          "type": "drink",
          "address": "学校商业街一楼",
          "location": "商业街",
          "longitude": 114.126,
          "latitude": 30.459,
          "rating": 4.6,
          "cost": 18,
          "source_keyword": "奶茶"
        },
        "deal": {
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
        },
        "reason": "这家店团购价为16.8元，低于20元预算，且月销量较高。"
      },
      {
        "order": 4,
        "stop_type": "end",
        "task_id": null,
        "name": "图书馆",
        "location": {
          "name": "图书馆",
          "address": "某大学图书馆",
          "location": "教学区",
          "longitude": 114.128,
          "latitude": 30.462
        },
        "poi": null,
        "deal": null,
        "reason": "目的地"
      }
    ],
    "polyline": [
      [114.123, 30.456],
      [114.125, 30.458],
      [114.126, 30.459],
      [114.128, 30.462]
    ],
    "recommendation_reason": "这条路线可以同时完成取快递和购买奶茶两个任务，相比直接去图书馆只增加约350米，预计多花6分钟，团购价格也符合20元以内预算。"
  },
  "alternative_plans": [
    {
      "plan_id": "plan_002",
      "score": 0.78,
      "total_distance_meters": 1500,
      "total_duration_minutes": 20,
      "detour_distance_meters": 500,
      "extra_time_minutes": 8,
      "estimated_cost": 9.9,
      "brief_reason": "价格更低，但绕路距离更长。"
    }
  ],
  "warnings": [],
  "debug_trace": {
    "parsed_task_count": 2,
    "poi_candidate_count": 8,
    "deal_candidate_count": 4,
    "route_candidate_count": 6
  }
}

失败返回：

{
  "success": false,
  "request_id": "req_001",
  "error_code": "NO_VALID_PLAN",
  "message": "附近没有找到符合预算和绕路限制的方案。",
  "fallback_suggestions": [
    "可以放宽预算到25元",
    "可以把最大绕路距离放宽到1200米",
    "可以只规划取快递路线"
  ]
}

==================================================
七、错误码
==========

请定义这些错误码：

MISSING_USER_QUERY:
用户没有输入需求。

MISSING_LOCATION:
缺少起点或终点坐标。

INTENT_PARSE_FAILED:
意图解析失败。

NO_TASK_PARSED:
没有解析出顺路任务。

NO_POI_FOR_REQUIRED_TASK:
某个必需任务没有候选 POI。

NO_DEAL_MATCHED:
有 POI，但没有符合预算的团购。

NO_ROUTE_FOUND:
路线计算失败。

NO_VALID_PLAN:
所有候选方案都被过滤，没有可用方案。

BACKEND_TOOL_ERROR:
调用后端工具失败。

LLM_ERROR:
大模型调用失败。

==================================================
八、目录结构
============

请生成以下项目结构：

alongway_agent/
  README.md
  requirements.txt
  .env.example
  agent/
    __init__.py
    models.py
    config.py
    exceptions.py
    backend_client.py
    llm_client.py
    prompts.py
    intent_parser.py
    candidate_generator.py
    filters.py
    route_evaluator.py
    scorer.py
    explainer.py
    planner_agent.py
  app/
    main.py
  tests/
    test_intent_parser.py
    test_scorer.py
    test_planner_agent.py

==================================================
九、测试要求
============

请实现测试。

1. test_intent_parser.py

输入：
“我从宿舍去图书馆，路上想取快递，再买一杯20元以内的奶茶。”

期望：

- 解析出两个任务；
- 包含 pickup_express；
- 包含 buy_drink；
- buy_drink 的 source_keywords 包含 奶茶；
- budget = 20。

2. test_scorer.py

构造三个 CandidatePlan：

- A：绕路少，价格高；
- B：绕路多，价格低；
- C：均衡。

当 prefer_less_detour=True 时，绕路少的方案应优先。
当 prefer_low_price=True 时，价格低的方案应优先。

3. test_planner_agent.py

使用 MockBackendClient 和 MockLLMClient。

输入完整 PlanRequest。

期望：

- success=True；
- selected_plan 不为空；
- stops 包含 start、task/deal、end；
- estimated_cost <= 20；
- detour_distance_meters <= max_detour_meters；
- summary 不为空。

==================================================
十、验收标准
============

最终代码必须满足：

1. 可以 pip install -r requirements.txt。
2. 可以 pytest 跑通测试。
3. 可以启动 FastAPI 服务。
4. 可以通过 POST /agent/plan 得到完整 PlanResponse。
5. 不依赖真实高德地图 API。
6. 不依赖真实美团 API。
7. 不依赖真实大模型 API。
8. Mock 模式下可以完整跑通：
   用户输入
   -> 意图解析
   -> 查询人工标注 POI
   -> 查询人工标注团购
   -> 组合路线
   -> 近似路线计算
   -> 评分排序
   -> 生成推荐理由
   -> 返回结构化 JSON。
9. 所有核心数据结构都用 Pydantic。
10. 所有核心函数都有类型标注。
11. Agent 不直接访问数据库。
12. Agent 不直接调用高德或美团。
13. LLM 不负责路线排序和数值计算。
14. 代码结构清晰，方便后续接入真实高德和美团 API。

请根据以上要求直接生成完整项目代码。
