# AIMath Helper - 数学题目生成器

一个基于 Gradio 的数学题目生成工具，用户可以通过输入提示词生成数学题目，并输出为 PDF 文件。

## 功能特性

- 🤖 AI 驱动的数学题目生成
- 📄 自动生成 PDF 文件
- 📁 会话管理（ID + 时间戳）
- 📊 历史会话查看
- 🎨 现代化的 Web 界面

## 安装和运行

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 配置环境变量

复制 `.env.example` 为 `.env` 并填入您的 OpenAI API Key：

```bash
cp .env.example .env
```

编辑 `.env` 文件，填入您的 OpenAI API Key：

```
OPENAI_API_KEY=your_actual_api_key_here
```

### 3. 运行程序

```bash
python src/gradio_ui.py
```

程序将在 `http://localhost:7860` 启动。

## 使用方法

1. **生成题目**：
   - 在"生成题目"标签页中输入提示词
   - 选择题目数量（1-20道）
   - 点击"生成题目"按钮
   - 查看生成的题目和下载 PDF 文件

2. **查看历史**：
   - 在"查看历史会话"标签页中查看所有生成的会话
   - 点击"刷新列表"更新会话记录

## 数据存储

- 所有生成的数据保存在 `data/` 目录下
- 每个会话使用 `ID_时间戳` 格式命名
- 每个会话包含：
  - `session_data.json`：会话元数据
  - `math_questions.pdf`：生成的 PDF 文件

## 项目结构

```
aimath-helper/
├── data/                   # 数据存储目录
├── src/
│   ├── main.py            # 核心逻辑
│   └── gradio_ui.py       # Gradio 界面
├── requirements.txt       # 依赖包
├── .env.example          # 环境变量示例
└── README.md             # 说明文档
```

## 依赖包

- `gradio==4.44.0`：Web 界面框架
- `reportlab==4.0.7`：PDF 生成
- `openai==1.3.7`：OpenAI API 客户端
- `python-dotenv==1.0.0`：环境变量管理