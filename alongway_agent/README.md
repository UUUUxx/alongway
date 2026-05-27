# Alongway Agent

“顺路 App”的 Agent 编排层 MVP。

本项目不调用真实高德地图、真实美团 API 或真实大模型 API。默认使用 `MockBackendClient` 内置的人工标注 POI、团购数据和 Haversine 近似路线计算，完整跑通：

用户输入 -> 意图解析 -> 查询 POI -> 查询团购 -> 组合路线 -> 路线计算 -> 确定性评分 -> 生成推荐理由 -> 返回结构化 JSON。

## 安装

```bash
pip install -r requirements.txt
```

## 运行测试

```bash
pytest
```

## 启动服务

```bash
uvicorn app.main:app --reload
```

然后请求：

```bash
POST http://127.0.0.1:8000/agent/plan
```

示例请求：

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
    "prefer_low_price": true
  }
}
```

## 模块说明

- `agent/models.py`: Pydantic 输入、内部和输出模型。
- `agent/backend_client.py`: 后端工具抽象、HTTP 实现和 Mock 实现。
- `agent/intent_parser.py`: LLM 优先、规则兜底的意图解析。
- `agent/candidate_generator.py`: 按任务查询 POI 和团购，生成候选。
- `agent/route_evaluator.py`: 组合候选路线并调用路线工具。
- `agent/scorer.py`: 确定性评分与排序。
- `agent/explainer.py`: LLM 或模板生成推荐理由。
- `agent/planner_agent.py`: `PlanAgent.plan()` 主编排流程。
- `app/main.py`: FastAPI 服务入口。
