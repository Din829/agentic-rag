"""
输入处理器
处理用户输入，包括命令解析、特殊按键处理等。
"""

import sys
import os
import asyncio
from typing import Optional

from ..ui.console import console
from ..app.config import CLIConfig
from ..i18n import _

# 尝试导入增强输入组件（可选功能）
try:
    from ..ui.simple_multiline_input import EnhancedInputHandler
    ENHANCED_INPUT_AVAILABLE = True
except ImportError:
    ENHANCED_INPUT_AVAILABLE = False


class InputHandler:
    """
    用户输入处理器
    - 获取用户输入
    - 处理特殊按键
    - 管理输入历史（通过readline）
    """
    
    def __init__(self, config: CLIConfig):
        self.config = config

        # 创建考虑no_color配置的console实例
        from ..ui.console import _detect_console_settings
        from rich.console import Console as RichConsole
        import os

        # 检查强制颜色模式
        force_color = os.environ.get('DBRHEO_FORCE_COLOR', 'true').lower() == 'true'

        if force_color:
            # 强制启用颜色，忽略配置
            input_console = RichConsole(**_detect_console_settings())
        elif config.no_color:
            # 仅在非强制模式下才禁用颜色
            input_console = RichConsole(no_color=True)
        else:
            input_console = RichConsole(**_detect_console_settings())

        # 初始化增强输入处理器（如果可用）
        self.enhanced_handler = None
        if ENHANCED_INPUT_AVAILABLE:
            try:
                self.enhanced_handler = EnhancedInputHandler(config, input_console)
                from dbrheo.utils.debug_logger import log_info
                log_info("InputHandler", "Enhanced input mode available")
            except Exception as e:
                # 初始化失败，使用传统模式
                self.enhanced_handler = None
                from dbrheo.utils.debug_logger import log_info
                log_info("InputHandler", f"Enhanced input initialization failed: {e}")
        
    async def get_input(self) -> str:
        """
        异步获取用户输入
        使用asyncio兼容的方式读取输入
        """
        # 优先使用增强输入（如果可用）
        if self.enhanced_handler:
            try:
                return await self.enhanced_handler.get_input()
            except Exception as e:
                # 增强输入失败，回退到传统模式
                from dbrheo.utils.debug_logger import log_info
                log_info("InputHandler", f"Enhanced input failed, falling back: {e}")
                self.enhanced_handler = None
        
        # 使用传统输入模式
        loop = asyncio.get_event_loop()
        
        try:
            # 在线程池中执行input
            user_input = await loop.run_in_executor(
                None, 
                self._blocking_input
            )
            return user_input.strip()
        except EOFError:
            # Ctrl+D
            raise
        except KeyboardInterrupt:
            # Ctrl+C
            raise

    async def _get_input_with_layout_support(self) -> str:
        """
        获取输入 - 支持固定底部输入框
        最小侵入性：优先使用增强布局，失败时回退到传统方式
        """
        # 尝试使用增强布局管理器
        try:
            from ..ui.layout_manager import create_layout_manager
            layout_manager = create_layout_manager(self.config)

            if layout_manager and layout_manager.is_available():
                # 使用固定底部输入框
                return await layout_manager.get_input_async()
        except Exception as e:
            from dbrheo.utils.debug_logger import log_info
            log_info("InputHandler", f"Enhanced layout input failed, using fallback: {e}")

        # 回退到传统输入方式
        if self.config.no_color:
            return input("> ")
        else:
            # 使用Rich的prompt功能
            return console.input("[bold cyan]>[/bold cyan] ")

    def _get_input_with_layout_support_sync(self) -> str:
        """
        简单的底部输入框 - 替换 > 提示符
        """
        # 检查是否启用底部输入框
        if os.getenv('DBRHEO_ENHANCED_LAYOUT', 'false').lower() == 'true':
            try:
                from prompt_toolkit import prompt
                from prompt_toolkit.shortcuts import prompt as pt_prompt

                # 使用 prompt-toolkit 的简单多行输入
                return pt_prompt(
                    '> ',
                    multiline=True,
                    mouse_support=True,
                    bottom_toolbar='💡 Enter发送 | Shift+Enter换行 | Esc退出'
                )
            except ImportError:
                pass  # 回退到传统方式

        # 传统方式
        if self.config.no_color:
            return input("> ")
        else:
            return console.input("[bold cyan]>[/bold cyan] ")

    def _blocking_input(self) -> str:
        """阻塞式输入（在线程池中执行）"""
        try:
            # 添加分隔线，让输入区域更明显
            if not hasattr(self, '_first_input'):
                self._first_input = False
            else:
                console.print()  # 简洁的空行分隔
            
            # 获取输入 - 支持固定底部输入框
            first_line = self._get_input_with_layout_support_sync()
            
            # 检查是否进入多行模式
            # 支持 ``` 或 <<< 作为多行输入标记
            if first_line.strip() in ['```', '<<<']:
                console.print(f"[dim]{_('multiline_mode_hint')}[/dim]")
                lines = []
                while True:
                    try:
                        if self.config.no_color:
                            line = input("... ")
                        else:
                            line = console.input("[dim]...[/dim] ")
                        
                        if line.strip() in ['```', '<<<']:
                            break
                        lines.append(line)
                    except EOFError:
                        break
                return "\n".join(lines)
            
            return first_line
        except KeyboardInterrupt:
            # 在input时按Ctrl+C
            raise
        except EOFError:
            # Ctrl+D
            raise