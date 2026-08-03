"""
AI Provider 基类
所有厂家都需要继承这个基类并实现 check_grammar 方法
"""

from abc import ABC, abstractmethod


CHECK_LIST = """## 检查清单
按以下维度逐项检查，不要遗漏：
1. **拼写**：错别字、英文拼写错误、同音字混淆
2. **语法**：主谓搭配、时态、语序、句式完整性
3. **标点**：标点使用是否正确、中英文标点是否混用
4. **语义**：用词是否准确、搭配是否得当、是否有歧义
5. **格式**：中英文间空格、全半角一致性"""


EXAMPLE = """## 示例

输入："我今天去了一个很好得餐厅，the food is delicous。"

输出：
{
  "has_error": true,
  "errors": [
    {
      "error_text": "好得",
      "correct_text": "好的",
      "reason": "结构助词误用：修饰名词应使用「的」而非「得」"
    },
    {
      "error_text": "delicous",
      "correct_text": "delicious",
      "reason": "英文拼写错误：缺少字母 i"
    },
    {
      "error_text": "。",
      "correct_text": ".",
      "reason": "英文句子末尾使用了中文句号，应统一标点风格"
    }
  ],
  "optimized_text": "我今天去了一个很好的餐厅，the food is delicious."
}"""


STUDENT_CHECK_LIST = """## 检查清单（中小学生语文作业）
按以下维度逐项检查，不要遗漏：
1. **错别字**：同音字混淆（如「在/再」「的/地/得」「做/坐」）、形近字误写、多笔少笔
2. **病句**：成分残缺、搭配不当、语序不当、重复啰嗦、前后矛盾、指代不明
3. **标点**：一逗到底、该断句未断句、句末标点缺失、引号冒号使用错误
4. **用词**：词语误用、成语误用、量词搭配不当"""


STUDENT_EXAMPLE = """## 示例

输入："妈妈今天回来了我就很开心了，我高兴的跳了起来，开心的说不出话来。"

输出：
{
  "has_error": true,
  "errors": [
    {
      "error_text": "高兴的跳了起来",
      "correct_text": "高兴地跳了起来",
      "reason": "错别字（的/地/得混淆）：「跳」是动词，前面修饰语应用「地」"
    },
    {
      "error_text": "开心的说不出话来",
      "correct_text": "开心地说不出话来",
      "reason": "错别字（的/地/得混淆）：「说不出话来」是动作状态，前面应用「地」"
    }
  ],
  "optimized_text": "妈妈今天回来了我就很开心了，我高兴地跳了起来，开心地说不出话来。"
}"""


TYPO_EXAMPLE = """## 示例

输入："今天我坐车去公园玩，我高兴的跳了起来，以经等不及了。"

输出：
{
  "has_error": true,
  "errors": [
    {
      "error_text": "高兴的跳了起来",
      "correct_text": "高兴地跳了起来",
      "reason": "错别字（的/地/得）：「跳」是动词，前面修饰语应用「地」"
    },
    {
      "error_text": "以经",
      "correct_text": "已经",
      "reason": "错别字（同音字混淆）：应为「已经」，表示事情完成"
    }
  ],
  "optimized_text": "今天我坐车去公园玩，我高兴地跳了起来，已经等不及了。"
}"""


class BaseProvider(ABC):
    """AI 语法检查 Provider 基类"""

    def __init__(
        self,
        api_key: str,
        base_url: str,
        model: str,
        json_mode: bool = False,
        thinking: bool = False,
        thinking_params: dict = None,
        thinking_disable_params: dict = None,
    ):
        self.api_key = api_key
        self.base_url = base_url
        self.model = model
        self.json_mode = json_mode
        self.thinking = thinking
        self.thinking_params = thinking_params or {}
        self.thinking_disable_params = thinking_disable_params or {}

    @abstractmethod
    def check_grammar(self, text: str = "", image: str = "", check_mode: str = "general") -> dict:
        """
        检查语法语义

        Args:
            text: 待检查的文本（文本模式）
            image: 图片 data URL，形如 "data:image/jpeg;base64,..."（图片模式）
            text 与 image 二选一。
            check_mode: 检查模式，"general" 通用校对 / "student" 中小学语文

        Returns:
            {
                "format": "json" | "raw",
                "data": {...} | "原始文本"
            }
        """
        pass

    def get_system_prompt(self) -> str:
        """获取系统提示词，可以被子类覆盖"""
        return """你是一位资深的中英文语言校对专家，具备以下能力：
- 语法分析：主谓一致、时态、句式结构、中文语序
- 拼写检查：英文单词拼写、中文错别字、同音字混淆
- 标点规范：中英文标点使用规范、全半角一致性
- 语义审查：用词准确性、搭配是否得当、表达是否自然
- 格式规范：中英文之间的空格、数字与单位的使用

## 核心原则
1. 只标注确定的错误，不标注风格偏好或可接受的表达变体
2. error_text 必须是原文的精确子串，逐字符匹配（包括空格和标点）
3. 每个错误独立标注，不合并相邻错误
4. 如果文本无错误，直接返回无错误结果"""

    def get_prompt(self, text: str) -> str:
        """文本模式提示词"""
        return f"""请检查以下文本，找出所有语法、拼写、标点和语义错误。

{CHECK_LIST}

{EXAMPLE}

## 输出格式
严格返回以下 JSON，不要包含任何其他文字：

{{
  "has_error": true/false,
  "errors": [
    {{
      "error_text": "原文中错误的精确子串",
      "correct_text": "修正后的文本",
      "reason": "错误类型 + 具体原因"
    }}
  ],
  "optimized_text": "修正后的完整文本"
}}

## 格式规则（重要，不得违反）
- optimized_text 必须与下方"待检查文本"的换行和段落结构完全一致（行数、空行位置、缩进、列表分行方式全部相同），仅在原位替换错误片段，不得重排、合并或拆分段落。
- 在 JSON 字符串中使用 \\n 表示换行；不要使用真实换行字符破坏 JSON。
- error_text 必须是原文的精确子串（含换行前后的字符）。
- 如果无错误，has_error 为 false，errors 为空数组，optimized_text 与原文完全相同（含换行结构）。

## 待检查文本
{text}"""

    def get_image_prompt(self) -> str:
        """图片模式提示词：先 OCR 再按相同规则检查"""
        return f"""请先准确识别图片中的所有文本（OCR），再对识别出的文本找出所有语法、拼写、标点和语义错误。

{CHECK_LIST}

{EXAMPLE}

## 输出格式
严格返回以下 JSON，不要包含任何其他文字：

{{
  "recognized_text": "从图片中识别出的完整原文",
  "has_error": true/false,
  "errors": [
    {{
      "error_text": "识别原文中错误的精确子串",
      "correct_text": "修正后的文本",
      "reason": "错误类型 + 具体原因"
    }}
  ],
  "optimized_text": "修正后的完整文本"
}}

## 格式规则（重要，不得违反）
- recognized_text 必须完整保留图片原文的段落与换行结构：标题、每个段落、每条列表项 / 题目选项（如 A. B. C. D.、1. 2. 3.）必须独立成行；图片中存在的空行也要保留为空行。绝对不允许把多段或多个选项合并成一行用空格分隔。
- optimized_text 必须与 recognized_text 的换行和段落结构完全一致（行数、空行位置、缩进、列表分行方式全部相同），仅在原位替换错误片段，不得重排、合并或拆分段落。
- 在 JSON 字符串中使用 \\n 表示换行；不要使用真实换行字符破坏 JSON。
- error_text 必须是 recognized_text 的精确子串（含换行前后的字符）。
- 如果无错误，has_error 为 false，errors 为空数组，optimized_text 与 recognized_text 完全相同（含换行结构）。"""

    def get_student_system_prompt(self) -> str:
        """语文模式系统提示词"""
        return """你是一位经验丰富的中小学语文老师，正在批改学生的作文/作业，具备以下能力：
- 错别字识别：同音字、形近字、「的地得」用法、多笔少笔
- 病句修改：成分残缺、搭配不当、语序不当、重复啰嗦、前后矛盾
- 标点规范：断句、句末标点、引号冒号使用
- 用词指导：词语、成语、量词使用是否恰当

## 核心原则
1. 以学生视角批改，指出确定的错误，不苛求文采，不按成人写作标准拔高
2. error_text 必须是原文的精确子串，逐字符匹配（包括空格和标点）
3. 每个错误独立标注，不合并相邻错误
4. reason 用「错误类型 + 具体讲解」的形式，语气像老师辅导学生，简明易懂
5. 如果文本无错误，直接返回无错误结果
6. 手写稿中作者自己涂改、划掉重写的部分不算错误，以最终保留的文字为准"""

    def get_student_prompt(self, text: str) -> str:
        """语文模式文本提示词"""
        return f"""请批改以下学生作文，找出所有错别字、病句、标点和用词错误。

{STUDENT_CHECK_LIST}

{STUDENT_EXAMPLE}

## 输出格式
严格返回以下 JSON，不要包含任何其他文字：

{{
  "has_error": true/false,
  "errors": [
    {{
      "error_text": "原文中错误的精确子串",
      "correct_text": "修正后的文本",
      "reason": "错误类型 + 具体讲解"
    }}
  ],
  "optimized_text": "修正后的完整文本"
}}

## 格式规则（重要，不得违反）
- optimized_text 必须与下方"待检查文本"的换行和段落结构完全一致（行数、空行位置、缩进、列表分行方式全部相同），仅在原位替换错误片段，不得重排、合并或拆分段落。
- 在 JSON 字符串中使用 \\n 表示换行；不要使用真实换行字符破坏 JSON。
- error_text 必须是原文的精确子串（含换行前后的字符）。
- 如果无错误，has_error 为 false，errors 为空数组，optimized_text 与原文完全相同（含换行结构）。

## 待检查文本
{text}"""

    def get_student_image_prompt(self) -> str:
        """语文模式图片提示词：先识别手写体再批改"""
        return f"""请先准确识别图片中学生手写作业的所有文字，再对识别出的文本进行批改，找出所有错别字、病句、标点和用词错误。

## 手写稿识别与涂改处理（最重要，优先执行）

这是学生手写稿，边写边改是常态。识别时严格遵守：

1. **只识别最终文本**：凡被划掉、涂黑、圈掉、打叉的字、词、标点，一律视为不存在，不得写入 recognized_text
2. **按修改符号还原作者意图**：
   - 插入符号（∧ 等）旁补写的小字 → 插入到符号所指位置
   - 对调符号连接的内容 → 按调换后的顺序识别
   - 原位 / 上方重写的字 → 替代被涂掉的原字
3. **涂改本身不是错误**：原字形与改正后字形的差异，是作者已完成的自我修正，严禁把被划掉的内容当作错别字或病句上报
4. **难辨字从宽**：字形潦草但结合上下文语义通顺时，按最合理的字识别且不报错；只标注最终文本中确定存在的错误
5. **标点涂改同理**：被划掉的标点不识别，以最终保留的标点判断标点使用是否正确
6. **逐字识别，不漏不多**：按行文顺序逐字识别，不得漏字、跳行、添字，也不得用自己的话改写或“顺”成通顺的句子；重复字、叠词（如「非常非常」）必须按实际数量保留
7. **逐段自检**：输出 recognized_text 前，按段落逐段与图片核对，确认无漏段、漏句、漏字

## 其他识别要求
- 忽略方格线、页眉页脚（年月日、第页）、「错别字改正栏」、家长签字、老师批语等非正文内容
- 段首缩进两个字的视为新段落；标题单独成行

{STUDENT_CHECK_LIST}

{STUDENT_EXAMPLE}

## 输出格式
严格返回以下 JSON，不要包含任何其他文字：

{{
  "recognized_text": "从图片中识别出的完整原文",
  "has_error": true/false,
  "errors": [
    {{
      "error_text": "识别原文中错误的精确子串",
      "correct_text": "修正后的文本",
      "reason": "错误类型 + 具体讲解"
    }}
  ],
  "optimized_text": "修正后的完整文本"
}}

## 格式规则（重要，不得违反）
- recognized_text 必须与图片中最终文本逐字一致：不漏字、不添字、不改写；重复字按实际数量保留。
- recognized_text 必须是涂改完成后的最终文本，不得包含任何被划掉的内容。
- error_text 必须是最终文本的精确子串；若一个“错误”只存在于被涂改的部分，不得上报。
- recognized_text 必须完整保留原文的段落与换行结构：标题、每个段落必须独立成行。绝对不允许把多段合并成一行用空格分隔。
- optimized_text 必须与 recognized_text 的换行和段落结构完全一致（行数、空行位置、缩进全部相同），仅在原位替换错误片段，不得重排、合并或拆分段落。
- 在 JSON 字符串中使用 \\n 表示换行；不要使用真实换行字符破坏 JSON。
- error_text 必须是 recognized_text 的精确子串（含换行前后的字符）。
- 如果无错误，has_error 为 false，errors 为空数组，optimized_text 与 recognized_text 完全相同（含换行结构）。"""

    def get_typo_system_prompt(self) -> str:
        """手写批改模式系统提示词"""
        return """你是一位专门批改学生手写作业的中小学语文老师，具备以下能力：
- 错别字识别：同音字、形近字、「的地得」用法、多笔少笔
- 病句修改：成分残缺、搭配不当、语序不当、重复啰嗦、前后矛盾
- 标点规范：断句、句末标点、引号冒号使用
- 用词指导：词语、成语、量词使用是否恰当

## 核心原则
1. 以学生视角批改，指出确定的错误，不苛求文采，不按成人写作标准拔高
2. 区分“潦草”与“写错”：字形潦草但能看出是某个正确字时，按正确字识别不报错；只有确属写成了另一个字或笔画明显错误时才标注为错别字
3. 不确定是否写错时，不报（宁可漏报不可误报）
4. error_text 必须是原文的精确子串，逐字符匹配
5. 每个错误独立标注，不合并相邻错误
6. reason 用「错误类型 + 具体讲解」的形式，简明易懂
7. 手写稿中作者自己涂改、划掉重写的部分不算错误，以最终保留的文字为准
8. 如果文本无错误，直接返回无错误结果"""

    def get_typo_prompt(self, text: str) -> str:
        """手写批改模式文本提示词"""
        return f"""请批改以下学生文本，找出所有错别字、病句、标点和用词错误。

{STUDENT_CHECK_LIST}

{TYPO_EXAMPLE}

## 输出格式
严格返回以下 JSON，不要包含任何其他文字：

{{
  "has_error": true/false,
  "errors": [
    {{
      "error_text": "原文中错误的精确子串",
      "correct_text": "修正后的文本",
      "reason": "错误类型 + 具体讲解"
    }}
  ],
  "optimized_text": "修正后的完整文本"
}}

## 格式规则（重要，不得违反）
- optimized_text 必须与下方"待检查文本"的换行和段落结构完全一致（行数、空行位置、缩进、列表分行方式全部相同），仅在原位替换错误片段，不得重排、合并或拆分段落。
- 在 JSON 字符串中使用 \\n 表示换行；不要使用真实换行字符破坏 JSON。
- error_text 必须是原文的精确子串（含换行前后的字符）。
- 如果无错误，has_error 为 false，errors 为空数组，optimized_text 与原文完全相同（含换行结构）。

## 待检查文本
{text}"""

    def get_typo_image_prompt(self) -> str:
        """手写批改模式图片提示词：先识别手写体再批改"""
        return f"""请先准确识别图片中学生手写作业的所有文字，再对识别出的文本进行批改，找出所有错别字、病句、标点和用词错误。

## 手写稿识别与涂改处理（最重要，优先执行）

这是学生手写稿，边写边改是常态。识别时严格遵守：

1. **只识别最终文本**：凡被划掉、涂黑、圈掉、打叉的字、词、标点，一律视为不存在，不得写入 recognized_text
2. **按修改符号还原作者意图**：
   - 插入符号（∧ 等）旁补写的小字 -> 插入到符号所指位置
   - 对调符号连接的内容 -> 按调换后的顺序识别
   - 原位 / 上方重写的字 -> 替代被涂掉的原字
3. **涂改本身不是错误**：原字形与改正后字形的差异，是作者已完成的自我修正，严禁把被划掉的内容当作错别字上报
4. **难辨字从宽**：字形潦草但结合上下文语义通顺时，按最合理的字识别且不报错；只标注最终文本中确定存在的错误
5. **标点涂改同理**：被划掉的标点不识别，以最终保留的标点判断标点使用是否正确
6. **逐字识别，不漏不多**：按行文顺序逐字识别，不得漏字、跳行、添字，也不得用自己的话改写或“顺”成通顺的句子；重复字、叠词（如「非常非常」）必须按实际数量保留
7. **逐段自检**：输出 recognized_text 前，按段落逐段与图片核对，确认无漏段、漏句、漏字

## 其他识别要求
- 忽略方格线、页眉页脚（年月日、第页）、「错别字改正栏」、家长签字、老师批语等非正文内容
- 段首缩进两个字的视为新段落；标题单独成行

## 错别字检查与“潦草/写错”区分（关键）
1. 先准确识别每个字，再逐字判断是否写成了错字
2. 字形潦草但能看出是某个正确字时，按正确字识别，不报错
3. 只有字迹足够清晰、确属写成了另一个字或笔画明显错误时，才标注为错别字
4. 不确定是否写错时，不报（宁可漏报不可误报）
5. 同音字用法错误（如该用「地」却写成「的」）只要该字写得清楚就应标注

{STUDENT_CHECK_LIST}

{TYPO_EXAMPLE}

## 输出格式
严格返回以下 JSON，不要包含任何其他文字：

{{
  "recognized_text": "从图片中识别出的完整原文",
  "has_error": true/false,
  "errors": [
    {{
      "error_text": "识别原文中错误的精确子串",
      "correct_text": "修正后的文本",
      "reason": "错误类型 + 具体讲解"
    }}
  ],
  "optimized_text": "修正后的完整文本"
}}

## 格式规则（重要，不得违反）
- recognized_text 必须与图片中最终文本逐字一致：不漏字、不添字、不改写；重复字按实际数量保留。
- recognized_text 必须是涂改完成后的最终文本，不得包含任何被划掉的内容。
- error_text 必须是最终文本的精确子串；若一个“错误”只存在于被涂改的部分，不得上报。
- recognized_text 必须完整保留原文的段落与换行结构：标题、每个段落必须独立成行。绝对不允许把多段合并成一行用空格分隔。
- optimized_text 必须与 recognized_text 的换行和段落结构完全一致（行数、空行位置、缩进全部相同），仅在原位替换错误片段，不得重排、合并或拆分段落。
- 在 JSON 字符串中使用 \\n 表示换行；不要使用真实换行字符破坏 JSON。
- error_text 必须是 recognized_text 的精确子串（含换行前后的字符）。
- 如果无错误，has_error 为 false，errors 为空数组，optimized_text 与 recognized_text 完全相同（含换行结构）。"""

    def clean_json_response(self, text: str) -> str:
        """清理 markdown 代码块标记，并提取 JSON 对象"""
        text = text.strip()
        if text.startswith("```json"):
            text = text[7:]
        elif text.startswith("```"):
            text = text[3:]
        if text.endswith("```"):
            text = text[:-3]
        text = text.strip()

        # 容错：模型有时输出双大括号 {{ }}，修正为单大括号
        if text.startswith("{{") and not text.startswith("{"):
            text = "{" + text[2:]
        if text.endswith("}}") and not text.endswith("}"):
            text = text[:-2] + "}"

        # LLM 有时在 JSON 前后输出说明文字，直接定位第一个 { 和最后一个 }
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1 and end > start:
            inner = text[start : end + 1]
            # 如果提取的内容内部有双大括号包裹，也尝试修正
            if inner.startswith("{{") and inner.endswith("}}"):
                inner = "{" + inner[2:-2] + "}"
            text = inner

        return text
