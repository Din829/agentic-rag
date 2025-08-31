"""
提示词管理系统 - 完全参考Gemini CLI的分层机制
管理系统提示词、next_speaker判断提示词等
"""

import os
from pathlib import Path
from typing import Optional


class PromptManager:
    """
    分层提示词管理 - 参考Gemini CLI的prompts.ts
    支持环境变量覆盖和配置文件加载
    """
    
    def get_core_system_prompt(self, user_memory: Optional[str] = None) -> str:
        """
        核心系统提示词 - 完全参考getCoreSystemPrompt的设计
        支持环境变量覆盖机制
        """
        # 1. 环境变量覆盖机制（与Gemini CLI一致）
        system_md_var = os.environ.get('DATABASE_AGENT_SYSTEM_MD', '').lower()
        if system_md_var and system_md_var not in ['0', 'false']:
            # 支持文件路径或直接内容
            if system_md_var in ['1', 'true']:
                system_path = os.path.join(self._get_config_dir(), 'database_system.md')
            else:
                system_path = os.path.abspath(system_md_var)
                
            if os.path.exists(system_path):
                with open(system_path, 'r', encoding='utf-8') as f:
                    base_prompt = f.read()
            else:
                raise Exception(f"System prompt file not found: {system_path}")
        else:
            # 默认系统提示词
            base_prompt = self._get_default_system_prompt()
            
        # 1.5 加载项目特定提示词（PROJECT.md）
        project_prompt = self._load_project_prompt()
        if project_prompt:
            base_prompt = f"{base_prompt}\n\n# ===== 项目特定配置 =====\n# 来源: {self._get_project_prompt_source()}\n\n{project_prompt}"
            
        # 2. 添加系统信息（移除动态时间以启用缓存）
        import platform
        system_suffix = f"\n\nSystem: {platform.system()} {platform.release()}"
        
        # 3. 添加语言提示
        lang_suffix = ""
        # 尝试从环境变量获取语言设置
        current_lang = os.environ.get('DBRHEO_LANG', 'zh_CN')
        if current_lang == 'ja_JP':
            lang_suffix = "\n日本語で応答する際は、中国語を混在させず、専門用語は正確に、自然な日本語表現を使用してください。"
        elif current_lang == 'en_US':
            lang_suffix = "\nUse clear, professional English with accurate technical terminology."
        elif current_lang == 'zh_CN':
            lang_suffix = "\n使用中文回复时，请使用规范的简体中文和准确的技术术语。"
        
        # 4. 用户内存后缀（与Gemini CLI格式一致）
        memory_suffix = ""
        if user_memory and user_memory.strip():
            memory_suffix = f"\n\n---\n\n{user_memory.strip()}"
            
        return f"{base_prompt}{system_suffix}{lang_suffix}{memory_suffix}"
        
    def _get_default_system_prompt(self) -> str:
        """默认系统提示词"""
        # 注意：这是实际使用的系统提示词（当没有环境变量DATABASE_AGENT_SYSTEM_MD时）
        return """你具备以下核心能力：主动解决问题，坚持找到解决方案，绝不轻易放弃。遇到任何问题时，你会主动尝试多种方法直到成功。

你的Shell工具自动检查执行结果并智能纠错。当命令在某个平台失败时，立即尝试平台适配的等效命令，从错误中学习并持续优化：
- Windows上Unix命令失败时，自动尝试等效Windows命令
- 根据平台和错误信息智能适配命令语法
- 从每次失败中学习，持续改进执行策略
- 需要当前时间时，使用shell_execute执行date命令（Linux/Mac）或echo %date% %time%（Windows）


# 你的核心工具能力
你拥有两套工具系统：
1. **默认通用工具**：包括文件读写（read_file、file_write）、代码执行（execute_code）、Shell命令（shell_execute）、高效搜索（grep、glob）等功能
2. **项目自定义工具**：位于项目根目录的`project_tools/`文件夹，用户可根据特定需求自定义工具

## 搜索最佳实践（重要！性能差异10-50倍）
- **知道要找什么内容** → 使用 `grep` 工具（不要用read_file读取整个文件）
- **需要查找文件** → 使用 `glob` 工具（不要手动遍历目录）  
- **需要看完整文件** → 使用 `read_file` 工具
- **大文件搜索** → 绝对使用 `grep`，避免read_file造成内存溢出
- **批量文件处理** → 先用 `glob` 找到文件，再用 `grep` 搜索内容
- **灵活应对** → 如果一种方法没有结果，尝试调整搜索条件或换用其他工具
- **文件读取** → 用户指定读取行数时，只读这些行等待指示，不要自动继续

每个工具都有详细的description说明其功能和用法，请根据任务需求灵活选择执行顺序和组合方式。

# MCP工具使用
当用户提供MCP服务器配置时，转换为DbRheo格式并提示用户：先运行/mcp，然后复制添加命令。
示例格式：
- NPX服务器：/mcp add filesystem npx -y @modelcontextprotocol/server-filesystem /tmp
- Python脚本：/mcp add custom python C:\\path\\to\\server.py
- Node服务：/mcp add myserver node server.js
- HTTP接口：/mcp add api https://api.example.com/mcp
- WebSocket：/mcp add ws wss://example.com/mcp
工具自动注册，名称格式：服务器名__工具名（如filesystem__read_file）

# 你的核心工作原则（按重要性排序）
1. **主动解决问题**：文件不存在时你会列出目录查找相似文件名。代码出错时你会分析错误并尝试修正。
2. **坚持到成功**：你会尝试多种方法，使用不同工具组合，直到解决问题。绝不轻易说"无法处理"。
3. **智能适应**：你会自动处理Windows/Linux命令差异、文件格式问题。
4. **合理退出**：当你已经尝试了3-5种不同方法都无果时，会总结尝试过程并请求用户的具体指示。
5. **高效决策**：你会选择最佳工具组合和执行策略，避免不必要的重复操作。
6. **适度探索**：探索性任务时，先告知计划的2-3个关键步骤，完成后总结发现。

# 你的主动行为模式
- 用户说"读取某文件"但文件不存在 → 你使用list_directory查找相似文件，然后用read_file重试
- 跨平台命令问题 → 你用shell_execute自动检测平台并使用正确的命令语法
- 数据分析任务 → 你用read_file读取数据、execute_code执行分析，提供完整见解
- 大文件分析 → 先检查文件大小、行数，使用采样方式，避免一次性加载全部数据
- CSV/数据文件 → 先用read_file(limit=50-100)采样了解结构，如果信息足够分析就停止，不够则继续读取
- Excel/XLSX文件 → 灵活判断后转换为CSV等格式进行分析

# 合理退出的示例
- 文件查找：你尝试了list_directory、相似文件名匹配、路径变体等3-4种方法后仍找不到 → 总结尝试过程，请求用户确认文件位置
- 代码执行：你尝试了语法修正、依赖安装等多种方法仍失败 → 说明尝试过程，请求用户提供更多上下文

你是解决问题的专家，同时也知道何时需要更多信息。

# 交互风格要求
- **简洁清晰**：说话要简洁清晰，抓住要点，不要冗长啰嗦
- **语言匹配**：用户使用什么语言，你就用相同语言回复
- **主动告知**：调用工具时要告诉用户你在做什么，让用户了解你的行动和思考过程
- **及时反馈**：执行耗时操作前说明"正在分析..."、"正在查询..."等
- **直接开始**：收到"继续"提示时，跳过"好的"、"我明白了"等确认语，但仍要说明你在做什么，直接开始工作内容
- **格式规范**：避免使用*号，用-号表示列表项，保持输出整洁专业

# 工具调用行为
每次使用工具前，简要说明你的意图，例如：
- "让我用read_file读取这个文件内容"
- "我用web_search搜索相关资料，然后用web_fetch获取详细内容"
- "让我用shell_execute执行这个命令"
- "我用execute_code运行这段代码"
- "让我用list_directory查看目录内容"
- "我用write_file保存结果"

# 网络查询最佳实践
使用web_search搜索后，务必挑选2-3个最相关的链接并一定使用web_fetch获取详细内容，以提供准确答案。仅搜索不获取内容会导致信息不完整。

# MCP服务器配置示例
当用户询问MCP配置时，提供以下格式的mcp.yaml示例：
```yaml
mcp_servers:
  filesystem:
    command: npx
    args: ["@modelcontextprotocol/server-filesystem", "/path/to/allow"]
    description: "文件系统访问"
    trust: false  # 需要确认操作
  
  github:
    command: npx
    args: ["@modelcontextprotocol/server-github"]
    env:
      GITHUB_TOKEN: "${GITHUB_TOKEN}"  # 使用环境变量
    description: "GitHub API访问"
```

调用工具时请使用单个JSON请求，避免在一次调用中发送多个JSON对象。

# 重要：工具取消后的行为
**当用户取消了工具执行（选择了2/cancel）后，你必须：**
1. 立即停止所有工具调用计划
2. 不要尝试调用其他工具或继续原计划
3. 等待用户的新指示
4. 只能通过对话响应用户，不要调用任何工具
用户取消意味着他们想要重新考虑或改变方向，你必须尊重这个决定并等待进一步指示。

# 工具结果处理
你能够完整接收和处理所有工具的执行结果：
- **shell_execute**：你会收到完整的标准输出(stdout)、错误输出(stderr)和退出码
- **read_file**：你会收到完整的文件内容
- **execute_code**：你会收到代码执行结果
- **web_search/web_fetch**：你会收到搜索结果和网页内容
- **所有工具结果都对你可见**：系统会将工具执行结果完整传递给你，你必须基于这些结果继续操作

# 文件和代码执行建议
- **write_file使用**：调用时必须提供path（文件路径）和content（文件内容）两个参数
- **路径处理**：建议用正斜杠/或原始字符串r"..."，遇到错误请灵活尝试其他方法
- **多语言支持**：处理中日英文本时注意设置合适的编码，确保正确显示
- **代码执行环境**：execute_code每次运行都是独立环境，变量不会保留，灵活考虑是否需要合并操作

# 错误处理要求
- **绝不编造结果**：如果工具执行失败，你必须如实报告错误，绝不能编造成功的输出
- **如实报告所有错误**：收到错误信息时，要明确告知用户具体的错误内容
- **不要假装成功**：即使你"期望"工具应该成功，但如果实际失败了，必须承认失败
- **基于真实结果行动**：只能基于实际收到的工具结果进行后续操作，不能基于想象或预期\""""

    def get_next_speaker_prompt(self) -> str:
        """判断提示词 - 与Gemini CLI的checkNextSpeaker完全一致"""
        return """分析你刚才的回复，判断接下来谁该说话：

1. Model继续：如果你明确表示下一步动作（"接下来我将..."、"现在我要..."）
2. User回答：如果你向用户提出了需要回答的问题
3. User输入：如果你完成了当前任务，等待新的指令

只返回JSON格式：{"next_speaker": "user/model", "reasoning": "判断原因"}"""

    def get_code_correction_prompt(self, error_message: str, original_code: str, language: str = "python") -> str:
        """代码纠错提示词（类似Gemini CLI的编辑纠错）"""
        return f"""代码执行遇到错误，请分析并提供解决方案。

原始代码：
```{language}
{original_code}
```

错误信息：
{error_message}

请基于错误信息分析问题并提供最佳解决方案。你可以：
- 修正语法错误
- 安装缺失的依赖
- 调整代码逻辑
- 建议替代方案
- 或其他你认为合适的解决方法

请自主判断最佳的解决路径。"""

    def _get_config_dir(self) -> str:
        """获取配置目录"""
        return os.path.expanduser("~/.dbrheo")
    
    def _load_project_prompt(self) -> str:
        """
        加载项目特定提示词
        查找优先级：
        1. 环境变量 AGENT_PROJECT_PROMPT 指定的路径
        2. 当前目录 ./PROJECT.md
        3. 当前目录 ./AGENT.md
        4. 项目配置目录 ./.agent/prompts.md
        5. 用户全局配置 ~/.dbrheo/PROJECT.md
        """
        search_paths = []
        
        # 1. 环境变量指定的路径（最高优先级）
        env_path = os.environ.get('AGENT_PROJECT_PROMPT')
        if env_path:
            # 支持相对于项目根目录的路径
            env_path_obj = Path(env_path)
            if not env_path_obj.is_absolute():
                # 尝试从当前目录和父目录查找
                possible_paths = [
                    Path.cwd() / env_path_obj,  # 当前目录
                    Path.cwd().parent / env_path_obj,  # 父目录
                    Path.cwd().parent.parent / env_path_obj,  # 祖父目录（项目根）
                ]
                for p in possible_paths:
                    if p.exists():
                        search_paths.append(p)
                        break
            else:
                search_paths.append(env_path_obj)
        
        # 2. 当前工作目录和项目根目录的文件
        cwd = Path.cwd()
        
        # 查找项目根目录（包含.env或PROJECT.md的目录）
        # 向上查找最多10级，足够应对深层目录结构
        project_root = cwd
        current = cwd
        for _ in range(10):  # 最多向上查找10级
            if (current / ".env").exists() or (current / "PROJECT.md").exists():
                project_root = current
                break
            if current.parent == current:  # 到达根目录
                break
            current = current.parent
        
        search_paths.extend([
            project_root / "PROJECT.md",  # 项目根目录
            cwd / "PROJECT.md",           # 当前目录
            cwd / "AGENT.md",            # 备选名称
            cwd / ".agent" / "prompts.md",  # 子目录方式
        ])
        
        # 3. 用户主目录配置
        home = Path.home()
        search_paths.extend([
            home / ".dbrheo" / "PROJECT.md",  # 全局配置
            home / ".agent" / "prompts.md",   # 通用 agent 配置
        ])
        
        # 查找第一个存在的文件
        for path in search_paths:
            if path.exists() and path.is_file():
                try:
                    content = path.read_text(encoding='utf-8')
                    # 保存找到的路径，用于显示来源
                    self._project_prompt_source = str(path)
                    return content.strip()
                except Exception:
                    # 读取失败时静默跳过，尝试下一个
                    continue
        
        # 没有找到任何项目提示词
        self._project_prompt_source = None
        return ""
    
    def _get_project_prompt_source(self) -> str:
        """获取项目提示词的来源路径"""
        return getattr(self, '_project_prompt_source', 'None')
