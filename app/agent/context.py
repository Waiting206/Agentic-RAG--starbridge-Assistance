"""不会暴露给模型自行填写的Agent运行上下文。"""

from dataclasses import dataclass

from app.security import AccessRole


@dataclass(frozen=True)
class AgentContext:
    role: AccessRole = "customer"
