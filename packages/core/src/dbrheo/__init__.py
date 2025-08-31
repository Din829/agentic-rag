"""
DbRheo数据库Agent核心包
导出主要API供外部使用 - 基于Gemini CLI架构设计
"""

# 核心组件
from .core.client import AgentClient
from .core.chat import AgentChat
from .core.turn import AgentTurn
from .core.scheduler import ToolScheduler
from .core.prompts import PromptManager

# 工具系统
from .tools.registry import ToolRegistry
from .tools.base import Tool

# 服务层
from .services.gemini_service_new import GeminiService

# 监控遥测
from .telemetry.tracer import AgentTracer
from .telemetry.metrics import AgentMetrics
from .telemetry.logger import AgentLogger

# 配置
from .config.base import AgentConfig

# 工具函数
from .utils.retry import with_retry, RetryConfig
from .utils.errors import AgentError, ToolExecutionError

# 类型定义
from .types.core_types import *
from .types.tool_types import *

# API
from .api.app import create_app

__version__ = "1.0.0"
__all__ = [
    # 核心组件
    "AgentClient",
    "AgentChat",
    "AgentTurn",
    "ToolScheduler",
    "PromptManager",

    # 工具系统
    "ToolRegistry",
    "Tool",

    # 服务层
    "GeminiService",

    # 监控遥测
    "AgentTracer",
    "AgentMetrics",
    "AgentLogger",

    # 配置
    "AgentConfig",

    # 工具函数
    "with_retry",
    "RetryConfig",
    "AgentError",
    "ToolExecutionError",

    # API
    "create_app"
]
