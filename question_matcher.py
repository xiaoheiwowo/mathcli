"""智能题目匹配模块 - 用于OCR识别题目与题库题目的智能匹配"""

import re
import json
import logging
from typing import Dict, List, Optional, Tuple, Any
from difflib import SequenceMatcher
from pathlib import Path
try:
    import jieba
    import jieba.analyse
    JIEBA_AVAILABLE = True
except ImportError:
    JIEBA_AVAILABLE = False
    print("警告: jieba模块未安装，关键词匹配功能将不可用")

from openai import OpenAI
import os


class QuestionMatcher:
    """智能题目匹配器"""
    
    def __init__(self):
        """初始化题目匹配器"""
        self.logger = logging.getLogger(__name__)
        
        # 初始化中文分词
        if JIEBA_AVAILABLE:
            jieba.initialize()
        else:
            self.logger.warning("jieba模块不可用，关键词匹配功能将被禁用")
        
        # 初始化AI客户端
        try:
            self.ai_client = OpenAI(
                api_key=os.getenv("DASHSCOPE_API_KEY"),
                base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
            )
            self.use_ai_matching = True
            self.logger.info("AI题目匹配客户端初始化成功")
        except Exception as e:
            self.logger.warning(f"AI客户端初始化失败: {e}. 使用传统匹配算法")
            self.ai_client = None
            self.use_ai_matching = False
        
        # 加载题库数据
        self.question_bank = self._load_question_bank()
        
        # 数学符号标准化映射
        self.symbol_mapping = {
            '×': '*', '÷': '/', '＋': '+', '－': '-',
            '（': '(', '）': ')', '【': '[', '】': ']',
            '｛': '{', '｝': '}', '，': ',', '。': '.',
            '：': ':', '；': ';', '？': '?', '！': '!',
            '＝': '=', '＜': '<', '＞': '>', '≤': '<=', '≥': '>=',
            '≠': '!=', '±': '±', '∞': '∞', '√': '√',
            '²': '^2', '³': '^3', '⁴': '^4', '⁵': '^5',
            '¹': '^1', '⁰': '^0', '⁻': '^-', '⁺': '^+'
        }
    
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
    
    def find_matching_question(self, ocr_text: str, question_type: str = None) -> Optional[Dict[str, Any]]:
        """查找匹配的题目
        
        Args:
            ocr_text: OCR识别的题目文本
            question_type: 题目类型 (choice/calculation)
            
        Returns:
            匹配的题目信息，包含匹配度和匹配方法
        """
        if not self.question_bank:
            self.logger.warning("题库为空，无法进行匹配")
            return None
        
        # 预处理OCR文本
        processed_text = self._preprocess_text(ocr_text)
        
        # 多级匹配策略
        match_results = []
        
        # 1. 精确匹配
        exact_match = self._exact_match(processed_text, question_type)
        if exact_match:
            match_results.append((exact_match, 1.0, "exact"))
        
        # 2. 模糊匹配
        fuzzy_matches = self._fuzzy_match(processed_text, question_type)
        match_results.extend(fuzzy_matches)
        
        # 3. 关键词匹配
        keyword_matches = self._keyword_match(processed_text, question_type)
        match_results.extend(keyword_matches)
        
        # 4. 数学表达式匹配
        expression_matches = self._expression_match(processed_text, question_type)
        match_results.extend(expression_matches)
        
        # 5. AI语义匹配（如果可用）
        if self.use_ai_matching:
            ai_matches = self._ai_semantic_match(processed_text, question_type)
            match_results.extend(ai_matches)
        
        # 选择最佳匹配
        if match_results:
            # 按匹配度排序
            match_results.sort(key=lambda x: x[1], reverse=True)
            best_match = match_results[0]
            
            self.logger.info(f"找到最佳匹配: {best_match[0]['id']}, 匹配度: {best_match[1]:.3f}, 方法: {best_match[2]}")
            
            return {
                "question": best_match[0],
                "similarity": best_match[1],
                "method": best_match[2],
                "all_matches": match_results[:5]  # 返回前5个匹配结果
            }
        
        self.logger.warning(f"未找到匹配的题目: {processed_text[:100]}...")
        return None
    
    def _preprocess_text(self, text: str) -> str:
        """预处理文本，标准化格式"""
        if not text:
            return ""
        
        # 移除多余空白
        text = re.sub(r'\s+', ' ', text.strip())
        
        # 标准化数学符号
        for old, new in self.symbol_mapping.items():
            text = text.replace(old, new)
        
        # 移除题目编号
        text = re.sub(r'^\d+[\.\)]\s*', '', text)
        
        # 移除多余标点
        text = re.sub(r'[，。；：！？]', '', text)
        
        return text.strip()
    
    def _exact_match(self, text: str, question_type: str = None) -> Optional[Dict[str, Any]]:
        """精确匹配"""
        for qid, question in self.question_bank.items():
            if question_type and question.get('question_type') != question_type:
                continue
            
            question_text = question.get('question_info', {}).get('text', '')
            if not question_text:
                continue
            
            processed_question = self._preprocess_text(question_text)
            
            if text == processed_question:
                return question
        
        return None
    
    def _fuzzy_match(self, text: str, question_type: str = None, threshold: float = 0.8) -> List[Tuple[Dict[str, Any], float, str]]:
        """模糊匹配"""
        matches = []
        
        for qid, question in self.question_bank.items():
            if question_type and question.get('question_type') != question_type:
                continue
            
            question_text = question.get('question_info', {}).get('text', '')
            if not question_text:
                continue
            
            processed_question = self._preprocess_text(question_text)
            
            # 计算相似度
            similarity = SequenceMatcher(None, text, processed_question).ratio()
            
            if similarity >= threshold:
                matches.append((question, similarity, "fuzzy"))
        
        return matches
    
    def _keyword_match(self, text: str, question_type: str = None, threshold: float = 0.6) -> List[Tuple[Dict[str, Any], float, str]]:
        """关键词匹配"""
        matches = []
        
        if not JIEBA_AVAILABLE:
            return matches
        
        # 提取关键词
        text_keywords = set(jieba.analyse.extract_tags(text, topK=10))
        
        for qid, question in self.question_bank.items():
            if question_type and question.get('question_type') != question_type:
                continue
            
            question_text = question.get('question_info', {}).get('text', '')
            if not question_text:
                continue
            
            # 提取题目关键词
            question_keywords = set(jieba.analyse.extract_tags(question_text, topK=10))
            
            # 计算关键词重叠度
            if text_keywords and question_keywords:
                overlap = len(text_keywords & question_keywords)
                union = len(text_keywords | question_keywords)
                similarity = overlap / union if union > 0 else 0
                
                if similarity >= threshold:
                    matches.append((question, similarity, "keyword"))
        
        return matches
    
    def _expression_match(self, text: str, question_type: str = None, threshold: float = 0.7) -> List[Tuple[Dict[str, Any], float, str]]:
        """数学表达式匹配"""
        matches = []
        
        # 提取数学表达式
        text_expressions = self._extract_math_expressions(text)
        
        for qid, question in self.question_bank.items():
            if question_type and question.get('question_type') != question_type:
                continue
            
            question_text = question.get('question_info', {}).get('text', '')
            if not question_text:
                continue
            
            question_expressions = self._extract_math_expressions(question_text)
            
            if text_expressions and question_expressions:
                # 计算表达式相似度
                similarity = self._calculate_expression_similarity(text_expressions, question_expressions)
                
                if similarity >= threshold:
                    matches.append((question, similarity, "expression"))
        
        return matches
    
    def _extract_math_expressions(self, text: str) -> List[str]:
        """提取数学表达式"""
        expressions = []
        
        # 匹配各种数学表达式模式
        patterns = [
            r'[+-]?\d+(?:\.\d+)?\s*[+\-*/]\s*[+-]?\d+(?:\.\d+)?',  # 基本运算
            r'\([^)]+\)',  # 括号表达式
            r'[+-]?\d+(?:\.\d+)?\s*[+\-*/]\s*\([^)]+\)',  # 数与括号的运算
            r'\([^)]+\)\s*[+\-*/]\s*[+-]?\d+(?:\.\d+)?',  # 括号与数的运算
            r'[+-]?\d+(?:\.\d+)?\^[+-]?\d+',  # 乘方
            r'√[+-]?\d+(?:\.\d+)?',  # 根号
            r'[+-]?\d+(?:\.\d+)?/[+-]?\d+(?:\.\d+)?',  # 分数
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, text)
            expressions.extend(matches)
        
        return list(set(expressions))  # 去重
    
    def _calculate_expression_similarity(self, expr1: List[str], expr2: List[str]) -> float:
        """计算数学表达式相似度"""
        if not expr1 or not expr2:
            return 0.0
        
        # 标准化表达式
        norm_expr1 = [self._normalize_expression(e) for e in expr1]
        norm_expr2 = [self._normalize_expression(e) for e in expr2]
        
        # 计算集合相似度
        set1 = set(norm_expr1)
        set2 = set(norm_expr2)
        
        if not set1 or not set2:
            return 0.0
        
        intersection = len(set1 & set2)
        union = len(set1 | set2)
        
        return intersection / union if union > 0 else 0.0
    
    def _normalize_expression(self, expr: str) -> str:
        """标准化数学表达式"""
        # 移除空格
        expr = expr.replace(' ', '')
        
        # 标准化符号
        for old, new in self.symbol_mapping.items():
            expr = expr.replace(old, new)
        
        # 标准化乘方符号
        expr = re.sub(r'\^(\d+)', r'^\1', expr)
        
        return expr
    
    def _ai_semantic_match(self, text: str, question_type: str = None, threshold: float = 0.7) -> List[Tuple[Dict[str, Any], float, str]]:
        """AI语义匹配"""
        if not self.ai_client:
            return []
        
        matches = []
        
        try:
            # 构建候选题目列表
            candidates = []
            for qid, question in self.question_bank.items():
                if question_type and question.get('question_type') != question_type:
                    continue
                
                question_text = question.get('question_info', {}).get('text', '')
                if question_text:
                    candidates.append({
                        'id': qid,
                        'text': question_text,
                        'question': question
                    })
            
            if not candidates:
                return matches
            
            # 使用AI进行语义匹配
            prompt = f"""请分析以下OCR识别的题目与题库中的题目是否相似。

OCR识别的题目：
{text}

题库题目：
{json.dumps([{'id': c['id'], 'text': c['text']} for c in candidates], ensure_ascii=False, indent=2)}

请返回JSON格式的匹配结果，包含每个题目的相似度分数（0-1之间）：
{{
  "matches": [
    {{"id": "题目ID", "similarity": 0.85, "reason": "匹配原因"}},
    ...
  ]
}}

要求：
1. 考虑数学表达式的等价性（如 2+3 和 3+2）
2. 忽略题目编号和格式差异
3. 重点关注数学内容和解题思路
4. 相似度分数要准确反映题目相似程度"""

            response = self.ai_client.chat.completions.create(
                model="qwen-plus",
                messages=[
                    {
                        'role': 'system',
                        'content': '你是一位专业的数学老师，擅长分析数学题目的相似性。请仔细比较题目内容并给出准确的相似度评分。'
                    },
                    {'role': 'user', 'content': prompt}
                ],
                temperature=0.1,
                max_tokens=2000
            )
            
            result_text = response.choices[0].message.content
            
            # 解析AI返回的结果
            try:
                result = json.loads(result_text)
                for match in result.get('matches', []):
                    similarity = match.get('similarity', 0)
                    if similarity >= threshold:
                        qid = match.get('id')
                        question = next((c['question'] for c in candidates if c['id'] == qid), None)
                        if question:
                            matches.append((question, similarity, "ai_semantic"))
            except json.JSONDecodeError:
                self.logger.warning("AI返回结果解析失败")
                
        except Exception as e:
            self.logger.error(f"AI语义匹配失败: {e}")
        
        return matches
    
    def get_question_by_id(self, question_id: str) -> Optional[Dict[str, Any]]:
        """根据ID获取题目"""
        return self.question_bank.get(question_id)
    
    def search_questions(self, query: str, question_type: str = None, limit: int = 10) -> List[Dict[str, Any]]:
        """搜索题目"""
        results = []
        
        for qid, question in self.question_bank.items():
            if question_type and question.get('question_type') != question_type:
                continue
            
            question_text = question.get('question_info', {}).get('text', '')
            if query.lower() in question_text.lower():
                results.append(question)
                
                if len(results) >= limit:
                    break
        
        return results
