"""试卷ID管理系统 - 用于生成和管理试卷唯一标识"""

import json
import uuid
import hashlib
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any


class TestIDManager:
    """试卷ID管理器"""
    
    def __init__(self, database_dir: str = "database"):
        """初始化试卷ID管理器
        
        Args:
            database_dir: 数据库目录路径
        """
        self.database_dir = Path(database_dir)
        self.database_dir.mkdir(exist_ok=True)
        
        self.test_id_file = self.database_dir / "db_practics_question.json"
        self.logger = logging.getLogger(__name__)
        
        # 初始化数据库
        self._init_database()
    
    def _init_database(self):
        """初始化试卷题目关联数据库"""
        if not self.test_id_file.exists():
            initial_data = {
                "version": "1.0",
                "metadata": {
                    "description": "试卷题目关联数据库",
                    "created_at": datetime.now().isoformat(),
                    "last_updated": datetime.now().isoformat(),
                    "total_tests": 0
                },
                "test_records": [],
                "question_mappings": {}
            }
            
            with open(self.test_id_file, 'w', encoding='utf-8') as f:
                json.dump(initial_data, f, ensure_ascii=False, indent=2)
            
            self.logger.info(f"初始化试卷题目关联数据库: {self.test_id_file}")
    
    def generate_test_id(self, question_ids: List[str], test_type: str = "practice") -> str:
        """生成试卷唯一ID
        
        Args:
            question_ids: 题目ID列表
            test_type: 试卷类型 (practice/exam/homework)
            
        Returns:
            试卷唯一ID
        """
        # 生成基于内容的哈希ID
        content = f"{test_type}_{sorted(question_ids)}_{datetime.now().strftime('%Y%m%d%H%M%S')}"
        test_id = hashlib.md5(content.encode('utf-8')).hexdigest()[:12].upper()
        
        # 添加前缀以便识别
        prefix = {
            "practice": "PR",
            "exam": "EX", 
            "homework": "HW"
        }.get(test_type, "TS")
        
        full_test_id = f"{prefix}{test_id}"
        
        self.logger.info(f"生成试卷ID: {full_test_id} (类型: {test_type}, 题目数: {len(question_ids)})")
        return full_test_id
    
    def save_test_record(self, test_id: str, question_ids: List[str], 
                        test_info: Dict[str, Any]) -> bool:
        """保存试卷记录
        
        Args:
            test_id: 试卷ID
            question_ids: 题目ID列表
            test_info: 试卷信息
            
        Returns:
            是否保存成功
        """
        try:
            # 加载现有数据
            with open(self.test_id_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # 创建试卷记录
            test_record = {
                "test_id": test_id,
                "question_ids": question_ids,
                "test_info": test_info,
                "created_at": datetime.now().isoformat(),
                "total_questions": len(question_ids)
            }
            
            # 添加到记录列表
            data["test_records"].append(test_record)
            
            # 更新题目映射
            for question_id in question_ids:
                if question_id not in data["question_mappings"]:
                    data["question_mappings"][question_id] = []
                data["question_mappings"][question_id].append(test_id)
            
            # 更新元数据
            data["metadata"]["last_updated"] = datetime.now().isoformat()
            data["metadata"]["total_tests"] = len(data["test_records"])
            
            # 保存到文件
            with open(self.test_id_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            
            self.logger.info(f"试卷记录已保存: {test_id}")
            return True
            
        except Exception as e:
            self.logger.error(f"保存试卷记录失败: {e}")
            return False
    
    def get_test_by_id(self, test_id: str) -> Optional[Dict[str, Any]]:
        """根据试卷ID获取试卷信息
        
        Args:
            test_id: 试卷ID
            
        Returns:
            试卷信息字典，如果不存在则返回None
        """
        try:
            with open(self.test_id_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            for record in data["test_records"]:
                if record["test_id"] == test_id:
                    return record
            
            return None
            
        except Exception as e:
            self.logger.error(f"获取试卷信息失败: {e}")
            return None
    
    def get_questions_by_test_id(self, test_id: str) -> List[str]:
        """根据试卷ID获取题目ID列表
        
        Args:
            test_id: 试卷ID
            
        Returns:
            题目ID列表
        """
        test_record = self.get_test_by_id(test_id)
        if test_record:
            return test_record.get("question_ids", [])
        return []
    
    def get_tests_by_question_id(self, question_id: str) -> List[str]:
        """根据题目ID获取包含该题目的试卷ID列表
        
        Args:
            question_id: 题目ID
            
        Returns:
            试卷ID列表
        """
        try:
            with open(self.test_id_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            return data["question_mappings"].get(question_id, [])
            
        except Exception as e:
            self.logger.error(f"获取题目关联试卷失败: {e}")
            return []
    
    def list_all_tests(self) -> List[Dict[str, Any]]:
        """获取所有试卷记录
        
        Returns:
            试卷记录列表
        """
        try:
            with open(self.test_id_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            return data["test_records"]
            
        except Exception as e:
            self.logger.error(f"获取试卷列表失败: {e}")
            return []
    
    def search_tests(self, test_type: str = None, date_from: str = None, 
                    date_to: str = None) -> List[Dict[str, Any]]:
        """搜索试卷记录
        
        Args:
            test_type: 试卷类型过滤
            date_from: 开始日期 (YYYY-MM-DD)
            date_to: 结束日期 (YYYY-MM-DD)
            
        Returns:
            匹配的试卷记录列表
        """
        all_tests = self.list_all_tests()
        filtered_tests = []
        
        for test in all_tests:
            # 类型过滤
            if test_type and test.get("test_info", {}).get("test_type") != test_type:
                continue
            
            # 日期过滤
            if date_from or date_to:
                created_at = test.get("created_at", "")
                if created_at:
                    test_date = created_at.split("T")[0]  # 提取日期部分
                    
                    if date_from and test_date < date_from:
                        continue
                    if date_to and test_date > date_to:
                        continue
            
            filtered_tests.append(test)
        
        return filtered_tests
    
    def delete_test(self, test_id: str) -> bool:
        """删除试卷记录
        
        Args:
            test_id: 试卷ID
            
        Returns:
            是否删除成功
        """
        try:
            with open(self.test_id_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # 查找并删除试卷记录
            original_count = len(data["test_records"])
            data["test_records"] = [r for r in data["test_records"] if r["test_id"] != test_id]
            
            if len(data["test_records"]) == original_count:
                self.logger.warning(f"试卷ID不存在: {test_id}")
                return False
            
            # 更新题目映射
            for question_id, test_ids in data["question_mappings"].items():
                if test_id in test_ids:
                    data["question_mappings"][question_id].remove(test_id)
                    if not data["question_mappings"][question_id]:
                        del data["question_mappings"][question_id]
            
            # 更新元数据
            data["metadata"]["last_updated"] = datetime.now().isoformat()
            data["metadata"]["total_tests"] = len(data["test_records"])
            
            # 保存到文件
            with open(self.test_id_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            
            self.logger.info(f"试卷记录已删除: {test_id}")
            return True
            
        except Exception as e:
            self.logger.error(f"删除试卷记录失败: {e}")
            return False
    
    def get_statistics(self) -> Dict[str, Any]:
        """获取数据库统计信息
        
        Returns:
            统计信息字典
        """
        try:
            with open(self.test_id_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            test_records = data["test_records"]
            
            # 基本统计
            total_tests = len(test_records)
            
            # 类型统计
            type_stats = {}
            for test in test_records:
                test_type = test.get("test_info", {}).get("test_type", "unknown")
                type_stats[test_type] = type_stats.get(test_type, 0) + 1
            
            # 题目数量统计
            question_counts = [test.get("total_questions", 0) for test in test_records]
            avg_questions = sum(question_counts) / len(question_counts) if question_counts else 0
            
            # 最近创建的试卷
            recent_tests = sorted(test_records, key=lambda x: x.get("created_at", ""), reverse=True)[:5]
            
            return {
                "total_tests": total_tests,
                "type_distribution": type_stats,
                "average_questions_per_test": round(avg_questions, 1),
                "total_questions_mapped": len(data["question_mappings"]),
                "recent_tests": recent_tests,
                "database_info": data["metadata"]
            }
            
        except Exception as e:
            self.logger.error(f"获取统计信息失败: {e}")
            return {"error": str(e)}


def main():
    """测试试卷ID管理器"""
    # 设置日志
    logging.basicConfig(level=logging.INFO)
    
    # 创建管理器
    manager = TestIDManager()
    
    # 测试生成试卷ID
    question_ids = ["q_001", "q_002", "q_003", "q_004"]
    test_id = manager.generate_test_id(question_ids, "practice")
    print(f"生成的试卷ID: {test_id}")
    
    # 测试保存试卷记录
    test_info = {
        "test_type": "practice",
        "error_types": ["符号错误", "计算错误"],
        "choice_count": 2,
        "calculation_count": 2,
        "generated_by": "test_user"
    }
    
    success = manager.save_test_record(test_id, question_ids, test_info)
    print(f"保存试卷记录: {'成功' if success else '失败'}")
    
    # 测试获取试卷信息
    test_record = manager.get_test_by_id(test_id)
    if test_record:
        print(f"获取试卷信息: {test_record['test_id']}")
        print(f"题目数量: {test_record['total_questions']}")
    
    # 测试获取题目列表
    questions = manager.get_questions_by_test_id(test_id)
    print(f"试卷题目: {questions}")
    
    # 测试统计信息
    stats = manager.get_statistics()
    print(f"数据库统计: {stats}")


if __name__ == "__main__":
    main()
