# MathCLI - 数学作业批改工具

AI驱动的数学作业批改工具，支持图片OCR识别、智能分析、自动批改、练习试卷生成和题库管理。

## 功能特性

- 📸 **图片OCR识别** - 支持中英文数学题目识别
- 📄 **OCR转Markdown** - 将试卷图片转换为结构化Markdown格式，支持智能题目匹配
- 🧠 **智能分析** - AI分析解题过程和结果
- ✅ **自动批改** - 判断答题正确性并分析错误原因
- 📊 **详细报告** - 生成JSON和Markdown格式的批改报告
- 📝 **练习试卷生成** - 根据错误类型生成针对性练习，支持随机性控制
- 📚 **题库管理** - 支持多源题库管理和统计
- 📈 **统计分析** - 提供详细的题库统计信息
- 🎲 **随机性增强** - 支持随机种子控制和难度范围筛选
- 🆔 **试卷ID系统** - 支持试卷唯一标识和题目映射管理

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

MathCLI提供以下主要命令：

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

# 使用随机种子（可重现的随机性）
python -m mathcli.cli practice -e 乘方 符号错误 --random-seed 12345

# 指定难度范围
python -m mathcli.cli practice -e 乘方 符号错误 --difficulty-range easy medium

# 组合使用
python -m mathcli.cli practice -e 乘方 符号错误 --choice-count 2 --calculation-count 2 --random-seed 42 --difficulty-range medium hard
```

**新增参数：**
- `--random-seed`: 随机种子，用于控制题目生成的随机性
- `--difficulty-range`: 难度范围，如 `easy medium` 或 `medium hard`

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

#### 4. OCR转Markdown (ocr-to-markdown)

```bash
# 基本用法（练习试卷格式）
python -m mathcli.cli ocr-to-markdown -i image.png

# 指定输出目录和文件名
python -m mathcli.cli ocr-to-markdown -i image.png -o my_output --filename my_test.md

# 使用考试试卷格式
python -m mathcli.cli ocr-to-markdown -i exam_image.png --format exam

# 使用作业格式
python -m mathcli.cli ocr-to-markdown -i homework_image.png --format homework

# 详细输出（显示智能匹配信息）
python -m mathcli.cli ocr-to-markdown -i image.png --verbose
```

### 智能题目匹配功能

OCR转Markdown功能现在支持智能题目匹配，能够：

- **多级匹配策略**：精确匹配、模糊匹配、关键词匹配、数学表达式匹配、AI语义匹配
- **自动题目分割**：智能识别和分割OCR文本中的各个题目
- **题目类型检测**：自动识别选择题和计算题
- **使用题库内容**：优先使用题库中的标准题目内容，提高转换质量
- **相似度评分**：为每个匹配结果提供相似度分数和匹配方法

#### 匹配算法

1. **精确匹配**：直接字符串比较，适用于OCR识别完全准确的情况
2. **模糊匹配**：使用SequenceMatcher计算相似度，适用于OCR有轻微错误的情况
3. **关键词匹配**：使用jieba分词提取关键词，计算关键词重叠度
4. **数学表达式匹配**：提取和比较数学表达式的等价性
5. **AI语义匹配**：使用qwen-plus模型进行语义理解，适用于复杂语义匹配

#### 使用示例

```bash
# 基本用法（自动智能匹配）
python -m mathcli.cli ocr-to-markdown -i image.png

# 详细输出模式（显示匹配过程）
python -m mathcli.cli ocr-to-markdown -i image.png --verbose

# 指定输出格式和文件
python -m mathcli.cli ocr-to-markdown -i image.png --format exam --filename exam_result.md
```

#### 5. 批改Markdown答卷 (grade-markdown)

```bash
# 基本用法
python -m mathcli.cli grade-markdown -f student_answer.md

# 使用LLM增强解析
python -m mathcli.cli grade-markdown -f student_answer.md --use-llm

# 禁用LLM，仅使用规则解析
python -m mathcli.cli grade-markdown -f student_answer.md --no-llm

# 使用试卷JSON文件进行精确匹配
python -m mathcli.cli grade-markdown -f student_answer.md -j practice_test.json

# 组合使用
python -m mathcli.cli grade-markdown -f student_answer.md -j practice_test.json --use-llm -o grading_output
```

**新增参数：**
- `-j, --json`: 试卷JSON文件路径，包含题目ID映射信息，用于精确匹配题目

#### 6. 基于易错点生成练习 (targeted-practice)

```bash
# 基本用法
python -m mathcli.cli targeted-practice -f student_answer.md

# 自定义题目数量
python -m mathcli.cli targeted-practice -f student_answer.md --choice-count 3 --calculation-count 3
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
- ✅ 支持随机种子控制
- ✅ 支持难度范围筛选
- ✅ 支持加权随机选择算法
- ✅ 支持题目顺序随机化

## 新功能特性

### 🎲 随机性增强

#### 随机种子控制
- 支持自定义随机种子，确保可重现的随机性
- 不指定种子时使用时间戳，确保每次生成都不同
- 适用于调试、测试和特定需求场景

#### 加权随机选择
- 实现智能加权选择算法，优先选择中等难度题目
- 添加随机因子，避免模式化选择
- 支持去重机制，确保不重复选择同一道题目

#### 多重随机化
- 题目筛选时随机打乱顺序
- 题目选择时使用加权随机
- 最终输出时再次随机打乱题目顺序

#### 难度范围筛选
- 支持指定难度范围（easy/medium/hard）
- 提供更精细的题目控制
- 确保生成符合要求的题目组合

### 🆔 试卷ID系统

#### 试卷唯一标识
- 自动生成试卷ID（格式：PR/EX/HW/TS + 12位十六进制）
- 支持试卷ID提取和识别
- 便于试卷管理和追踪

#### 题目映射管理
- 支持题目编号到题库ID的映射
- 从JSON文件解析题目映射信息
- 确保批改时精确匹配题目

#### 智能题目匹配
- 优先使用试卷JSON文件进行精确匹配
- 支持LLM增强解析和规则解析
- 提供详细的匹配过程日志

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

#### Markdown格式

```markdown
# 数学练习试卷

## 学生信息

**姓名**: _________________

**学号**: _________________

**班级**: _________________

---

## 试卷信息

**试卷ID**: PR123456789ABC
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

#### JSON格式

```json
{
  "test_info": {
    "test_id": "PR123456789ABC",
    "generated_at": "2024-01-01T12:00:00",
    "error_types": ["符号错误", "计算错误"],
    "total_questions": 4,
    "choice_questions": 2,
    "calculation_questions": 2,
    "test_type": "practice"
  },
  "questions": [
    {
      "id": "q_001",
      "question_number": "第 1 题",
      "question_type": "choice",
      "question_info": {
        "text": "计算：(-3 × (-2)³) 的值是？",
        "difficulty": "medium",
        "tags": ["有理数", "乘方", "乘法", "负数运算"]
      },
      "choices": [
        {"id": "a", "content": "24", "is_correct": true},
        {"id": "b", "content": "-24", "is_correct": false},
        {"id": "c", "content": "-48", "is_correct": false},
        {"id": "d", "content": "18", "is_correct": false}
      ]
    },
    {
      "id": "q_002",
      "question_number": "第 2 题",
      "question_type": "calculation",
      "question_info": {
        "text": "计算：(-2)⁴ ÷ 8 的值是？",
        "difficulty": "medium",
        "tags": ["有理数", "乘方", "除法"]
      }
    }
  ],
  "instructions": "练习试卷说明：\n本试卷重点练习：符号错误, 计算错误\n\n答题要求：\n1. 选择题请选择正确答案\n2. 计算题请写出完整的解题过程\n3. 注意运算符号的正确使用\n4. 仔细检查计算结果\n\n祝学习进步！"
}
```

**新JSON结构特点：**
- 在 `questions` 数组中包含 `question_number` 字段
- 移除了冗余的 `question_mapping` 字段
- 支持从 `questions` 数组直接解析题目映射
- 包含试卷ID和完整的题目信息

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

## 使用技巧

### 随机性控制

#### 开发环境
```bash
# 使用固定随机种子，便于调试和测试
python -m mathcli.cli practice -e 乘方 --random-seed 12345
```

#### 生产环境
```bash
# 不指定随机种子，确保每次生成都不同
python -m mathcli.cli practice -e 乘方 符号错误
```

#### 特殊需求
```bash
# 需要特定难度分布
python -m mathcli.cli practice -e 乘方 --difficulty-range easy medium

# 需要重现特定结果
python -m mathcli.cli practice -e 乘方 --random-seed 42
```

### 试卷ID系统

#### 生成试卷
```bash
# 生成试卷时会自动创建试卷ID
python -m mathcli.cli practice -e 乘方 -o my_test
# 生成的JSON文件包含试卷ID和题目映射
```

#### 批改答卷
```bash
# 使用试卷JSON文件进行精确匹配
python -m mathcli.cli grade-markdown -f student_answer.md -j my_test/practice_test.json
```

### 题库管理

#### 查看统计信息
```bash
# 查看题库统计
python -m mathcli.cli stats

# 保存统计信息到文件
python -m mathcli.cli stats -o statistics.txt
```

#### 添加新题目
1. 在 `database/` 目录下编辑相应的JSON文件
2. 确保题目格式符合模式定义
3. 运行统计命令验证新题目

## 故障排除

### 常见问题

#### 1. API密钥问题
```bash
# 检查环境变量
echo $DASHSCOPE_API_KEY

# 设置环境变量
export DASHSCOPE_API_KEY=your_api_key_here
```

#### 2. 题目生成失败
```bash
# 检查题库文件是否存在
ls database/

# 查看详细错误信息
python -m mathcli.cli practice -e 乘方 --verbose
```

#### 3. 批改结果不准确
```bash
# 使用试卷JSON文件进行精确匹配
python -m mathcli.cli grade-markdown -f student_answer.md -j practice_test.json

# 启用LLM增强解析
python -m mathcli.cli grade-markdown -f student_answer.md --use-llm
```

#### 4. 随机性不足
```bash
# 确保不指定随机种子
python -m mathcli.cli practice -e 乘方

# 检查题库大小
python -m mathcli.cli stats
```

### 调试模式

```bash
# 启用详细输出
python -m mathcli.cli practice -e 乘方 --verbose

# 查看处理日志
cat output/log.txt
```

## 更新日志

### v2.0.0 (最新)
- ✨ 新增随机性增强功能
- ✨ 新增试卷ID系统
- ✨ 新增题目映射管理
- ✨ 新增难度范围筛选
- ✨ 新增加权随机选择算法
- 🔧 优化JSON数据结构
- 🔧 改进题目匹配算法
- 🔧 增强错误处理机制

### v1.0.0
- 🎉 初始版本发布
- ✨ 支持图片OCR识别
- ✨ 支持自动批改
- ✨ 支持练习试卷生成
- ✨ 支持题库管理

## 许可证

MIT License
