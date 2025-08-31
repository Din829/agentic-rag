"""
Grep工具 - 高效文件内容搜索
借鉴Gemini CLI的三层降级策略，确保高性能和兼容性
"""

import os
import re
import subprocess
import asyncio
from pathlib import Path
from typing import Dict, Any, Optional, List, Tuple
from dataclasses import dataclass
from enum import Enum

from ..types.tool_types import ToolResult
from ..types.core_types import AbortSignal
from .base import Tool
from ..config.base import AgentConfig
from ..utils.debug_logger import DebugLogger, log_info


class SearchEngine(Enum):
    """搜索引擎优先级"""
    RIPGREP = "ripgrep"      # 最快
    GIT_GREP = "git_grep"    # Git仓库中快速
    SYSTEM_GREP = "grep"      # 系统grep
    PYTHON_RE = "python"      # Python正则（保底）


@dataclass
class GrepMatch:
    """搜索匹配结果"""
    file_path: str
    line_number: int
    line_content: str
    match_content: str
    context_before: List[str] = None
    context_after: List[str] = None


class GrepTool(Tool):
    """
    高效的文件内容搜索工具
    
    核心特性（参考Gemini CLI）：
    1. 多层降级策略：ripgrep > git grep > system grep > Python
    2. 智能结果展示：文件名+行号+匹配内容
    3. 上下文支持：显示匹配行的前后文
    4. 性能优化：自动选择最快的可用工具
    5. 安全限制：避免搜索二进制文件和超大文件
    """
    
    def __init__(self, config: AgentConfig, i18n=None):
        self._i18n = i18n
        
        super().__init__(
            name="grep",
            display_name=self._('grep_tool_name', default="内容搜索") if i18n else "内容搜索",
            description="""Search for patterns in files. MUCH faster than reading entire files with read_file.
Uses the fastest available search engine (ripgrep > git grep > grep > Python).
Returns file paths, line numbers, and matching content.
Best practice: Use grep when you know what to search for, not read_file.""",
            parameter_schema={
                "type": "object",
                "properties": {
                    "pattern": {
                        "type": "string",
                        "description": "Search pattern (supports regex)"
                    },
                    "path": {
                        "type": "string",
                        "description": "Path to search in (file or directory). Defaults to current directory",
                        "default": "."
                    },
                    "include": {
                        "type": "string",
                        "description": "Include only files matching this glob pattern (e.g., '*.py', '*.js')"
                    },
                    "exclude": {
                        "type": "string",
                        "description": "Exclude files/dirs matching this pattern (e.g., 'node_modules', '.git')"
                    },
                    "case_sensitive": {
                        "type": "boolean",
                        "description": "Case sensitive search",
                        "default": True
                    },
                    "context_lines": {
                        "type": "integer",
                        "description": "Number of context lines before and after match (0-10)",
                        "default": 0,
                        "minimum": 0,
                        "maximum": 10
                    },
                    "max_results": {
                        "type": "integer",
                        "description": "Maximum number of results to return",
                        "default": 100,
                        "minimum": 1,
                        "maximum": 1000
                    }
                },
                "required": ["pattern"]
            },
            is_output_markdown=True,
            should_summarize_display=True,
            i18n=i18n
        )
        self.config = config
        # 不再缓存引擎，每次根据目标路径动态检测
        
    def validate_tool_params(self, params: Dict[str, Any]) -> Optional[str]:
        """验证参数"""
        pattern = params.get("pattern", "")
        if not pattern:
            return self._('grep_pattern_empty', default="Search pattern cannot be empty")
        
        # 验证正则表达式
        try:
            re.compile(pattern)
        except re.error as e:
            return self._('grep_invalid_regex', default=f"Invalid regex pattern: {e}")
        
        # 验证路径
        path = params.get("path", ".")
        if not os.path.exists(path):
            return self._('grep_path_not_found', default=f"Path not found: {path}")
        
        return None
    
    async def execute(
        self,
        params: Dict[str, Any],
        signal: AbortSignal,
        update_output: Optional[Any] = None
    ) -> ToolResult:
        """执行搜索"""
        pattern = params.get("pattern")
        search_path = params.get("path", ".")
        include = params.get("include")
        exclude = params.get("exclude")
        case_sensitive = params.get("case_sensitive", True)
        context_lines = params.get("context_lines", 0)
        max_results = params.get("max_results", 100)
        
        # 检测所有可用的搜索引擎
        available_engines = await self._detect_available_engines(search_path)
        
        if not available_engines:
            return ToolResult(
                error=self._('grep_no_engine', default="No search engine available")
            )
        
        # 尝试每个引擎，直到成功（降级机制）
        last_error = None
        for engine in available_engines:
            if DebugLogger.should_log("DEBUG"):
                log_info("GrepTool", f"Trying search engine: {engine.value}")
            
            try:
                # 根据引擎执行搜索
                if engine == SearchEngine.RIPGREP:
                    matches = await self._search_with_ripgrep(
                        pattern, search_path, include, exclude, 
                        case_sensitive, context_lines, max_results, signal
                    )
                elif engine == SearchEngine.GIT_GREP:
                    matches = await self._search_with_git_grep(
                        pattern, search_path, include, exclude,
                        case_sensitive, context_lines, max_results, signal
                    )
                elif engine == SearchEngine.SYSTEM_GREP:
                    matches = await self._search_with_system_grep(
                        pattern, search_path, include, exclude,
                        case_sensitive, context_lines, max_results, signal
                    )
                else:  # Python fallback
                    matches = await self._search_with_python(
                        pattern, search_path, include, exclude,
                        case_sensitive, context_lines, max_results, signal
                    )
                
                # 成功执行，格式化结果并返回
                return self._format_results(matches, pattern, engine)
                
            except asyncio.CancelledError:
                # 用户取消，立即返回
                return ToolResult(
                    error=self._('grep_cancelled', default="Search cancelled by user")
                )
            except Exception as e:
                # 记录错误，尝试下一个引擎
                last_error = str(e)
                if DebugLogger.should_log("DEBUG"):
                    log_info("GrepTool", f"{engine.value} failed: {e}, trying next engine...")
                continue
        
        # 所有引擎都失败了
        return ToolResult(
            error=self._('grep_all_failed', default=f"All search engines failed. Last error: {last_error}")
        )
    
    async def _detect_available_engines(self, search_path: str) -> List[SearchEngine]:
        """检测所有可用引擎，返回按优先级排序的列表（支持降级）"""
        # 每次都重新检测，确保针对具体路径选择正确的引擎
        available_engines = []
        
        # 检查ripgrep（最快）
        if await self._is_command_available("rg"):
            available_engines.append(SearchEngine.RIPGREP)
        
        # 检查git grep（只在目标路径是git仓库时使用）
        if await self._is_git_repository(search_path):
            if await self._is_command_available("git"):
                available_engines.append(SearchEngine.GIT_GREP)
        
        # 检查系统grep
        if await self._is_command_available("grep"):
            available_engines.append(SearchEngine.SYSTEM_GREP)
        
        # Python总是可用（保底方案）
        available_engines.append(SearchEngine.PYTHON_RE)
        
        return available_engines
    
    async def _is_command_available(self, command: str) -> bool:
        """检查命令是否可用（跨平台）"""
        try:
            # Windows使用where，Unix使用which
            check_cmd = "where" if os.name == 'nt' else "which"
            result = await asyncio.create_subprocess_exec(
                check_cmd, command,
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL
            )
            await result.communicate()
            return result.returncode == 0
        except:
            return False
    
    async def _is_git_repository(self, path: str) -> bool:
        """检查是否在git仓库中"""
        try:
            git_dir = Path(path).resolve()
            while git_dir != git_dir.parent:
                if (git_dir / ".git").exists():
                    return True
                git_dir = git_dir.parent
            return False
        except:
            return False
    
    async def _search_with_ripgrep(
        self, pattern: str, path: str, include: Optional[str],
        exclude: Optional[str], case_sensitive: bool,
        context_lines: int, max_results: int, signal: AbortSignal
    ) -> List[GrepMatch]:
        """使用ripgrep搜索（最快）"""
        cmd = ["rg", "--line-number", "--no-heading", "--with-filename"]
        
        # 添加参数
        if not case_sensitive:
            cmd.append("-i")
        if context_lines > 0:
            cmd.extend(["-C", str(context_lines)])
        if include:
            cmd.extend(["--glob", include])
        if exclude:
            cmd.extend(["--glob", f"!{exclude}"])
        cmd.extend(["-m", str(max_results)])  # 限制结果数
        
        # 添加搜索模式和路径
        cmd.extend([pattern, path])
        
        # 执行命令
        return await self._execute_command_and_parse(cmd, signal)
    
    async def _search_with_git_grep(
        self, pattern: str, path: str, include: Optional[str],
        exclude: Optional[str], case_sensitive: bool,
        context_lines: int, max_results: int, signal: AbortSignal
    ) -> List[GrepMatch]:
        """使用git grep搜索（在git仓库中快速）"""
        cmd = ["git", "grep", "--line-number"]
        
        if not case_sensitive:
            cmd.append("-i")
        if context_lines > 0:
            cmd.extend([f"-C{context_lines}"])
        
        # 添加搜索模式（必须在选项之后，pathspec之前）
        cmd.append(pattern)
        
        # 添加pathspec（必须在pattern之后）
        if include:
            # git grep使用pathspec，include已经包含了通配符（如*.py）
            cmd.extend(["--", include])
        else:
            cmd.extend(["--", "."])
        
        return await self._execute_command_and_parse(cmd, signal, max_results)
    
    async def _search_with_system_grep(
        self, pattern: str, path: str, include: Optional[str],
        exclude: Optional[str], case_sensitive: bool,
        context_lines: int, max_results: int, signal: AbortSignal
    ) -> List[GrepMatch]:
        """使用系统grep搜索"""
        cmd = ["grep", "-r", "-n", "-H"]  # 递归、行号、文件名
        
        if not case_sensitive:
            cmd.append("-i")
        if context_lines > 0:
            cmd.extend([f"-C{context_lines}"])
        if include:
            cmd.extend(["--include", include])
        if exclude:
            cmd.extend(["--exclude", exclude])
        # 只在用户没有指定exclude时，才添加默认排除
        else:
            # 默认排除常见的无关目录
            cmd.extend(["--exclude-dir", ".git", "--exclude-dir", "node_modules"])
        
        cmd.extend([pattern, path])
        
        return await self._execute_command_and_parse(cmd, signal, max_results)
    
    async def _search_with_python(
        self, pattern: str, path: str, include: Optional[str],
        exclude: Optional[str], case_sensitive: bool,
        context_lines: int, max_results: int, signal: AbortSignal
    ) -> List[GrepMatch]:
        """使用Python正则搜索（保底方案）"""
        import fnmatch
        
        matches = []
        regex_flags = 0 if case_sensitive else re.IGNORECASE
        pattern_re = re.compile(pattern, regex_flags)
        
        # 确定搜索路径
        search_path = Path(path).resolve()
        
        # 文件匹配模式
        include_pattern = include or "*"
        exclude_patterns = []
        if exclude:
            exclude_patterns = exclude.split(",")
        
        # 递归搜索文件
        files_to_search = []
        if search_path.is_file():
            files_to_search = [search_path]
        else:
            for root, dirs, files in os.walk(search_path):
                # 排除特定目录
                dirs[:] = [d for d in dirs if d not in ['.git', '__pycache__', 'node_modules']]
                
                for file in files:
                    # 检查是否匹配include模式
                    if not fnmatch.fnmatch(file, include_pattern):
                        continue
                    
                    # 检查是否需要排除
                    should_exclude = False
                    for exc_pattern in exclude_patterns:
                        if fnmatch.fnmatch(file, exc_pattern):
                            should_exclude = True
                            break
                    
                    if not should_exclude:
                        files_to_search.append(Path(root) / file)
                
                # 检查是否超过文件数限制
                if len(files_to_search) > 1000:
                    break
        
        # 搜索每个文件
        for file_path in files_to_search:
            if signal and signal.aborted:
                break
            
            try:
                # 跳过二进制文件
                if self._is_binary_file(file_path):
                    continue
                
                # 读取文件并搜索
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    lines = f.readlines()
                    
                for i, line in enumerate(lines, 1):
                    if pattern_re.search(line):
                        match = GrepMatch(
                            file_path=str(file_path),
                            line_number=i,
                            line_content=line.rstrip('\n'),
                            match_content=line.rstrip('\n')
                        )
                        
                        # 添加上下文
                        if context_lines > 0:
                            start = max(0, i - context_lines - 1)
                            end = min(len(lines), i + context_lines)
                            match.context_before = [l.rstrip('\n') for l in lines[start:i-1]]
                            match.context_after = [l.rstrip('\n') for l in lines[i:end]]
                        
                        matches.append(match)
                        
                        if len(matches) >= max_results:
                            return matches
            except Exception as e:
                # 忽略无法读取的文件
                if DebugLogger.should_log("DEBUG"):
                    log_info("GrepTool", f"Skip file {file_path}: {e}")
                continue
        
        return matches
    
    async def _execute_command_and_parse(
        self, cmd: List[str], signal: AbortSignal, 
        max_results: int = 100
    ) -> List[GrepMatch]:
        """执行命令并解析输出"""
        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            # 等待命令完成
            stdout, stderr = await process.communicate()
            
            # 处理错误输出
            if process.returncode not in [0, 1]:  # 0=成功, 1=没有匹配
                if stderr:
                    stderr_text = stderr.decode('utf-8', errors='ignore')
                    
                    # 过滤掉常见的无害错误（参考Gemini CLI）
                    if any(ignore in stderr_text.lower() for ignore in [
                        'permission denied',
                        'is a directory',
                        'binary file',
                        'no such file or directory',  # 文件在搜索过程中被删除
                        'outside repository',  # git grep在非仓库路径
                        'not a git repository'  # git grep在非仓库路径
                    ]):
                        if DebugLogger.should_log("DEBUG"):
                            log_info("GrepTool", f"Ignoring common error: {stderr_text[:100]}")
                    else:
                        # 严重错误，抛出异常触发降级
                        raise Exception(f"Command failed: {stderr_text}")
            
            # 解析输出（即使有一些被忽略的错误）
            return self._parse_grep_output(stdout.decode('utf-8', errors='ignore'), max_results)
            
        except Exception as e:
            if DebugLogger.should_log("DEBUG"):
                log_info("GrepTool", f"Command execution failed: {e}")
            raise
    
    def _parse_grep_output(self, output: str, max_results: int) -> List[GrepMatch]:
        """解析grep输出格式: filename:line_number:content"""
        matches = []
        lines = output.strip().split('\n')
        
        for line in lines[:max_results]:
            if not line:
                continue
            
            # 解析格式: file:line_num:content
            parts = line.split(':', 2)
            if len(parts) >= 3:
                try:
                    match = GrepMatch(
                        file_path=parts[0],
                        line_number=int(parts[1]),
                        line_content=parts[2],
                        match_content=parts[2]
                    )
                    matches.append(match)
                except ValueError:
                    # 忽略解析错误的行
                    continue
        
        return matches
    
    def _is_binary_file(self, file_path: Path) -> bool:
        """检查是否为二进制文件"""
        try:
            with open(file_path, 'rb') as f:
                chunk = f.read(1024)
                # 检查是否包含空字节
                return b'\x00' in chunk
        except:
            return True
    
    def _format_results(self, matches: List[GrepMatch], pattern: str, engine: SearchEngine) -> ToolResult:
        """格式化搜索结果"""
        if not matches:
            return ToolResult(
                summary=self._('grep_no_matches', default=f"No matches found for pattern: {pattern}"),
                llm_content=self._('grep_no_matches_llm', default=f"No matches found for pattern '{pattern}'"),
                return_display=self._('grep_no_matches_display', default="🔍 No matches found")
            )
        
        # 统计结果
        file_count = len(set(m.file_path for m in matches))
        
        # 构建LLM内容（详细）
        llm_lines = [f"Found {len(matches)} matches in {file_count} files:"]
        
        # 按文件分组显示
        matches_by_file = {}
        for match in matches:
            if match.file_path not in matches_by_file:
                matches_by_file[match.file_path] = []
            matches_by_file[match.file_path].append(match)
        
        for file_path, file_matches in matches_by_file.items():
            llm_lines.append(f"\n{file_path}:")
            for match in file_matches[:10]:  # 每个文件最多显示10个匹配
                llm_lines.append(f"  {match.line_number}: {match.line_content}")
            if len(file_matches) > 10:
                llm_lines.append(f"  ... and {len(file_matches) - 10} more matches")
        
        # 构建显示内容（简洁）
        display_lines = [
            f"🔍 Pattern: {pattern}",
            f"⚡ Engine: {engine.value}",
            f"📊 Results: {len(matches)} matches in {file_count} files"
        ]
        
        # 显示前几个匹配作为示例
        display_lines.append("\n📍 Sample matches:")
        for match in matches[:5]:
            rel_path = os.path.relpath(match.file_path)
            display_lines.append(f"  {rel_path}:{match.line_number}")
        
        if len(matches) > 5:
            display_lines.append(f"  ... and {len(matches) - 5} more")
        
        return ToolResult(
            summary=self._('grep_summary', default=f"Found {len(matches)} matches for '{pattern}' in {file_count} files"),
            llm_content="\n".join(llm_lines),
            return_display="\n".join(display_lines)
        )
    
    def get_description(self, params: Dict[str, Any]) -> str:
        """获取操作描述"""
        pattern = params.get("pattern", "")
        path = params.get("path", ".")
        include = params.get("include", "")
        
        desc = self._('grep_description', default=f"Search for '{pattern}'")
        if path != ".":
            desc += f" in {path}"
        if include:
            desc += f" (files: {include})"
        
        return desc
    
    async def should_confirm_execute(self, params: Dict[str, Any], signal: AbortSignal) -> Optional[Any]:
        """搜索通常不需要确认"""
        return False