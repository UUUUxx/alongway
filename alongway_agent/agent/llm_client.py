from __future__ import annotations

import json
import re
from abc import ABC, abstractmethod
from typing import Optional

import httpx

from agent.call_logger import log_call
from agent.models import AlternativePlanSummary, CandidatePlan, UserPreferences


class LLMClient(ABC):
    @abstractmethod
    async def parse_intent(
        self,
        user_query: str,
        budget: Optional[float],
        preferences: UserPreferences,
    ) -> Optional[dict]:
        raise NotImplementedError

    @abstractmethod
    async def generate_explanation(
        self,
        user_query: str,
        selected_plan: CandidatePlan,
        alternative_plans: list[AlternativePlanSummary],
    ) -> Optional[dict]:
        raise NotImplementedError


class MockLLMClient(LLMClient):
    async def parse_intent(
        self,
        user_query: str,
        budget: Optional[float],
        preferences: UserPreferences,
    ) -> Optional[dict]:
        return None

    async def generate_explanation(
        self,
        user_query: str,
        selected_plan: CandidatePlan,
        alternative_plans: list[AlternativePlanSummary],
    ) -> Optional[dict]:
        return None


class StepFunLLMClient(LLMClient):
    def __init__(
        self,
        api_key: str,
        base_url: str = "https://api.stepfun.com/v1",
        model: str = "step-3.5-flash",
        timeout_seconds: float = 20.0,
    ) -> None:
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout_seconds = timeout_seconds

    async def parse_intent(
        self,
        user_query: str,
        budget: Optional[float],
        preferences: UserPreferences,
    ) -> Optional[dict]:
        if not self.api_key:
            return None

        payload = {
            "model": self.model,
            "temperature": 0.0,
            "max_tokens": 800,
            "stop": ["\n\n\n", "```"],
            "messages": [
                {
                    "role": "system",
                    "content": _INTENT_SYSTEM_PROMPT,
                },
                {
                    "role": "user",
                    "content": json.dumps(
                        {
                            "user_query": user_query,
                            "budget": budget,
                            "preferences": preferences.model_dump(),
                        },
                        ensure_ascii=False,
                    ),
                },
            ],
        }

        try:
            async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                response = await client.post(
                    f"{self.base_url}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                    },
                    json=payload,
                )
                response.raise_for_status()
                data = response.json()
        except Exception as exc:
            log_call(
                "agent.stepfun.parse_intent.error",
                request={"model": self.model, "user_query": user_query, "budget": budget},
                error=str(exc),
            )
            raise

        content = (
            data.get("choices", [{}])[0]
            .get("message", {})
            .get("content", "")
        )
        parsed = _loads_json_object(content)
        log_call(
            "agent.stepfun.parse_intent.result",
            request={"model": self.model, "user_query": user_query, "budget": budget},
            result={"parsed": parsed, "raw_content": content},
        )
        return parsed

    async def generate_explanation(
        self,
        user_query: str,
        selected_plan: CandidatePlan,
        alternative_plans: list[AlternativePlanSummary],
    ) -> Optional[dict]:
        return None


def _loads_json_object(content: str) -> Optional[dict]:
    text = content.strip()
    if not text:
        return None
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    if not text.startswith("{"):
        match = re.search(r"\{.*\}", text, flags=re.S)
        if not match:
            return None
        text = match.group(0)
    parsed = json.loads(text)
    return parsed if isinstance(parsed, dict) else None


_INTENT_SYSTEM_PROMPT = """
你是顺路规划 Agent 的意图解析器。只输出一个 JSON 对象，不要解释。

字段:
- start_text: 用户明确说出的起点；没有则 null。
- end_text: 用户明确说出的最终目的地；没有则 null。
- budget: 数字或 null。用户说\"20元以内/预算20\"等要提取为 20。
- preferences: 原样保留用户传入偏好，只有用户文本明确表达时才覆盖为 true。
- tasks: 数组，按用户希望顺路完成的顺序排列。

tasks item:
- task_id: 用 \"task_1\"、\"task_2\"。
- type: 只能是 pickup_express、buy_drink、eat_meal、visit_place、custom。
- raw_text: 用户原话中的任务短语。
- category: express、drink、food、movie、board_game、hair、nail、entertainment、study、life、custom。
- specific_place_name: 用户点名的商家/地点，例如\"星巴克\"\"韵苑菜鸟驿站\"；没有则 null。
- source_keywords: 搜索词数组。若用户点名具体地点，第一项必须是该地点名；若只说大类，给出大类和同义词。
- budget: 该任务预算或 null。
- required: true。

规则:
1. \"想喝星巴克\"必须保留 specific_place_name=星巴克，不要泛化成咖啡。
2. \"想吃韩餐\"输出 food 类，source_keywords 包含 韩餐、韩国料理。
3. \"去某某菜鸟驿站/某某快递柜\"保留具体地点名。
4. \"去图书馆/教学楼\"如果是最终目的地，不要再作为顺路任务；如果是中途想去，则作为 visit_place。
5. 起点没说就 start_text=null，不要编造。
6. 终点没说就 end_text=null，不要编造。
7. \"看电影/看场电影/去影院\"输出独立任务 category=movie，source_keywords 包含 电影院、影城、影院、电影票。
8. \"玩桌游/桌游吧/剧本杀\"输出独立任务 category=board_game，source_keywords 包含 桌游店、桌游吧、桌游、剧本杀。
9. \"理发/剪头发/做头发\"输出独立任务 category=hair，source_keywords 包含 理发店、美发、发型设计、沙龙。
10. \"美甲/做指甲\"输出独立任务 category=nail，source_keywords 包含 美甲店、美甲、美睫美甲。
11. 用户说多个事项时必须拆成多个 tasks，例如\"想剪个头发，再看场电影\"应输出 hair 和 movie 两个任务，不要合并成 entertainment/custom 一个任务。
12. 【重要】不同品类的食物必须拆成独立 task，每个 task 的 source_keywords 只能包含同一品类的近义词，严禁混入其他品类:
    - 错误: source_keywords=[\"烤鱼\",\"烧烤\",\"烤肉\"]（含不同品类）-> 正确: source_keywords=[\"烤鱼\",\"鱼火锅\"]
    - 错误: 把\"韩餐和烧烤\"合并成一个 task -> 正确: task_1: source_keywords=[\"韩餐\",\"韩国料理\"], task_2: source_keywords=[\"烧烤\",\"烤肉\"]
    - \"吃早餐/吃早饭\" -> source_keywords=[\"早餐\",\"早点\",\"小吃\"]
    - \"吃午餐/吃中饭\" -> source_keywords=[\"简餐\",\"午餐\",\"食堂\"]
    - \"吃晚餐/吃夜宵\" -> source_keywords=[\"晚餐\",\"夜宵\",\"餐厅\"]
13. source_keywords 中不要放过于泛化的词（如\"餐厅\"\"吃饭\"\"便利店\"），除非该品类本身就是泛化查询。
""".strip()
