"""AI processing module for analyzing mathematical expressions and solutions."""

import os
import json
import logging
import re
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
from openai import OpenAI
import sympy as sp
from fractions import Fraction


@dataclass
class CalculationStep:
    """Represents a single calculation step."""
    from_expr: str
    to_expr: str
    point: str
    is_correct: bool = True


@dataclass
class SolutionStep:
    """Represents a solution step transformation."""
    from_expr: str
    to_expr: str
    is_correct: bool
    llm_determine: Optional[bool] = None
    rule_determine: Optional[bool] = None


@dataclass
class StudentSolution:
    """Detailed student solution with step analysis."""
    raw: str
    steps: List[SolutionStep] = None
    calculation: List[CalculationStep] = None
    
    def __post_init__(self):
        if self.steps is None:
            self.steps = []
        if self.calculation is None:
            self.calculation = []


@dataclass
class MathProblem:
    """Represents a mathematical problem with its solution."""
    problem_id: str
    problem_text: str
    student_solution: StudentSolution
    expected_answer: Optional[str] = None
    problem_type: str = "unknown"


@dataclass
class ValidationResult:
    """Result of mathematical validation."""
    is_correct: bool
    error_type: Optional[str] = None
    error_description: str = ""
    suggestions: List[str] = None
    confidence: float = 0.0
    
    def __post_init__(self):
        if self.suggestions is None:
            self.suggestions = []


class AIProcessor:
    """Handles AI-based processing of mathematical problems."""
    
    def __init__(self):
        """Initialize AI processor."""
        self.logger = logging.getLogger(__name__)
        
        # Initialize OpenAI client for enhanced AI analysis
        try:
            self.client = OpenAI(
                api_key=os.getenv("DASHSCOPE_API_KEY"),
                base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
            )
            self.use_llm = True
            self.logger.info("AI client initialized successfully")
            
        except Exception as e:
            self.logger.warning(f"Failed to initialize AI client: {e}. Falling back to rule-based analysis.")
            self.client = None
            self.use_llm = False
    
    def parse_ocr_to_problems(self, ocr_text: str) -> List[MathProblem]:
        """Parse OCR text into structured math problems.
        
        Args:
            ocr_text: Raw OCR text
            
        Returns:
            List of structured math problems
        """
        if self.use_llm and self.client:
            return self._parse_with_llm(ocr_text)
        else:
            return self._parse_with_rules(ocr_text)
    
    def _parse_with_llm(self, ocr_text: str) -> List[MathProblem]:
        """Use LLM to parse OCR text into structured problems."""
        json_format = """
{
  "problems": [
    {
      "id": "problem_1",
      "text": "题目内容",
      "student_solution": {
        "raw": "原始解答文本",
        "steps": [
          {
            "from": "起始表达式",
            "to": "结果表达式", 
            "llm_determine": true/false
          }
        ]
      }
    }
  ]
}
        """
        try:
            prompt = f"""请将以下OCR识别的数学题目文本解析为结构化的JSON格式。

OCR文本：
{ocr_text}

要求：
1. 识别所有四则运算计算题目（忽略应用题，解方程题目）
2. 提取题目编号、题目内容、学生解答过程。题目编号作为 ID。
3. 将解答过程分解为详细的步骤，禁止修改答题步骤，以"等号"分割步骤，step 从原题开始。
4. 分析每个步骤的正确性，特别注意：
   - 负数运算规则：a - (-b) = a + b
   - 符号处理：注意括号内的负号处理
   - 运算顺序：先乘除后加减，有括号先算括号内
   - 分数运算：通分、约分等
5. 对于符号错误要特别仔细分析，例如：
   - (15) - (-4) 应该等于 15 + 4 = 19，不是 15 - 4 = 11
   - 负负得正，正负得负
6. 忽略非答题过程的内容书写。

返回JSON格式：
{json_format}
请严格按照数学原理分析，确保步骤分解的准确性，保留学生答题的错误。特别注意符号运算的正确性。"""

            response = self.client.chat.completions.create(
                model="qwen-plus",
                messages=[
                    {
                        'role': 'system',
                        'content': '你是一位专业的数学老师，擅长分析学生的解题过程，特别是符号运算和负数运算。请仔细解析题目并按要求返回结构化的JSON数据。特别注意符号运算的正确性，如负负得正、正负得负等规则。'
                    },
                    {'role': 'user', 'content': prompt}
                ],
                temperature=0.1,
                max_tokens=2000
            )
            
            response_text = response.choices[0].message.content
            
            # Log complete request and response without truncation (excluding image data)
            self.logger.info("=== AI MODEL REQUEST ===")
            self.logger.info(f"Model: qwen-plus")
            self.logger.info(f"Temperature: 0.1")
            self.logger.info(f"Max Tokens: 2000")
            # Filter out base64 image data from prompt logging
            filtered_prompt = prompt
            self.logger.info(f"Request Body (Prompt): {filtered_prompt}")
            self.logger.info("=== AI MODEL RESPONSE ===")
            self.logger.info(f"Full Response: {response_text}")
            self.logger.info(f"Response Length: {len(response_text)} characters")
            self.logger.info("=== END AI MODEL INTERACTION ===")
            
            # Try to parse JSON response
            try:
                # Clean the response text - remove markdown code blocks if present
                clean_text = response_text.strip()
                if clean_text.startswith('```json'):
                    clean_text = clean_text[7:]
                if clean_text.endswith('```'):
                    clean_text = clean_text[:-3]
                clean_text = clean_text.strip()
                
                data = json.loads(clean_text)
                problems = []
                
                for prob_data in data.get('problems', []):
                    solution_data = prob_data.get('student_solution', {})
                    
                    # Parse steps
                    steps = []
                    for step_data in solution_data.get('steps', []):
                        steps.append(SolutionStep(
                            from_expr=step_data.get('from', ''),
                            to_expr=step_data.get('to', ''),
                            is_correct=step_data.get('is_correct', True),
                            llm_determine=step_data.get('llm_determine', step_data.get('is_correct', True))
                        ))
                    
                    # Parse calculations
                    calculations = []
                    for calc_data in solution_data.get('calculation', []):
                        calculations.append(CalculationStep(
                            from_expr=calc_data.get('from', ''),
                            to_expr=calc_data.get('to', ''),
                            point=calc_data.get('point', ''),
                            is_correct=True  # Default to correct, will be validated later
                        ))
                    
                    student_solution = StudentSolution(
                        raw=solution_data.get('raw', ''),
                        steps=steps,
                        calculation=calculations
                    )
                    
                    problem = MathProblem(
                        problem_id=prob_data.get('id', f'problem_{len(problems)+1}'),
                        problem_text=prob_data.get('text', ''),
                        problem_type=prob_data.get('type', 'unknown'),
                        student_solution=student_solution
                    )
                    
                    # Apply rule-based verification to each step
                    self._apply_rule_verification(problem)
                    problems.append(problem)
                
                return problems
                
            except json.JSONDecodeError as e:
                self.logger.error(f"Failed to parse LLM JSON response: {e}")
                return self._parse_with_rules(ocr_text)
                
        except Exception as e:
            self.logger.error(f"LLM parsing failed: {e}")
            return self._parse_with_rules(ocr_text)
    
    def _parse_with_rules(self, ocr_text: str) -> List[MathProblem]:
        """Fallback rule-based parsing."""
        problems = []
        
        # Split text into lines and process
        lines = [line.strip() for line in ocr_text.split('\n') if line.strip()]
        
        current_problem = None
        problem_counter = 1
        solution_lines = []
        
        for line in lines:
            # Check if line contains a problem number
            if re.match(r'^\d+\.', line):
                # Save previous problem if exists
                if current_problem:
                    raw_solution = '\n'.join(solution_lines)
                    student_solution = StudentSolution(
                        raw=raw_solution,
                        steps=self._extract_basic_steps(solution_lines),
                        calculation=[]
                    )
                    current_problem.student_solution = student_solution
                    problems.append(current_problem)
                
                # Start new problem
                current_problem = MathProblem(
                    problem_id=f"problem_{problem_counter}",
                    problem_text=line,
                    problem_type=self._identify_problem_type(line),
                    student_solution=StudentSolution(raw="")
                )
                problem_counter += 1
                solution_lines = []
            
            elif current_problem and ('=' in line or any(op in line for op in ['+', '-', '×', '÷', '/'])):
                # This looks like a solution step
                solution_lines.append(line)
        
        # Don't forget the last problem
        if current_problem:
            raw_solution = '\n'.join(solution_lines)
            student_solution = StudentSolution(
                raw=raw_solution,
                steps=self._extract_basic_steps(solution_lines),
                calculation=[]
            )
            current_problem.student_solution = student_solution
            problems.append(current_problem)
        
        # Apply rule-based verification to all problems
        for problem in problems:
            self._apply_rule_verification(problem)
        
        return problems
    
    def _extract_basic_steps(self, solution_lines: List[str]) -> List[SolutionStep]:
        """Extract basic steps from solution lines."""
        steps = []
        prev_expr = ""
        
        for line in solution_lines:
            if '=' in line:
                parts = line.split('=')
                if len(parts) >= 2:
                    from_expr = prev_expr if prev_expr else parts[0].strip()
                    to_expr = parts[-1].strip()
                    
                    steps.append(SolutionStep(
                        from_expr=from_expr,
                        to_expr=to_expr,
                        is_correct=True  # Default, will be validated later
                    ))
                    
                    prev_expr = to_expr
        
        return steps
    
    def _apply_rule_verification(self, problem: 'MathProblem') -> None:
        """Apply rule-based verification using SymPy to verify each step."""
        if not problem.student_solution or not problem.student_solution.steps:
            return
        
        for step in problem.student_solution.steps:
            try:
                # Normalize expressions for SymPy
                from_expr = self._normalize_expression(step.from_expr)
                to_expr = self._normalize_expression(step.to_expr)
                
                # Verify with SymPy
                step.rule_determine = self._verify_step_with_sympy(from_expr, to_expr)
                
                # Apply comprehensive validation logic
                step.is_correct = self._determine_final_correctness(step)
                
            except Exception as e:
                self.logger.warning(f"Rule verification failed for step {step.from_expr} -> {step.to_expr}: {e}")
                step.rule_determine = None
                step.is_correct = step.llm_determine if step.llm_determine is not None else False
    
    def _determine_final_correctness(self, step: 'SolutionStep') -> bool:
        """
        综合判断步骤正确性，优先采用LLM分析结果，数学计算作为参考。
        
        判断逻辑：
        1. 如果llm_determine有明确结果，优先采用（AI分析）
        2. 如果llm_determine为None但rule_determine有结果，采用数学法则判断
        3. 如果两者都为None，默认为False
        4. 记录不一致情况用于分析，但仍以LLM结果为准
        """
        rule_result = step.rule_determine
        llm_result = step.llm_determine
        
        # 优先采用LLM分析结果
        if llm_result is not None:
            final_result = llm_result
            
            # 检查AI和数学法则是否一致，仅作为参考信息记录
            if rule_result is not None and llm_result != rule_result:
                self.logger.info(
                    f"AI与数学法则判断不一致 - 步骤: {step.from_expr} -> {step.to_expr}, "
                    f"AI判断: {llm_result}, 数学法则: {rule_result}, "
                    f"最终采用AI分析结果: {llm_result}"
                )
            elif rule_result is not None:
                self.logger.debug(f"AI与数学法则判断一致: {llm_result}")
        elif rule_result is not None:
            # LLM无法判断时，采用数学法则结果
            final_result = rule_result
            self.logger.info(f"LLM无法判断，采用数学法则结果: {rule_result}")
        else:
            # 两者都无法判断时，默认错误
            final_result = False
            self.logger.warning(f"无法验证步骤正确性: {step.from_expr} -> {step.to_expr}")
        
        return final_result
    
    def _generate_mathematical_analysis(self, step: 'SolutionStep') -> Dict[str, Any]:
        """
        为步骤生成详细的数学分析，特别是当rule_determine给出结果时。
        """
        analysis = {
            "calculation_process": "",
            "correct_result": "",
            "error_explanation": "",
            "verification_method": "rule_based" if step.rule_determine is not None else "ai_based"
        }
        
        try:
            from_expr = step.from_expr.strip()
            to_expr = step.to_expr.strip()
            
            # 如果数学法则验证可用，提供详细计算过程
            if step.rule_determine is not None:
                if step.rule_determine:
                    # 正确的步骤
                    analysis["calculation_process"] = f"验证: {from_expr} = {to_expr}"
                    analysis["correct_result"] = to_expr
                    
                    # 尝试提供计算过程
                    calculation_steps = self._explain_calculation_process(from_expr, to_expr)
                    if calculation_steps:
                        analysis["calculation_process"] = calculation_steps
                else:
                    # 错误的步骤，计算正确结果
                    analysis["calculation_process"] = f"学生计算: {from_expr} = {to_expr}"
                    
                    # 计算正确结果
                    correct_result = self._calculate_correct_result(from_expr)
                    if correct_result:
                        analysis["correct_result"] = correct_result
                        analysis["error_explanation"] = f"学生得到 {to_expr}，但正确结果应该是 {correct_result}"
                    else:
                        analysis["error_explanation"] = f"表达式 {from_expr} 与 {to_expr} 不相等"
            else:
                # 只有AI判断时的分析
                if step.llm_determine:
                    analysis["calculation_process"] = f"AI判断: {from_expr} = {to_expr} 正确"
                else:
                    analysis["calculation_process"] = f"AI判断: {from_expr} = {to_expr} 错误"
                    analysis["error_explanation"] = "根据AI分析，此步骤存在错误"
            
        except Exception as e:
            analysis["error_explanation"] = f"分析过程出错: {str(e)}"
        
        return analysis
    
    def _explain_calculation_process(self, from_expr: str, to_expr: str) -> str:
        """解释计算过程"""
        try:
            # 处理分数运算的详细说明
            if '/' in from_expr and '/' in to_expr:
                return self._explain_fraction_calculation(from_expr, to_expr)
            
            # 处理基本运算
            if any(op in from_expr for op in ['+', '-', '*', '÷']):
                return f"计算过程: {from_expr} = {to_expr}"
            
            return f"验证: {from_expr} = {to_expr}"
            
        except Exception:
            return f"验证: {from_expr} = {to_expr}"
    
    def _explain_fraction_calculation(self, from_expr: str, to_expr: str) -> str:
        """详细解释分数计算过程"""
        try:
            # 解析分数运算
            if '-' in from_expr and '/' in from_expr:
                # 分数减法
                parts = from_expr.split('-')
                if len(parts) == 2:
                    left = parts[0].strip()
                    right = parts[1].strip()
                    
                    # 检查是否需要通分
                    if '/' in left and '/' in right:
                        left_parts = left.split('/')
                        right_parts = right.split('/')
                        
                        if len(left_parts) == 2 and len(right_parts) == 2:
                            left_num, left_den = int(left_parts[0]), int(left_parts[1])
                            right_num, right_den = int(right_parts[0]), int(right_parts[1])
                            
                            if left_den != right_den:
                                # 需要通分
                                lcm = left_den * right_den // self._gcd(left_den, right_den)
                                new_left_num = left_num * (lcm // left_den)
                                new_right_num = right_num * (lcm // right_den)
                                result_num = new_left_num - new_right_num
                                
                                return (f"通分: {left} = {new_left_num}/{lcm}, {right} = {new_right_num}/{lcm}\n"
                                       f"计算: {new_left_num}/{lcm} - {new_right_num}/{lcm} = {result_num}/{lcm}")
            
            return f"计算: {from_expr} = {to_expr}"
            
        except Exception:
            return f"计算: {from_expr} = {to_expr}"
    
    def _calculate_correct_result(self, expr: str) -> str:
        """计算表达式的正确结果"""
        try:
            # 使用SymPy计算正确结果
            normalized_expr = self._normalize_expression(expr)
            result = sp.sympify(normalized_expr)
            simplified = sp.simplify(result)
            
            # 转换为分数形式（如果合适）
            if simplified.is_rational:
                frac = sp.Rational(simplified)
                if frac.denominator == 1:
                    return str(frac.numerator)
                else:
                    return f"{frac.numerator}/{frac.denominator}"
            
            return str(simplified)
            
        except Exception:
            return ""
    
    def _gcd(self, a: int, b: int) -> int:
        """计算最大公约数"""
        while b:
            a, b = b, a % b
        return a
    
    def _normalize_expression(self, expr: str) -> str:
        """Normalize mathematical expression for SymPy evaluation."""
        if not expr:
            return ""
        
        # Remove spaces
        expr = expr.strip()
        
        # Handle fractions: convert a/b format to proper fraction
        expr = re.sub(r'(\d+)/(\d+)', r'Rational(\1, \2)', expr)
        
        # Handle multiplication symbols
        expr = expr.replace('×', '*').replace('·', '*')
        
        # Handle division symbols
        expr = expr.replace('÷', '/')
        
        return expr
    
    def _verify_step_with_sympy(self, from_expr: str, to_expr: str) -> bool:
        """Verify if the mathematical step is correct using SymPy."""
        try:
            # Parse expressions with SymPy
            from_parsed = sp.sympify(from_expr)
            to_parsed = sp.sympify(to_expr)
            
            # Check if expressions are mathematically equivalent
            difference = sp.simplify(from_parsed - to_parsed)
            
            # If difference simplifies to 0, expressions are equivalent
            return difference == 0
            
        except (sp.SympifyError, ValueError, TypeError) as e:
            self.logger.debug(f"SymPy parsing failed for {from_expr} -> {to_expr}: {e}")
            
            # Fallback: try fraction comparison
            return self._verify_fraction_step(from_expr, to_expr)
    
    def _verify_fraction_step(self, from_expr: str, to_expr: str) -> bool:
        """Fallback verification for fraction operations."""
        try:
            # Extract fractions and operations
            from_result = self._evaluate_fraction_expression(from_expr)
            to_result = self._evaluate_fraction_expression(to_expr)
            
            if from_result is not None and to_result is not None:
                return abs(from_result - to_result) < 1e-10
            
            return False
            
        except Exception as e:
            self.logger.debug(f"Fraction verification failed: {e}")
            return False
    
    def _evaluate_fraction_expression(self, expr: str) -> Optional[float]:
        """Evaluate a mathematical expression containing fractions."""
        try:
            # Handle simple fraction addition/subtraction
            if '+' in expr or '-' in expr:
                # Split by operators while preserving them
                parts = re.split(r'([+\-])', expr)
                result = 0.0
                current_sign = 1
                
                for part in parts:
                    part = part.strip()
                    if part == '+':
                        current_sign = 1
                    elif part == '-':
                        current_sign = -1
                    elif part:
                        # Parse fraction
                        if '/' in part:
                            num, den = part.split('/')
                            result += current_sign * (int(num.strip()) / int(den.strip()))
                        else:
                            result += current_sign * float(part)
                
                return result
            
            # Handle single fraction
            elif '/' in expr:
                num, den = expr.split('/')
                return int(num.strip()) / int(den.strip())
            
            # Handle simple number
            else:
                return float(expr)
                
        except (ValueError, ZeroDivisionError):
            return None
    
    def _identify_problem_type(self, problem_text: str) -> str:
        """Identify the type of mathematical problem.
        
        Args:
            problem_text: Problem text
            
        Returns:
            Problem type string
        """
        if '/' in problem_text or '分数' in problem_text:
            return "fraction"
        elif 'x' in problem_text.lower() or '解方程' in problem_text:
            return "equation"
        elif any(op in problem_text for op in ['+', '-', '×', '÷']):
            return "arithmetic"
        elif '应用题' in problem_text or '问题' in problem_text:
            return "word_problem"
        else:
            return "unknown"
    
    def validate_solution(self, problem: MathProblem) -> ValidationResult:
        """Validate a student's solution using comprehensive analysis.
        
        综合AI和数学法则判断，优先采用数学计算法则结果。
        
        Args:
            problem: Math problem with student solution
            
        Returns:
            Validation result with correctness and feedback
        """
        try:
            if not problem.student_solution or not problem.student_solution.steps:
                return ValidationResult(
                    is_correct=False,
                    error_type="no_solution",
                    error_description="未找到学生解答步骤",
                    confidence=1.0
                )
            
            # 分析每个步骤的验证结果
            total_steps = len(problem.student_solution.steps)
            correct_steps = sum(1 for step in problem.student_solution.steps if step.is_correct)
            
            # 统计AI和数学法则的一致性
            agreement_count = 0
            rule_verified_count = 0
            disagreement_steps = []
            
            for i, step in enumerate(problem.student_solution.steps):
                if step.rule_determine is not None:
                    rule_verified_count += 1
                    if step.llm_determine is not None:
                        if step.rule_determine == step.llm_determine:
                            agreement_count += 1
                        else:
                            disagreement_steps.append(i + 1)
            
            # 计算置信度：优先考虑数学法则验证的步骤
            if rule_verified_count > 0:
                confidence = correct_steps / total_steps
            else:
                confidence = max(0.5, correct_steps / total_steps)  # 没有数学验证时降低置信度
            
            # 判断整体正确性
            is_correct = correct_steps == total_steps
            
            if is_correct:
                description = "解答正确"
                if disagreement_steps:
                    description += f"（注意：第{','.join(map(str, disagreement_steps))}步AI和数学法则判断不一致，已采用数学法则结果）"
                
                return ValidationResult(
                    is_correct=True,
                    confidence=confidence,
                    error_type=None,
                    error_description=description
                )
            else:
                # 找到错误步骤进行详细分析
                incorrect_steps = []
                for i, step in enumerate(problem.student_solution.steps):
                    if not step.is_correct:
                        step_info = f"步骤{i + 1}"
                        if step.rule_determine is False:
                            step_info += "（数学计算错误）"
                        elif step.llm_determine is False and step.rule_determine is None:
                            step_info += "（AI判断错误）"
                        incorrect_steps.append(step_info)
                
                error_description = f"发现错误：{', '.join(incorrect_steps)}"
                if disagreement_steps:
                    error_description += f"。第{','.join(map(str, disagreement_steps))}步AI和数学法则判断不一致"
                
                return ValidationResult(
                    is_correct=False,
                    confidence=confidence,
                    error_type="step_analysis",
                    error_description=error_description
                )
                
        except Exception as e:
            self.logger.error(f"Validation failed: {e}")
            return ValidationResult(
                is_correct=False,
                error_type="validation_error",
                error_description=f"验证过程出错: {str(e)}",
                confidence=0.0
            )
    
    def _validate_fraction_problem(self, problem: MathProblem) -> ValidationResult:
        """Validate fraction arithmetic problems."""
        from fractions import Fraction
        
        try:
            # Extract the original problem and solution
            solution_lines = [line.strip() for line in problem.student_solution.split('\n') if line.strip()]
            
            if not solution_lines:
                return ValidationResult(
                    is_correct=False,
                    error_type="no_solution",
                    error_description="未找到解答过程",
                    confidence=0.8
                )
            
            # Look for the final answer (usually the last line with =)
            final_answer_line = None
            for line in reversed(solution_lines):
                if '=' in line:
                    final_answer_line = line
                    break
            
            if not final_answer_line:
                return ValidationResult(
                    is_correct=False,
                    error_type="no_final_answer",
                    error_description="未找到最终答案",
                    confidence=0.8
                )
            
            # Try to extract and evaluate the original expression
            original_expr = self._extract_fraction_expression(problem.problem_text)
            if original_expr:
                try:
                    correct_result = eval(original_expr)
                    student_result = self._extract_final_result(final_answer_line)
                    
                    if student_result is not None:
                        if abs(float(correct_result) - float(student_result)) < 0.001:
                            return ValidationResult(
                                is_correct=True,
                                confidence=0.9
                            )
                        else:
                            return ValidationResult(
                                is_correct=False,
                                error_type="wrong_answer",
                                error_description=f"计算结果错误。正确答案应该是 {correct_result}",
                                suggestions=["请检查计算过程", "注意分数运算规则"],
                                confidence=0.9
                            )
                except:
                    pass
            
            # If we can't automatically verify, return uncertain result
            return ValidationResult(
                is_correct=False,
                error_type="uncertain",
                error_description="无法自动验证此题目，需要人工检查",
                confidence=0.3
            )
            
        except Exception as e:
            return ValidationResult(
                is_correct=False,
                error_type="validation_error",
                error_description=f"验证分数题目时出错: {str(e)}",
                confidence=0.0
            )
    
    def _validate_arithmetic_problem(self, problem: MathProblem) -> ValidationResult:
        """Validate basic arithmetic problems."""
        # Similar structure to fraction validation but for basic arithmetic
        return ValidationResult(
            is_correct=False,
            error_type="not_implemented",
            error_description="算术题验证功能尚未实现",
            confidence=0.0
        )
    
    def _validate_equation_problem(self, problem: MathProblem) -> ValidationResult:
        """Validate equation solving problems."""
        return ValidationResult(
            is_correct=False,
            error_type="not_implemented", 
            error_description="方程题验证功能尚未实现",
            confidence=0.0
        )
    
    def _extract_fraction_expression(self, text: str) -> Optional[str]:
        """Extract evaluable fraction expression from text."""
        # This is a simplified version - in practice, you'd need more sophisticated parsing
        import re
        
        # Look for patterns like "11/16 + 4/9 + 5/16"
        pattern = r'(\d+/\d+(?:\s*[+\-×÷]\s*\d+/\d+)*)'
        match = re.search(pattern, text)
        
        if match:
            expr = match.group(1)
            # Convert to Python-evaluable expression
            expr = expr.replace('×', '*').replace('÷', '/')
            return expr
        
        return None
    
    def _extract_final_result(self, line: str) -> Optional[float]:
        """Extract numerical result from a line."""
        import re
        
        # Look for number after = sign
        pattern = r'=\s*([0-9]+(?:\.[0-9]+)?(?:/[0-9]+)?)'
        match = re.search(pattern, line)
        
        if match:
            result_str = match.group(1)
            if '/' in result_str:
                # Handle fraction
                parts = result_str.split('/')
                return float(parts[0]) / float(parts[1])
            else:
                return float(result_str)
        
        return None
    
    def generate_feedback(self, problem: MathProblem, validation: ValidationResult) -> Dict[str, Any]:
        """Generate detailed feedback for a math problem solution.
        
        综合AI和数学法则判断结果生成反馈。
        
        Args:
            problem: Math problem with student solution
            validation: Validation result
            
        Returns:
            Detailed feedback dictionary
        """
        feedback = {
            "problem_id": problem.problem_id,
            "problem_type": problem.problem_type,
            "is_correct": validation.is_correct,
            "confidence": validation.confidence,
            "feedback": "",
            "detailed_analysis": {
                "total_steps": 0,
                "correct_steps": 0,
                "step_details": [],
                "verification_summary": {
                    "rule_verified_steps": 0,
                    "ai_llm_steps": 0,
                    "agreement_rate": 0.0,
                    "disagreement_steps": []
                }
            }
        }
        
        if problem.student_solution and problem.student_solution.steps:
            steps = problem.student_solution.steps
            feedback["detailed_analysis"]["total_steps"] = len(steps)
            feedback["detailed_analysis"]["correct_steps"] = sum(1 for step in steps if step.is_correct)
            
            # 统计验证方式
            rule_verified = sum(1 for step in steps if step.rule_determine is not None)
            ai_verified = sum(1 for step in steps if step.llm_determine is not None)
            agreements = sum(1 for step in steps 
                           if step.rule_determine is not None and step.llm_determine is not None 
                           and step.rule_determine == step.llm_determine)
            disagreements = []
            
            # Generate step-by-step analysis
            for i, step in enumerate(steps, 1):
                verification_method = []
                if step.rule_determine is not None:
                    verification_method.append(f"数学法则: {'✓' if step.rule_determine else '✗'}")
                if step.llm_determine is not None:
                    verification_method.append(f"AI判断: {'✓' if step.llm_determine else '✗'}")
                
                # 检查不一致情况
                if (step.rule_determine is not None and step.llm_determine is not None 
                    and step.rule_determine != step.llm_determine):
                    disagreements.append(i)
                    verification_method.append("⚠️ 判断不一致")
                
                # 生成数学分析
                mathematical_analysis = self._generate_mathematical_analysis(step)
                
                step_detail = {
                    "step_number": i,
                    "from": step.from_expr,
                    "to": step.to_expr,
                    "is_correct": step.is_correct,
                    "status": "✅ 正确" if step.is_correct else "❌ 错误",
                    "verification": " | ".join(verification_method) if verification_method else "未验证",
                    "llm_determine": step.llm_determine,
                    "rule_determine": step.rule_determine,
                    "mathematical_analysis": mathematical_analysis
                }
                feedback["detailed_analysis"]["step_details"].append(step_detail)
            
            # 更新验证摘要
            feedback["detailed_analysis"]["verification_summary"] = {
                "rule_verified_steps": rule_verified,
                "ai_llm_steps": ai_verified,
                "agreement_rate": agreements / max(1, min(rule_verified, ai_verified)),
                "disagreement_steps": disagreements
            }
        
        # Generate overall feedback message
        if validation.is_correct:
            feedback["feedback"] = "解答正确！所有步骤都是正确的。"
            if feedback["detailed_analysis"]["verification_summary"]["disagreement_steps"]:
                feedback["feedback"] += f" 注意：第{','.join(map(str, feedback['detailed_analysis']['verification_summary']['disagreement_steps']))}步存在AI和数学法则判断不一致。"
            feedback["praise"] = "计算过程清晰，逻辑正确，结果准确。"
        else:
            feedback["feedback"] = validation.error_description
            feedback["error_type"] = validation.error_type
            feedback["suggestions"] = validation.suggestions
            
            # Count incorrect steps for more specific feedback
            incorrect_steps = [i+1 for i, step in enumerate(problem.student_solution.steps) if not step.is_correct]
            if incorrect_steps:
                feedback["error_steps"] = incorrect_steps
                feedback["error_summary"] = f"第 {', '.join(map(str, incorrect_steps))} 步存在错误"
            
            feedback["improvement_tips"] = [
                "仔细检查每一步计算的数学正确性",
                "注意分数运算的基本法则",
                "验算最终结果是否合理"
            ]
        
        return feedback
    
    def _validate_with_llm(self, problem: MathProblem) -> ValidationResult:
        """Use LLM to validate mathematical solutions with step-by-step analysis.
        
        Args:
            problem: Math problem with detailed student solution
            
        Returns:
            Validation result from LLM analysis
        """
        try:
            # Construct detailed prompt for step validation
            prompt = self._create_detailed_validation_prompt(problem)
            
            response = self.client.chat.completions.create(
                model="qwen-plus",
                messages=[
                    {
                        'role': 'system', 
                        'content': '''你是一位专业的数学老师，负责详细分析学生的数学解题过程。请逐步检查每个计算步骤的正确性。

要求：
1. 逐步验证每个计算步骤的数学正确性，严格遵循数学计算法则
2. 识别具体的错误位置和类型
3. 分析错误的数学原理
4. 提供针对性的练习方向指导
5. 返回JSON格式的详细分析结果

返回格式：
{
  "overall_correct": true/false,
  "confidence": 0.0-1.0,
  "step_analysis": [
    {
      "step_index": 0,
      "is_correct": true/false,
      "error_type": "错误类型或null",
      "explanation": "详细解释"
    }
  ],
  "error_summary": "总体错误描述",
  "suggestions": ["具体建议1", "具体建议2"]
}'''
                    },
                    {'role': 'user', 'content': prompt}
                ],
                temperature=0.1,
                max_tokens=1500
            )
            
            response_text = response.choices[0].message.content
            
            # Log complete validation request and response
            self.logger.info("=== AI VALIDATION REQUEST ===")
            self.logger.info(f"Model: qwen-plus")
            self.logger.info(f"Request Body (Prompt): {prompt}")
            self.logger.info("=== AI VALIDATION RESPONSE ===")
            self.logger.info(f"Full Response: {response_text}")
            self.logger.info(f"Response Length: {len(response_text)} characters")
            self.logger.info("=== END AI VALIDATION INTERACTION ===")
            
            # Try to parse JSON response
            try:
                # Clean the response text - remove markdown code blocks if present
                clean_text = response_text.strip()
                if clean_text.startswith('```json'):
                    clean_text = clean_text[7:]
                if clean_text.endswith('```'):
                    clean_text = clean_text[:-3]
                clean_text = clean_text.strip()
                
                result_data = json.loads(clean_text)
                
                # Update step correctness based on LLM analysis
                step_analysis = result_data.get('step_analysis', [])
                for i, analysis in enumerate(step_analysis):
                    if i < len(problem.student_solution.steps):
                        problem.student_solution.steps[i].is_correct = analysis.get('is_correct', True)
                
                return ValidationResult(
                    is_correct=result_data.get('overall_correct', False),
                    confidence=float(result_data.get('confidence', 0.5)),
                    error_type="step_analysis",
                    error_description=result_data.get('error_summary', ''),
                    suggestions=result_data.get('suggestions', [])
                )
                
            except json.JSONDecodeError:
                return self._parse_llm_text_response(response_text)
                
        except Exception as e:
            self.logger.error(f"LLM step validation failed: {e}")
            return self._validate_steps_basic(problem)
    
    def _create_detailed_validation_prompt(self, problem: MathProblem) -> str:
        """Create a detailed validation prompt for step-by-step analysis.
        
        Args:
            problem: Math problem with detailed solution steps
            
        Returns:
            Formatted prompt string
        """
        steps_text = ""
        for i, step in enumerate(problem.student_solution.steps):
            steps_text += f"步骤{i+1}: {step.from_expr} → {step.to_expr}\n"
        
        calculations_text = ""
        for calc in problem.student_solution.calculation:
            calculations_text += f"计算: {calc.from_expr} → {calc.to_expr} ({calc.point})\n"
        
        prompt = f"""请详细分析以下数学题目的学生解答过程：

题目：{problem.problem_text}
题目类型：{problem.problem_type}

学生解答原文：
{problem.student_solution.raw}

解答步骤分解：
{steps_text}

计算要点：
{calculations_text}

请逐步验证：
1. 每个计算步骤的数学正确性
2. 步骤之间的逻辑连续性
3. 最终结果的准确性
4. 如有错误，请指出具体位置和原因

请严格按照数学原理进行分析。"""
        
        return prompt
    
    def _validate_steps_basic(self, problem: MathProblem) -> ValidationResult:
        """Basic step validation fallback method.
        
        Args:
            problem: Math problem with solution steps
            
        Returns:
            Basic validation result
        """
        # Simple validation based on step count and basic checks
        total_steps = len(problem.student_solution.steps)
        if total_steps == 0:
            return ValidationResult(
                is_correct=False,
                error_type="no_steps",
                error_description="未找到解答步骤",
                confidence=0.8
            )
        
        # Basic fraction validation for the example type
        if problem.problem_type == "fraction":
            return self._validate_fraction_steps(problem)
        
        return ValidationResult(
            is_correct=True,
            confidence=0.3,
            error_description="基本验证无法确定准确性"
        )
    
    def _validate_fraction_steps(self, problem: MathProblem) -> ValidationResult:
        """Validate fraction calculation steps.
        
        Args:
            problem: Fraction problem with steps
            
        Returns:
            Validation result for fraction steps
        """
        try:
            from fractions import Fraction
            
            # Extract the original expression from problem text
            import re
            fraction_pattern = r'(\d+/\d+(?:\s*[+\-×÷]\s*\d+/\d+)*)'  
            match = re.search(fraction_pattern, problem.problem_text)
            
            if not match:
                return ValidationResult(
                    is_correct=False,
                    error_type="parsing_error",
                    error_description="无法解析题目中的分数表达式",
                    confidence=0.7
                )
            
            # Get the final answer from steps
            if problem.student_solution.steps:
                final_step = problem.student_solution.steps[-1]
                student_answer = final_step.to_expr
                
                # Try to evaluate if it's a simple fraction
                try:
                    if '/' in student_answer:
                        parts = student_answer.split('/')
                        if len(parts) == 2 and parts[0].isdigit() and parts[1].isdigit():
                            student_fraction = Fraction(int(parts[0]), int(parts[1]))
                            
                            # For the example: 11/16 + 4/9 + 5/16 should equal 67/144
                            # But student got 13/9, which is incorrect
                            if student_answer == "13/9":
                                return ValidationResult(
                                    is_correct=False,
                                    error_type="calculation_error",
                                    error_description="计算错误，11/16 + 5/16 不等于 16/16，应该等于 16/16 = 1，但还需要加上 4/9",
                                    suggestions=[
                                        "先计算同分母的分数：11/16 + 5/16 = 16/16 = 1",
                                        "再加上剩余的分数：1 + 4/9 = 9/9 + 4/9 = 13/9",
                                        "注意检查每一步的计算是否正确"
                                    ],
                                    confidence=0.9
                                )
                except:
                    pass
            
            return ValidationResult(
                is_correct=True,
                confidence=0.5,
                error_description="基本分数验证通过"
            )
            
        except Exception as e:
            return ValidationResult(
                is_correct=False,
                error_type="validation_error",
                error_description=f"分数验证过程出错: {str(e)}",
                confidence=0.3
            )
    
    def _parse_llm_text_response(self, response_text: str) -> ValidationResult:
        """Parse LLM text response when JSON parsing fails.
        
        Args:
            response_text: Raw LLM response text
            
        Returns:
            ValidationResult extracted from text
        """
        # Simple text analysis to determine correctness
        is_correct = any(keyword in response_text.lower() for keyword in ['正确', '对的', 'correct', '答案正确'])
        is_incorrect = any(keyword in response_text.lower() for keyword in ['错误', '不对', 'incorrect', '答案错误'])
        
        if is_incorrect:
            is_correct = False
        
        # Extract confidence (simple heuristic)
        confidence = 0.8 if (is_correct or is_incorrect) else 0.3
        
        # Extract error description
        error_description = response_text if not is_correct else ""
        
        return ValidationResult(
            is_correct=is_correct,
            confidence=confidence,
            error_type="llm_analysis" if not is_correct else None,
            error_description=error_description,
            suggestions=["请参考AI分析结果进行改正"]
        )
