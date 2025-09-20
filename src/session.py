import os
import datetime
import json
import uuid
from typing import List, Dict, Any


def save_session_data(session_path: str, prompt: str, questions: List[Dict[str, Any]], extra_data: Dict[str, Any] = None):
    """保存会话数据"""
    data = {
        "prompt": prompt,
        "questions": questions,
        "created_at": datetime.datetime.now().isoformat(),
        "session_id": os.path.basename(session_path)
    }
    
    # 添加额外数据
    if extra_data:
        data.update(extra_data)
    
    json_path = os.path.join(session_path, "session_data.json")
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def create_session() -> str:
    """创建以ID+时间命名的会话目录"""
    data_dir = os.getenv('DATA_DIR')
    session_id = str(uuid.uuid4())[:8]
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    session_name = f"{session_id}_{timestamp}"
    session_path = os.path.join(data_dir, session_name)
    os.makedirs(session_path, exist_ok=True)
    return session_path

def get_all_sessions() -> List[Dict[str, Any]]:
    """获取所有会话目录信息"""
    data_dir = os.getenv('DATA_DIR')
    sessions = []
    if not os.path.exists(data_dir):
        return sessions

    for item in os.listdir(data_dir):
        item_path = os.path.join(data_dir, item)
        if os.path.isdir(item_path):
            session_info = {
                "name": item,
                "path": item_path,
                "created_at": datetime.datetime.fromtimestamp(os.path.getctime(item_path)).strftime("%Y-%m-%d %H:%M:%S")
            }

            # 尝试读取会话数据
            json_path = os.path.join(item_path, "session_data.json")
            if os.path.exists(json_path):
                try:
                    with open(json_path, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        session_info.update(data)
                except:
                    pass

            sessions.append(session_info)

    # 按创建时间倒序排列
    sessions.sort(key=lambda x: x['created_at'], reverse=True)
    return sessions
