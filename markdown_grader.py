"""Markdown格式答卷批改模块"""

import re
import json
import logging
import os
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
from pathlib import Path
from datetime import datetime

try:
    from .ai_processor import AIProcessor, SolutionStep
    from .question_models import Question, QuestionType, StudentAnswer, ErrorAnalysis
    from .test_id_manager import TestIDManager
except ImportError:
    from ai_processor import AIProcessor, SolutionStep
    from question_models import Question, QuestionType, StudentAnswer, ErrorAnalysis
    from test_id_manager import TestIDManager


@dataclass
class MarkdownAnswer:
    """Markdown答卷中的单个答案"""
    question_number: str  # 试卷中的题目编号，如"1", "2", "3"
    question_id: str      # 题库中的题目ID，如"q_001", "choice_006"
    question_text: str
    question_type: str    # "choice" or "calculation"
    student_answer: str
    choices: Optional[List[Dict[str, str]]] = None
    is_correct: Optional[bool] = None
    error_analysis: Optional[Dict[str, Any]] = None


@dataclass
class MarkdownTest:
    """Markdown格式的测试卷"""
    student_info: Dict[str, str]
    test_info: Dict[str, Any]
    answers: List[MarkdownAnswer]


class MarkdownGrader:
    """Markdown格式答卷批改器"""
    
    def __init__(self, output_dir: str = "output"):
        """初始化Markdown批改器
        
        Args:
            output_dir: 输出目录
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
        
        self.ai_processor = AIProcessor()
        self.logger = logging.getLogger(__name__)
        self.test_id_manager = TestIDManager()
        
        # 初始化LLM客户端用于增强解析
        try:
            from openai import OpenAI
            self.llm_client = OpenAI(
                api_key=os.getenv("DASHSCOPE_API_KEY"),
                base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
            )
            self.use_llm = True
            self.logger.info("LLM客户端初始化成功")
        except Exception as e:
            self.logger.warning(f"LLM客户端初始化失败: {e}")
            self.llm_client = None
            self.use_llm = False
        
        # 加载题库数据
        self.question_bank = self._load_question_bank()
    
    def _load_question_bank(self) -> Dict[str, Any]:
        """加载题库数据"""
        try:
            database_dir = Path(__file__).parent / "database"
            all_questions = {}
            
            # 加载选择题库
            choice_file = database_dir / "db_question_bank_choice.json"
            if choice_file.exists():
                with open(choice_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    questions = data.get('question_bank', {}).get('questions', [])
                    for q in questions:
                        all_questions[q['id']] = q
            
            # 加载计算题库
            calc_file = database_dir / "db_question_bank.json"
            if calc_file.exists():
                with open(calc_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    questions = data.get('question_bank', {}).get('questions', [])
                    for q in questions:
                        all_questions[q['id']] = q
            
            self.logger.info(f"加载了 {len(all_questions)} 道题目")
            return all_questions
            
        except Exception as e:
            self.logger.error(f"加载题库失败: {e}")
            return {}
    
    def find_questions_by_test_id(self, test_id: str) -> List[Dict[str, Any]]:
        """根据试卷ID查找题目
        
        Args:
            test_id: 试卷ID
            
        Returns:
            题目列表
        """
        try:
            # 获取试卷关联的题目ID列表
            question_ids = self.test_id_manager.get_questions_by_test_id(test_id)
            
            if not question_ids:
                self.logger.warning(f"未找到试卷ID对应的题目: {test_id}")
                return []
            
            # 根据题目ID从题库中获取题目详情
            questions = []
            for question_id in question_ids:
                if question_id in self.question_bank:
                    questions.append(self.question_bank[question_id])
                else:
                    self.logger.warning(f"题目ID在题库中不存在: {question_id}")
            
            self.logger.info(f"根据试卷ID {test_id} 找到 {len(questions)} 道题目")
            return questions
            
        except Exception as e:
            self.logger.error(f"根据试卷ID查找题目失败: {e}")
            return []
    
    def extract_test_id_from_markdown(self, markdown_content: str) -> Optional[str]:
        """从Markdown内容中提取试卷ID
        
        Args:
            markdown_content: Markdown内容
            
        Returns:
            试卷ID字符串，如果未找到则返回None
        """
        import re
        
        # 试卷ID模式：PR/EX/HW + 12位十六进制字符
        test_id_patterns = [
            r'试卷ID[：:]\s*([A-Z]{2}[A-F0-9]{12})',
            r'试卷编号[：:]\s*([A-Z]{2}[A-F0-9]{12})',
            r'Test ID[：:]\s*([A-Z]{2}[A-F0-9]{12})',
            r'\*\*试卷ID\*\*[：:]\s*([A-Z]{2}[A-F0-9]{12})',
            r'试卷标识.*?([A-Z]{2}[A-F0-9]{12})',
        ]
        
        for pattern in test_id_patterns:
            match = re.search(pattern, markdown_content, re.IGNORECASE | re.DOTALL)
            if match:
                test_id = match.group(1).upper()
                self.logger.info(f"从Markdown中提取到试卷ID: {test_id}")
                return test_id
        
        return None
    
    def _match_questions_by_questions_array(self, questions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """根据questions数组匹配题目
        
        Args:
            questions: 题目数组，每个题目包含question_number字段
            
        Returns:
            匹配的题目列表
        """
        matched_questions = []
        
        for question in questions:
            question_id = question.get('id', '')
            question_number = question.get('question_number', '')
            
            if question_id and question_id in self.question_bank:
                question_data = self.question_bank[question_id].copy()
                # 添加题目编号信息
                question_data['question_number'] = question_number
                # 确保题目ID正确
                question_data['id'] = question_id
                matched_questions.append(question_data)
                self.logger.info(f"题目编号 {question_number} 匹配题库ID {question_id} 成功")
            else:
                self.logger.warning(f"题目编号 {question_number} 对应的题库ID {question_id} 在题库中未找到")
        
        return matched_questions
    
    def parse_markdown_test(self, markdown_content: str, use_llm: bool = True, question_mapping: Optional[Dict[str, Any]] = None, questions: Optional[List[Dict[str, Any]]] = None) -> MarkdownTest:
        """解析Markdown格式的答卷
        
        Args:
            markdown_content: Markdown内容
            use_llm: 是否使用LLM进行增强解析
            question_mapping: 题号到题目ID的映射字典
            
        Returns:
            解析后的测试卷对象
        """
        self.logger.info("开始解析Markdown答卷")
        
        # 首先尝试提取试卷ID
        test_id = self.extract_test_id_from_markdown(markdown_content)
        matched_questions = []
        
        if test_id:
            self.logger.info(f"检测到试卷ID: {test_id}")
            # 根据试卷ID查找题目
            matched_questions = self.find_questions_by_test_id(test_id)
            if matched_questions:
                self.logger.info(f"根据试卷ID找到 {len(matched_questions)} 道题目")
            else:
                self.logger.warning(f"根据试卷ID未找到题目: {test_id}")
        
        # 优先使用questions数组，如果提供了question_mapping则使用它
        if questions:
            self.logger.info(f"使用questions数组进行匹配: {len(questions)} 道题目")
            matched_questions = self._match_questions_by_questions_array(questions)
        elif question_mapping:
            self.logger.info(f"使用题目映射进行匹配: {len(question_mapping)} 道题目")
            matched_questions = self._match_questions_by_mapping(question_mapping)
        
        # 优先使用LLM解析，如果失败则回退到规则解析
        if use_llm and self.use_llm and self.llm_client:
            try:
                return self._parse_with_llm(markdown_content, test_id, matched_questions, question_mapping, questions)
            except Exception as e:
                self.logger.warning(f"LLM解析失败，回退到规则解析: {e}")
                return self._parse_with_rules(markdown_content, test_id, matched_questions, question_mapping, questions)
        else:
            return self._parse_with_rules(markdown_content, test_id, matched_questions, question_mapping, questions)
    
    def _parse_with_rules(self, markdown_content: str, test_id: Optional[str] = None, matched_questions: List[Dict[str, Any]] = None, question_mapping: Optional[Dict[str, Any]] = None, questions: Optional[List[Dict[str, Any]]] = None) -> MarkdownTest:
        """使用规则解析Markdown答卷
        
        Args:
            markdown_content: Markdown内容
            
        Returns:
            解析后的测试卷对象
        """
        self.logger.info("使用规则解析Markdown答卷")
        
        lines = markdown_content.split('\n')
        student_info = {}
        test_info = {}
        answers = []
        
        current_section = None
        current_question = None
        current_answer = None
        
        i = 0
        while i < len(lines):
            line = lines[i].strip()
            self.logger.debug(f"处理第{i}行: {line}")
            
            # 解析学生信息
            if line.startswith('**姓名**'):
                student_info['name'] = self._extract_value(line)
            elif line.startswith('**学号**'):
                student_info['student_id'] = self._extract_value(line)
            elif line.startswith('**班级**'):
                student_info['class'] = self._extract_value(line)
            
            # 解析试卷信息
            elif line.startswith('**生成时间**'):
                test_info['generated_at'] = self._extract_value(line)
            elif line.startswith('**重点练习**'):
                test_info['error_types'] = self._extract_value(line).split(', ')
            elif line.startswith('**题目总数**'):
                test_info['total_questions'] = int(self._extract_value(line))
            elif line.startswith('**选择题**'):
                test_info['choice_questions'] = int(self._extract_value(line).split()[0])
            elif line.startswith('**计算题**'):
                test_info['calculation_questions'] = int(self._extract_value(line).split()[0])
            
            # 解析题目
            elif line.startswith('### 第') and '题' in line:
                # 保存上一个题目
                if current_question:
                    answers.append(current_question)
                
                # 开始新题目
                question_num = self._extract_question_number(line)
                
                # 优先使用questions数组获取题目信息
                question_id = f"q_{question_num}"
                question_type = "unknown"
                
                if questions:
                    # 从questions数组中查找对应题目
                    for q in questions:
                        if q.get('question_number') == f"第 {question_num} 题":
                            question_id = q.get('id', f"q_{question_num}")
                            question_type = q.get('question_type', 'unknown')
                            self.logger.info(f"题目编号 {question_num} 对应题库ID: {question_id}")
                            break
                    else:
                        self.logger.warning(f"题目编号 {question_num} 在questions数组中未找到")
                elif question_mapping and str(question_num) in question_mapping:
                    mapping_info = question_mapping[str(question_num)]
                    question_id = mapping_info.get('question_id', f"q_{question_num}")
                    question_type = mapping_info.get('question_type', 'unknown')
                    self.logger.info(f"题目编号 {question_num} 对应题库ID: {question_id}")
                else:
                    self.logger.warning(f"题目编号 {question_num} 未找到映射，使用默认ID: {question_id}")
                
                current_question = MarkdownAnswer(
                    question_number=str(question_num),  # 试卷中的题目编号
                    question_id=question_id,            # 题库中的题目ID
                    question_text="",
                    question_type=question_type,
                    student_answer=""
                )
                current_section = "question"
            
            elif current_question and line.startswith('**题目**'):
                current_question.question_text = self._extract_value(line)
                current_section = "question"
            
            elif current_question and line.startswith('**选项**'):
                current_section = "choices"
                current_question.choices = []
            
            elif current_question and current_section == "choices" and line.startswith('- '):
                choice_text = line[2:].strip()
                if choice_text:
                    choice_letter = choice_text[0] if choice_text else ""
                    choice_content = choice_text[2:].strip() if len(choice_text) > 2 else ""
                    current_question.choices.append({
                        'letter': choice_letter,
                        'content': choice_content
                    })
            
            elif current_question and line.startswith('**答案**'):
                if current_question:
                    # 查找学生填写的答案
                    self.logger.debug(f"处理答案行: {line}")
                    
                    # 检查当前行是否包含答案
                    if '(' in line and ')' in line:
                        # 从当前行提取答案，支持空格
                        answer_match = re.search(r'\(\s*([a-d])\s*\)', line)
                        if answer_match:
                            current_question.student_answer = answer_match.group(1).strip()
                            self.logger.debug(f"从当前行提取答案: '{current_question.student_answer}'")
                        else:
                            self.logger.debug("当前行有括号但未找到有效答案")
                    else:
                        # 查找下一行的答案
                        self.logger.debug("查找下一行答案")
                        i += 1
                        while i < len(lines) and not lines[i].strip().startswith('**'):
                            answer_line = lines[i].strip()
                            self.logger.debug(f"检查答案行: '{answer_line}'")
                            if answer_line and not answer_line.startswith('**'):
                                # 提取括号内的答案，支持空格
                                answer_match = re.search(r'\(\s*([a-d])\s*\)', answer_line)
                                if answer_match:
                                    current_question.student_answer = answer_match.group(1).strip()
                                    self.logger.debug(f"从下一行提取答案: '{current_question.student_answer}'")
                                else:
                                    # 如果没有括号，直接提取内容
                                    current_question.student_answer = answer_line.strip('()').strip()
                                    self.logger.debug(f"直接提取答案: '{current_question.student_answer}'")
                                break
                            i += 1
                        i -= 1
                else:
                    self.logger.warning("找到答案行但没有当前题目")
            
            elif current_question and (line.startswith('**解答过程**') or line.startswith('**解答**')):
                current_section = "solution"
                current_question.question_type = "calculation"
                current_question.student_answer = ""
            
            elif current_question and current_section == "solution" and line:
                # 跳过代码块标记
                if line.startswith('```'):
                    continue
                # 收集解答内容
                if not current_question.student_answer:
                    current_question.student_answer = line
                else:
                    current_question.student_answer += "\n" + line
            
            i += 1
        
        # 保存最后一个题目
        if current_question:
            answers.append(current_question)
        
        self.logger.info(f"解析完成，共 {len(answers)} 道题目")
        
        return MarkdownTest(
            student_info=student_info,
            test_info=test_info,
            answers=answers
        )
    
    def _parse_with_llm(self, markdown_content: str, test_id: Optional[str] = None, matched_questions: List[Dict[str, Any]] = None, question_mapping: Optional[Dict[str, Any]] = None, questions: Optional[List[Dict[str, Any]]] = None) -> MarkdownTest:
        """使用LLM解析Markdown答卷
        
        Args:
            markdown_content: Markdown内容
            
        Returns:
            解析后的测试卷对象
        """
        self.logger.info("使用LLM解析Markdown答卷")
        
        try:
            # 构建LLM解析提示，包含题目匹配信息
            prompt = self._create_llm_parsing_prompt(markdown_content, matched_questions)
            
            response = self.llm_client.chat.completions.create(
                model="qwen-plus",
                messages=[
                    {
                        'role': 'system',
                        'content': '''你是一位专业的数学老师，擅长解析学生答卷。请将Markdown格式的答卷解析为结构化的JSON数据。

要求：
1. 准确提取学生信息（姓名、学号、班级）
2. 提取试卷信息（生成时间、题目数量等）
3. 解析每道题目，包括题目题号，内容、类型、选项、学生答案
4. 区分选择题和计算题
5. 对于选择题，提取选项和学生选择的答案
6. 对于计算题，提取学生的解答过程
7. 返回标准的JSON格式数据

请严格按照要求解析，确保数据准确性。'''
                    },
                    {'role': 'user', 'content': prompt}
                ],
                temperature=0.1,
                max_tokens=3000
            )
            
            response_text = response.choices[0].message.content
            
            # 记录LLM请求和响应
            self.logger.info("=== LLM解析请求 ===")
            self.logger.info(f"模型: qwen-plus")
            self.logger.info(f"请求内容: {prompt}")
            self.logger.info("=== LLM解析响应 ===")
            self.logger.info(f"完整响应: {response_text}")
            self.logger.info(f"响应长度: {len(response_text)} 字符")
            self.logger.info("=== LLM解析结束 ===")
            
            # 解析JSON响应
            try:
                # 清理响应文本，移除markdown代码块
                clean_text = response_text.strip()
                if clean_text.startswith('```json'):
                    clean_text = clean_text[7:]
                if clean_text.endswith('```'):
                    clean_text = clean_text[:-3]
                clean_text = clean_text.strip()

                      
                data = json.loads(clean_text)
                
                # 构建MarkdownTest对象
                student_info = data.get('student_info', {})
                test_info = data.get('test_info', {})
                answers = []
                
                for q_data in data.get('questions', []):
                    answer = MarkdownAnswer(
                        question_number=q_data.get('question_number', ''),
                        question_id=q_data.get('question_id', ''),
                        question_text=q_data.get('question_text', ''),
                        question_type=q_data.get('question_type', 'unknown'),
                        student_answer=q_data.get('student_answer', ''),
                        choices=q_data.get('choices', [])
                    )
                    answers.append(answer)
                
                self.logger.info(f"LLM解析完成，共 {len(answers)} 道题目")
                
                return MarkdownTest(
                    student_info=student_info,
                    test_info=test_info,
                    answers=answers
                )
                
            except json.JSONDecodeError as e:
                self.logger.error(f"LLM JSON解析失败: {e}")
                self.logger.info("回退到规则解析")
                return self._parse_with_rules(markdown_content, test_id, matched_questions, question_mapping, questions)
                
        except Exception as e:
            self.logger.error(f"LLM解析失败: {e}")
            self.logger.info("回退到规则解析")
            return self._parse_with_rules(markdown_content, test_id, matched_questions, question_mapping, questions)
    
    def _create_llm_parsing_prompt(self, markdown_content: str, matched_questions: List[Dict[str, Any]] = None) -> str:
        """创建LLM解析提示
        
        Args:
            markdown_content: Markdown内容
            
        Returns:
            格式化的提示字符串
        """
        json_format = """
{
  "student_info": {
    "name": "学生姓名",
    "student_id": "学号",
    "class": "班级"
  },
  "test_info": {
    "generated_at": "生成时间",
    "total_questions": 题目总数,
    "choice_questions": 选择题数量,
    "calculation_questions": 计算题数量,
    "error_types": ["错误类型1", "错误类型2"]
  },
  "questions": [
    {
      "question_number": "题目编号，如'1', '2', '3'",
      "question_id": "题库中的题目ID，如'q_001', 'choice_006'",
      "question_text": "题目内容",
      "question_type": "choice" 或 "calculation",
      "student_answer": "学生答案",
      "choices": [
        {
          "letter": "a",
          "content": "选项内容"
        }
      ]
    }
  ]
}
        """
        
        # 构建题目匹配信息
        question_info = ""
        if matched_questions:
            question_info = "\n\n题目匹配信息：\n"
            for q in matched_questions:
                question_number = q.get('question_number', '')
                question_id = q.get('id', '')
                question_text = q.get('question_info', {}).get('text', '')
                question_type = q.get('question_type', '')
                question_info += f"- 题目编号: {question_number}, 题库ID: {question_id}, 类型: {question_type}\n"
                question_info += f"  题目内容: {question_text[:100]}...\n"
        
        prompt = f"""请将以下Markdown格式的答卷解析为结构化的JSON数据：

{markdown_content}
{question_info}

请按照以下JSON格式返回解析结果：
{json_format}

注意：
1. 对于选择题，question_type为"choice"，choices包含所有选项
2. 对于计算题，question_type为"calculation"，choices为空数组
3. 学生答案要准确提取，包括选择题的选项字母和计算题的解答过程
4. question_number从"第X题"中提取数字，如"第1题"提取为"1"
5. question_id请使用上面提供的题目匹配信息中的题库ID，确保准确匹配
6. 如果题目匹配信息中有对应的题目，请使用提供的question_id和question_type
7. 确保所有字段都有值，不要遗漏任何信息
8. 严格按照JSON格式返回，不要包含其他内容"""
        
        return prompt
    
    def _extract_value(self, line: str) -> str:
        """从Markdown行中提取值"""
        # 移除**标记和冒号
        value = re.sub(r'\*\*.*?\*\*:\s*', '', line)
        return value.strip()
    
    def _extract_question_number(self, line: str) -> int:
        """从题目行中提取题目编号"""
        match = re.search(r'第\s*(\d+)\s*题', line)
        return int(match.group(1)) if match else 0
    
    def grade_markdown_test(self, markdown_test: MarkdownTest) -> Dict[str, Any]:
        """批改Markdown答卷
        
        Args:
            markdown_test: 解析后的测试卷
            
        Returns:
            批改结果
        """
        self.logger.info("开始批改Markdown答卷", markdown_test)
        
        graded_answers = []
        total_questions = len(markdown_test.answers)
        correct_count = 0
        
        for answer in markdown_test.answers:
            self.logger.info(f"批改题目编号 {answer.question_number} (题库ID: {answer.question_id})")
            
            # 根据题目类型进行批改
            if answer.question_type == "choice":
                graded_answer = self._grade_choice_question(answer)
            elif answer.question_type == "calculation":
                graded_answer = self._grade_calculation_question(answer)
            else:
                # 尝试自动识别题目类型
                graded_answer = self._auto_grade_question(answer)
            
            if graded_answer.is_correct:
                correct_count += 1
            
            graded_answers.append(graded_answer)
        
        # 计算准确率
        accuracy = (correct_count / total_questions * 100) if total_questions > 0 else 0
        
        # 生成易错点分析
        error_analysis = self._analyze_student_errors(graded_answers)
        
        # 生成练习推荐
        practice_recommendations = self._generate_practice_recommendations(error_analysis)
        
        result = {
            "student_info": markdown_test.student_info,
            "test_info": markdown_test.test_info,
            "grading_summary": {
                "total_questions": total_questions,
                "correct_questions": correct_count,
                "accuracy_percentage": accuracy,
                "grading_timestamp": datetime.now().isoformat()
            },
            "graded_answers": [
                {
                    "question_id": answer.question_id,
                    "question_text": answer.question_text,
                    "question_type": answer.question_type,
                    "student_answer": answer.student_answer,
                    "is_correct": answer.is_correct,
                    "error_analysis": answer.error_analysis
                } for answer in graded_answers
            ],
            "error_analysis": error_analysis,
            "practice_recommendations": practice_recommendations
        }
        
        self.logger.info(f"批改完成，准确率: {accuracy:.1f}%")
        return result
    
    def _grade_choice_question(self, answer: MarkdownAnswer) -> MarkdownAnswer:
        """批改选择题"""
        try:
            # 从题库中查找对应题目
            self.logger.info(f"查找题目编号 {answer.question_number} 对应的题库ID: {answer.question_id}")
            question_data = self.question_bank.get(answer.question_id)
            
            if not question_data:
                # 如果题库中没有，尝试通过题目文本匹配
                question_data = self._find_question_by_text(answer.question_text)
            
            if not question_data:
                self.logger.warning(f"题目编号 {answer.question_number} 对应的题库ID {answer.question_id} 未找到")
                answer.is_correct = False
                answer.error_analysis = {
                    "primary_error": "题目未找到",
                    "error_description": f"题库中未找到题目ID: {answer.question_id}",
                    "suggested_remediation": "请检查题目映射是否正确"
                }
                return answer
            
            if question_data and 'choices' in question_data:
                # 查找正确答案
                correct_choice = None
                for choice in question_data['choices']:
                    if choice.get('is_correct', False):
                        correct_choice = choice['id']
                        break
                
                if correct_choice:
                    is_correct = answer.student_answer.strip().lower() == correct_choice.lower()
                    
                    if is_correct:
                        error_analysis = None
                    else:
                        # 分析错误原因
                        error_analysis = self._analyze_choice_error(
                            answer, question_data, correct_choice
                        )
                    
                    answer.is_correct = is_correct
                    answer.error_analysis = error_analysis
                else:
                    answer.is_correct = False
                    answer.error_analysis = {
                        "error_type": "grading_error",
                        "description": "无法找到正确答案"
                    }
            else:
                answer.is_correct = False
                answer.error_analysis = {
                    "error_type": "question_not_found",
                    "description": "题库中未找到对应题目"
                }
            
        except Exception as e:
            self.logger.error(f"批改选择题失败: {e}")
            answer.is_correct = False
            answer.error_analysis = {
                "error_type": "grading_error",
                "description": f"批改过程出错: {str(e)}"
            }
        
        return answer
    
    def _grade_calculation_question(self, answer: MarkdownAnswer) -> MarkdownAnswer:
        """批改计算题"""
        try:
            # 使用AI处理器分析计算题
            if self.ai_processor and self.ai_processor.use_llm:
                # 构造数学问题对象
                from .ai_processor import MathProblem, StudentSolution, SolutionStep
                
                # 解析学生解答步骤（包含题目信息）
                solution_steps = self._parse_calculation_steps_with_context(
                    answer.question_text, answer.student_answer
                )
                
                student_solution = StudentSolution(
                    raw=answer.student_answer,
                    steps=solution_steps
                )
                
                problem = MathProblem(
                    problem_id=answer.question_id,  # 使用题库中的题目ID
                    problem_text=answer.question_text,
                    student_solution=student_solution,
                    problem_type="calculation"
                )
                
                # 使用AI验证解答
                validation = self.ai_processor.validate_solution(problem)
                feedback = self.ai_processor.generate_feedback(problem, validation)
                
                answer.is_correct = validation.is_correct
                
                # 生成详细的错误分析
                error_analysis = self._analyze_calculation_error(
                    answer, validation, feedback, solution_steps
                )
                answer.error_analysis = error_analysis
            else:
                # 简单的文本匹配验证
                answer.is_correct = self._simple_calculation_check(answer)
                answer.error_analysis = self._analyze_calculation_error_simple(answer)
            
        except Exception as e:
            self.logger.error(f"批改计算题失败: {e}")
            answer.is_correct = False
            answer.error_analysis = {
                "error_type": "grading_error",
                "description": f"批改过程出错: {str(e)}"
            }
        
        return answer
    
    def _analyze_calculation_error(self, answer: MarkdownAnswer, validation, feedback, solution_steps) -> Dict[str, Any]:
        """分析计算题错误"""
        error_analysis = {
            "error_type": validation.error_type,
            "description": validation.error_description,
            "suggestions": validation.suggestions,
            "confidence": validation.confidence,
            "step_analysis": [],
            "knowledge_points": [],
            "error_categories": []
        }
        
        # 分析每个步骤的错误
        if solution_steps:
            for i, step in enumerate(solution_steps):
                step_analysis = self._analyze_calculation_step(step, i + 1)
                error_analysis["step_analysis"].append(step_analysis)
                
                # 收集知识点
                if not step.is_correct:
                    error_analysis["knowledge_points"].extend(step_analysis.get("knowledge_points", []))
                    error_analysis["error_categories"].append(step_analysis.get("error_category", "未知错误"))
        
        # 去重知识点
        error_analysis["knowledge_points"] = list(set(error_analysis["knowledge_points"]))
        error_analysis["error_categories"] = list(set(error_analysis["error_categories"]))
        
        # 生成总体错误分析
        if not answer.is_correct:
            error_analysis["overall_analysis"] = self._generate_overall_error_analysis(
                answer.question_text, error_analysis["error_categories"], solution_steps
            )
        
        return error_analysis
    
    def _analyze_calculation_step(self, step: SolutionStep, step_number: int) -> Dict[str, Any]:
        """分析计算题单个步骤"""
        step_analysis = {
            "step_number": step_number,
            "from_expr": step.from_expr,
            "to_expr": step.to_expr,
            "is_correct": step.is_correct,
            "error_category": "无错误",
            "knowledge_points": [],
            "error_reason": "",
            "suggestions": []
        }
        
        if not step.is_correct:
            # 分析错误类型
            error_category = self._classify_calculation_error(step.from_expr, step.to_expr)
            step_analysis["error_category"] = error_category
            
            # 提取知识点
            knowledge_points = self._extract_calculation_knowledge_points(step.from_expr, step.to_expr)
            step_analysis["knowledge_points"] = knowledge_points
            
            # 分析错误原因
            error_reason = self._analyze_calculation_error_reason(step.from_expr, step.to_expr, error_category)
            step_analysis["error_reason"] = error_reason
            
            # 生成改进建议
            suggestions = self._generate_calculation_suggestions(error_category, knowledge_points)
            step_analysis["suggestions"] = suggestions
        
        return step_analysis
    
    def _classify_calculation_error(self, from_expr: str, to_expr: str) -> str:
        """分类计算题错误类型"""
        # 检查符号错误
        if self._has_sign_error(from_expr, to_expr):
            return '符号错误'
        
        # 检查分数运算错误
        if self._has_fraction_error(from_expr, to_expr):
            return '分数运算错误'
        
        # 检查乘方运算错误
        if self._has_power_error(from_expr, to_expr):
            return '乘方运算错误'
        
        # 检查运算顺序错误
        if self._has_order_error(from_expr, to_expr):
            return '运算顺序错误'
        
        # 检查基本计算错误
        if self._has_calculation_error(from_expr, to_expr):
            return '计算错误'
        
        return '未知错误'
    
    def _has_sign_error(self, from_expr: str, to_expr: str) -> bool:
        """检查是否有符号错误"""
        try:
            # 计算两个表达式的值
            from_val = self._evaluate_math_expression(from_expr)
            to_val = self._evaluate_math_expression(to_expr)
            
            if from_val is not None and to_val is not None:
                # 如果值不相等，检查是否是符号错误
                if abs(from_val - to_val) > 0.001:
                    # 检查是否是符号处理错误
                    # 例如: (15) - (-4) = 15 + 4 = 19，但学生写成了 15 - 4 = 11
                    if self._is_sign_processing_error(from_expr, to_expr):
                        return True
            
            # 检查负号处理
            if '-' in from_expr and '-' not in to_expr:
                return True
            if '-' not in from_expr and '-' in to_expr:
                return True
            
            # 检查括号内的符号
            if '(-' in from_expr and not '(-' in to_expr:
                return True
            
        except:
            pass
        
        return False
    
    def _is_sign_processing_error(self, from_expr: str, to_expr: str) -> bool:
        """检查是否是符号处理错误"""
        try:
            # 检查 a - (-b) 的情况
            # 如果原表达式是 a - (-b)，但学生写成了 a - b
            if '(-' in from_expr:
                # 提取数字
                import re
                from_numbers = re.findall(r'-?\d+(?:\.\d+)?', from_expr)
                to_numbers = re.findall(r'-?\d+(?:\.\d+)?', to_expr)
                
                if len(from_numbers) >= 2 and len(to_numbers) >= 2:
                    # 检查是否是符号处理错误
                    # 例如: (15) - (-4) 应该等于 19，但学生写成了 15 - 4 = 11
                    if len(from_numbers) == 2 and len(to_numbers) == 2:
                        from_a, from_b = float(from_numbers[0]), float(from_numbers[1])
                        to_a, to_b = float(to_numbers[0]), float(to_numbers[1])
                        
                        # 如果 from_expr 是 a - (-b) 的形式，正确结果应该是 a + b
                        if from_a - (-from_b) == to_a - to_b:
                            return True
        except:
            pass
        
        return False
    
    def _has_fraction_error(self, from_expr: str, to_expr: str) -> bool:
        """检查是否有分数运算错误"""
        return '/' in from_expr or '/' in to_expr
    
    def _has_power_error(self, from_expr: str, to_expr: str) -> bool:
        """检查是否有乘方运算错误"""
        return '²' in from_expr or '³' in from_expr or '**' in from_expr
    
    def _has_order_error(self, from_expr: str, to_expr: str) -> bool:
        """检查是否有运算顺序错误"""
        # 检查是否有括号但结果不正确
        if '(' in from_expr and ')' in from_expr:
            return True
        return False
    
    def _has_calculation_error(self, from_expr: str, to_expr: str) -> bool:
        """检查是否有基本计算错误"""
        try:
            # 尝试计算两个表达式是否相等
            from_val = self._evaluate_math_expression(from_expr)
            to_val = self._evaluate_math_expression(to_expr)
            
            if from_val is not None and to_val is not None:
                return abs(from_val - to_val) > 0.001
        except:
            pass
        
        return True
    
    def _extract_calculation_knowledge_points(self, from_expr: str, to_expr: str) -> List[str]:
        """提取计算题知识点"""
        knowledge_points = []
        
        if '(-' in from_expr or '(-' in to_expr:
            knowledge_points.append('负数运算规则')
        
        if '/' in from_expr or '/' in to_expr:
            knowledge_points.append('分数运算')
        
        if '²' in from_expr or '³' in from_expr or '**' in from_expr:
            knowledge_points.append('乘方运算')
        
        if '(' in from_expr and ')' in from_expr:
            knowledge_points.append('运算顺序')
        
        if '+' in from_expr or '-' in from_expr or '×' in from_expr or '÷' in from_expr:
            knowledge_points.append('四则运算')
        
        return knowledge_points
    
    def _analyze_calculation_error_reason(self, from_expr: str, to_expr: str, error_category: str) -> str:
        """分析计算题错误原因"""
        if error_category == '符号错误':
            return "符号处理错误，可能混淆了正负号规则或括号内的符号"
        elif error_category == '分数运算错误':
            return "分数运算错误，可能通分、约分或分数四则运算有误"
        elif error_category == '乘方运算错误':
            return "乘方运算错误，可能混淆了底数和指数的关系"
        elif error_category == '运算顺序错误':
            return "运算顺序错误，可能没有按照正确的运算顺序进行计算"
        elif error_category == '计算错误':
            return "基本计算错误，可能加减乘除运算有误"
        else:
            return "未知错误类型"
    
    def _generate_calculation_suggestions(self, error_category: str, knowledge_points: List[str]) -> List[str]:
        """生成计算题改进建议"""
        suggestions = []
        
        if error_category == '符号错误':
            suggestions.extend([
                "重点练习正负数的运算规则",
                "注意括号内符号的处理",
                "多做符号相关的练习题"
            ])
        elif error_category == '分数运算错误':
            suggestions.extend([
                "加强分数的通分和约分练习",
                "注意分数运算的基本法则",
                "练习分数的四则运算"
            ])
        elif error_category == '乘方运算错误':
            suggestions.extend([
                "重点练习乘方的计算规则",
                "注意底数和指数的关系",
                "多做乘方相关的练习题"
            ])
        elif error_category == '运算顺序错误':
            suggestions.extend([
                "复习运算顺序规则：先乘除后加减，有括号先算括号内",
                "注意括号的正确使用",
                "多做混合运算练习题"
            ])
        else:
            suggestions.extend([
                "加强基础计算练习",
                "仔细检查每一步计算",
                "多做相关类型的练习题"
            ])
        
        return suggestions
    
    def _generate_overall_error_analysis(self, question_text: str, error_categories: List[str], solution_steps: List) -> str:
        """生成总体错误分析"""
        if not error_categories:
            return "解答正确"
        
        # 统计错误类型
        error_counts = {}
        for category in error_categories:
            error_counts[category] = error_counts.get(category, 0) + 1
        
        # 生成分析
        analysis_parts = []
        for category, count in error_counts.items():
            if count > 1:
                analysis_parts.append(f"{category}（{count}处）")
            else:
                analysis_parts.append(category)
        
        return f"主要错误类型：{', '.join(analysis_parts)}"
    
    def _analyze_calculation_error_simple(self, answer: MarkdownAnswer) -> Dict[str, Any]:
        """简单计算题错误分析"""
        return {
            "error_type": "simple_check",
            "description": "使用简单验证方法",
            "suggestions": ["建议使用AI模型进行更详细的分析"],
            "confidence": 0.5,
            "step_analysis": [],
            "knowledge_points": [],
            "error_categories": []
        }
    
    def _auto_grade_question(self, answer: MarkdownAnswer) -> MarkdownAnswer:
        """自动识别题目类型并批改"""
        # 根据题目特征判断类型
        if answer.choices:
            answer.question_type = "choice"
            return self._grade_choice_question(answer)
        elif any(keyword in answer.question_text for keyword in ['计算', '求', '解']):
            answer.question_type = "calculation"
            return self._grade_calculation_question(answer)
        else:
            # 默认按计算题处理
            answer.question_type = "calculation"
            return self._grade_calculation_question(answer)
    
    def _find_question_by_text(self, question_text: str) -> Optional[Dict[str, Any]]:
        """通过题目文本在题库中查找题目"""
        for question_id, question_data in self.question_bank.items():
            if question_text in question_data.get('question_info', {}).get('text', ''):
                return question_data
        return None
    
    def _analyze_choice_error(self, answer: MarkdownAnswer, question_data: Dict, correct_choice: str) -> Dict[str, Any]:
        """分析选择题错误原因"""
        student_choice = answer.student_answer.strip().lower()
        correct_choice = correct_choice.lower()
        
        # 获取选项内容
        choices = question_data.get('choices', [])
        student_content = ""
        correct_content = ""
        student_explanation = ""
        correct_explanation = ""
        
        for choice in choices:
            if choice['id'].lower() == student_choice:
                student_content = choice.get('content', '')
                student_explanation = choice.get('explanation', '')
            if choice['id'].lower() == correct_choice:
                correct_content = choice.get('content', '')
                correct_explanation = choice.get('explanation', '')
        
        # 分析错误类型
        error_type = self._classify_choice_error(answer.question_text, student_content, correct_content)
        
        # 获取题目标签和知识点
        question_info = question_data.get('question_info', {})
        tags = question_info.get('tags', [])
        chapter = question_info.get('chapter', '')
        
        return {
            "error_type": "wrong_choice",
            "error_category": error_type,
            "description": f"选择了错误选项 {student_choice.upper()}",
            "student_choice": student_content,
            "correct_choice": correct_content,
            "student_explanation": student_explanation,
            "correct_explanation": correct_explanation,
            "knowledge_points": self._extract_knowledge_points(tags, chapter),
            "error_analysis": self._analyze_choice_error_reason(answer.question_text, student_content, correct_content),
            "suggestions": self._generate_choice_suggestions(error_type, tags)
        }
    
    def _classify_choice_error(self, question_text: str, student_content: str, correct_content: str) -> str:
        """分类选择题错误类型"""
        # 基于题目内容和选项内容分析错误类型
        if '符号' in question_text or '负数' in question_text or '正负' in question_text:
            return '符号错误'
        elif '分数' in question_text or '/' in question_text:
            return '分数运算错误'
        elif '乘方' in question_text or '²' in question_text or '³' in question_text:
            return '乘方运算错误'
        elif '方程' in question_text or '解' in question_text:
            return '方程求解错误'
        elif '混合' in question_text or ('+' in question_text and '×' in question_text):
            return '混合运算错误'
        else:
            return '计算错误'
    
    def _extract_knowledge_points(self, tags: List[str], chapter: str) -> List[str]:
        """提取知识点"""
        knowledge_points = []
        
        # 从标签中提取知识点
        tag_mapping = {
            '有理数': '有理数概念',
            '负数运算': '负数运算规则',
            '乘方': '乘方运算',
            '分数': '分数运算',
            '方程': '方程求解',
            '混合运算': '运算顺序'
        }
        
        for tag in tags:
            if tag in tag_mapping:
                knowledge_points.append(tag_mapping[tag])
        
        # 从章节中提取知识点
        if chapter:
            knowledge_points.append(f"{chapter}相关概念")
        
        return list(set(knowledge_points))  # 去重
    
    def _analyze_choice_error_reason(self, question_text: str, student_content: str, correct_content: str) -> str:
        """分析选择题错误原因"""
        # 尝试计算正确答案
        try:
            correct_value = self._calculate_expression_value(question_text)
            student_value = self._parse_choice_value(student_content)
            
            if correct_value is not None and student_value is not None:
                if abs(correct_value - student_value) < 0.001:
                    return "计算过程正确，但选择了错误选项"
                else:
                    return f"计算错误：学生得到 {student_value}，正确答案是 {correct_value}"
        except:
            pass
        
        # 基于内容分析
        if '符号' in question_text:
            return "符号处理错误，可能混淆了正负号规则"
        elif '分数' in question_text:
            return "分数运算错误，可能通分或约分有误"
        elif '乘方' in question_text:
            return "乘方运算错误，可能混淆了底数和指数的关系"
        else:
            return "基本计算错误"
    
    def _calculate_expression_value(self, question_text: str) -> Optional[float]:
        """计算题目表达式的值"""
        try:
            # 提取计算表达式
            if '计算：' in question_text:
                expr_match = re.search(r'计算：(.+?)[？?]', question_text)
                if expr_match:
                    expression = expr_match.group(1).strip()
                    return self._evaluate_math_expression(expression)
        except:
            pass
        return None
    
    def _parse_choice_value(self, choice_content: str) -> Optional[float]:
        """解析选项的数值"""
        try:
            # 提取数字
            numbers = re.findall(r'-?\d+(?:\.\d+)?', choice_content)
            if numbers:
                return float(numbers[0])
        except:
            pass
        return None
    
    def _evaluate_math_expression(self, expression: str) -> Optional[float]:
        """计算数学表达式的值"""
        try:
            # 标准化表达式
            expr = expression.replace('×', '*').replace('÷', '/').replace('²', '**2').replace('³', '**3')
            
            # 处理负数运算的特殊情况
            # 例如: (15) - (-4) 应该等于 15 + 4 = 19
            expr = self._normalize_negative_operations(expr)
            
            # 简单的安全计算
            return eval(expr)
        except:
            return None
    
    def _normalize_negative_operations(self, expr: str) -> str:
        """标准化负数运算表达式"""
        import re
        
        # 处理 a - (-b) 的情况，转换为 a + b
        # 匹配模式: 数字或括号 - (负号 数字或括号)
        pattern = r'(\d+(?:\.\d+)?|\([^)]+\))\s*-\s*\(\s*-\s*(\d+(?:\.\d+)?|\([^)]+\))\s*\)'
        
        def replace_neg_neg(match):
            left = match.group(1)
            right = match.group(2)
            return f"{left} + {right}"
        
        # 应用替换
        expr = re.sub(pattern, replace_neg_neg, expr)
        
        # 处理其他负数运算情况
        # a - (-b) -> a + b (更通用的模式)
        pattern2 = r'(\d+(?:\.\d+)?)\s*-\s*\(\s*-\s*(\d+(?:\.\d+)?)\s*\)'
        expr = re.sub(pattern2, r'\1 + \2', expr)
        
        return expr
    
    def _generate_choice_suggestions(self, error_type: str, tags: List[str]) -> List[str]:
        """生成选择题改进建议"""
        suggestions = []
        
        if error_type == '符号错误':
            suggestions.extend([
                "重点练习正负数的运算规则",
                "注意负号的处理，特别是乘方运算",
                "多做符号相关的练习题"
            ])
        elif error_type == '分数运算错误':
            suggestions.extend([
                "加强分数的通分和约分练习",
                "注意分数运算的基本法则",
                "练习分数的四则运算"
            ])
        elif error_type == '乘方运算错误':
            suggestions.extend([
                "重点练习乘方的计算规则",
                "注意底数和指数的关系",
                "多做乘方相关的练习题"
            ])
        else:
            suggestions.extend([
                "加强基础计算练习",
                "注意运算顺序",
                "仔细检查每一步计算"
            ])
        
        return suggestions
    
    def _parse_calculation_steps(self, solution_text: str) -> List[SolutionStep]:
        """使用AI解析计算题的解答步骤"""
        if self.use_llm and self.llm_client:
            return self._parse_calculation_steps_with_ai(solution_text)
        else:
            return self._parse_calculation_steps_simple(solution_text)
    
    def _parse_calculation_steps_with_context(self, question_text: str, solution_text: str) -> List[SolutionStep]:
        """使用AI解析计算题步骤（包含题目上下文）"""
        if self.use_llm and self.llm_client:
            return self._parse_calculation_steps_with_context_ai(question_text, solution_text)
        else:
            return self._parse_calculation_steps_simple(solution_text)
    
    def _parse_calculation_steps_with_ai(self, solution_text: str) -> List[SolutionStep]:
        """使用AI解析计算题步骤"""
        try:
            prompt = f"""请将以下学生解答过程解析为结构化的步骤信息。

学生解答过程：
{solution_text}

请按照以下JSON格式返回解析结果：
{{
  "steps": [
    {{
      "from_expr": "起始表达式",
      "to_expr": "结果表达式",
      "is_correct": true/false,
      "error_type": "错误类型（如果is_correct为false）",
      "explanation": "步骤说明"
    }}
  ]
}}

要求：
1. 将解答过程分解为详细的步骤
2. 每个步骤包含from_expr（起始表达式）和to_expr（结果表达式）
3. 判断每个步骤是否正确
4. 如果步骤错误，提供错误类型和说明
5. 特别注意符号运算的正确性，如 a - (-b) = a + b
6. 确保from_expr不为空

请严格按照JSON格式返回，不要包含其他内容。"""

            response = self.llm_client.chat.completions.create(
                model="qwen-plus",
                messages=[
                    {
                        'role': 'system',
                        'content': '你是一位专业的数学老师，擅长分析学生的解题过程。请仔细解析解答步骤并按要求返回结构化的JSON数据。特别注意符号运算的正确性。'
                    },
                    {'role': 'user', 'content': prompt}
                ],
                temperature=0.1,
                max_tokens=2000
            )
            
            response_text = response.choices[0].message.content
            
            # 解析JSON响应
            try:
                # 清理响应文本
                clean_text = response_text.strip()
                if clean_text.startswith('```json'):
                    clean_text = clean_text[7:]
                if clean_text.endswith('```'):
                    clean_text = clean_text[:-3]
                clean_text = clean_text.strip()
                
                data = json.loads(clean_text)
                
                # 构建SolutionStep对象
                steps = []
                for step_data in data.get('steps', []):
                    step = SolutionStep(
                        from_expr=step_data.get('from_expr', ''),
                        to_expr=step_data.get('to_expr', ''),
                        is_correct=step_data.get('is_correct', True)
                    )
                    steps.append(step)
                
                self.logger.info(f"AI解析完成，共 {len(steps)} 个步骤")
                return steps
                
            except json.JSONDecodeError as e:
                self.logger.error(f"AI JSON解析失败: {e}")
                return self._parse_calculation_steps_simple(solution_text)
                
        except Exception as e:
            self.logger.error(f"AI解析步骤失败: {e}")
            return self._parse_calculation_steps_simple(solution_text)
    
    def _parse_calculation_steps_simple(self, solution_text: str) -> List[SolutionStep]:
        """简单的步骤解析（备用方案）"""
        steps = []
        lines = solution_text.split('\n')
        
        for line in lines:
            line = line.strip()
            if '=' in line and not line.startswith('```'):
                parts = line.split('=')
                if len(parts) >= 2:
                    from_expr = parts[0].strip()
                    to_expr = parts[-1].strip()
                    
                    # 如果from_expr为空，尝试从前面的步骤获取
                    if not from_expr and steps:
                        from_expr = steps[-1].to_expr
                    
                    steps.append(SolutionStep(
                        from_expr=from_expr,
                        to_expr=to_expr,
                        is_correct=True  # 默认正确，后续验证
                    ))
        
        return steps
    
    def _parse_calculation_steps_with_context_ai(self, question_text: str, solution_text: str) -> List[SolutionStep]:
        """使用AI解析计算题步骤（包含题目上下文）"""
        try:
            prompt = f"""请将以下数学题目和学生解答过程解析为结构化的步骤信息。

题目：
{question_text}

学生解答过程：
{solution_text}

请按照以下JSON格式返回解析结果：
{{
  "steps": [
    {{
      "from_expr": "起始表达式",
      "to_expr": "结果表达式",
      "is_correct": true/false,
      "error_type": "错误类型（如果is_correct为false）",
      "explanation": "步骤说明"
    }}
  ]
}}

要求：
1. 将解答过程分解为详细的步骤
2. 每个步骤包含from_expr（起始表达式）和to_expr（结果表达式）
3. 判断每个步骤是否正确
4. 如果步骤错误，提供错误类型和说明
5. 特别注意符号运算的正确性，如 a - (-b) = a + b
6. 确保from_expr不为空
7. 结合题目内容理解解答过程

请严格按照JSON格式返回，不要包含其他内容。"""

            response = self.llm_client.chat.completions.create(
                model="qwen-plus",
                messages=[
                    {
                        'role': 'system',
                        'content': '你是一位专业的数学老师，擅长分析学生的解题过程。请仔细解析解答步骤并按要求返回结构化的JSON数据。特别注意符号运算的正确性。'
                    },
                    {'role': 'user', 'content': prompt}
                ],
                temperature=0.1,
                max_tokens=2000
            )
            
            response_text = response.choices[0].message.content
            
            # 解析JSON响应
            try:
                # 清理响应文本
                clean_text = response_text.strip()
                if clean_text.startswith('```json'):
                    clean_text = clean_text[7:]
                if clean_text.endswith('```'):
                    clean_text = clean_text[:-3]
                clean_text = clean_text.strip()
                
                data = json.loads(clean_text)
                
                # 构建SolutionStep对象
                steps = []
                for step_data in data.get('steps', []):
                    step = SolutionStep(
                        from_expr=step_data.get('from_expr', ''),
                        to_expr=step_data.get('to_expr', ''),
                        is_correct=step_data.get('is_correct', True)
                    )
                    steps.append(step)
                
                self.logger.info(f"AI解析完成（含上下文），共 {len(steps)} 个步骤")
                return steps
                
            except json.JSONDecodeError as e:
                self.logger.error(f"AI JSON解析失败: {e}")
                return self._parse_calculation_steps_simple(solution_text)
                
        except Exception as e:
            self.logger.error(f"AI解析步骤失败: {e}")
            return self._parse_calculation_steps_simple(solution_text)
    
    def _simple_calculation_check(self, answer: MarkdownAnswer) -> bool:
        """简单的计算题检查"""
        try:
            # 尝试从题目中提取数学表达式
            question_text = answer.question_text
            student_answer = answer.student_answer.strip()
            
            # 简单的数学表达式验证
            if '计算：' in question_text:
                # 提取计算表达式
                expr_match = re.search(r'计算：(.+?)[？?]', question_text)
                if expr_match:
                    expression = expr_match.group(1).strip()
                    # 使用SymPy验证
                    return self._verify_calculation_with_sympy(expression, student_answer)
            
            return True  # 默认返回正确
            
        except Exception as e:
            self.logger.warning(f"简单计算检查失败: {e}")
            return True
    
    def _verify_calculation_with_sympy(self, expression: str, student_answer: str) -> bool:
        """使用SymPy验证计算题答案"""
        try:
            try:
                import sympy as sp
            except ImportError:
                self.logger.warning("SymPy未安装，无法进行数学验证")
                return True
            
            # 标准化表达式
            normalized_expr = self._normalize_expression(expression)
            normalized_answer = self._normalize_expression(student_answer)
            
            # 计算正确答案
            correct_result = sp.sympify(normalized_expr)
            student_result = sp.sympify(normalized_answer)
            
            # 比较结果
            return sp.simplify(correct_result - student_result) == 0
            
        except Exception as e:
            self.logger.debug(f"SymPy验证失败: {e}")
            return True
    
    def _normalize_expression(self, expr: str) -> str:
        """标准化数学表达式"""
        if not expr:
            return ""
        
        # 移除空格
        expr = expr.strip()
        
        # 处理分数
        expr = re.sub(r'(\d+)/(\d+)', r'Rational(\1, \2)', expr)
        
        # 处理乘方
        expr = expr.replace('²', '**2').replace('³', '**3')
        
        # 处理乘法符号
        expr = expr.replace('×', '*').replace('·', '*')
        
        # 处理除法符号
        expr = expr.replace('÷', '/')
        
        return expr
    
    def _analyze_student_errors(self, graded_answers: List[MarkdownAnswer]) -> Dict[str, Any]:
        """分析学生易错点"""
        error_types = {}
        weak_areas = []
        knowledge_point_errors = {}
        error_categories = {}
        step_errors = []
        
        for answer in graded_answers:
            if not answer.is_correct and answer.error_analysis:
                # 统计错误类型
                error_type = answer.error_analysis.get('error_type', 'unknown')
                error_types[error_type] = error_types.get(error_type, 0) + 1
                
                # 统计错误分类
                error_category = answer.error_analysis.get('error_category', 'unknown')
                if error_category:
                    error_categories[error_category] = error_categories.get(error_category, 0) + 1
                
                # 收集知识点错误
                knowledge_points = answer.error_analysis.get('knowledge_points', [])
                for kp in knowledge_points:
                    knowledge_point_errors[kp] = knowledge_point_errors.get(kp, 0) + 1
                
                # 收集步骤错误（计算题）
                step_analysis = answer.error_analysis.get('step_analysis', [])
                for step in step_analysis:
                    if not step.get('is_correct', True):
                        step_errors.append({
                            'question_id': answer.question_id,
                            'step_number': step.get('step_number', 0),
                            'error_category': step.get('error_category', 'unknown'),
                            'knowledge_points': step.get('knowledge_points', []),
                            'error_reason': step.get('error_reason', '')
                        })
                
                # 根据题目内容分析薄弱环节
                if '符号' in answer.question_text or '负数' in answer.question_text:
                    weak_areas.append('符号运算')
                elif '分数' in answer.question_text:
                    weak_areas.append('分数运算')
                elif '乘方' in answer.question_text:
                    weak_areas.append('乘方运算')
                elif '方程' in answer.question_text:
                    weak_areas.append('方程求解')
                elif '混合' in answer.question_text:
                    weak_areas.append('混合运算')
        
        # 统计薄弱环节
        weak_area_counts = {}
        for area in weak_areas:
            weak_area_counts[area] = weak_area_counts.get(area, 0) + 1
        
        # 关联到题库错误类型
        bank_error_mapping = self._map_to_bank_error_types(error_categories, knowledge_point_errors)
        
        return {
            "error_type_distribution": error_types,
            "error_categories": error_categories,
            "knowledge_point_errors": knowledge_point_errors,
            "step_errors": step_errors,
            "weak_areas": list(set(weak_areas)),
            "weak_area_counts": weak_area_counts,
            "total_errors": sum(error_types.values()),
            "most_common_error": max(error_types.items(), key=lambda x: x[1])[0] if error_types else None,
            "bank_error_mapping": bank_error_mapping,
            "detailed_analysis": self._generate_detailed_error_analysis(error_categories, knowledge_point_errors, step_errors)
        }
    
    def _map_to_bank_error_types(self, error_categories: Dict[str, int], knowledge_point_errors: Dict[str, int]) -> Dict[str, Any]:
        """将错误类型映射到题库错误类型"""
        mapping = {
            "符号错误": {
                "bank_error_type": "符号错误",
                "description": "正负号处理错误",
                "related_knowledge": ["负数运算规则", "有理数概念"],
                "practice_focus": "符号运算练习"
            },
            "分数运算错误": {
                "bank_error_type": "分数运算",
                "description": "分数四则运算错误",
                "related_knowledge": ["分数运算", "通分约分"],
                "practice_focus": "分数运算练习"
            },
            "乘方运算错误": {
                "bank_error_type": "乘方",
                "description": "乘方计算错误",
                "related_knowledge": ["乘方运算", "指数运算"],
                "practice_focus": "乘方运算练习"
            },
            "运算顺序错误": {
                "bank_error_type": "混合运算",
                "description": "运算顺序错误",
                "related_knowledge": ["运算顺序", "四则运算"],
                "practice_focus": "混合运算练习"
            },
            "计算错误": {
                "bank_error_type": "计算错误",
                "description": "基本计算错误",
                "related_knowledge": ["四则运算", "基础计算"],
                "practice_focus": "基础计算练习"
            }
        }
        
        result = {}
        for category, count in error_categories.items():
            if category in mapping:
                result[category] = {
                    **mapping[category],
                    "error_count": count,
                    "frequency": count / sum(error_categories.values()) if error_categories else 0
                }
        
        return result
    
    def _generate_detailed_error_analysis(self, error_categories: Dict[str, int], 
                                        knowledge_point_errors: Dict[str, int], 
                                        step_errors: List[Dict]) -> Dict[str, Any]:
        """生成详细的错误分析"""
        analysis = {
            "error_patterns": {},
            "knowledge_gaps": [],
            "step_error_patterns": {},
            "recommendations": []
        }
        
        # 分析错误模式
        for category, count in error_categories.items():
            analysis["error_patterns"][category] = {
                "count": count,
                "percentage": count / sum(error_categories.values()) * 100 if error_categories else 0,
                "severity": "high" if count >= 2 else "medium" if count == 1 else "low"
            }
        
        # 分析知识缺口
        for kp, count in knowledge_point_errors.items():
            analysis["knowledge_gaps"].append({
                "knowledge_point": kp,
                "error_count": count,
                "priority": "high" if count >= 2 else "medium" if count == 1 else "low"
            })
        
        # 分析步骤错误模式
        step_error_categories = {}
        for step_error in step_errors:
            category = step_error.get('error_category', 'unknown')
            step_error_categories[category] = step_error_categories.get(category, 0) + 1
        
        analysis["step_error_patterns"] = step_error_categories
        
        # 生成具体建议
        if error_categories:
            most_common = max(error_categories.items(), key=lambda x: x[1])
            error_type = most_common[0]
            if error_type == "符号错误":
                analysis["recommendations"].append("重点练习正负数的运算规则，特别注意符号变化规律")
            elif error_type == "计算错误":
                analysis["recommendations"].append("加强基础运算练习，提高计算准确性和速度")
            elif error_type == "分数运算错误":
                analysis["recommendations"].append("重点练习分数的四则运算，掌握通分和约分技巧")
            elif error_type == "乘方运算错误":
                analysis["recommendations"].append("加强乘方运算练习，理解底数、指数和幂的关系")
            else:
                analysis["recommendations"].append(f"重点练习{error_type}相关题目")
        
        if knowledge_point_errors:
            most_problematic = max(knowledge_point_errors.items(), key=lambda x: x[1])
            knowledge_point = most_problematic[0]
            if knowledge_point == "正负数运算":
                analysis["recommendations"].append("深入理解正负数的概念，掌握同号相加、异号相减的规律")
            elif knowledge_point == "分数运算":
                analysis["recommendations"].append("加强分数运算练习，掌握通分、约分和分数四则运算")
            elif knowledge_point == "乘方运算":
                analysis["recommendations"].append("重点学习乘方的定义和运算法则，多做相关练习")
            else:
                analysis["recommendations"].append(f"加强{knowledge_point}的学习")
        
        return analysis
    
    def _generate_practice_recommendations(self, error_analysis: Dict[str, Any]) -> Dict[str, Any]:
        """基于错误分析生成练习推荐"""
        recommendations = {
            "priority_areas": [],
            "practice_suggestions": [],
            "next_practice_focus": []
        }
        
        # 根据错误类型推荐练习重点
        error_types = error_analysis.get('error_type_distribution', {})
        weak_areas = error_analysis.get('weak_areas', [])
        
        if 'wrong_choice' in error_types:
            # 分析具体的选择题错误类型
            choice_errors = error_analysis.get('choice_errors', [])
            if choice_errors:
                # 统计最常见的错误原因
                error_reasons = {}
                for error in choice_errors:
                    reason = error.get('error_reason', '未知原因')
                    error_reasons[reason] = error_reasons.get(reason, 0) + 1
                
                if error_reasons:
                    most_common_reason = max(error_reasons.items(), key=lambda x: x[1])
                    if '符号处理' in most_common_reason[0]:
                        recommendations["priority_areas"].append("正负数运算规则")
                        recommendations["practice_suggestions"].append("重点练习正负数的加减乘除运算，特别注意符号变化规律")
                    elif '计算错误' in most_common_reason[0]:
                        recommendations["priority_areas"].append("基础运算能力")
                        recommendations["practice_suggestions"].append("加强四则运算的基本功练习，提高计算准确性")
                    elif '概念理解' in most_common_reason[0]:
                        recommendations["priority_areas"].append("数学概念理解")
                        recommendations["practice_suggestions"].append("深入理解相关数学概念，多做概念辨析题")
                    else:
                        recommendations["priority_areas"].append("选择题解题策略")
                        recommendations["practice_suggestions"].append("学习选择题的解题技巧，包括排除法、代入法等")
            else:
                recommendations["priority_areas"].append("选择题解题策略")
                recommendations["practice_suggestions"].append("加强选择题的审题和选项分析能力")
        
        if '符号运算' in weak_areas:
            recommendations["priority_areas"].append("正负数运算")
            recommendations["practice_suggestions"].append("重点练习正负数的四则运算，掌握同号相加、异号相减的规律")
        
        if '分数运算' in weak_areas:
            recommendations["priority_areas"].append("分数计算")
            recommendations["practice_suggestions"].append("加强分数的加减乘除运算练习，特别注意通分和约分技巧")
        
        if '乘方运算' in weak_areas:
            recommendations["priority_areas"].append("乘方计算")
            recommendations["practice_suggestions"].append("重点练习乘方的计算规则，理解底数、指数和幂的关系")
        
        # 生成下次练习重点，避免重复
        if recommendations["priority_areas"]:
            # 去重并限制数量
            unique_areas = list(dict.fromkeys(recommendations["priority_areas"]))
            recommendations["next_practice_focus"] = unique_areas[:3]  # 取前3个重点
        
        return recommendations
    
    def save_grading_results(self, results: Dict[str, Any], filename: str = "markdown_grading_results.json"):
        """保存批改结果"""
        output_file = self.output_dir / filename
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        
        self.logger.info(f"批改结果已保存到: {output_file}")
        
        # 同时生成Markdown格式的报告
        self._create_markdown_report(results)
    
    def _create_markdown_report(self, results: Dict[str, Any]):
        """创建Markdown格式的批改报告"""
        report_file = self.output_dir / "markdown_grading_report.md"
        
        with open(report_file, 'w', encoding='utf-8') as f:
            f.write("# 数学答卷批改报告\n\n")
            
            # 学生信息
            student_info = results.get('student_info', {})
            f.write("## 学生信息\n\n")
            f.write(f"**姓名**: {student_info.get('name', '未知')}\n")
            f.write(f"**学号**: {student_info.get('student_id', '未知')}\n")
            f.write(f"**班级**: {student_info.get('class', '未知')}\n\n")
            
            # 批改摘要
            summary = results.get('grading_summary', {})
            f.write("## 批改摘要\n\n")
            f.write(f"**总题数**: {summary.get('total_questions', 0)}\n")
            f.write(f"**正确题数**: {summary.get('correct_questions', 0)}\n")
            f.write(f"**准确率**: {summary.get('accuracy_percentage', 0):.1f}%\n")
            f.write(f"**批改时间**: {summary.get('grading_timestamp', '')}\n\n")
            
            # 详细批改结果
            f.write("## 详细批改结果\n\n")
            graded_answers = results.get('graded_answers', [])
            
            for i, answer in enumerate(graded_answers, 1):
                status = "✅ 正确" if answer.get('is_correct', False) else "❌ 错误"
                f.write(f"### 第 {i} 题 {status}\n\n")
                f.write(f"**题目**: {answer.get('question_text', '')}\n")
                f.write(f"**类型**: {answer.get('question_type', '')}\n")
                f.write(f"**学生答案**: {answer.get('student_answer', '')}\n")
                
                error_analysis = answer.get('error_analysis', {})
                if error_analysis:
                    f.write(f"**错误分析**: {error_analysis.get('description', '')}\n")
                    if 'suggestions' in error_analysis:
                        f.write("**改进建议**:\n")
                        for suggestion in error_analysis['suggestions']:
                            f.write(f"- {suggestion}\n")
                f.write("\n")
            
            # 易错点分析
            error_analysis = results.get('error_analysis', {})
            if error_analysis:
                f.write("## 易错点分析\n\n")
                f.write(f"**总错误数**: {error_analysis.get('total_errors', 0)}\n\n")
                
                # 错误类型分布
                error_types = error_analysis.get('error_type_distribution', {})
                if error_types:
                    f.write("### 错误类型分布\n\n")
                    for error_type, count in error_types.items():
                        f.write(f"- **{error_type}**: {count} 次\n")
                    f.write("\n")
                
                # 错误分类详细分析
                error_categories = error_analysis.get('error_categories', {})
                if error_categories:
                    f.write("### 错误分类分析\n\n")
                    for category, count in error_categories.items():
                        f.write(f"- **{category}**: {count} 次\n")
                    f.write("\n")
                
                # 知识点错误统计
                knowledge_point_errors = error_analysis.get('knowledge_point_errors', {})
                if knowledge_point_errors:
                    f.write("### 知识点错误统计\n\n")
                    for kp, count in knowledge_point_errors.items():
                        f.write(f"- **{kp}**: {count} 次错误\n")
                    f.write("\n")
                
                # 步骤错误分析（计算题）
                step_errors = error_analysis.get('step_errors', [])
                if step_errors:
                    f.write("### 计算题步骤错误分析\n\n")
                    for step_error in step_errors:
                        f.write(f"- **第{step_error['step_number']}步** ({step_error['question_id']}): {step_error['error_category']}\n")
                        f.write(f"  - 错误原因: {step_error['error_reason']}\n")
                        if step_error['knowledge_points']:
                            f.write(f"  - 涉及知识点: {', '.join(step_error['knowledge_points'])}\n")
                    f.write("\n")
                
                # 题库错误类型映射
                bank_error_mapping = error_analysis.get('bank_error_mapping', {})
                if bank_error_mapping:
                    f.write("### 题库错误类型关联\n\n")
                    for category, mapping in bank_error_mapping.items():
                        f.write(f"- **{category}**\n")
                        f.write(f"  - 题库错误类型: {mapping['bank_error_type']}\n")
                        f.write(f"  - 描述: {mapping['description']}\n")
                        f.write(f"  - 错误次数: {mapping['error_count']}\n")
                        f.write(f"  - 错误频率: {mapping['frequency']:.1%}\n")
                        f.write(f"  - 相关知识点: {', '.join(mapping['related_knowledge'])}\n")
                        f.write(f"  - 练习重点: {mapping['practice_focus']}\n\n")
                
                # 详细分析
                detailed_analysis = error_analysis.get('detailed_analysis', {})
                if detailed_analysis:
                    f.write("### 详细错误分析\n\n")
                    
                    # 错误模式
                    error_patterns = detailed_analysis.get('error_patterns', {})
                    if error_patterns:
                        f.write("**错误模式分析**:\n")
                        for pattern, info in error_patterns.items():
                            f.write(f"- {pattern}: {info['count']}次 ({info['percentage']:.1f}%) - {info['severity']}严重程度\n")
                        f.write("\n")
                    
                    # 知识缺口
                    knowledge_gaps = detailed_analysis.get('knowledge_gaps', [])
                    if knowledge_gaps:
                        f.write("**知识缺口分析**:\n")
                        for gap in knowledge_gaps:
                            f.write(f"- {gap['knowledge_point']}: {gap['error_count']}次错误 - {gap['priority']}优先级\n")
                        f.write("\n")
                    
                    # 建议
                    recommendations = detailed_analysis.get('recommendations', [])
                    if recommendations:
                        f.write("**改进建议**:\n")
                        for rec in recommendations:
                            f.write(f"- {rec}\n")
                        f.write("\n")
                
                # 薄弱环节
                weak_areas = error_analysis.get('weak_areas', [])
                if weak_areas:
                    f.write(f"**薄弱环节**: {', '.join(weak_areas)}\n\n")
            
            # 练习推荐
            recommendations = results.get('practice_recommendations', {})
            if recommendations:
                f.write("## 练习推荐\n\n")
                
                priority_areas = recommendations.get('priority_areas', [])
                if priority_areas:
                    f.write("**重点练习领域**:\n")
                    for area in priority_areas:
                        f.write(f"- {area}\n")
                
                suggestions = recommendations.get('practice_suggestions', [])
                if suggestions:
                    f.write("\n**具体建议**:\n")
                    for suggestion in suggestions:
                        f.write(f"- {suggestion}\n")
                
                next_focus = recommendations.get('next_practice_focus', [])
                if next_focus:
                    f.write(f"\n**下次练习重点**: {', '.join(next_focus)}\n")
        
        self.logger.info(f"批改报告已保存到: {report_file}")
    
    def generate_practice_from_errors(self, error_analysis: Dict[str, Any], 
                                    choice_count: int = 2, calculation_count: int = 2) -> Dict[str, Any]:
        """基于易错点生成练习题目
        
        Args:
            error_analysis: 错误分析结果
            choice_count: 选择题数量
            calculation_count: 计算题数量
            
        Returns:
            生成的练习题目
        """
        self.logger.info("基于易错点生成练习题目")
        
        try:
            # 获取薄弱环节
            weak_areas = error_analysis.get('weak_areas', [])
            error_types = error_analysis.get('error_type_distribution', {})
            
            # 映射薄弱环节到错误类型
            error_type_mapping = {
                '符号运算': '符号错误',
                '分数运算': '分数运算',
                '乘方运算': '乘方',
                '方程求解': '方程',
                '混合运算': '混合运算'
            }
            
            # 确定要练习的错误类型
            practice_error_types = []
            for area in weak_areas:
                if area in error_type_mapping:
                    practice_error_types.append(error_type_mapping[area])
            
            # 如果没有明确的薄弱环节，使用最常见的错误类型
            if not practice_error_types and error_types:
                most_common = max(error_types.items(), key=lambda x: x[1])
                practice_error_types = [most_common[0]]
            
            # 如果没有错误类型，使用默认的
            if not practice_error_types:
                practice_error_types = ['符号错误', '计算错误']
            
            # 使用现有的练习生成功能
            from .cli import MathGrader
            grader = MathGrader(output_dir=str(self.output_dir))
            
            practice_test = grader.generate_practice_test(
                error_types=practice_error_types,
                choice_count=choice_count,
                calculation_count=calculation_count
            )
            
            if "error" in practice_test:
                return {"error": practice_test["error"]}
            
            # 添加基于错误分析的说明
            practice_test["error_analysis_based"] = True
            practice_test["targeted_weak_areas"] = weak_areas
            practice_test["practice_error_types"] = practice_error_types
            
            # 生成针对性的说明
            instructions = f"""
练习试卷说明：
本试卷针对您的易错点进行专项练习

重点练习领域：{', '.join(weak_areas) if weak_areas else '基础运算'}
错误类型：{', '.join(practice_error_types)}

答题要求：
1. 选择题请选择正确答案
2. 计算题请写出完整的解题过程
3. 特别注意之前容易出错的地方
4. 仔细检查每一步计算

建议：
- 放慢解题速度，确保每一步都正确
- 重点练习薄弱环节
- 完成后仔细检查答案

祝学习进步！
            """.strip()
            
            practice_test["instructions"] = instructions
            
            self.logger.info(f"基于易错点生成了 {len(practice_test.get('questions', []))} 道练习题目")
            return practice_test
            
        except Exception as e:
            self.logger.error(f"生成练习题目失败: {e}")
            return {"error": f"生成练习题目失败: {str(e)}"}
    
    def save_practice_test(self, practice_test: Dict[str, Any], filename: str = "targeted_practice_test.json"):
        """保存针对性练习题目"""
        output_file = self.output_dir / filename
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(practice_test, f, ensure_ascii=False, indent=2)
        
        self.logger.info(f"针对性练习题目已保存到: {output_file}")
        
        # 同时创建Markdown格式的试卷
        self._create_practice_test_markdown(practice_test)
    
    def _create_practice_test_markdown(self, practice_test: Dict[str, Any]):
        """创建针对性练习试卷的Markdown格式"""
        md_file = self.output_dir / "targeted_practice_test.md"
        
        with open(md_file, 'w', encoding='utf-8') as f:
            f.write("# 针对性数学练习试卷\n\n")
            
            # 学生信息填写区域
            f.write("## 学生信息\n\n")
            f.write("**姓名**: _________________\n\n")
            f.write("**学号**: _________________\n\n")
            f.write("**班级**: _________________\n\n")
            f.write("---\n\n")
            
            # 试卷信息
            f.write("## 试卷信息\n\n")
            test_info = practice_test.get('test_info', {})
            
            f.write(f"**生成时间**: {test_info.get('generated_at', '')}\n")
            f.write(f"**针对性练习**: {', '.join(test_info.get('error_types', []))}\n")
            f.write(f"**题目总数**: {test_info.get('total_questions', 0)}\n")
            f.write(f"**选择题**: {test_info.get('choice_questions', 0)} 道\n")
            f.write(f"**计算题**: {test_info.get('calculation_questions', 0)} 道\n\n")
            
            # 针对性说明
            if practice_test.get('error_analysis_based'):
                f.write("## 针对性练习说明\n\n")
                f.write("本试卷基于您之前的答题情况，针对以下薄弱环节进行专项练习：\n\n")
                
                weak_areas = practice_test.get('targeted_weak_areas', [])
                if weak_areas:
                    f.write("**薄弱环节**:\n")
                    for area in weak_areas:
                        f.write(f"- {area}\n")
                    f.write("\n")
                
                error_types = practice_test.get('practice_error_types', [])
                if error_types:
                    f.write("**重点练习错误类型**:\n")
                    for error_type in error_types:
                        f.write(f"- {error_type}\n")
                    f.write("\n")
            
            # 说明
            f.write("## 答题说明\n\n")
            f.write(practice_test.get('instructions', ''))
            f.write("\n\n")
            
            # 题目
            f.write("## 题目\n\n")
            questions = practice_test.get('questions', [])
            for i, question in enumerate(questions, 1):
                f.write(f"### 第 {i} 题\n\n")
                
                # 题目文本
                question_text = question.get('question_info', {}).get('text', '') or question.get('question', {}).get('text', '')
                f.write(f"**题目**: {question_text}\n\n")
                
                # 选择题选项
                if 'choices' in question and question['choices']:
                    f.write("**选项**:\n")
                    for choice in question['choices']:
                        choice_id = choice.get('id', '')
                        choice_content = choice.get('content', '')
                        f.write(f"- {choice_id}. {choice_content}\n")
                    f.write("\n")
                    f.write("**答案**: (    )\n\n")
                
                # 计算题答题空间
                question_type = question.get('question_type', '')
                has_choices = 'choices' in question and question['choices']
                
                if question_type == 'calculation' or (not has_choices and question_type != 'choice'):
                    f.write("**解答**: \n\n")
                    f.write("```\n")
                    f.write("请在此处写出完整的解题过程\n")
                    f.write("```\n\n")
                
                f.write("---\n\n")
        
        self.logger.info(f"针对性练习试卷已保存到: {md_file}")


def main():
    """测试函数"""
    # 示例Markdown内容
    sample_markdown = """
# 数学练习试卷

## 学生信息

**姓名**: 张三

**学号**: 2024001

**班级**: 七年级1班

---

## 试卷信息

**生成时间**: 2024-01-01T10:00:00

**重点练习**: 符号错误, 计算错误

**题目总数**: 2

**选择题**: 1 道

**计算题**: 1 道

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

**题目**: 计算：((-3) × (-3) - (-3) × 3) 等于多少？

**选项**:
- a. 18
- b. 0
- c. -18
- d. -6

**答案**: (b)

### 第 2 题

**题目**: 计算：(15) - (-4) 的值是？

**解答**: 

```
15 - (-4) = 15 + 4 = 19
```

---

"""
    
    # 测试解析和批改
    grader = MarkdownGrader()
    markdown_test = grader.parse_markdown_test(sample_markdown)
    results = grader.grade_markdown_test(markdown_test)
    grader.save_grading_results(results)
    
    print("Markdown答卷批改完成！")


if __name__ == "__main__":
    main()
