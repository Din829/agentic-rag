"""
ToolRegistry - 增强的工具注册表
管理工具的注册、发现和获取，支持基于能力的智能查询
"""

from typing import Dict, List, Optional, Set, Any
from enum import Enum
from dataclasses import dataclass

from .base import Tool
from ..config.base import AgentConfig
from ..core.memory import MemoryManager, MemoryTool


class ToolCapability(Enum):
    """工具能力枚举 - 支持Agent基于能力而非名称选择工具"""
    # 数据操作能力
    QUERY = "query"                    # 查询数据
    MODIFY = "modify"                  # 修改数据
    SCHEMA_CHANGE = "schema_change"    # 变更表结构
    
    # 探索能力
    EXPLORE = "explore"                # 探索数据库
    ANALYZE = "analyze"                # 分析数据
    PROFILE = "profile"                # 性能分析
    
    # 管理能力
    BACKUP = "backup"                  # 备份数据
    RESTORE = "restore"                # 恢复数据
    OPTIMIZE = "optimize"              # 优化性能
    
    # 辅助能力
    MEMORY = "memory"                  # 记忆管理
    EXPORT = "export"                  # 导出数据
    IMPORT = "import"                  # 导入数据
    
    # 文件操作能力
    READ = "read"                      # 读取文件
    WRITE = "write"                    # 写入文件
    
    # 网络能力
    SEARCH = "search"                  # 网络搜索
    
    # 安全能力
    AUDIT = "audit"                    # 审计日志
    PERMISSION = "permission"          # 权限管理
    
    # 外部集成能力
    EXTERNAL = "external"              # 外部工具
    MCP = "mcp"                        # MCP协议工具
    CODE_EXECUTION = "code_execution"  # 代码执行
    WEB_ACCESS = "web_access"          # Web访问
    FILE_OPERATION = "file_operation"  # 文件操作


@dataclass
class ToolInfo:
    """工具信息扩展 - 包含能力标签和元数据"""
    tool: Tool
    capabilities: Set[ToolCapability]
    tags: Set[str]                     # 额外的标签
    priority: int = 50                 # 优先级（0-100）
    metadata: Dict[str, Any] = None    # 额外元数据


class ToolRegistry:
    """
    增强的数据库工具注册表
    - 工具注册和管理
    - 基于能力的智能查询
    - 动态工具发现和加载
    - 工具优先级管理
    """
    
    def __init__(self, config: AgentConfig):
        self.config = config
        self.tools: Dict[str, ToolInfo] = {}
        self._capability_index: Dict[ToolCapability, Set[str]] = {}
        self._tag_index: Dict[str, Set[str]] = {}
        
        # 初始化记忆管理器
        self.memory_manager = MemoryManager(config)
        
        # 从config获取i18n（如果有）
        self._i18n = config.get('i18n', None)
        
        # MCP registry (lazy initialization)
        self._mcp_registry = None
        
        # 注册核心工具
        self._register_core_tools()
        
        # 注册项目特定工具（如果存在）
        self._register_project_tools()
        
    def _create_tool(self, tool_class, *args, **kwargs):
        """
        灵活创建工具实例，自动处理i18n参数
        保持最小侵入性：如果工具不支持i18n，则不传递
        """
        try:
            # 尝试传递i18n参数
            return tool_class(self.config, *args, i18n=self._i18n, **kwargs)
        except TypeError:
            # 如果失败，则不传递i18n参数
            return tool_class(self.config, *args, **kwargs)
    
    def _register_core_tools(self):
        """注册核心工具 - 泛用化Agent基础工具集"""
        # 只导入通用工具，移除数据库特定工具
        from .file_read_tool import FileReadTool
        from .file_write_tool import FileWriteTool
        from .web_search_tool import WebSearchTool
        from .web_fetch_tool import WebFetchTool
        from .directory_list_tool import DirectoryListTool
        from .code_execution_tool import CodeExecutionTool
        from .shell_tool import ShellTool
        from .grep_tool import GrepTool
        from .glob_tool import GlobTool
        
        # 注册记忆工具（通用功能，保留）
        memory_tool = MemoryTool(self.memory_manager)
        self.register_tool(
            tool=memory_tool,
            capabilities={ToolCapability.MEMORY},
            tags={"memory", "save", "knowledge", "auxiliary"},
            priority=70
        )
        
        # 注册文件读取工具
        file_read_tool = self._create_tool(FileReadTool)
        self.register_tool(
            tool=file_read_tool,
            capabilities={
                ToolCapability.READ,
                ToolCapability.IMPORT
            },
            tags={"file", "read", "import", "csv", "json", "auxiliary"},
            priority=75
        )
        
        # 注册文件写入工具
        file_write_tool = self._create_tool(FileWriteTool)
        self.register_tool(
            tool=file_write_tool,
            capabilities={
                ToolCapability.WRITE,
                ToolCapability.EXPORT
            },
            tags={"file", "write", "export", "report", "csv", "json", "auxiliary"},
            priority=75
        )
        
        # 注册网络搜索工具
        web_search_tool = self._create_tool(WebSearchTool)
        self.register_tool(
            tool=web_search_tool,
            capabilities={
                ToolCapability.SEARCH,
                ToolCapability.EXPLORE
            },
            tags={"web", "search", "online", "documentation", "auxiliary"},
            priority=65
        )
        
        # 注册网页内容获取工具
        web_fetch_tool = self._create_tool(WebFetchTool)
        self.register_tool(
            tool=web_fetch_tool,
            capabilities={
                ToolCapability.READ,
                ToolCapability.SEARCH,
                ToolCapability.EXPLORE
            },
            tags={"web", "fetch", "content", "html", "auxiliary"},
            priority=70
        )
        
        # 注册目录浏览工具
        directory_list_tool = self._create_tool(DirectoryListTool)
        self.register_tool(
            tool=directory_list_tool,
            capabilities={
                ToolCapability.READ,
                ToolCapability.EXPLORE
            },
            tags={"directory", "list", "browse", "files", "filesystem", "core"},
            priority=80
        )
        
        # 注册代码执行工具
        code_execution_tool = self._create_tool(CodeExecutionTool)
        self.register_tool(
            tool=code_execution_tool,
            capabilities={
                ToolCapability.ANALYZE,
                ToolCapability.MODIFY,
                ToolCapability.CODE_EXECUTION
            },
            tags={"code", "execute", "python", "javascript", "shell", "analysis", "automation", "core"},
            priority=88  # 高优先级，因为很实用
        )
        
        # 注册Shell执行工具
        shell_tool = self._create_tool(ShellTool)
        self.register_tool(
            tool=shell_tool,
            capabilities={
                ToolCapability.MODIFY,    # 系统修改能力
                ToolCapability.EXPLORE,   # 系统探索
                ToolCapability.ANALYZE,   # 日志分析等
                ToolCapability.FILE_OPERATION  # 文件操作
            },
            tags={"shell", "system", "command", "management", "monitoring", "core"},
            priority=85
        )
        
        # 注册Grep搜索工具（高优先级，性能工具）
        grep_tool = self._create_tool(GrepTool)
        self.register_tool(
            tool=grep_tool,
            capabilities={
                ToolCapability.SEARCH,     # 搜索能力
                ToolCapability.ANALYZE,    # 分析能力
                ToolCapability.EXPLORE     # 探索能力
            },
            tags={"grep", "search", "pattern", "regex", "fast", "content", "core"},
            priority=90  # 高优先级，推荐使用
        )
        
        # 注册Glob文件发现工具（高优先级，性能工具）
        glob_tool = self._create_tool(GlobTool)
        self.register_tool(
            tool=glob_tool,
            capabilities={
                ToolCapability.EXPLORE,    # 探索能力
                ToolCapability.SEARCH,     # 搜索能力
                ToolCapability.FILE_OPERATION  # 文件操作
            },
            tags={"glob", "files", "find", "pattern", "discovery", "fast", "core"},
            priority=90  # 高优先级，推荐使用
        )
    
    def _register_project_tools(self):
        """
        注册项目特定工具
        自动扫描项目根目录的 project_tools 文件夹
        """
        import importlib
        import inspect
        import sys
        from pathlib import Path
        from ..utils.debug_logger import log_info
        
        # 查找项目根目录（包含 .env 或 PROJECT.md 的目录）
        current = Path.cwd()
        project_root = None
        
        # 向上查找最多10级
        for _ in range(10):
            if (current / "project_tools").exists():
                project_root = current
                break
            if (current / ".env").exists() or (current / "PROJECT.md").exists():
                if (current / "project_tools").exists():
                    project_root = current
                    break
            if current.parent == current:
                break
            current = current.parent
        
        if not project_root or not (project_root / "project_tools").exists():
            # 没有找到 project_tools 文件夹，正常返回
            return
        
        tools_dir = project_root / "project_tools"
        log_info("ToolRegistry", f"Found project_tools directory: {tools_dir}")
        
        # 将 project_tools 目录添加到 Python 路径
        if str(project_root) not in sys.path:
            sys.path.insert(0, str(project_root))
        
        # 扫描 project_tools 目录中的所有 .py 文件
        for py_file in tools_dir.glob("*.py"):
            if py_file.name.startswith("_"):
                continue  # 跳过私有文件
                
            module_name = f"project_tools.{py_file.stem}"
            
            try:
                # 动态导入模块
                module = importlib.import_module(module_name)
                
                # 查找所有继承自 Tool 的类
                for name, obj in inspect.getmembers(module):
                    if (inspect.isclass(obj) and 
                        issubclass(obj, Tool) and 
                        obj != Tool and
                        not name.startswith("_")):
                        
                        try:
                            # 创建工具实例
                            tool_instance = self._create_tool(obj)
                            
                            # 自动注册工具
                            # 使用默认的能力和标签
                            self.register_tool(
                                tool=tool_instance,
                                capabilities={ToolCapability.EXTERNAL},  # 项目工具默认标记为外部工具
                                tags={"project", "custom", py_file.stem},
                                priority=60  # 项目工具的默认优先级
                            )
                            
                            log_info("ToolRegistry", f"Registered project tool: {tool_instance.name}")
                            
                        except Exception as e:
                            log_info("ToolRegistry", f"Failed to register tool {name}: {str(e)}")
                            
            except Exception as e:
                log_info("ToolRegistry", f"Failed to import module {module_name}: {str(e)}")
        
    def register_tool(
        self,
        tool: Tool,
        capabilities: Set[ToolCapability],
        tags: Optional[Set[str]] = None,
        priority: int = 50,
        metadata: Optional[Dict[str, Any]] = None
    ):
        """
        注册工具及其能力信息
        
        Args:
            tool: 工具实例
            capabilities: 工具具备的能力集合
            tags: 额外的标签
            priority: 优先级（0-100）
            metadata: 额外元数据
        """
        tool_info = ToolInfo(
            tool=tool,
            capabilities=capabilities,
            tags=tags or set(),
            priority=priority,
            metadata=metadata or {}
        )
        
        # 注册到主索引
        self.tools[tool.name] = tool_info
        
        # 更新能力索引
        for capability in capabilities:
            if capability not in self._capability_index:
                self._capability_index[capability] = set()
            self._capability_index[capability].add(tool.name)
            
        # 更新标签索引
        for tag in tool_info.tags:
            if tag not in self._tag_index:
                self._tag_index[tag] = set()
            self._tag_index[tag].add(tool.name)
            
    def get_tool(self, name: str) -> Optional[Tool]:
        """根据名称获取工具"""
        tool_info = self.tools.get(name)
        return tool_info.tool if tool_info else None
        
    def get_all_tools(self) -> List[Tool]:
        """获取所有已注册的工具"""
        return [info.tool for info in self.tools.values()]
        
    def get_gemini_function_declarations(self) -> List[Dict]:
        """获取所有工具的函数声明 - 供Gemini API使用"""
        # 按优先级排序
        sorted_tools = sorted(
            self.tools.values(),
            key=lambda x: x.priority,
            reverse=True
        )
        return [info.tool.schema for info in sorted_tools]
        
    def get_tools_by_capability(
        self, 
        capability: ToolCapability,
        min_priority: int = 0
    ) -> List[Tool]:
        """
        根据能力获取工具 - 支持Agent基于能力选择工具
        
        Args:
            capability: 所需能力
            min_priority: 最低优先级要求
            
        Returns:
            符合条件的工具列表，按优先级排序
        """
        tool_names = self._capability_index.get(capability, set())
        
        # 过滤并排序
        matching_tools = []
        for name in tool_names:
            tool_info = self.tools[name]
            if tool_info.priority >= min_priority:
                matching_tools.append(tool_info)
                
        # 按优先级降序排序
        matching_tools.sort(key=lambda x: x.priority, reverse=True)
        
        return [info.tool for info in matching_tools]
        
    def get_tools_by_capabilities(
        self,
        capabilities: List[ToolCapability],
        match_all: bool = False
    ) -> List[Tool]:
        """
        根据多个能力获取工具
        
        Args:
            capabilities: 能力列表
            match_all: True表示必须具备所有能力，False表示具备任一能力即可
            
        Returns:
            符合条件的工具列表
        """
        if not capabilities:
            return []
            
        # 获取每个能力对应的工具集合
        capability_tools = [
            self._capability_index.get(cap, set())
            for cap in capabilities
        ]
        
        # 根据匹配模式计算结果
        if match_all:
            # 交集：必须具备所有能力
            result_names = set.intersection(*capability_tools) if capability_tools else set()
        else:
            # 并集：具备任一能力即可
            result_names = set.union(*capability_tools) if capability_tools else set()
            
        # 获取工具信息并排序
        results = [self.tools[name] for name in result_names]
        results.sort(key=lambda x: x.priority, reverse=True)
        
        return [info.tool for info in results]
        
    def get_tools_by_tag(self, tag: str) -> List[Tool]:
        """根据标签获取工具"""
        tool_names = self._tag_index.get(tag, set())
        
        # 获取工具信息并排序
        results = [self.tools[name] for name in tool_names]
        results.sort(key=lambda x: x.priority, reverse=True)
        
        return [info.tool for info in results]
        
    def search_tools(
        self,
        query: str,
        capabilities: Optional[List[ToolCapability]] = None,
        tags: Optional[List[str]] = None
    ) -> List[Tool]:
        """
        智能搜索工具 - 支持文本搜索和过滤
        
        Args:
            query: 搜索关键词（在名称、描述中搜索）
            capabilities: 能力过滤条件
            tags: 标签过滤条件
            
        Returns:
            匹配的工具列表
        """
        results = []
        query_lower = query.lower() if query else ""
        
        for tool_info in self.tools.values():
            # 文本匹配
            if query and not (
                query_lower in tool_info.tool.name.lower() or
                query_lower in tool_info.tool.description.lower()
            ):
                continue
                
            # 能力过滤
            if capabilities:
                if not any(cap in tool_info.capabilities for cap in capabilities):
                    continue
                    
            # 标签过滤
            if tags:
                if not any(tag in tool_info.tags for tag in tags):
                    continue
                    
            results.append(tool_info)
            
        # 按优先级排序
        results.sort(key=lambda x: x.priority, reverse=True)
        
        return [info.tool for info in results]
        
    def get_capability_summary(self) -> Dict[str, List[str]]:
        """获取能力摘要 - 显示每个能力有哪些工具"""
        summary = {}
        
        for capability in ToolCapability:
            tools = self.get_tools_by_capability(capability)
            if tools:
                summary[capability.value] = [
                    f"{tool.name} (p:{self.tools[tool.name].priority})"
                    for tool in tools
                ]
                
        return summary
        
    def get_tool_info(self, name: str) -> Optional[ToolInfo]:
        """获取工具的完整信息"""
        return self.tools.get(name)
        
    def get_function_declarations(self) -> List[Dict[str, Any]]:
        """
        获取所有工具的函数声明 - 供Gemini API使用
        完全对齐Gemini CLI的设计：让AI基于工具描述自主选择
        
        Returns:
            工具函数声明列表，用于Gemini API调用
        """
        from ..utils.parameter_sanitizer import sanitize_parameters
        
        declarations = []
        
        # 按优先级排序工具
        sorted_tools = sorted(
            self.tools.values(),
            key=lambda x: x.priority,
            reverse=True
        )
        
        for tool_info in sorted_tools:
            tool = tool_info.tool
            # 清理参数模式，移除不支持的字段
            cleaned_parameters = sanitize_parameters(tool.parameter_schema)
            
            declarations.append({
                "name": tool.name,
                "description": tool.description,
                "parameters": cleaned_parameters
            })
            
        return declarations
    
    async def initialize_mcp(self):
        """
        初始化 MCP 支持（异步方法）
        最小侵入性设计：只在需要时加载 MCP 模块
        """
        try:
            # 动态导入 MCP 模块（避免强依赖）
            from .mcp import MCPRegistry
            
            # 创建 MCP 注册表
            self._mcp_registry = MCPRegistry(self.config)
            
            # 初始化并注册 MCP 工具
            await self._mcp_registry.initialize(self)
            
            return True
        except ImportError:
            # MCP 模块不存在或依赖未安装，静默失败
            return False
        except Exception as e:
            # 其他错误，记录但不中断系统
            import logging
            logging.warning(f"Failed to initialize MCP: {e}")
            return False
    
    def get_mcp_registry(self):
        """获取 MCP 注册表（如果已初始化）"""
        return self._mcp_registry