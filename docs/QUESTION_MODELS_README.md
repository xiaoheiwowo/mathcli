# 数学题库数据结构设计

## 概述

本设计提供了一个完整的数学题库数据结构，支持选择题和计算题两种类型，包含错误分析和学习推荐功能，特别针对学生易错点出题训练进行了优化。

## 核心特性

- **双题型支持**: 选择题和计算题
- **错误分析**: 详细的错误分类和分析
- **学习推荐**: 基于错误分析的个性化练习推荐
- **可扩展性**: 支持未来功能扩展
- **JSON存储**: 便于数据交换和存储

## 数据结构

### 1. Question Model (题目模型)

#### 基本信息
- `id`: 题目唯一标识符
- `question_info`: 题目详细信息
- `question_type`: 题目类型 (choice/calculation)
- `correct_answer`: 正确答案
- `choices`: 选择题选项 (仅选择题)
- `solution_steps`: 解题步骤
- `question_settings`: 题目设置

#### 题目信息 (QuestionInfo)
```json
{
  "text": "题目文本",
  "subject": "学科",
  "grade": "年级", 
  "chapter": "章节",
  "difficulty": "难度等级 (easy/medium/hard)",
  "tags": ["标签列表"],
  "estimated_time": "预估答题时间(秒)"
}
```

#### 选择题答案 (ChoiceAnswer)
```json
{
  "type": "single_choice/multiple_choice",
  "value": "正确答案值",
  "explanation": "答案解释"
}
```

#### 计算题答案 (CalculationAnswer)
```json
{
  "type": "exact_value/range_value/expression",
  "value": "正确答案值",
  "unit": "单位(可选)",
  "tolerance": "容差",
  "explanation": "答案解释"
}
```

### 2. Answer Model (答案模型)

#### 学生答案 (StudentAnswer)
- `answer_id`: 答案唯一标识符
- `question_id`: 题目ID
- `student_id`: 学生ID
- `selected_choice`: 选择的选项 (选择题)
- `calculated_answer`: 计算答案 (计算题)
- `is_correct`: 是否正确
- `error_analysis`: 错误分析
- `timestamp`: 答题时间
- `time_spent`: 答题用时

#### 错误分析 (ErrorAnalysis)
- `primary_error`: 主要错误类型
- `secondary_error`: 次要错误类型
- `error_description`: 错误描述
- `suggested_remediation`: 建议补救措施

### 3. 错误分类系统

#### 主要错误类别
1. **符号错误 (sign_error)**
   - 负号处理错误
   - 运算符号混淆

2. **计算错误 (calculation_error)**
   - 算术错误
   - 运算顺序错误

3. **概念错误 (concept_error)**
   - 公式理解错误
   - 性质混淆

### 4. 学习分析功能

#### 常见错误分析
- 错误频率统计
- 影响题目识别
- 错误模式分析

#### 个性化推荐
- 薄弱领域识别
- 推荐题目生成
- 难度递进规划

## 使用示例

### 创建题目

```python
from mathcli.question_models import Question, QuestionInfo, Choice, ChoiceAnswer

# 创建选择题
question = Question(
    id="q_001",
    question_info=QuestionInfo(
        text="计算：(-3 × (-2)³) 的值是？",
        subject="数学",
        grade="七年级",
        chapter="有理数运算",
        difficulty="medium",
        tags=["有理数", "乘方", "乘法"],
        estimated_time=120
    ),
    question_type="choice",
    correct_answer=ChoiceAnswer(
        type="single_choice",
        value="24",
        explanation="正确计算了乘方及乘法，负负得正"
    ),
    choices=[
        Choice(id="a", content="24", is_correct=True, explanation="正确"),
        Choice(id="b", content="-24", is_correct=False, explanation="符号错误"),
        # ... 更多选项
    ]
)
```

### 记录学生答案

```python
from mathcli.question_models import StudentAnswer, ErrorAnalysis

# 记录错误答案
student_answer = StudentAnswer(
    answer_id="ans_001",
    question_id="q_001",
    student_id="student_001",
    selected_choice="b",
    is_correct=False,
    error_analysis=ErrorAnalysis(
        primary_error="sign_error",
        secondary_error="negative_sign_handling",
        error_description="学生错误地忽略了乘方的负号",
        suggested_remediation="重点练习负数的乘方运算"
    ),
    time_spent=95
)
```

### 题库操作

```python
from mathcli.question_models import QuestionDatabase, create_sample_question_database

# 创建题库
db = create_sample_question_database()

# 添加题目
db.add_question(question)

# 添加学生答案
db.add_student_answer(student_answer)

# 分析常见错误
common_errors = db.analyze_common_errors()

# 生成练习推荐
recommendation = db.generate_practice_recommendation("student_001")

# 保存为JSON
db.to_json("question_bank.json")
```

## 文件结构

```
windsurf-project/
├── question_models.json          # 完整数据结构示例
├── question_schema.json          # JSON Schema 定义
├── mathcli/
│   └── question_models.py        # Python 数据模型类
├── example_usage.py              # 使用示例
└── QUESTION_MODELS_README.md     # 本文档
```

## 扩展性设计

### 1. 题目类型扩展
- 支持更多题目类型 (填空题、判断题等)
- 通过 `question_type` 字段扩展

### 2. 错误分类扩展
- 添加新的错误类别
- 支持多级错误分类

### 3. 学习分析扩展
- 添加更多分析维度
- 支持更复杂的推荐算法

### 4. 数据存储扩展
- 支持数据库存储
- 支持分布式存储

## 针对易错点出题训练

### 错误模式识别
1. 分析学生历史答题数据
2. 识别常见错误模式
3. 建立错误-知识点映射

### 个性化出题
1. 基于错误分析生成相似题目
2. 调整题目难度和类型
3. 提供针对性练习

### 学习路径规划
1. 识别学生薄弱环节
2. 制定个性化学习计划
3. 跟踪学习进度

## 技术特点

- **类型安全**: 使用 Python dataclass 确保类型安全
- **JSON Schema**: 提供完整的数据验证
- **可序列化**: 支持 JSON 格式存储和传输
- **可扩展**: 模块化设计便于功能扩展
- **易用性**: 提供简洁的 API 接口

## 未来规划

1. **AI 集成**: 集成 AI 进行智能出题和错误分析
2. **实时分析**: 支持实时学习数据分析
3. **多语言支持**: 支持多语言题目和界面
4. **云端同步**: 支持多设备数据同步
5. **高级推荐**: 基于机器学习的个性化推荐

## 总结

本数据结构设计充分考虑了数学教育的实际需求，特别是针对学生易错点的训练需求。通过详细的错误分类和分析系统，能够为每个学生提供个性化的学习建议和练习推荐，有效提高学习效果。
