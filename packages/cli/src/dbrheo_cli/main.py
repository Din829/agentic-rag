#!/usr/bin/env python3
"""
DbRheo CLI 主入口
保持专业、简洁、可靠的设计原则
"""

import os
import sys
import signal
import asyncio
import logging
from pathlib import Path
from typing import Optional

import click
from rich.console import Console

# 关闭 httpx 的调试日志
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("openai").setLevel(logging.WARNING)
logging.getLogger("anthropic").setLevel(logging.WARNING)


def preprocess_language_args():
    """预处理语言参数，设置环境变量（最小侵入性实现）"""
    for i, arg in enumerate(sys.argv):
        if arg in ['--lang', '--language'] and i + 1 < len(sys.argv):
            lang_value = sys.argv[i + 1].lower()
            lang_map = {
                'zh': 'zh_CN', 'cn': 'zh_CN', 'zh_cn': 'zh_CN',
                'ja': 'ja_JP', 'jp': 'ja_JP', 'ja_jp': 'ja_JP',
                'en': 'en_US', 'us': 'en_US', 'en_us': 'en_US'
            }
            lang_code = lang_map.get(lang_value, lang_value)
            if lang_code in ['zh_CN', 'ja_JP', 'en_US']:
                os.environ['DBRHEO_LANG'] = lang_code
            break


# 在所有导入前预处理语言参数
preprocess_language_args()

# 设置默认调试级别，如果环境变量中没有设置的话
if 'DBRHEO_DEBUG_LEVEL' not in os.environ:
    os.environ['DBRHEO_DEBUG_LEVEL'] = 'ERROR'
if 'DBRHEO_DEBUG_VERBOSITY' not in os.environ:
    os.environ['DBRHEO_DEBUG_VERBOSITY'] = 'MINIMAL'

# 添加src到Python路径（开发时需要）
sys.path.insert(0, str(Path(__file__).parent.parent))

# 尝试加载.env文件
try:
    from dotenv import load_dotenv
    # 支持多个可能的.env文件位置，注意大小写变化
    current_file = Path(__file__).resolve()
    base_paths = [
        current_file.parent.parent.parent.parent.parent,  # 向上5级到gemini-cli目录
        current_file.parent.parent.parent.parent,  # 向上4级
        current_file.parent.parent.parent,  # CLI包目录
        Path.cwd(),  # 当前工作目录
    ]
    
    # 尝试不同的目录名称组合
    for base in base_paths:
        for dirname in ["DbRheo", "Dbrheo", "dbrheo"]:
            env_path = base / "学习中" / dirname / ".env"
            if env_path.exists():
                load_dotenv(env_path)
                # print(f"[INFO] Loaded .env from: {env_path}")
                break
        # 也尝试直接在base目录下
        env_path = base / ".env"
        if env_path.exists():
            load_dotenv(env_path)
            print(f"[INFO] Loaded .env from: {env_path}")
            break
except ImportError:
    # 如果没有安装python-dotenv，继续运行
    pass

from dbrheo_cli.app.cli import DbRheoCLI
from dbrheo_cli.app.config import CLIConfig
from dbrheo_cli.i18n import _
from dbrheo_cli.constants import ENV_VARS, DEFAULTS, DEBUG_LEVEL_RANGE
from dbrheo.utils.debug_logger import DebugLogger, log_info


# 全局控制台实例
console = Console()


def setup_signal_handlers(cli: DbRheoCLI):
    """设置信号处理器，确保优雅退出"""
    def signal_handler(signum, frame):
        log_info("Main", _('signal_received', signum=signum))
        # 立即设置退出标志
        cli.running = False
        
        # 中止所有操作
        if hasattr(cli, 'signal') and cli.signal:
            cli.signal.abort()
        
        # 强制退出事件循环
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                loop.stop()
        except:
            pass
        
        # 如果上述方法都不行，强制退出
        os._exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)


def setup_environment():
    """从环境变量读取配置"""
    # DEBUG模式 - DebugLogger通过环境变量读取，这里只是确保环境变量设置正确
    if ENV_VARS['DEBUG_LEVEL'] not in os.environ:
        os.environ[ENV_VARS['DEBUG_LEVEL']] = DEFAULTS['DEBUG_LEVEL']
    
    # DEBUG详细程度
    if ENV_VARS['DEBUG_VERBOSITY'] not in os.environ:
        os.environ[ENV_VARS['DEBUG_VERBOSITY']] = DEFAULTS['DEBUG_VERBOSITY']
    
    # 实时日志
    if os.environ.get(ENV_VARS['ENABLE_LOG'], '').lower() == 'true':
        # 日志已通过环境变量启用，无需额外操作
        log_info("Main", "Realtime logging enabled via environment")


@click.command()
@click.option('--log',
              is_flag=True,
              help='启用实时日志输出')
@click.option('--debug',
              type=click.IntRange(*DEBUG_LEVEL_RANGE),
              help='设置调试级别 (0-5)')
@click.option('--no-color',
              is_flag=True,
              help='禁用彩色输出')
@click.option('--config',
              type=click.Path(exists=True),
              help='配置文件路径')
@click.option('--model',
              help='选择AI模型 (例如: gemini, claude-3.5-sonnet, gpt-5)')
@click.option('--lang', '--language',
              help='设置界面语言 (zh/en/ja)',
              type=click.Choice(['zh', 'en', 'ja', 'zh_CN', 'en_US', 'ja_JP']))
def main(log: bool,
         debug: Optional[int],
         no_color: bool,
         config: Optional[str],
         model: Optional[str],
         lang: Optional[str]):
    """
    通用Agent CLI - 智能助手框架

    专业、简洁、可靠的数据库操作界面
    """
    # 语言参数已通过预处理函数设置，这里无需额外处理
    # 设置环境变量配置
    setup_environment()
    
    # 命令行参数覆盖环境变量
    if debug is not None:
        # 将数字转换为日志级别名称
        level_map = {0: 'ERROR', 1: 'WARNING', 2: 'INFO', 3: 'DEBUG', 4: 'DEBUG', 5: 'DEBUG'}
        debug_level = level_map.get(debug, 'INFO')
        os.environ[ENV_VARS['DEBUG_LEVEL']] = debug_level
        # 重新导入debug_logger模块以应用新的日志级别
        import importlib
        import dbrheo.utils.debug_logger
        importlib.reload(dbrheo.utils.debug_logger)
        log_info("Main", _('debug_level_set', level=debug))
    
    if log:
        os.environ[ENV_VARS['ENABLE_LOG']] = 'true'
        log_info("Main", _('log_enabled'))
    
    # 设置模型（命令行参数优先）
    if model:
        os.environ[ENV_VARS['MODEL']] = model
        log_info("Main", _('model_switched', model=model))
    elif not os.environ.get(ENV_VARS['MODEL']):
        # 如果没有命令行参数和环境变量，尝试从配置文件加载
        try:
            config_path = Path.cwd() / "config.yaml"
            if config_path.exists():
                import yaml
                with open(config_path, 'r', encoding='utf-8') as f:
                    config_data = yaml.safe_load(f) or {}
                    saved_model = config_data.get('model')
                    if saved_model and saved_model != 'gemini-2.5-flash':
                        os.environ[ENV_VARS['MODEL']] = saved_model
                        log_info("Main", f"Loaded model from config.yaml: {saved_model}")
        except Exception:
            # 静默失败
            pass
    
    # 创建CLI配置（泛用化：移除数据库特定参数）
    cli_config = CLIConfig(
        no_color=no_color,
        config_file=config
    )
    
    # 创建并运行CLI
    try:
        cli = DbRheoCLI(cli_config)
        setup_signal_handlers(cli)
        
        # 显示启动画面
        from dbrheo_cli.ui.startup import StartupScreen
        from dbrheo_cli.ui.branding_config import get_branding
        startup = StartupScreen(cli_config, console)
        
        # 检查是否在主目录运行（类似 Gemini CLI）
        custom_message = None
        if os.path.expanduser("~") == os.getcwd():
            # 使用品牌配置的警告或默认警告
            branding = get_branding()
            if branding.should_use_custom_warning():
                custom_message = branding.home_dir_warning
            else:
                custom_message = _('home_dir_warning')
            
        # 显示完整启动画面
        from . import __version__
        startup.display(
            version=__version__,
            show_tips=True,
            custom_message=custom_message,
            logo_style="default"  # 使用默认大号版本
        )
        
        # 检查当前模型的 API Key（第一次启动时）
        from dbrheo_cli.utils.api_key_checker import show_api_key_setup_guide
        current_model = os.environ.get(ENV_VARS['MODEL'], 'gemini-2.5-flash')
        show_api_key_setup_guide(current_model)
        
        # 运行主循环
        asyncio.run(cli.run())
        
        # 确保清理资源
        cli.cleanup()
        
    except KeyboardInterrupt:
        console.print(f"\n[yellow]{_('user_interrupt')}[/yellow]")
        sys.exit(0)
    except Exception as e:
        console.print(f"\n[red]{_('error_occurred', error=e)}[/red]")
        if DebugLogger.should_log("DEBUG"):
            import traceback
            traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()