"""MathCLI - Command-line interface for math homework grading."""

import argparse
import json
import logging
import os
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional

try:
    from .ocr_processor import OCRProcessor
    from .ai_processor import AIProcessor, MathProblem
except ImportError:
    # Handle direct execution
    from ocr_processor import OCRProcessor
    from ai_processor import AIProcessor, MathProblem


class ImageDataFilter(logging.Filter):
    """Custom filter to redact large image data from logs."""
    
    def filter(self, record):
        """Filter out or redact log messages containing large base64 image data."""
        if hasattr(record, 'msg') and record.msg:
            msg = str(record.msg)
            # Check if message contains base64 image data
            if 'data:image/' in msg and 'base64,' in msg:
                # Find and redact base64 data
                pattern = r'data:image/[^;]+;base64,[A-Za-z0-9+/=]+'
                redacted_msg = re.sub(pattern, 'data:image/[REDACTED_BASE64_IMAGE_DATA]', msg)
                record.msg = redacted_msg
            # Also check for very long strings that might be base64 data
            elif len(msg) > 1000 and re.search(r'[A-Za-z0-9+/=]{100,}', msg):
                # Truncate very long messages that likely contain base64 data
                if len(msg) > 2000:
                    record.msg = msg[:500] + '...[TRUNCATED_LARGE_DATA]...' + msg[-100:]
        return True


class MathGrader:
    """Main class for math homework grading."""
    
    def __init__(self, output_dir: str = "output"):
        """Initialize the math grader.
        
        Args:
            output_dir: Directory to save output files
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
        
        self.ocr_processor = OCRProcessor()
        self.ai_processor = AIProcessor()
        
        # Setup logging
        self.setup_logging()
    
    def setup_logging(self):
        """Setup logging configuration."""
        log_file = self.output_dir / "log.txt"
        
        # Create custom filter for image data
        image_filter = ImageDataFilter()
        
        # Configure logging with no truncation
        logging.basicConfig(
            level=logging.DEBUG,  # Changed to DEBUG for complete logging
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(log_file, encoding='utf-8'),
                logging.StreamHandler()
            ]
        )
        
        # Apply image data filter to all handlers
        for handler in logging.getLogger().handlers:
            handler.addFilter(image_filter)
        
        # Ensure no log message truncation
        logging.getLogger().handlers[0].setLevel(logging.DEBUG)
        logging.getLogger().handlers[1].setLevel(logging.INFO)  # Keep console less verbose
        
        # Reduce verbosity of HTTP and OpenAI logs to avoid large image data in logs
        logging.getLogger('openai._base_client').setLevel(logging.WARNING)
        logging.getLogger('httpcore').setLevel(logging.WARNING)
        logging.getLogger('httpx').setLevel(logging.WARNING)
        
        self.logger = logging.getLogger(__name__)
    
    def process_image(self, image_path: str) -> Dict[str, Any]:
        """Process a math homework image and generate grading results.
        
        Args:
            image_path: Path to the homework image
            
        Returns:
            Complete grading results
        """
        self.logger.info(f"开始处理图片: {image_path}")
        
        # Step 1: OCR Processing
        self.logger.info("步骤1: OCR文字识别")
        ocr_result = self.ocr_processor.extract_text(image_path)
        
        if 'error' in ocr_result:
            self.logger.error(f"OCR处理失败: {ocr_result['error']}")
            return {"error": "OCR processing failed", "details": ocr_result['error']}
        
        self.logger.info(f"OCR识别完成，置信度: {ocr_result['confidence']:.2f}%")
        self.logger.info(f"识别文本:\n{ocr_result['raw_text']}")
        
        # Step 2: Parse into structured problems
        self.logger.info("步骤2: 解析数学题目")
        problems = self.ai_processor.parse_ocr_to_problems(ocr_result['raw_text'])
        self.logger.info(f"识别到 {len(problems)} 道题目")
        
        # Step 3: Validate each problem
        self.logger.info("步骤3: 验证解答过程")
        results = []
        
        for i, problem in enumerate(problems, 1):
            self.logger.info(f"验证第 {i} 题: {problem.problem_id}")
            validation = self.ai_processor.validate_solution(problem)
            feedback = self.ai_processor.generate_feedback(problem, validation)
            
            result = {
                "problem": {
                    "id": problem.problem_id,
                    "text": problem.problem_text,
                    "type": problem.problem_type,
                    "student_solution": {
                        "raw": problem.student_solution.raw,
                        "steps": [
                            {
                                "from": step.from_expr,
                                "to": step.to_expr,
                                "is_correct": step.is_correct,
                                "llm_determine": step.llm_determine,
                                "rule_determine": step.rule_determine
                            } for step in problem.student_solution.steps
                        ],
                        "calculation": [
                            {
                                "from": calc.from_expr,
                                "to": calc.to_expr,
                                "point": calc.point,
                                "is_correct": calc.is_correct
                            } for calc in problem.student_solution.calculation
                        ]
                    }
                },
                "validation": {
                    "is_correct": validation.is_correct,
                    "confidence": validation.confidence,
                    "error_type": validation.error_type,
                    "error_description": validation.error_description,
                    "suggestions": validation.suggestions
                },
                "feedback": feedback
            }
            
            results.append(result)
            
            status = "✓ 正确" if validation.is_correct else "✗ 错误"
            self.logger.info(f"第 {i} 题结果: {status} (置信度: {validation.confidence:.2f})")
            if not validation.is_correct:
                self.logger.info(f"错误类型: {validation.error_type}")
                self.logger.info(f"错误描述: {validation.error_description}")
        
        # Step 4: Generate summary
        correct_count = sum(1 for r in results if r['validation']['is_correct'])
        total_count = len(results)
        accuracy = (correct_count / total_count * 100) if total_count > 0 else 0
        
        summary = {
            "total_problems": total_count,
            "correct_problems": correct_count,
            "accuracy_percentage": accuracy,
            "processing_timestamp": datetime.now().isoformat(),
            "image_path": image_path,
            "ocr_confidence": ocr_result['confidence']
        }
        
        self.logger.info(f"步骤4: 生成总结报告")
        self.logger.info(f"总题数: {total_count}, 正确: {correct_count}, 准确率: {accuracy:.1f}%")
        
        # Generate practice recommendations
        practice_recommendations = self._generate_practice_recommendations(results, summary)
        
        return {
            "summary": summary,
            "ocr_result": ocr_result,
            "problems": results,
            "practice_recommendations": practice_recommendations
        }
    
    def save_results(self, results: Dict[str, Any], filename: str = "result.json"):
        """Save results to JSON file.
        
        Args:
            results: Grading results
            filename: Output filename
        """
        output_file = self.output_dir / filename
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        
        self.logger.info(f"结果已保存到: {output_file}")
        
        # Also create a markdown summary
        self.create_markdown_summary(results)
    
    def create_markdown_summary(self, results: Dict[str, Any]):
        """Create a markdown summary of the results."""
        summary_file = self.output_dir / "summary.md"
        
        with open(summary_file, 'w', encoding='utf-8') as f:
            f.write("# 数学作业批改报告\n\n")
            
            summary = results['summary']
            f.write(f"**处理时间**: {summary['processing_timestamp']}\n")
            f.write(f"**图片路径**: {summary['image_path']}\n")
            f.write(f"**OCR置信度**: {summary['ocr_confidence']:.2f}%\n\n")
            
            f.write("## 总体结果\n\n")
            f.write(f"- 总题数: {summary['total_problems']}\n")
            f.write(f"- 正确题数: {summary['correct_problems']}\n")
            f.write(f"- 准确率: {summary['accuracy_percentage']:.1f}%\n\n")
            
            f.write("## 详细分析\n\n")
            
            for i, problem_result in enumerate(results['problems'], 1):
                problem = problem_result['problem']
                validation = problem_result['validation']
                
                status = "✅ 正确" if validation['is_correct'] else "❌ 错误"
                f.write(f"### 第 {i} 题 {status}\n\n")
                f.write(f"**题目**: {problem['text']}\n")
                f.write(f"**类型**: {problem['type']}\n")
                f.write(f"**置信度**: {validation['confidence']:.2f}\n\n")
                
                if problem['student_solution']:
                    f.write("**学生解答**:\n```\n")
                    # Handle both dict and string formats
                    if isinstance(problem['student_solution'], dict):
                        f.write(problem['student_solution'].get('raw', str(problem['student_solution'])))
                    else:
                        f.write(str(problem['student_solution']))
                    f.write("\n```\n\n")
                
                if not validation['is_correct']:
                    f.write(f"**错误类型**: {validation['error_type']}\n")
                    f.write(f"**错误描述**: {validation['error_description']}\n")
                    
                    if validation['suggestions']:
                        f.write("**建议**:\n")
                        for suggestion in validation['suggestions']:
                            f.write(f"- {suggestion}\n")
                    f.write("\n")
        
        self.logger.info(f"总结报告已保存到: {summary_file}")
    
    def _generate_practice_recommendations(self, results: List[Dict], summary: Dict) -> Dict[str, Any]:
        """Generate practice recommendations based on student performance."""
        total_problems = summary['total_problems']
        correct_problems = summary['correct_problems']
        accuracy = summary['accuracy_percentage']
        
        # Analyze error patterns
        error_patterns = {
            'fraction_operations': 0,
            'decimal_operations': 0,
            'mixed_operations': 0,
            'calculation_errors': 0,
            'concept_errors': 0,
            'step_logic_errors': 0
        }
        
        common_mistakes = []
        weak_areas = []
        
        for result in results:
            if not result['validation']['is_correct']:
                problem = result['problem']
                validation = result['validation']
                
                # Analyze problem type and errors
                problem_text = problem.get('text', '')
                
                # Check for fraction operations
                if '/' in problem_text:
                    error_patterns['fraction_operations'] += 1
                    
                # Check for decimal operations  
                if '.' in problem_text:
                    error_patterns['decimal_operations'] += 1
                    
                # Check for mixed operations
                if any(op in problem_text for op in ['×', '÷', '+', '-']) and len([op for op in ['×', '÷', '+', '-'] if op in problem_text]) > 1:
                    error_patterns['mixed_operations'] += 1
                
                # Analyze error description for specific issues
                error_desc = validation.get('error_description', '')
                if '数学计算错误' in error_desc:
                    error_patterns['calculation_errors'] += 1
                if '步骤' in error_desc:
                    error_patterns['step_logic_errors'] += 1
        
        # Generate recommendations based on performance
        recommendations = {
            'overall_assessment': self._get_overall_assessment(accuracy),
            'priority_areas': self._identify_priority_areas(error_patterns, total_problems),
            'specific_suggestions': self._get_specific_suggestions(error_patterns, accuracy),
            'practice_focus': self._get_practice_focus(error_patterns, accuracy),
            'next_steps': self._get_next_steps(accuracy, total_problems)
        }
        
        return recommendations
    
    def _get_overall_assessment(self, accuracy: float) -> str:
        """Get overall performance assessment."""
        if accuracy >= 90:
            return "优秀！数学基础扎实，计算准确性很高。"
        elif accuracy >= 80:
            return "良好！大部分题目都能正确解答，还有小幅提升空间。"
        elif accuracy >= 60:
            return "及格！基本概念掌握，但在计算准确性上需要加强练习。"
        else:
            return "需要加强！建议重点复习基础概念和计算方法。"
    
    def _identify_priority_areas(self, error_patterns: Dict, total_problems: int) -> List[str]:
        """Identify priority areas for improvement."""
        priority_areas = []
        
        if error_patterns['fraction_operations'] > 0:
            priority_areas.append("分数运算")
        if error_patterns['decimal_operations'] > 0:
            priority_areas.append("小数运算")
        if error_patterns['mixed_operations'] > 0:
            priority_areas.append("混合运算")
        if error_patterns['calculation_errors'] > total_problems * 0.3:
            priority_areas.append("计算准确性")
        if error_patterns['step_logic_errors'] > 0:
            priority_areas.append("解题步骤逻辑")
            
        return priority_areas if priority_areas else ["继续保持当前水平"]
    
    def _get_specific_suggestions(self, error_patterns: Dict, accuracy: float) -> List[str]:
        """Get specific practice suggestions."""
        suggestions = []
        
        if error_patterns['fraction_operations'] > 0:
            suggestions.append("加强分数的加减乘除运算练习，特别注意通分和约分")
        if error_patterns['decimal_operations'] > 0:
            suggestions.append("练习小数的四则运算，注意小数点位置的对齐")
        if error_patterns['mixed_operations'] > 0:
            suggestions.append("复习运算顺序规则，先乘除后加减，有括号先算括号内")
        if error_patterns['calculation_errors'] > 0:
            suggestions.append("提高计算准确性，建议多做基础计算练习")
        if error_patterns['step_logic_errors'] > 0:
            suggestions.append("注意解题步骤的逻辑性，每一步都要有明确的数学依据")
            
        if accuracy >= 90:
            suggestions.append("可以尝试更复杂的综合性题目来挑战自己")
        elif accuracy < 60:
            suggestions.append("建议从基础题目开始，逐步提高难度")
            
        return suggestions if suggestions else ["继续保持良好的学习习惯"]
    
    def _get_practice_focus(self, error_patterns: Dict, accuracy: float) -> Dict[str, str]:
        """Get focused practice recommendations."""
        focus = {}
        
        if error_patterns['fraction_operations'] > 0:
            focus['分数运算'] = "每天练习10道分数加减法和10道分数乘除法"
        if error_patterns['mixed_operations'] > 0:
            focus['混合运算'] = "每天练习5道含有括号的混合运算题"
        if accuracy < 80:
            focus['基础计算'] = "每天练习20道基础四则运算题，提高计算速度和准确性"
        if accuracy >= 90:
            focus['提高练习'] = "可以练习更复杂的应用题和综合性计算题"
            
        return focus
    
    def _get_next_steps(self, accuracy: float, total_problems: int) -> List[str]:
        """Get next steps recommendations."""
        steps = []
        
        if accuracy < 60:
            steps.extend([
                "1. 复习基础概念和运算法则",
                "2. 每天完成基础计算练习",
                "3. 重点关注错误题目的解题方法"
            ])
        elif accuracy < 80:
            steps.extend([
                "1. 针对错误题目进行专项练习",
                "2. 提高计算准确性和速度",
                "3. 加强混合运算的练习"
            ])
        else:
            steps.extend([
                "1. 保持当前良好的学习状态",
                "2. 可以尝试更有挑战性的题目",
                "3. 帮助同学解答疑问，巩固知识"
            ])
            
        return steps
    
    def generate_practice_test(self, error_types: List[str], choice_count: int = 2, 
                              calculation_count: int = 2) -> Dict[str, Any]:
        """根据错误类型生成练习试卷
        
        Args:
            error_types: 错误类型列表
            choice_count: 选择题数量
            calculation_count: 计算题数量
            
        Returns:
            练习试卷数据
        """
        self.logger.info(f"开始生成练习试卷，错误类型: {error_types}")
        
        try:
            # 加载题库数据
            question_db = self._load_question_database()
            if not question_db:
                return {"error": "无法加载题库数据"}
            
            # 根据错误类型筛选题目
            selected_questions = self._select_questions_by_error_types(
                question_db, error_types, choice_count, calculation_count
            )
            
            if not selected_questions:
                return {"error": "没有找到匹配的题目"}
            
            # 统计题目类型
            choice_count_actual = 0
            calculation_count_actual = 0
            
            for question in selected_questions:
                question_type = question.get('question_type', '')
                has_choices = 'choices' in question and question['choices']
                
                if question_type == 'choice' or has_choices:
                    choice_count_actual += 1
                elif question_type == 'calculation' or (not has_choices and question_type != 'choice'):
                    calculation_count_actual += 1
            
            # 生成练习试卷（移除答案和解题过程）
            practice_questions = []
            for question in selected_questions:
                # 创建不包含答案的题目副本
                practice_question = {
                    "id": question.get('id', ''),
                    "question_info": question.get('question_info', {}),
                    "question_type": question.get('question_type', ''),
                }
                
                # 只保留选择题的选项内容，不包含正确答案标识
                if 'choices' in question and question['choices']:
                    practice_choices = []
                    for choice in question['choices']:
                        practice_choices.append({
                            "id": choice.get('id', ''),
                            "content": choice.get('content', '')
                        })
                    practice_question['choices'] = practice_choices
                
                practice_questions.append(practice_question)
            
            # 生成练习试卷
            practice_test = {
                "test_info": {
                    "generated_at": datetime.now().isoformat(),
                    "error_types": error_types,
                    "total_questions": len(practice_questions),
                    "choice_questions": choice_count_actual,
                    "calculation_questions": calculation_count_actual
                },
                "questions": practice_questions,
                "instructions": self._generate_test_instructions(error_types)
            }
            
            self.logger.info(f"练习试卷生成完成，共 {len(selected_questions)} 道题目")
            return practice_test
            
        except Exception as e:
            self.logger.error(f"生成练习试卷时出错: {e}")
            return {"error": f"生成练习试卷失败: {str(e)}"}
    
    def _load_question_database(self) -> Optional[Dict[str, Any]]:
        """加载题库数据，从database目录读取"""
        try:
            database_dir = Path(__file__).parent / "database"
            all_questions = []
            
            # 定义要加载的题库文件列表
            question_bank_files = [
                "db_question_bank.json",
                "db_question_bank_choice.json"
            ]
            
            for json_file in question_bank_files:
                file_path = database_dir / json_file
                if file_path.exists():
                    self.logger.info(f"加载题库文件: {json_file}")
                    with open(file_path, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        
                        # 提取题目数据
                        questions = data.get('question_bank', {}).get('questions', [])
                        all_questions.extend(questions)
                        self.logger.info(f"从 {json_file} 加载了 {len(questions)} 道题目")
            
            if not all_questions:
                self.logger.warning("没有找到任何题目数据")
                return None
            
            # 创建统一的题库结构
            question_database = {
                "version": "1.0",
                "metadata": {
                    "description": "合并题库数据",
                    "total_questions": len(all_questions),
                    "source_files": question_bank_files
                },
                "question_bank": {
                    "questions": all_questions
                }
            }
            
            self.logger.info(f"总共加载了 {len(all_questions)} 道题目")
            return question_database
            
        except Exception as e:
            self.logger.error(f"加载题库数据失败: {e}")
            return None
    
    
    def _select_questions_by_error_types(self, question_db: Dict[str, Any], 
                                       error_types: List[str], choice_count: int, 
                                       calculation_count: int) -> List[Dict[str, Any]]:
        """根据错误类型选择题目"""
        selected_questions = []
        
        # 获取所有题目
        all_questions = question_db.get('question_bank', {}).get('questions', [])
        
        if not all_questions:
            self.logger.warning("题库中没有题目")
            return selected_questions
        
        self.logger.info(f"题库中共有 {len(all_questions)} 道题目")
        
        # 分离选择题和计算题
        choice_questions = []
        calculation_questions = []
        
        for question in all_questions:
            if self._question_matches_error_types(question, error_types):
                # 判断题目类型
                question_type = question.get('question_type', '')
                has_choices = 'choices' in question and question['choices']
                
                if question_type == 'choice' or has_choices:
                    choice_questions.append(question)
                elif question_type == 'calculation' or (not has_choices and question_type != 'choice'):
                    calculation_questions.append(question)
        
        self.logger.info(f"匹配的题目: 选择题 {len(choice_questions)} 道, 计算题 {len(calculation_questions)} 道")
        
        # 随机选择指定数量的题目
        import random
        
        if choice_questions:
            selected_choice_count = min(choice_count, len(choice_questions))
            selected_questions.extend(random.sample(choice_questions, selected_choice_count))
            self.logger.info(f"选择了 {selected_choice_count} 道选择题")
        
        if calculation_questions:
            selected_calc_count = min(calculation_count, len(calculation_questions))
            selected_questions.extend(random.sample(calculation_questions, selected_calc_count))
            self.logger.info(f"选择了 {selected_calc_count} 道计算题")
        
        return selected_questions
    
    def _question_matches_error_types(self, question: Dict[str, Any], error_types: List[str]) -> bool:
        """检查题目是否匹配指定的错误类型"""
        # 获取题目标签
        tags = question.get('question_info', {}).get('tags', [])
        if not tags:
            # 如果没有标签，尝试从题目文本中推断
            text = question.get('question_info', {}).get('text', '') or question.get('question', {}).get('text', '')
            tags = self._extract_tags_from_text(text)
        
        # 中文错误类型映射到标签
        error_type_mapping = {
            '符号错误': ['负数运算', '符号', '负号', '正负号', '有理数', '乘方'],
            '计算错误': ['计算', '运算', '四则运算', '算术'],
            '分数运算': ['分数', '分数运算'],
            '小数运算': ['小数', '小数运算'],
            '混合运算': ['混合运算', '综合运算'],
            '方程': ['方程', '一元一次方程', '解方程'],
            '乘方': ['乘方', '幂运算']
        }
        
        # 检查是否有任何错误类型匹配题目标签
        for error_type in error_types:
            if error_type in error_type_mapping:
                if any(tag in tags for tag in error_type_mapping[error_type]):
                    return True
        
        return False
    
    def _extract_tags_from_text(self, text: str) -> List[str]:
        """从题目文本中提取标签"""
        tags = []
        text_lower = text.lower()
        
        if any(word in text_lower for word in ['分数', 'fraction', '/']):
            tags.append('分数运算')
        if any(word in text_lower for word in ['小数', 'decimal', '.']):
            tags.append('小数运算')
        if any(word in text_lower for word in ['负数', 'negative', '-']):
            tags.append('负数运算')
        if any(word in text_lower for word in ['方程', 'equation', '=']):
            tags.append('方程')
        if any(word in text_lower for word in ['乘方', 'power', '^']):
            tags.append('乘方')
        
        return tags
    
    def _generate_test_instructions(self, error_types: List[str]) -> str:
        """生成测试说明"""
        # 直接使用中文错误类型作为练习重点
        focus_areas = error_types
        
        instructions = f"""
练习试卷说明：
本试卷重点练习：{', '.join(focus_areas)}

答题要求：
1. 选择题请选择正确答案
2. 计算题请写出完整的解题过程
3. 注意运算符号的正确使用
4. 仔细检查计算结果

祝学习进步！
        """.strip()
        
        return instructions
    
    def save_practice_test(self, practice_test: Dict[str, Any], filename: str = "practice_test.json"):
        """保存练习试卷到文件
        
        Args:
            practice_test: 练习试卷数据
            filename: 输出文件名
        """
        output_file = self.output_dir / filename
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(practice_test, f, ensure_ascii=False, indent=2)
        
        self.logger.info(f"练习试卷已保存到: {output_file}")
        
        # 同时创建Markdown格式的试卷
        self.create_practice_test_markdown(practice_test)
    
    def create_practice_test_markdown(self, practice_test: Dict[str, Any]):
        """创建Markdown格式的练习试卷"""
        md_file = self.output_dir / "practice_test.md"
        
        with open(md_file, 'w', encoding='utf-8') as f:
            f.write("# 数学练习试卷\n\n")
            
            # 学生信息填写区域
            f.write("## 学生信息\n\n")
            f.write("**姓名**: _________________\n\n")
            f.write("**学号**: _________________\n\n")
            f.write("**班级**: _________________\n\n")
            f.write("---\n\n")
            
            # 试卷信息
            f.write("## 试卷信息\n\n")
            test_info = practice_test['test_info']

            f.write(f"**生成时间**: {test_info['generated_at']}\n")
            f.write(f"**重点练习**: {', '.join(test_info['error_types'])}\n")
            f.write(f"**题目总数**: {test_info['total_questions']}\n")
            f.write(f"**选择题**: {test_info['choice_questions']} 道\n")
            f.write(f"**计算题**: {test_info['calculation_questions']} 道\n\n")
            
            # 说明
            f.write("## 答题说明\n\n")
            f.write(practice_test['instructions'])
            f.write("\n\n")
            
            # 题目
            f.write("## 题目\n\n")
            for i, question in enumerate(practice_test['questions'], 1):
                f.write(f"### 第 {i} 题\n\n")
                
                # 题目文本
                question_text = question.get('question_info', {}).get('text', '') or question.get('question', {}).get('text', '')
                f.write(f"**题目**: {question_text}\n\n")
                
                # 选择题选项（不显示正确答案标识）
                if 'choices' in question and question['choices']:
                    f.write("**选项**:\n")
                    for choice in question['choices']:
                        choice_id = choice.get('id', '')
                        choice_content = choice.get('content', '')
                        f.write(f"- {choice_id}. {choice_content}\n")
                    f.write("\n")
                    f.write("**答案**: (    )\n\n")
                
                # 为计算题留出答题空间
                question_type = question.get('question_type', '')
                has_choices = 'choices' in question and question['choices']
                
                if question_type == 'calculation' or (not has_choices and question_type != 'choice'):
                    f.write("**解答**: \n\n")
                    f.write("```\n")
                    f.write("请在此处写出完整的解题过程\n")
                    f.write("```\n\n")
                
                f.write("---\n\n")
        
        self.logger.info(f"Markdown试卷已保存到: {md_file}")
    
    def save_student_answer(self, answer_data: Dict[str, Any]) -> bool:
        """保存学生答题记录到数据库
        
        Args:
            answer_data: 答题数据
            
        Returns:
            是否保存成功
        """
        try:
            database_dir = Path(__file__).parent / "database"
            answer_file = database_dir / "db_answer.json"
            
            # 加载现有答题记录
            if answer_file.exists():
                with open(answer_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
            else:
                data = {
                    "version": "1.0",
                    "metadata": {"description": "学生答题记录数据库", "total_answers": 0},
                    "answer_records": [],
                    "sessions": [],
                    "statistics": {"total_sessions": 0, "total_answers": 0, "overall_accuracy": 0.0}
                }
            
            # 添加新的答题记录
            data["answer_records"].append(answer_data)
            data["metadata"]["total_answers"] = len(data["answer_records"])
            
            # 保存到文件
            with open(answer_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            
            self.logger.info(f"答题记录已保存: {answer_data.get('answer_id', 'unknown')}")
            return True
            
        except Exception as e:
            self.logger.error(f"保存答题记录失败: {e}")
            return False
    
    def get_student_errors(self, student_id: str) -> List[Dict[str, Any]]:
        """获取学生的错误答题记录
        
        Args:
            student_id: 学生ID
            
        Returns:
            错误答题记录列表
        """
        try:
            database_dir = Path(__file__).parent / "database"
            answer_file = database_dir / "db_answer.json"
            
            if not answer_file.exists():
                return []
            
            with open(answer_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # 筛选该学生的错误答题
            error_answers = []
            for record in data.get("answer_records", []):
                if (record.get("student_id") == student_id and 
                    not record.get("result", {}).get("is_correct", True)):
                    error_answers.append(record)
            
            return error_answers
            
        except Exception as e:
            self.logger.error(f"获取学生错误记录失败: {e}")
            return []
    
    def analyze_common_errors(self) -> List[Dict[str, Any]]:
        """分析常见错误类型
        
        Returns:
            常见错误分析结果
        """
        try:
            database_dir = Path(__file__).parent / "database"
            answer_file = database_dir / "db_answer.json"
            
            if not answer_file.exists():
                return []
            
            with open(answer_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # 统计错误类型
            error_counts = {}
            for record in data.get("answer_records", []):
                if not record.get("result", {}).get("is_correct", True):
                    error_analysis = record.get("error_analysis", {})
                    if error_analysis:
                        error_type = error_analysis.get("primary_error", "未知错误")
                        error_counts[error_type] = error_counts.get(error_type, 0) + 1
            
            # 转换为列表格式
            common_errors = []
            total_errors = sum(error_counts.values())
            for error_type, count in error_counts.items():
                common_errors.append({
                    "error_type": error_type,
                    "count": count,
                    "percentage": (count / total_errors * 100) if total_errors > 0 else 0
                })
            
            # 按数量排序
            common_errors.sort(key=lambda x: x["count"], reverse=True)
            return common_errors
            
        except Exception as e:
            self.logger.error(f"分析常见错误失败: {e}")
            return []
    
    def generate_question_bank_statistics(self) -> Dict[str, Any]:
        """生成题库统计信息
        
        Returns:
            统计信息字典
        """
        try:
            # 加载题库数据
            question_db = self._load_question_database()
            if not question_db:
                return {"error": "无法加载题库数据"}
            
            all_questions = question_db.get('question_bank', {}).get('questions', [])
            
            # 基本统计
            total_questions = len(all_questions)
            
            # 题型统计
            question_types = {}
            for question in all_questions:
                q_type = question.get('question_type', 'unknown')
                question_types[q_type] = question_types.get(q_type, 0) + 1
            
            # 难度统计
            difficulty_stats = {}
            for question in all_questions:
                difficulty = question.get('question_info', {}).get('difficulty', 'unknown')
                difficulty_stats[difficulty] = difficulty_stats.get(difficulty, 0) + 1
            
            # 章节统计
            chapter_stats = {}
            for question in all_questions:
                chapter = question.get('question_info', {}).get('chapter', '未知章节')
                chapter_stats[chapter] = chapter_stats.get(chapter, 0) + 1
            
            # 标签统计
            tag_stats = {}
            for question in all_questions:
                tags = question.get('question_info', {}).get('tags', [])
                for tag in tags:
                    tag_stats[tag] = tag_stats.get(tag, 0) + 1
            
            # 错误类型匹配统计
            error_type_stats = {}
            error_type_mapping = {
                '符号错误': ['负数运算', '符号', '负号', '正负号', '有理数', '乘方'],
                '计算错误': ['计算', '运算', '四则运算', '算术'],
                '分数运算': ['分数', '分数运算'],
                '小数运算': ['小数', '小数运算'],
                '混合运算': ['混合运算', '综合运算'],
                '方程': ['方程', '一元一次方程', '解方程'],
                '乘方': ['乘方', '幂运算']
            }
            
            for error_type, matching_tags in error_type_mapping.items():
                count = 0
                for question in all_questions:
                    question_tags = question.get('question_info', {}).get('tags', [])
                    if any(tag in question_tags for tag in matching_tags):
                        count += 1
                error_type_stats[error_type] = count
            
            # 预估时间统计
            total_estimated_time = sum(
                question.get('question_info', {}).get('estimated_time', 0) 
                for question in all_questions
            )
            avg_estimated_time = total_estimated_time / total_questions if total_questions > 0 else 0
            
            # 构建统计结果
            statistics = {
                "basic_info": {
                    "total_questions": total_questions,
                    "source_files": question_db.get('metadata', {}).get('source_files', []),
                    "last_updated": question_db.get('metadata', {}).get('last_updated', ''),
                    "total_estimated_time": total_estimated_time,
                    "average_estimated_time": round(avg_estimated_time, 1)
                },
                "question_types": question_types,
                "difficulty_distribution": difficulty_stats,
                "chapter_distribution": chapter_stats,
                "tag_distribution": dict(sorted(tag_stats.items(), key=lambda x: x[1], reverse=True)),
                "error_type_coverage": error_type_stats,
                "generated_at": datetime.now().isoformat()
            }
            
            self.logger.info(f"题库统计信息生成完成，共 {total_questions} 道题目")
            return statistics
            
        except Exception as e:
            self.logger.error(f"生成题库统计信息失败: {e}")
            return {"error": f"生成统计信息失败: {str(e)}"}
    
    def format_statistics_table(self, stats: Dict[str, Any]) -> str:
        """格式化统计信息为表格形式
        
        Args:
            stats: 统计信息字典
            
        Returns:
            格式化的表格字符串
        """
        if "error" in stats:
            return f"错误: {stats['error']}"
        
        output = []
        output.append("=" * 60)
        output.append("📊 数学题库统计信息")
        output.append("=" * 60)
        
        # 基本信息
        basic_info = stats.get('basic_info', {})
        output.append(f"\n📋 基本信息")
        output.append(f"总题目数: {basic_info.get('total_questions', 0)}")
        output.append(f"来源文件: {', '.join(basic_info.get('source_files', []))}")
        output.append(f"总预估时间: {basic_info.get('total_estimated_time', 0)} 分钟")
        output.append(f"平均预估时间: {basic_info.get('average_estimated_time', 0)} 分钟/题")
        
        # 题型分布
        output.append(f"\n📝 题型分布")
        question_types = stats.get('question_types', {})
        for q_type, count in question_types.items():
            percentage = (count / basic_info.get('total_questions', 1)) * 100
            output.append(f"  {q_type}: {count} 题 ({percentage:.1f}%)")
        
        # 难度分布
        output.append(f"\n🎯 难度分布")
        difficulty_stats = stats.get('difficulty_distribution', {})
        for difficulty, count in difficulty_stats.items():
            percentage = (count / basic_info.get('total_questions', 1)) * 100
            output.append(f"  {difficulty}: {count} 题 ({percentage:.1f}%)")
        
        # 章节分布
        output.append(f"\n📚 章节分布")
        chapter_stats = stats.get('chapter_distribution', {})
        for chapter, count in chapter_stats.items():
            percentage = (count / basic_info.get('total_questions', 1)) * 100
            output.append(f"  {chapter}: {count} 题 ({percentage:.1f}%)")
        
        # 标签分布（前10个）
        output.append(f"\n🏷️  标签分布 (前10个)")
        tag_stats = stats.get('tag_distribution', {})
        for i, (tag, count) in enumerate(list(tag_stats.items())[:10], 1):
            percentage = (count / basic_info.get('total_questions', 1)) * 100
            output.append(f"  {i:2d}. {tag}: {count} 题 ({percentage:.1f}%)")
        
        # 错误类型覆盖
        output.append(f"\n❌ 错误类型覆盖")
        error_type_stats = stats.get('error_type_coverage', {})
        for error_type, count in error_type_stats.items():
            percentage = (count / basic_info.get('total_questions', 1)) * 100
            output.append(f"  {error_type}: {count} 题 ({percentage:.1f}%)")
        
        output.append(f"\n⏰ 生成时间: {stats.get('generated_at', '')}")
        output.append("=" * 60)
        
        return "\n".join(output)


def main() -> None:
    """Main entry point for the CLI application."""
    parser = argparse.ArgumentParser(description="MathCLI - 数学作业批改工具")
    
    # 创建子命令
    subparsers = parser.add_subparsers(dest='command', help='可用命令')
    
    # 批改命令
    grade_parser = subparsers.add_parser('grade', help='批改数学作业')
    grade_parser.add_argument("-i", "--image", required=True, help="输入图片路径")
    grade_parser.add_argument("-o", "--output", default="output", help="输出目录 (默认: output)")
    grade_parser.add_argument("--verbose", "-v", action="store_true", help="详细输出")
    
    # 生成练习试卷命令
    practice_parser = subparsers.add_parser('practice', help='生成练习试卷')
    practice_parser.add_argument("-e", "--error-types", nargs='+', required=True, 
                                help="错误类型列表，如：符号错误 计算错误 分数运算 小数运算 混合运算")
    practice_parser.add_argument("-o", "--output", default="output", help="输出目录 (默认: output)")
    practice_parser.add_argument("--choice-count", type=int, default=2, help="选择题数量 (默认: 2)")
    practice_parser.add_argument("--calculation-count", type=int, default=2, help="计算题数量 (默认: 2)")
    practice_parser.add_argument("--verbose", "-v", action="store_true", help="详细输出")
    
    # 查看题库统计命令
    stats_parser = subparsers.add_parser('stats', help='查看题库统计信息')
    stats_parser.add_argument("--format", choices=['table', 'json'], default='table', 
                             help="输出格式 (默认: table)")
    stats_parser.add_argument("-o", "--output", help="输出到文件")
    stats_parser.add_argument("--verbose", "-v", action="store_true", help="详细输出")
    
    args = parser.parse_args()
    
    # 如果没有提供命令，显示帮助
    if not args.command:
        parser.print_help()
        return
    
    if args.command == 'grade':
        # 检查图片文件是否存在
        if not os.path.exists(args.image):
            print(f"错误: 图片文件不存在: {args.image}", file=sys.stderr)
            sys.exit(1)
    
    try:
        if args.command == 'grade':
            # Initialize grader
            grader = MathGrader(output_dir=args.output)
            
            # Process image
            results = grader.process_image(args.image)
            
            if "error" in results:
                print(f"处理失败: {results['error']}", file=sys.stderr)
                if "details" in results:
                    print(f"详细信息: {results['details']}", file=sys.stderr)
                sys.exit(1)
            
            # Save results
            grader.save_results(results)
            
            # Print summary
            summary = results['summary']
            print(f"\n批改完成!")
            print(f"总题数: {summary['total_problems']}")
            print(f"正确题数: {summary['correct_problems']}")
            print(f"准确率: {summary['accuracy_percentage']:.1f}%")
            print(f"结果已保存到: {args.output}/")
            
        elif args.command == 'practice':
            # Initialize grader for practice test generation
            grader = MathGrader(output_dir=args.output)
            
            # Generate practice test
            practice_test = grader.generate_practice_test(
                error_types=args.error_types,
                choice_count=args.choice_count,
                calculation_count=args.calculation_count
            )
            
            if "error" in practice_test:
                print(f"生成练习试卷失败: {practice_test['error']}", file=sys.stderr)
                sys.exit(1)
            
            # Save practice test
            grader.save_practice_test(practice_test)
            
            # Print summary
            print(f"\n练习试卷生成完成!")
            print(f"错误类型: {', '.join(args.error_types)}")
            print(f"选择题数量: {args.choice_count}")
            print(f"计算题数量: {args.calculation_count}")
            print(f"结果已保存到: {args.output}/")
            
        elif args.command == 'stats':
            # Initialize grader for statistics
            grader = MathGrader(output_dir=args.output if args.output else "output")
            
            # Generate statistics
            stats = grader.generate_question_bank_statistics()
            
            if "error" in stats:
                print(f"获取统计信息失败: {stats['error']}", file=sys.stderr)
                sys.exit(1)
            
            # Display statistics
            if args.format == 'json':
                output = json.dumps(stats, ensure_ascii=False, indent=2)
            else:
                output = grader.format_statistics_table(stats)
            
            if args.output:
                with open(args.output, 'w', encoding='utf-8') as f:
                    f.write(output)
                print(f"统计信息已保存到: {args.output}")
            else:
                print(output)
        
    except Exception as e:
        print(f"程序运行出错: {e}", file=sys.stderr)
        if args.verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
