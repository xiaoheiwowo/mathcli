"""
数学题库数据模型
支持选择题和计算题，包含错误分析和学习推荐功能
"""

import json
from typing import Dict, List, Optional, Union, Any
from dataclasses import dataclass, asdict
from datetime import datetime
from enum import Enum


class QuestionType(Enum):
    """题目类型枚举"""
    CHOICE = "choice"
    CALCULATION = "calculation"


class Difficulty(Enum):
    """难度等级枚举"""
    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"


class AnswerType(Enum):
    """答案类型枚举"""
    SINGLE_CHOICE = "single_choice"
    MULTIPLE_CHOICE = "multiple_choice"
    EXACT_VALUE = "exact_value"
    RANGE_VALUE = "range_value"
    EXPRESSION = "expression"


@dataclass
class QuestionInfo:
    """题目基本信息"""
    text: str
    subject: str
    grade: str
    chapter: str
    difficulty: str
    tags: List[str]
    estimated_time: int


@dataclass
class Choice:
    """选择题选项"""
    id: str
    content: str
    is_correct: bool
    explanation: str


@dataclass
class SolutionStep:
    """解题步骤"""
    step: int
    description: str
    formula: str


@dataclass
class QuestionSettings:
    """题目设置"""
    randomize_choices: bool = True
    multiple_select: bool = False
    has_none_of_above: bool = False
    show_hint: bool = True
    allow_calculator: bool = False
    require_work_shown: bool = False


@dataclass
class ChoiceAnswer:
    """选择题答案"""
    type: str
    value: str
    explanation: str


@dataclass
class CalculationAnswer:
    """计算题答案"""
    type: str
    value: str
    unit: Optional[str] = None
    tolerance: float = 0.0
    explanation: str = ""


@dataclass
class Question:
    """题目模型"""
    id: str
    question_info: QuestionInfo
    question_type: str
    correct_answer: Union[ChoiceAnswer, CalculationAnswer]
    choices: Optional[List[Choice]] = None
    solution_steps: Optional[List[SolutionStep]] = None
    question_settings: Optional[QuestionSettings] = None

    def __post_init__(self):
        if self.question_type == QuestionType.CHOICE.value and not self.choices:
            raise ValueError("选择题必须提供选项")
        if self.question_type == QuestionType.CALCULATION.value and self.choices:
            raise ValueError("计算题不应提供选项")


@dataclass
class ErrorCategory:
    """错误类别"""
    category_id: str
    name: str
    description: str
    subcategories: List[Dict[str, str]]


@dataclass
class ErrorAnalysis:
    """错误分析"""
    primary_error: str
    secondary_error: Optional[str] = None
    error_description: str = ""
    suggested_remediation: str = ""


@dataclass
class StudentAnswer:
    """学生答案"""
    answer_id: str
    question_id: str
    student_id: str
    selected_choice: Optional[str] = None
    calculated_answer: Optional[str] = None
    is_correct: bool = False
    error_analysis: Optional[ErrorAnalysis] = None
    timestamp: str = ""
    time_spent: int = 0

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now().isoformat()


@dataclass
class CommonError:
    """常见错误"""
    error_category: str
    frequency: float
    affected_questions: List[str]


@dataclass
class PracticeRecommendation:
    """练习推荐"""
    student_id: str
    weak_areas: List[str]
    recommended_questions: List[str]
    difficulty_progression: List[str]


@dataclass
class DifficultyDistribution:
    """难度分布"""
    easy: float
    medium: float
    hard: float

    def __post_init__(self):
        total = self.easy + self.medium + self.hard
        if abs(total - 1.0) > 0.01:
            raise ValueError("难度分布总和必须为1.0")


@dataclass
class LearningAnalytics:
    """学习分析"""
    difficulty_distribution: DifficultyDistribution
    common_errors: List[CommonError]
    recommended_practice: List[PracticeRecommendation]


@dataclass
class QuestionBank:
    """题库"""
    questions: List[Question]


@dataclass
class AnswerAnalysis:
    """答案分析"""
    error_categories: List[ErrorCategory]
    student_answers: List[StudentAnswer]


@dataclass
class QuestionDatabase:
    """完整的题库数据库"""
    version: str
    metadata: Dict[str, Any]
    question_bank: QuestionBank
    answer_analysis: AnswerAnalysis
    learning_analytics: LearningAnalytics

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return asdict(self)

    def to_json(self, filepath: str) -> None:
        """保存为JSON文件"""
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(self.to_dict(), f, ensure_ascii=False, indent=2)

    @classmethod
    def from_json(cls, filepath: str) -> 'QuestionDatabase':
        """从JSON文件加载"""
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return cls._from_dict(data)

    @classmethod
    def _from_dict(cls, data: Dict[str, Any]) -> 'QuestionDatabase':
        """从字典创建实例"""
        # 这里需要实现复杂的反序列化逻辑
        # 为了简化，这里只返回基本结构
        return cls(
            version=data.get('version', '1.0'),
            metadata=data.get('metadata', {}),
            question_bank=QuestionBank(questions=[]),
            answer_analysis=AnswerAnalysis(error_categories=[], student_answers=[]),
            learning_analytics=LearningAnalytics(
                difficulty_distribution=DifficultyDistribution(0.3, 0.5, 0.2),
                common_errors=[],
                recommended_practice=[]
            )
        )

    def add_question(self, question: Question) -> None:
        """添加题目"""
        self.question_bank.questions.append(question)
        self.metadata['total_questions'] = len(self.question_bank.questions)

    def add_student_answer(self, answer: StudentAnswer) -> None:
        """添加学生答案"""
        self.answer_analysis.student_answers.append(answer)

    def get_questions_by_difficulty(self, difficulty: str) -> List[Question]:
        """根据难度获取题目"""
        return [q for q in self.question_bank.questions 
                if q.question_info.difficulty == difficulty]

    def get_questions_by_tags(self, tags: List[str]) -> List[Question]:
        """根据标签获取题目"""
        return [q for q in self.question_bank.questions 
                if any(tag in q.question_info.tags for tag in tags)]

    def get_student_errors(self, student_id: str) -> List[StudentAnswer]:
        """获取学生的错误答案"""
        return [a for a in self.answer_analysis.student_answers 
                if a.student_id == student_id and not a.is_correct]

    def analyze_common_errors(self) -> List[CommonError]:
        """分析常见错误"""
        error_counts = {}
        question_errors = {}
        
        for answer in self.answer_analysis.student_answers:
            if not answer.is_correct and answer.error_analysis:
                error_type = answer.error_analysis.primary_error
                error_counts[error_type] = error_counts.get(error_type, 0) + 1
                
                if error_type not in question_errors:
                    question_errors[error_type] = set()
                question_errors[error_type].add(answer.question_id)
        
        total_answers = len(self.answer_analysis.student_answers)
        common_errors = []
        
        for error_type, count in error_counts.items():
            frequency = count / total_answers if total_answers > 0 else 0
            common_errors.append(CommonError(
                error_category=error_type,
                frequency=frequency,
                affected_questions=list(question_errors[error_type])
            ))
        
        return sorted(common_errors, key=lambda x: x.frequency, reverse=True)

    def generate_practice_recommendation(self, student_id: str) -> PracticeRecommendation:
        """为学生生成练习推荐"""
        student_errors = self.get_student_errors(student_id)
        
        # 分析学生的薄弱领域
        weak_areas = []
        if student_errors:
            error_types = [a.error_analysis.primary_error for a in student_errors 
                          if a.error_analysis]
            weak_areas = list(set(error_types))
        
        # 推荐相关题目
        recommended_questions = []
        if weak_areas:
            for question in self.question_bank.questions:
                # 这里可以根据错误类型和题目标签进行匹配
                if any(area in question.question_info.tags for area in weak_areas):
                    recommended_questions.append(question.id)
        
        return PracticeRecommendation(
            student_id=student_id,
            weak_areas=weak_areas,
            recommended_questions=recommended_questions[:10],  # 限制推荐数量
            difficulty_progression=["easy", "medium", "hard"]
        )


def create_sample_question_database() -> QuestionDatabase:
    """创建示例题库"""
    # 创建示例题目
    question1 = Question(
        id="q_001",
        question_info=QuestionInfo(
            text="计算：(-3 × (-2)³) 的值是？",
            subject="数学",
            grade="七年级",
            chapter="有理数运算",
            difficulty="medium",
            tags=["有理数", "乘方", "乘法", "负数运算"],
            estimated_time=120
        ),
        question_type="choice",
        correct_answer=ChoiceAnswer(
            type="single_choice",
            value="24",
            explanation="首先计算括号内的乘方：(-2)³ = -8，然后计算乘积：-3 × (-8) = 24"
        ),
        choices=[
            Choice(id="a", content="24", is_correct=True, 
                   explanation="正确计算了乘方及乘法，负负得正。"),
            Choice(id="b", content="-24", is_correct=False,
                   explanation="错误地忽略了乘方的负号对最终结果的影响。"),
            Choice(id="c", content="-48", is_correct=False,
                   explanation="计算过程中把乘方弄错和乘法弄混。"),
            Choice(id="d", content="18", is_correct=False,
                   explanation="错误将乘方计算为乘法。")
        ],
        solution_steps=[
            SolutionStep(step=1, description="首先计算括号内的乘方：(-2)³ = -8", 
                        formula="(-2)³ = -8"),
            SolutionStep(step=2, description="然后计算乘积：-3 × (-8) = 24", 
                        formula="-3 × (-8) = 24")
        ],
        question_settings=QuestionSettings()
    )

    question2 = Question(
        id="q_002",
        question_info=QuestionInfo(
            text="计算：2x + 3 = 11 中 x 的值",
            subject="数学",
            grade="七年级",
            chapter="一元一次方程",
            difficulty="easy",
            tags=["方程", "一元一次方程", "解方程"],
            estimated_time=90
        ),
        question_type="calculation",
        correct_answer=CalculationAnswer(
            type="exact_value",
            value="4",
            explanation="通过移项和系数化1得到 x = 4"
        ),
        solution_steps=[
            SolutionStep(step=1, description="移项：2x = 11 - 3", formula="2x = 8"),
            SolutionStep(step=2, description="系数化1：x = 8 ÷ 2", formula="x = 4")
        ],
        question_settings=QuestionSettings(require_work_shown=True)
    )

    # 创建题库
    question_bank = QuestionBank(questions=[question1, question2])

    # 创建错误类别
    error_categories = [
        ErrorCategory(
            category_id="sign_error",
            name="符号错误",
            description="在运算过程中符号处理错误",
            subcategories=[
                {"sub_id": "negative_sign_handling", "name": "负号处理错误", 
                 "description": "对负号的理解和运用错误"},
                {"sub_id": "operation_sign_confusion", "name": "运算符号混淆",
                 "description": "加减乘除符号使用错误"}
            ]
        ),
        ErrorCategory(
            category_id="calculation_error",
            name="计算错误",
            description="基本运算计算错误",
            subcategories=[
                {"sub_id": "arithmetic_mistake", "name": "算术错误",
                 "description": "基本加减乘除计算错误"},
                {"sub_id": "order_of_operations", "name": "运算顺序错误",
                 "description": "没有按照正确的运算顺序进行计算"}
            ]
        )
    ]

    # 创建答案分析
    answer_analysis = AnswerAnalysis(
        error_categories=error_categories,
        student_answers=[]
    )

    # 创建学习分析
    learning_analytics = LearningAnalytics(
        difficulty_distribution=DifficultyDistribution(0.3, 0.5, 0.2),
        common_errors=[],
        recommended_practice=[]
    )

    # 创建完整数据库
    return QuestionDatabase(
        version="1.0",
        metadata={
            "description": "数学题库数据结构 - 支持选择题和计算题",
            "created_at": "2024-01-01",
            "last_updated": "2024-01-01",
            "total_questions": 2
        },
        question_bank=question_bank,
        answer_analysis=answer_analysis,
        learning_analytics=learning_analytics
    )


if __name__ == "__main__":
    # 创建示例数据库
    db = create_sample_question_database()
    
    # 保存为JSON文件
    db.to_json("sample_question_database.json")
    print("示例题库已保存为 sample_question_database.json")
    
    # 演示一些功能
    print(f"题库中共有 {len(db.question_bank.questions)} 道题目")
    
    medium_questions = db.get_questions_by_difficulty("medium")
    print(f"中等难度题目有 {len(medium_questions)} 道")
    
    # 添加一个学生答案示例
    student_answer = StudentAnswer(
        answer_id="ans_001",
        question_id="q_001",
        student_id="student_001",
        selected_choice="b",
        is_correct=False,
        error_analysis=ErrorAnalysis(
            primary_error="sign_error",
            secondary_error="negative_sign_handling",
            error_description="学生错误地忽略了乘方的负号对最终结果的影响",
            suggested_remediation="重点练习负数的乘方运算，理解负数的奇偶次幂规律"
        ),
        time_spent=95
    )
    
    db.add_student_answer(student_answer)
    print(f"已添加学生答案，当前共有 {len(db.answer_analysis.student_answers)} 个答案记录")
