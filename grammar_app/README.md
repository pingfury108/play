# 语法语义检查应用

基于 DeepSeek AI 的语法语义检查工具，支持中英文文本的语法、语义和拼写错误检查。

## 功能特点

- 智能语法检查：基于上下文语境分析语法错误
- 语义分析：检测语义不当或表达不清晰的地方
- 拼写检查：识别单词拼写错误
- 错误高亮：原文中红色标记错误位置，悬停查看原因
- 详细建议：提供每个错误的修改建议
- 优化文本：给出修正后的完整文本
- 支持中英文：支持中文和英文文本检查

## 安装

1. 安装依赖：

```bash
uv sync
```

2. 配置环境变量：

复制 `.env.example` 为 `.env`：

```bash
cp grammar_app/.env.example grammar_app/.env
```

编辑 `grammar_app/.env` 文件，填入你的 DeepSeek API Key：

```
DEEPSEEK_API_KEY=your_actual_api_key_here
DEEPSEEK_BASE_URL=https://api.deepseek.com
```

## 使用

1. 启动服务：

```bash
cd grammar_app
python grammar_app.py
```

默认运行在 `http://localhost:5002`，也可以指定端口：

```bash
python grammar_app.py 8000
```

2. 在浏览器中打开 `http://localhost:5002`

3. 在输入框中输入需要检查的文本

4. 点击"开始检查"按钮

5. 查看检查结果，包括：
   - 原文
   - 检查结果（错误列表）
   - 修改建议（详细的修改理由）
   - 优化后的文本

## API 接口

### 检查文本

- **URL**: `/check`
- **方法**: `POST`
- **请求体**:

```json
{
  "text": "需要检查的文本内容"
}
```

- **响应**:

```json
{
  "success": true,
  "result": {
    "format": "text",
    "data": "AI返回的检查结果（包含错误列表、修改建议、优化后的文本）"
  }
}
```

## 注意事项

- 文本长度限制：最多 5000 字符
- 建议文本长度：500-2000 字符效果最佳
- API 调用需要稳定的网络连接
- API 调用可能会产生费用，请注意使用量

## 技术栈

- 后端：Flask + Python 3.14+
- AI 服务：DeepSeek（OpenAI 兼容 API）
- 前端：原生 HTML/CSS/JavaScript
