# MathCLI - 数学作业批改工具

AI驱动的数学作业批改工具，支持图片OCR识别、智能分析、自动批改、练习试卷生成和题库管理。

## 功能特性

- 📸 **图片OCR识别** - 支持中英文数学题目识别
- 🧠 **智能分析** - AI分析解题过程和结果
- ✅ **自动批改** - 判断答题正确性并分析错误原因
- 📊 **详细报告** - 生成JSON和Markdown格式的批改报告
- 📝 **练习试卷生成** - 根据错误类型生成针对性练习
- 📚 **题库管理** - 支持多源题库管理和统计
- 📈 **统计分析** - 提供详细的题库统计信息

## 模型

- qwen-vl-ocr
- qwen-plus

## 安装 & 运行

### 环境准备

```bash
# 安装依赖
pip install -r requirements.txt

# 设置API密钥
export DASHSCOPE_API_KEY=sk-25ad********63587a
```

### 命令行工具

MathCLI提供三个主要命令：

#### 1. 批改作业 (grade)

```bash
# 基本用法
python -m mathcli.cli grade -i image.png

# 指定输出目录
python -m mathcli.cli grade -i image.png -o my_output

# 详细输出
python -m mathcli.cli grade -i image.png --verbose
```

#### 2. 生成练习试卷 (practice)

```bash
# 基本用法
python -m mathcli.cli practice -e 符号错误 计算错误

# 自定义题目数量
python -m mathcli.cli practice -e 分数运算 小数运算 --choice-count 3 --calculation-count 3

# 指定输出目录
python -m mathcli.cli practice -e 混合运算 -o practice_output
```

支持的错误类型：
- 符号错误
- 计算错误
- 分数运算
- 小数运算
- 混合运算
- 方程
- 乘方

#### 3. 查看题库统计 (stats)

```bash
# 表格格式（默认）
python -m mathcli.cli stats

# JSON格式
python -m mathcli.cli stats --format json

# 保存到文件
python -m mathcli.cli stats -o statistics.txt
```

### 传统运行方式

```bash
# 使用run.py（仅支持批改功能）
python3 run.py -i ims/0-good.png
```

## 数据存储

### 数据库结构

项目使用分离的数据存储架构：

```
database/
├── db_question_bank.json      # 主题库（计算题等）
├── db_question_bank_choice.json  # 选择题库
├── db_student.json           # 学生信息
└── db_answer.json           # 答题记录
```

### 输出文件

#### 批改作业 (grade)
运行后会在指定输出目录生成：
- `result.json` - 完整的批改结果（JSON格式）
- `summary.md` - 批改报告摘要（Markdown格式）
- `log.txt` - 详细的处理日志

#### 练习试卷 (practice)
生成练习试卷文件：
- `practice_test.json` - 试卷数据（JSON格式）
- `practice_test.md` - 试卷内容（Markdown格式）

#### 统计信息 (stats)
- 控制台输出：表格或JSON格式
- 文件输出：保存到指定文件

## 处理流程

1. **图片预处理** - 优化图片质量以提高OCR准确率
2. **OCR文字识别** - 提取图片中的文字和数学表达式
3. **题目解析** - 将OCR结果解析为结构化的数学题目
4. **解答验证** - 验证学生解答的正确性
5. **错误分析** - 分析错误原因并提供改进建议
6. **报告生成** - 生成详细的批改报告

## 支持的题型

### 批改功能
- ✅ 分数四则运算
- ✅ 基础算术运算
- ✅ 有理数运算
- ✅ 乘方运算
- 🔄 方程求解（开发中）
- 🔄 应用题（开发中）

### 练习试卷生成
- ✅ 选择题（从题库随机选择）
- ✅ 计算题（从题库随机选择）
- ✅ 支持按错误类型筛选
- ✅ 支持自定义题目数量

## 示例输出

### 批改结果示例

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

### 练习试卷示例

```markdown
# 数学练习试卷

## 学生信息

**姓名**: _________________

**学号**: _________________

**班级**: _________________

---

## 试卷信息

**生成时间**: 2024-01-01 12:00:00
**重点练习**: 符号错误, 计算错误
**题目总数**: 4
**选择题**: 2 道
**计算题**: 2 道

## 答题说明

练习试卷说明：
本试卷重点练习：符号错误, 计算错误

答题要求：
1. 选择题请选择正确答案
2. 计算题请写出完整的解题过程
3. 注意运算符号的正确使用
4. 仔细检查计算结果

祝学习进步！

## 题目

### 第 1 题

**题目**: 计算：(-3) × (-2)³ 的值是？

**选项**:
- a. 24
- b. -24
- c. -48
- d. 18

**答案**: (    )

---

### 第 2 题

**题目**: 计算：(-7) + 12 的值是？

**选项**:
- a. -19
- b. 19
- c. 5
- d. -5

**答案**: (    )

---

### 第 3 题

**题目**: 计算：(-5) - (-9) 的值是？

**解答**: 

```
请在此处写出完整的解题过程
```

---

### 第 4 题

**题目**: 计算：(-4) × (-6) 的值是？

**解答**: 

```
请在此处写出完整的解题过程
```

---
```

### 统计信息示例

```
============================================================
📊 数学题库统计信息
============================================================

📋 基本信息
总题目数: 25
来源文件: db_question_bank.json, db_question_bank_choice.json
总预估时间: 1500 分钟
平均预估时间: 60.0 分钟/题

📝 题型分布
  choice: 15 题 (60.0%)
  calculation: 10 题 (40.0%)

🎯 难度分布
  easy: 15 题 (60.0%)
  medium: 8 题 (32.0%)
  hard: 2 题 (8.0%)

📚 章节分布
  有理数运算: 20 题 (80.0%)
  一元一次方程: 3 题 (12.0%)
  数的性质: 2 题 (8.0%)

🏷️  标签分布 (前10个)
   1. 有理数: 20 题 (80.0%)
   2. 负数运算: 15 题 (60.0%)
   3. 乘方: 8 题 (32.0%)
   4. 方程: 3 题 (12.0%)
   5. 质数: 2 题 (8.0%)

❌ 错误类型覆盖
  符号错误: 20 题 (80.0%)
  计算错误: 25 题 (100.0%)
  分数运算: 0 题 (0.0%)
  小数运算: 0 题 (0.0%)
  混合运算: 0 题 (0.0%)
  方程: 3 题 (12.0%)
  乘方: 8 题 (32.0%)

⏰ 生成时间: 2024-01-01T12:00:00
============================================================
```

## 开发

### 项目结构

```
mathcli/
├── __init__.py              # 包初始化
├── cli.py                  # 命令行接口（主要功能）
├── ocr_processor.py        # OCR处理模块
├── ai_processor.py         # AI分析模块
├── question_models.py      # 题目数据模型
├── question.py             # 题目处理模块
├── requirements.txt        # 依赖列表
├── setup.py               # 安装配置
├── run.py                 # 传统运行入口
├── docs/                  # 文档目录
│   ├── design.md          # 设计文档
│   ├── QUESTION_MODELS_README.md  # 数据模型说明
│   └── question_schema.json       # 题目模式定义
├── resource/              # 资源文件
│   └── choice.json        # 选择题数据
└── README.md              # 项目文档

database/                  # 数据库目录
├── db_question_bank.json      # 主题库
├── db_question_bank_choice.json  # 选择题库
├── db_student.json           # 学生信息
└── db_answer.json           # 答题记录

output/                    # 输出目录
├── result.json            # 批改结果
├── summary.md             # 批改摘要
├── practice_test.json     # 练习试卷数据
├── practice_test.md       # 练习试卷内容
└── log.txt               # 处理日志
```

### 扩展功能

#### 添加新题型支持

要添加新的题型支持，请在 `ai_processor.py` 中：

1. 在 `_identify_problem_type()` 中添加题型识别逻辑
2. 实现对应的验证函数（如 `_validate_new_problem_type()`）
3. 在 `validate_solution()` 中添加调用逻辑

#### 添加新错误类型

要添加新的错误类型支持，请在 `cli.py` 中：

1. 在 `error_type_mapping` 中添加新的错误类型映射
2. 更新 `_question_matches_error_types()` 方法
3. 更新命令行帮助文档

#### 添加新题库源

要添加新的题库源：

1. 在 `database/` 目录下创建新的JSON文件
2. 在 `_load_question_database()` 中添加文件路径
3. 确保JSON格式符合题目模式定义

### 配置说明

#### 环境变量

- `DASHSCOPE_API_KEY`: 阿里云DashScope API密钥（必需）

#### 配置文件

- `database/`: 数据库文件目录
- `output/`: 默认输出目录
- `mathcli/docs/question_schema.json`: 题目数据模式定义

## 许可证

MIT License
