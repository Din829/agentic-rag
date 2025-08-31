"""
品牌配置加载器 - 支持自定义Agent品牌展示
最小侵入性设计，完全向后兼容
"""

import os
import json
from pathlib import Path
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field

# 默认DbRheo品牌配置（向后兼容）
DEFAULT_BRANDING = {
    "name": "DbRheo CLI",
    "ascii_art": {
        "default": """██████╗ ██████╗ ██████╗ ██╗  ██╗███████╗ ██████╗      ██████╗██╗     ██╗
██╔══██╗██╔══██╗██╔══██╗██║  ██║██╔════╝██╔═══██╗    ██╔════╝██║     ██║
██║  ██║██████╔╝██████╔╝███████║█████╗  ██║   ██║    ██║     ██║     ██║
██║  ██║██╔══██╗██╔══██╗██╔══██║██╔══╝  ██║   ██║    ██║     ██║     ██║
██████╔╝██████╔╝██║  ██║██║  ██║███████╗╚██████╔╝    ╚██████╗███████╗██║
╚═════╝ ╚═════╝ ╚═╝  ╚═╝╚═╝  ╚═╝╚══════╝ ╚═════╝      ╚═════╝╚══════╝╚═╝""",
        "short": r""" ____  _     ____  _               
|  _ \| |__ |  _ \| |__   ___  ___ 
| | | | '_ \| |_) | '_ \ / _ \/ _ \
| |_| | |_) |  _ <| | | |  __/ (_) |
|____/|_.__/|_| \_\_| |_|\___|\___/""",
        "minimal": "DbRheo CLI"
    },
    "colors": {
        "gradient": ["#000033", "#001155", "#0033AA", "#0055FF", "#3377FF"],
        "tips": "#8899AA"
    },
    "startup_tips": None,  # None表示使用i18n的默认提示
    "home_dir_warning": None,  # None表示使用i18n的默认警告
    "version": None  # None表示使用代码中的版本号
}


@dataclass
class BrandingConfig:
    """
    品牌配置类
    支持从JSON文件加载自定义品牌信息
    """
    name: str = "DbRheo CLI"
    ascii_art: Dict[str, str] = field(default_factory=dict)
    colors: Dict[str, Any] = field(default_factory=dict)
    startup_tips: Optional[List[str]] = None
    startup_tips_title: Optional[str] = None  # 新增：提示标题
    home_dir_warning: Optional[str] = None
    version: Optional[str] = None
    keyboard_hints: Optional[str] = None  # 新增：键盘提示
    
    # 内部属性：配置来源
    _config_source: str = "default"
    
    def __post_init__(self):
        """初始化后加载配置"""
        self.load_branding()
    
    def load_branding(self) -> None:
        """
        加载品牌配置
        优先级：
        1. 环境变量 AGENT_BRANDING_CONFIG 指定的路径
        2. 项目根目录的 branding.json
        3. 默认 DbRheo 品牌
        """
        config_data = None
        config_path = None
        
        # 1. 尝试从环境变量指定的路径加载
        env_path = os.environ.get('AGENT_BRANDING_CONFIG')
        if env_path:
            env_path_obj = Path(env_path)
            if not env_path_obj.is_absolute():
                # 相对路径，从当前目录开始查找
                env_path_obj = Path.cwd() / env_path_obj
            
            if env_path_obj.exists() and env_path_obj.is_file():
                try:
                    with open(env_path_obj, 'r', encoding='utf-8') as f:
                        config_data = json.load(f)
                        config_path = str(env_path_obj)
                        self._config_source = f"env: {config_path}"
                        if os.environ.get('DEBUG_BRANDING'):
                            print(f"[Branding] Loaded from env path: {config_path}")
                except (json.JSONDecodeError, IOError) as e:
                    if os.environ.get('DEBUG_BRANDING'):
                        print(f"[Branding] Failed to load from env: {e}")
                    pass
        
        # 2. 尝试从项目根目录加载
        if not config_data:
            # 查找项目根目录（与prompts.py保持一致）
            project_root = self._find_project_root()
            if project_root:
                branding_file = project_root / "branding.json"
                if branding_file.exists():
                    try:
                        with open(branding_file, 'r', encoding='utf-8') as f:
                            config_data = json.load(f)
                            config_path = str(branding_file)
                            self._config_source = f"project: {config_path}"
                            if os.environ.get('DEBUG_BRANDING'):
                                print(f"[Branding] Loaded from project: {config_path}")
                    except (json.JSONDecodeError, IOError) as e:
                        if os.environ.get('DEBUG_BRANDING'):
                            print(f"[Branding] Failed to load from project: {e}")
                        pass
        
        # 3. 应用配置（合并默认值）
        if config_data:
            self._apply_config(config_data)
        else:
            # 使用默认配置
            self._apply_config(DEFAULT_BRANDING)
            self._config_source = "default"
            if os.environ.get('DEBUG_BRANDING'):
                print(f"[Branding] Using default branding")
    
    def _find_project_root(self) -> Optional[Path]:
        """
        查找项目根目录
        优先从代码位置向上查找，其次从工作目录查找
        """
        # 策略1：从当前文件位置向上查找（更可靠）
        current_file = Path(__file__).resolve()
        current = current_file.parent
        
        # 向上查找最多15级（足够深的目录结构）
        for _ in range(15):
            # 优先检查branding.json（最明确的标志）
            if (current / "branding.json").exists():
                if os.environ.get('DEBUG_BRANDING'):
                    print(f"[Branding] Found project root at: {current}")
                return current
            
            # 检查是否是DbRheo-CLI项目根（packages目录的父目录）
            if (current / "packages" / "cli").exists() and (current / "packages" / "core").exists():
                if os.environ.get('DEBUG_BRANDING'):
                    print(f"[Branding] Found DbRheo-CLI root at: {current}")
                return current
            
            # 其他特征文件
            if any((current / marker).exists() for marker in [
                ".env", "PROJECT.md", ".git"
            ]):
                # 但要确保不是packages/cli目录（它也有pyproject.toml）
                if current.name != "cli":
                    if os.environ.get('DEBUG_BRANDING'):
                        print(f"[Branding] Found project root at: {current}")
                    return current
            
            # 到达根目录
            if current.parent == current:
                break
            current = current.parent
        
        # 策略2：从工作目录向上查找（兼容性）
        cwd = Path.cwd()
        current = cwd
        
        for _ in range(10):
            if any((current / marker).exists() for marker in [
                "branding.json", ".env", "PROJECT.md", "pyproject.toml", 
                "package.json", ".git"
            ]):
                if os.environ.get('DEBUG_BRANDING'):
                    print(f"[Branding] Found project root (cwd) at: {current}")
                return current
            
            if current.parent == current:
                break
            current = current.parent
        
        # 默认返回工作目录
        return cwd
    
    def _apply_config(self, config: Dict[str, Any]) -> None:
        """
        应用配置数据
        支持部分覆盖，未定义的字段使用默认值
        """
        # 名称
        self.name = config.get('name', DEFAULT_BRANDING['name'])
        
        # ASCII艺术（合并默认值）
        default_art = DEFAULT_BRANDING['ascii_art'].copy()
        if 'ascii_art' in config:
            default_art.update(config['ascii_art'])
        self.ascii_art = default_art
        
        # 颜色配置（合并默认值）
        default_colors = DEFAULT_BRANDING['colors'].copy()
        if 'colors' in config:
            default_colors.update(config['colors'])
        self.colors = default_colors
        
        # 启动提示（可选）
        self.startup_tips = config.get('startup_tips', None)
        self.startup_tips_title = config.get('startup_tips_title', None)
        
        # 主目录警告（可选）
        self.home_dir_warning = config.get('home_dir_warning', None)
        
        # 版本号（可选）
        self.version = config.get('version', None)
        
        # 键盘提示（可选）
        self.keyboard_hints = config.get('keyboard_hints', None)
    
    def get_logo(self, style: str = "default") -> str:
        """
        获取指定风格的LOGO
        支持数组格式和字符串格式
        """
        # 检查是否有数组格式（优先使用）
        array_key = f"{style}_array"
        if array_key in self.ascii_art:
            # 将数组连接成字符串
            logo_array = self.ascii_art[array_key]
            if isinstance(logo_array, list):
                return "\n".join(logo_array)
        
        # 使用字符串格式（但如果有数组格式就不用字符串格式）
        if style in self.ascii_art and array_key not in self.ascii_art:
            return self.ascii_art[style]
        
        # 回退策略
        if style == "short" and "default" in self.ascii_art:
            return self.ascii_art["default"]
        elif style == "minimal":
            return f"\n {self.name} \n"
        
        # 最终回退
        return self.ascii_art.get("default", f"\n {self.name} \n")
    
    def get_gradient_colors(self) -> List[str]:
        """获取渐变颜色配置"""
        return self.colors.get('gradient', DEFAULT_BRANDING['colors']['gradient'])
    
    def get_tips_color(self) -> str:
        """获取提示文字颜色"""
        return self.colors.get('tips', DEFAULT_BRANDING['colors']['tips'])
    
    def should_use_custom_tips(self) -> bool:
        """是否使用自定义启动提示"""
        return self.startup_tips is not None and len(self.startup_tips) > 0
    
    def should_use_custom_warning(self) -> bool:
        """是否使用自定义主目录警告"""
        return self.home_dir_warning is not None
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式（用于调试）"""
        return {
            'name': self.name,
            'ascii_art': self.ascii_art,
            'colors': self.colors,
            'startup_tips': self.startup_tips,
            'home_dir_warning': self.home_dir_warning,
            'version': self.version,
            'config_source': self._config_source
        }


# 全局实例（延迟加载）
_global_branding: Optional[BrandingConfig] = None


def get_branding() -> BrandingConfig:
    """
    获取全局品牌配置实例
    使用单例模式确保配置只加载一次
    """
    global _global_branding
    if _global_branding is None:
        _global_branding = BrandingConfig()
    return _global_branding


def reset_branding() -> None:
    """
    重置品牌配置（主要用于测试）
    """
    global _global_branding
    _global_branding = None