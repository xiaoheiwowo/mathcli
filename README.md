# MathCLI - 数学作业批改工具

AI驱动的数学作业批改工具，支持图片OCR识别、智能分析和自动批改。

## 功能特性

- 📸 **图片OCR识别** - 支持中英文数学题目识别
- 🧠 **智能分析** - AI分析解题过程和结果
- ✅ **自动批改** - 判断答题正确性并分析错误原因
- 📊 **详细报告** - 生成JSON和Markdown格式的批改报告

## 模型

- qwen-vl-ocr
- qwen-plus

## 安装 & 运行

```bash
pip install -r requirements.txt

export DASHSCOPE_API_KEY=sk-25ad********63587a

python3 run.py -i ims/0-good.png
```

## 说明

### 输出文件

运行后会在 `output` 目录生成以下文件：

- `result.json` - 完整的批改结果（JSON格式）
- `summary.md` - 批改报告摘要（Markdown格式）
- `log.txt` - 详细的处理日志

## 处理流程

1. **图片预处理** - 优化图片质量以提高OCR准确率
2. **OCR文字识别** - 提取图片中的文字和数学表达式
3. **题目解析** - 将OCR结果解析为结构化的数学题目
4. **解答验证** - 验证学生解答的正确性
5. **错误分析** - 分析错误原因并提供改进建议
6. **报告生成** - 生成详细的批改报告

## 支持的题型

- ✅ 分数四则运算
- ✅ 基础算术运算
- 🔄 方程求解（开发中）
- 🔄 应用题（开发中）

## 示例输出

```json
{
  "summary": {
    "total_problems": 3,
    "correct_problems": 2,
    "accuracy_percentage": 66.7,
    "processing_timestamp": "2024-01-01T12:00:00"
  },
  "problems": [
    {
      "problem": {
        "id": "problem_1",
        "text": "14. 11/16 + 4/9 + 5/16",
        "type": "fraction",
        "student_solution": "= 11/16 + 5/16 + 4/9\n= 16/16 + 4/9\n= 1 + 4/9\n= 13/9"
      },
      "validation": {
        "is_correct": true,
        "confidence": 0.9
      }
    }
  ]
}
```

## 开发

### 项目结构

```
mathcli/
├── __init__.py          # 包初始化
├── cli.py              # 命令行接口
├── ocr_processor.py    # OCR处理模块
├── ai_processor.py     # AI分析模块
├── requirements.txt    # 依赖列表
├── setup.py           # 安装配置
└── README.md          # 项目文档
```

### 扩展功能

要添加新的题型支持，请在 `ai_processor.py` 中：

1. 在 `_identify_problem_type()` 中添加题型识别逻辑
2. 实现对应的验证函数（如 `_validate_new_problem_type()`）
3. 在 `validate_solution()` 中添加调用逻辑

## 许可证

MIT License
