"""
Glob工具 - 智能文件发现
借鉴Gemini CLI的时间感知排序和高效文件匹配
"""

import os
import fnmatch
import time
from pathlib import Path
from typing import Dict, Any, Optional, List, Tuple
from dataclasses import dataclass
from datetime import datetime, timedelta
import asyncio

from ..types.tool_types import ToolResult
from ..types.core_types import AbortSignal
from .base import Tool
from ..config.base import AgentConfig
from ..utils.debug_logger import DebugLogger, log_info


@dataclass
class FileEntry:
    """文件条目信息"""
    path: str
    name: str
    size: int
    modified_time: float
    is_directory: bool
    relative_path: str


class GlobTool(Tool):
    """
    智能文件发现工具
    
    核心特性（参考Gemini CLI）：
    1. 时间感知排序：最近修改的文件优先
    2. 支持复杂glob模式：*, **, ?, []
    3. 智能忽略：自动识别.gitignore等
    4. 性能优化：限制搜索深度和结果数
    5. 跨平台兼容：处理不同系统的路径差异
    """
    
    # 默认忽略的目录（提高性能）
    DEFAULT_IGNORE_DIRS = {
        '.git', '__pycache__', 'node_modules', '.idea', '.vscode',
        'dist', 'build', 'target', '.cache', '.pytest_cache',
        'venv', 'env', '.env', 'virtualenv', '.venv'
    }
    
    # 默认忽略的文件模式
    DEFAULT_IGNORE_FILES = {
        '*.pyc', '*.pyo', '*.swp', '*.swo', '.DS_Store',
        'Thumbs.db', '*.class', '*.o', '*.so', '*.dll'
    }
    
    # 时间阈值（7天内的文件被认为是"最近的"）
    RECENCY_THRESHOLD_DAYS = 7
    
    def __init__(self, config: AgentConfig, i18n=None):
        self._i18n = i18n
        
        super().__init__(
            name="glob",
            display_name=self._('glob_tool_name', default="文件查找") if i18n else "文件查找",
            description="""Find files matching glob patterns. Returns files sorted by relevance (recent files first).
Supports patterns like '*.py', '**/*.js', 'src/**/test_*.py'.
MUCH faster than manually listing directories.
Best practice: Use glob to find files, not manual directory traversal.""",
            parameter_schema={
                "type": "object",
                "properties": {
                    "pattern": {
                        "type": "string",
                        "description": "Glob pattern to match files (e.g., '*.py', '**/*.js', 'src/**/*.ts')"
                    },
                    "path": {
                        "type": "string",
                        "description": "Base path to search from. Defaults to current directory",
                        "default": "."
                    },
                    "case_sensitive": {
                        "type": "boolean",
                        "description": "Case sensitive matching",
                        "default": True
                    },
                    "include_dirs": {
                        "type": "boolean",
                        "description": "Include directories in results",
                        "default": False
                    },
                    "respect_gitignore": {
                        "type": "boolean",
                        "description": "Respect .gitignore rules",
                        "default": True
                    },
                    "max_results": {
                        "type": "integer",
                        "description": "Maximum number of results to return",
                        "default": 100,
                        "minimum": 1,
                        "maximum": 1000
                    },
                    "max_depth": {
                        "type": "integer",
                        "description": "Maximum directory depth to search",
                        "default": 10,
                        "minimum": 1,
                        "maximum": 20
                    }
                },
                "required": ["pattern"]
            },
            is_output_markdown=True,
            should_summarize_display=True,
            i18n=i18n
        )
        self.config = config
        self._gitignore_cache = {}
    
    def validate_tool_params(self, params: Dict[str, Any]) -> Optional[str]:
        """验证参数"""
        pattern = params.get("pattern", "")
        if not pattern:
            return self._('glob_pattern_empty', default="File pattern cannot be empty")
        
        # 验证路径
        path = params.get("path", ".")
        if not os.path.exists(path):
            return self._('glob_path_not_found', default=f"Path not found: {path}")
        
        return None
    
    async def execute(
        self,
        params: Dict[str, Any],
        signal: AbortSignal,
        update_output: Optional[Any] = None
    ) -> ToolResult:
        """执行文件查找"""
        pattern = params.get("pattern")
        base_path = params.get("path", ".")
        case_sensitive = params.get("case_sensitive", True)
        include_dirs = params.get("include_dirs", False)
        respect_gitignore = params.get("respect_gitignore", True)
        max_results = params.get("max_results", 100)
        max_depth = params.get("max_depth", 10)
        
        try:
            # 规范化基础路径
            base_path = Path(base_path).resolve()
            
            # 加载gitignore规则
            gitignore_patterns = []
            if respect_gitignore:
                gitignore_patterns = await self._load_gitignore_patterns(base_path)
            
            # 执行文件搜索
            matches = await self._find_files(
                pattern, base_path, case_sensitive, include_dirs,
                gitignore_patterns, max_results, max_depth, signal
            )
            
            # 智能排序（参考Gemini CLI）
            sorted_matches = self._sort_by_relevance(matches)
            
            # 限制结果数
            if len(sorted_matches) > max_results:
                sorted_matches = sorted_matches[:max_results]
            
            # 格式化结果
            return self._format_results(sorted_matches, pattern, base_path)
            
        except asyncio.CancelledError:
            return ToolResult(
                error=self._('glob_cancelled', default="File search cancelled by user")
            )
        except Exception as e:
            return ToolResult(
                error=self._('glob_error', default=f"File search failed: {str(e)}")
            )
    
    async def _find_files(
        self, pattern: str, base_path: Path, case_sensitive: bool,
        include_dirs: bool, gitignore_patterns: List[str],
        max_results: int, max_depth: int, signal: AbortSignal
    ) -> List[FileEntry]:
        """递归查找匹配的文件"""
        matches = []
        
        # 处理glob模式
        # ** 表示递归所有子目录
        if '**' in pattern:
            recursive = True
            # 将 ** 转换为具体的搜索逻辑
            pattern_parts = pattern.split('**')
        else:
            recursive = False
            pattern_parts = [pattern]
        
        # 使用asyncio提高性能
        async def process_directory(dir_path: Path, depth: int):
            if signal and signal.aborted:
                return
            
            if depth > max_depth:
                return
            
            try:
                for entry in os.scandir(dir_path):
                    if signal and signal.aborted:
                        break
                    
                    # 检查是否应该忽略
                    if self._should_ignore(entry.path, entry.is_dir(), gitignore_patterns):
                        continue
                    
                    # 获取相对路径
                    rel_path = os.path.relpath(entry.path, base_path)
                    
                    # 匹配检查
                    if self._match_pattern(entry.name, rel_path, pattern, case_sensitive, recursive):
                        if entry.is_dir():
                            if include_dirs:
                                stat = entry.stat()
                                matches.append(FileEntry(
                                    path=entry.path,
                                    name=entry.name,
                                    size=0,
                                    modified_time=stat.st_mtime,
                                    is_directory=True,
                                    relative_path=rel_path
                                ))
                        else:
                            stat = entry.stat()
                            matches.append(FileEntry(
                                path=entry.path,
                                name=entry.name,
                                size=stat.st_size,
                                modified_time=stat.st_mtime,
                                is_directory=False,
                                relative_path=rel_path
                            ))
                            
                            if len(matches) >= max_results * 2:  # 收集额外的用于排序
                                return
                    
                    # 递归处理子目录
                    if entry.is_dir() and (recursive or depth == 0):
                        await process_directory(Path(entry.path), depth + 1)
                        
            except PermissionError:
                # 忽略没有权限的目录
                if DebugLogger.should_log("DEBUG"):
                    log_info("GlobTool", f"Permission denied: {dir_path}")
            except Exception as e:
                if DebugLogger.should_log("DEBUG"):
                    log_info("GlobTool", f"Error processing {dir_path}: {e}")
        
        # 开始搜索
        await process_directory(base_path, 0)
        
        return matches
    
    def _match_pattern(self, name: str, rel_path: str, pattern: str, 
                      case_sensitive: bool, recursive: bool) -> bool:
        """匹配文件名或路径"""
        # 处理大小写
        if not case_sensitive:
            name = name.lower()
            rel_path = rel_path.lower()
            pattern = pattern.lower()
        
        # 如果模式包含路径分隔符，匹配完整路径
        if '/' in pattern or os.sep in pattern:
            return fnmatch.fnmatch(rel_path, pattern)
        
        # 处理 ** 递归模式
        if '**' in pattern:
            # 例如: **/*.py 匹配所有子目录中的.py文件
            parts = pattern.split('**')
            if len(parts) == 2:
                prefix = parts[0].strip('/')
                suffix = parts[1].strip('/')
                
                # 检查路径是否匹配
                if prefix and not rel_path.startswith(prefix):
                    return False
                if suffix:
                    # 检查文件名或路径后缀
                    if '/' in suffix:
                        return fnmatch.fnmatch(rel_path, f"*{suffix}")
                    else:
                        return fnmatch.fnmatch(name, suffix)
                return True
        
        # 简单文件名匹配
        return fnmatch.fnmatch(name, pattern)
    
    def _should_ignore(self, path: str, is_dir: bool, gitignore_patterns: List[str]) -> bool:
        """检查是否应该忽略该文件/目录"""
        name = os.path.basename(path)
        
        # 检查默认忽略的目录
        if is_dir and name in self.DEFAULT_IGNORE_DIRS:
            return True
        
        # 检查默认忽略的文件
        if not is_dir:
            for pattern in self.DEFAULT_IGNORE_FILES:
                if fnmatch.fnmatch(name, pattern):
                    return True
        
        # 检查gitignore规则
        for pattern in gitignore_patterns:
            if fnmatch.fnmatch(name, pattern):
                return True
        
        return False
    
    async def _load_gitignore_patterns(self, base_path: Path) -> List[str]:
        """加载.gitignore规则"""
        patterns = []
        
        # 查找.gitignore文件
        gitignore_path = base_path / ".gitignore"
        if gitignore_path.exists():
            try:
                with open(gitignore_path, 'r', encoding='utf-8') as f:
                    for line in f:
                        line = line.strip()
                        # 忽略空行和注释
                        if line and not line.startswith('#'):
                            # 简化gitignore规则（不完全实现）
                            pattern = line.rstrip('/')
                            if pattern.startswith('/'):
                                pattern = pattern[1:]
                            patterns.append(pattern)
            except Exception as e:
                if DebugLogger.should_log("DEBUG"):
                    log_info("GlobTool", f"Failed to read .gitignore: {e}")
        
        # 也检查.geminiignore或.agentignore
        agentignore_path = base_path / ".agentignore"
        if agentignore_path.exists():
            try:
                with open(agentignore_path, 'r', encoding='utf-8') as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith('#'):
                            patterns.append(line.rstrip('/'))
            except:
                pass
        
        return patterns
    
    def _sort_by_relevance(self, files: List[FileEntry]) -> List[FileEntry]:
        """
        智能排序文件（参考Gemini CLI）
        1. 最近修改的文件优先（7天内）
        2. 旧文件按字母顺序
        """
        now = time.time()
        recency_threshold = now - (self.RECENCY_THRESHOLD_DAYS * 24 * 60 * 60)
        
        recent_files = []
        old_files = []
        
        for file in files:
            if file.modified_time > recency_threshold:
                recent_files.append(file)
            else:
                old_files.append(file)
        
        # 最近的文件按修改时间降序
        recent_files.sort(key=lambda f: f.modified_time, reverse=True)
        
        # 旧文件按路径字母顺序
        old_files.sort(key=lambda f: f.relative_path.lower())
        
        # 合并结果
        return recent_files + old_files
    
    def _format_results(self, matches: List[FileEntry], pattern: str, base_path: Path) -> ToolResult:
        """格式化搜索结果"""
        if not matches:
            return ToolResult(
                summary=self._('glob_no_matches', default=f"No files found matching: {pattern}"),
                llm_content=self._('glob_no_matches_llm', default=f"No files found matching pattern '{pattern}'"),
                return_display=self._('glob_no_matches_display', default="📁 No matching files found")
            )
        
        # 统计信息
        total_size = sum(f.size for f in matches if not f.is_directory)
        dir_count = sum(1 for f in matches if f.is_directory)
        file_count = len(matches) - dir_count
        
        # 构建LLM内容（详细列表）
        llm_lines = [f"Found {len(matches)} items matching '{pattern}':"]
        
        # 分组显示
        if dir_count > 0:
            llm_lines.append(f"\nDirectories ({dir_count}):")
            for entry in matches:
                if entry.is_directory:
                    llm_lines.append(f"  📁 {entry.relative_path}/")
        
        if file_count > 0:
            llm_lines.append(f"\nFiles ({file_count}):")
            for entry in matches:
                if not entry.is_directory:
                    mod_time = datetime.fromtimestamp(entry.modified_time)
                    time_str = mod_time.strftime("%Y-%m-%d %H:%M")
                    size_str = self._format_size(entry.size)
                    llm_lines.append(f"  📄 {entry.relative_path} ({size_str}, {time_str})")
        
        # 构建显示内容（简洁摘要）
        display_lines = [
            f"🔍 Pattern: {pattern}",
            f"📊 Results: {file_count} files, {dir_count} directories"
        ]
        
        if total_size > 0:
            display_lines.append(f"💾 Total size: {self._format_size(total_size)}")
        
        # 时间统计
        now = time.time()
        recency_threshold = now - (self.RECENCY_THRESHOLD_DAYS * 24 * 60 * 60)
        recent_count = sum(1 for f in matches if f.modified_time > recency_threshold)
        if recent_count > 0:
            display_lines.append(f"🕐 Recent files (7 days): {recent_count}")
        
        # 显示前几个结果
        display_lines.append("\n📍 Sample results:")
        for entry in matches[:10]:
            if entry.is_directory:
                display_lines.append(f"  📁 {entry.relative_path}/")
            else:
                display_lines.append(f"  📄 {entry.relative_path}")
        
        if len(matches) > 10:
            display_lines.append(f"  ... and {len(matches) - 10} more")
        
        return ToolResult(
            summary=self._('glob_summary', default=f"Found {len(matches)} items matching '{pattern}'"),
            llm_content="\n".join(llm_lines),
            return_display="\n".join(display_lines)
        )
    
    def _format_size(self, size_bytes: int) -> str:
        """格式化文件大小"""
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size_bytes < 1024.0:
                return f"{size_bytes:.1f}{unit}"
            size_bytes /= 1024.0
        return f"{size_bytes:.1f}TB"
    
    def get_description(self, params: Dict[str, Any]) -> str:
        """获取操作描述"""
        pattern = params.get("pattern", "")
        path = params.get("path", ".")
        
        desc = self._('glob_description', default=f"Find files matching '{pattern}'")
        if path != ".":
            desc += f" in {path}"
        
        return desc
    
    async def should_confirm_execute(self, params: Dict[str, Any], signal: AbortSignal) -> Optional[Any]:
        """文件查找通常不需要确认"""
        return False