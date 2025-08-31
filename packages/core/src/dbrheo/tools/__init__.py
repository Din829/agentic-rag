"""
工具系统 - 通用Agent工具框架
遵循"工具极简，智能在Agent层"的设计原则
"""

from .base import Tool
from .registry import ToolRegistry

__all__ = [
    "Tool",
    "ToolRegistry"
]
