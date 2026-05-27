from __future__ import annotations

from enum import Enum
from typing import List, Optional


class ErrorCode(str, Enum):
    MISSING_USER_QUERY = "MISSING_USER_QUERY"
    MISSING_LOCATION = "MISSING_LOCATION"
    INTENT_PARSE_FAILED = "INTENT_PARSE_FAILED"
    NO_TASK_PARSED = "NO_TASK_PARSED"
    NO_POI_FOR_REQUIRED_TASK = "NO_POI_FOR_REQUIRED_TASK"
    NO_DEAL_MATCHED = "NO_DEAL_MATCHED"
    NO_ROUTE_FOUND = "NO_ROUTE_FOUND"
    NO_VALID_PLAN = "NO_VALID_PLAN"
    BACKEND_TOOL_ERROR = "BACKEND_TOOL_ERROR"
    LLM_ERROR = "LLM_ERROR"


class AgentError(Exception):
    def __init__(
        self,
        code: ErrorCode,
        message: str,
        *,
        missing_fields: Optional[List[str]] = None,
        fallback_suggestions: Optional[List[str]] = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.missing_fields = missing_fields or []
        self.fallback_suggestions = fallback_suggestions or []
