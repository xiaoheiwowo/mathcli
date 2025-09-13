"""MathCLI - Command-line interface for math homework grading."""

import argparse
import json
import logging
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List

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


def main() -> None:
    """Main entry point for the CLI application."""
    parser = argparse.ArgumentParser(description="MathCLI - 数学作业批改工具")
    parser.add_argument("-i", "--image", required=True, help="输入图片路径")
    parser.add_argument("-o", "--output", default="output", help="输出目录 (默认: output)")
    parser.add_argument("--verbose", "-v", action="store_true", help="详细输出")
    
    args = parser.parse_args()
    
    # Check if image file exists
    if not os.path.exists(args.image):
        print(f"错误: 图片文件不存在: {args.image}", file=sys.stderr)
        sys.exit(1)
    
    try:
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
        
    except Exception as e:
        print(f"程序运行出错: {e}", file=sys.stderr)
        if args.verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
