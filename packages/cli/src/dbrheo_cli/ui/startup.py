"""
DbRheo 启动画面
使用 rich-gradient 实现优雅的渐变效果
"""

import os
from typing import Optional, List, Tuple
from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from rich.align import Align
from rich.columns import Columns

from .ascii_art import select_logo, get_logo_width, LONG_LOGO, EXTRA_LARGE_LOGO
from .branding_config import get_branding
from ..i18n import _
from ..app.config import CLIConfig

# 尝试导入 rich-gradient，提供优雅降级
try:
    from rich_gradient import Gradient
    GRADIENT_AVAILABLE = True
except ImportError:
    GRADIENT_AVAILABLE = False

# 颜色主题（可被品牌配置覆盖）
DBRHEO_GRADIENT_COLORS = ["#000033", "#001155", "#0033AA", "#0055FF", "#3377FF"]  # 蓝黑渐变
TIPS_COLOR = "#8899AA"  # 提示文字颜色


class StartupScreen:
    """启动画面管理器"""
    
    def __init__(self, config: CLIConfig, console: Console):
        self.config = config
        self.console = console
        self.terminal_width = console.width
        # 加载品牌配置
        self.branding = get_branding()
        
    def display(self, version: str = "0.2.0", show_tips: bool = True, 
                custom_message: Optional[str] = None, logo_style: str = "default"):
        """
        显示启动画面
        
        Args:
            version: 版本号
            show_tips: 是否显示使用提示
            custom_message: 自定义消息（如警告）
            logo_style: logo 风格 - "default", "italic", "extra"
        """
        # 选择合适的 logo（优先使用品牌配置）
        logo = self._get_branded_logo(logo_style)
        
        # 显示 logo（带渐变效果）
        self._display_logo(logo)
        
        # 显示版本信息（使用品牌配置的版本或传入的版本）
        display_version = self.branding.version or version
        self._display_version(display_version)
        
        # 显示使用提示
        if show_tips:
            self._display_tips()
            
        # 显示自定义消息（如工作目录警告）
        if custom_message:
            self._display_custom_message(custom_message)
            
        # 添加底部间距
        self.console.print()
        
    def _display_logo(self, logo: str):
        """显示带渐变效果的 logo"""
        # 使用品牌配置的颜色
        gradient_colors = self.branding.get_gradient_colors()

        # 检查强制颜色模式
        force_color = os.environ.get('DBRHEO_FORCE_COLOR', 'true').lower() == 'true'

        if GRADIENT_AVAILABLE and (force_color or not self.config.no_color):
            # 使用 rich-gradient 实现渐变
            gradient_logo = Gradient(
                logo.rstrip(),  # 只移除右侧空格，保留左侧缩进
                colors=gradient_colors
            )
            self.console.print(gradient_logo, justify="left")
        else:
            # 降级方案：使用配置的颜色
            # 优先使用logo_fallback颜色，如果没有则使用tips颜色
            logo_color = self.branding.colors.get('logo_fallback', self.branding.get_tips_color())
            self.console.print(
                Text(logo.rstrip(), style=f"bold {logo_color}"),  # 使用独立的logo颜色
                justify="left"  # 改为左对齐
            )
            
    def _display_version(self, version: str):
        """显示版本信息"""
        version_text = f"v{version}"
        # 版本号始终使用灰色，不使用渐变
        self.console.print(
            Text(version_text, style="dim #808080"),  # 使用灰色
            justify="right"
        )
            
    def _display_tips(self):
        """显示使用提示"""
        # 如果有品牌配置，完全使用品牌配置（不考虑i18n）
        if self.branding._config_source != "default" and self.branding.startup_tips:
            # 使用品牌配置的提示（完全覆盖i18n）
            tips = self.branding.startup_tips
            tips_title = self.branding.startup_tips_title or "Tips:"
        else:
            # 只有在没有品牌配置时，才使用i18n系统
            tips = [
                _('startup_tip_1'),
                _('startup_tip_2'),
                _('startup_tip_3'),
                _('startup_tip_4'),
                _('startup_tip_5'),
                _('startup_tip_6')
            ]
            tips_title = _('startup_tips_title')
        
        tips_color = self.branding.get_tips_color()
        self.console.print()
        self.console.print(tips_title, style=f"bold {tips_color}")
        for tip in tips:
            self.console.print(f"  {tip}", style=tips_color)
            
    def _display_custom_message(self, message: str):
        """显示自定义消息（如警告框）"""
        self.console.print()
        panel = Panel(
            message,
            border_style="yellow",
            padding=(0, 2)
        )
        self.console.print(panel)
    
    def _get_branded_logo(self, style: str) -> str:
        """
        获取品牌配置的LOGO
        如果配置中有自定义LOGO，使用自定义的
        否则使用原有的select_logo逻辑
        """
        # 如果不是默认配置，优先使用品牌配置的LOGO
        if self.branding._config_source != "default":
            custom_logo = self.branding.get_logo(style)
            if custom_logo:
                # 检查宽度是否合适
                logo_width = get_logo_width(custom_logo)
                if self.terminal_width >= logo_width + 10:
                    return custom_logo
                else:
                    # 如果太宽，尝试更小的版本
                    if style != "minimal":
                        return self._get_branded_logo("minimal")
                    else:
                        return f"\n {self.branding.name} \n"
        
        # 使用默认配置或回退到原有的select_logo逻辑
        return select_logo(self.terminal_width, style=style)


def create_minimal_startup(console: Console, version: str = "0.2.0"):
    """创建最小化的启动信息（用于 --quiet 模式）"""
    branding = get_branding()
    name = branding.name
    display_version = branding.version or version
    console.print(f"[bold blue]{name}[/bold blue] v{display_version}")


def create_rainbow_logo(logo: str) -> Optional[str]:
    """创建彩虹效果的 logo（特殊场合使用）"""
    if not GRADIENT_AVAILABLE:
        return None
        
    try:
        rainbow_logo = Gradient(
            logo.strip(),
            rainbow=True
        )
        return rainbow_logo
    except:
        return None