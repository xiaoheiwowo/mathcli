#!/usr/bin/env python3
"""
SSE (Server-Sent Events) 数据拼接脚本
用于处理AI模型返回的流式数据，将其拼接成完整的JSON对象
"""

import json
import re
import logging
from typing import Dict, List, Optional, Any, Generator
from dataclasses import dataclass


@dataclass
class SSEEvent:
    """SSE事件数据结构"""
    data: str
    event: Optional[str] = None
    id: Optional[str] = None
    retry: Optional[int] = None


class SSEParser:
    """SSE数据解析器"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        
    def parse_sse_line(self, line: str) -> Optional[SSEEvent]:
        """解析单行SSE数据"""
        line = line.strip()
        if not line:
            return None
            
        # 解析SSE格式: field: value
        if ':' in line:
            field, value = line.split(':', 1)
            field = field.strip()
            value = value.strip()
            
            if field == 'data':
                return SSEEvent(data=value)
            elif field == 'event':
                return SSEEvent(data='', event=value)
            elif field == 'id':
                return SSEEvent(data='', id=value)
            elif field == 'retry':
                try:
                    return SSEEvent(data='', retry=int(value))
                except ValueError:
                    self.logger.warning(f"Invalid retry value: {value}")
                    return None
        else:
            # 可能是纯数据行
            return SSEEvent(data=line)
    
    def parse_sse_stream(self, stream: str) -> Generator[SSEEvent, None, None]:
        """解析SSE流数据"""
        lines = stream.split('\n')
        current_event = SSEEvent(data='')
        
        for line in lines:
            if not line.strip():
                # 空行表示事件结束
                if current_event.data:
                    yield current_event
                    current_event = SSEEvent(data='')
                continue
                
            event = self.parse_sse_line(line)
            if event:
                if event.data:
                    current_event.data = event.data
                if event.event:
                    current_event.event = event.event
                if event.id:
                    current_event.id = event.id
                if event.retry:
                    current_event.retry = event.retry


class SSEDataConcatenator:
    """SSE数据拼接器"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.parser = SSEParser()
        
    def extract_content_from_choice(self, choice_data: Dict[str, Any]) -> str:
        """从choice数据中提取content内容"""
        try:
            if 'delta' in choice_data and 'content' in choice_data['delta']:
                return choice_data['delta']['content']
            return ""
        except (KeyError, TypeError) as e:
            self.logger.warning(f"Error extracting content from choice: {e}")
            return ""
    
    def concatenate_sse_data(self, sse_stream: str) -> Dict[str, Any]:
        """拼接SSE流数据为完整JSON对象"""
        events = list(self.parser.parse_sse_stream(sse_stream))
        
        # 存储所有choice的增量内容
        choice_contents = {}
        complete_data = {}
        
        for event in events:
            if not event.data:
                continue
                
            try:
                # 解析JSON数据
                data = json.loads(event.data)
                
                # 处理choices数组
                if 'choices' in data and isinstance(data['choices'], list):
                    for choice in data['choices']:
                        if isinstance(choice, dict) and 'index' in choice:
                            index = choice['index']
                            
                            # 初始化choice数据
                            if index not in choice_contents:
                                choice_contents[index] = {
                                    'index': index,
                                    'delta': {},
                                    'logprobs': None,
                                    'finish_reason': None
                                }
                            
                            # 合并delta内容
                            if 'delta' in choice and isinstance(choice['delta'], dict):
                                for key, value in choice['delta'].items():
                                    if key == 'content':
                                        # 拼接content内容
                                        if 'content' not in choice_contents[index]['delta']:
                                            choice_contents[index]['delta']['content'] = ""
                                        choice_contents[index]['delta']['content'] += value
                                    else:
                                        # 直接赋值其他字段
                                        choice_contents[index]['delta'][key] = value
                            
                            # 更新其他字段
                            if 'logprobs' in choice:
                                choice_contents[index]['logprobs'] = choice['logprobs']
                            if 'finish_reason' in choice:
                                choice_contents[index]['finish_reason'] = choice['finish_reason']
                
                # 合并其他顶级字段
                for key, value in data.items():
                    if key != 'choices':
                        complete_data[key] = value
                        
            except json.JSONDecodeError as e:
                self.logger.warning(f"Failed to parse JSON data: {event.data[:100]}... Error: {e}")
                continue
        
        # 构建最终结果
        if choice_contents:
            complete_data['choices'] = list(choice_contents.values())
        
        return complete_data
    
    def extract_final_content(self, concatenated_data: Dict[str, Any]) -> str:
        """从拼接后的数据中提取最终内容"""
        try:
            if 'choices' in concatenated_data and concatenated_data['choices']:
                choice = concatenated_data['choices'][0]
                if 'delta' in choice and 'content' in choice['delta']:
                    return choice['delta']['content']
            return ""
        except (KeyError, TypeError, IndexError) as e:
            self.logger.warning(f"Error extracting final content: {e}")
            return ""


def process_sse_file(input_file: str, output_file: Optional[str] = None) -> Dict[str, Any]:
    """处理SSE文件并返回拼接结果"""
    concatenator = SSEDataConcatenator()
    
    # 读取输入文件
    with open(input_file, 'r', encoding='utf-8') as f:
        sse_content = f.read()
    
    # 拼接数据
    result = concatenator.concatenate_sse_data(sse_content)
    
    # 保存结果
    if output_file:
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        print(f"结果已保存到: {output_file}")
    
    return result


def main():
    """主函数 - 命令行接口"""
    import argparse
    
    parser = argparse.ArgumentParser(description='SSE数据拼接脚本')
    parser.add_argument('input_file', help='输入SSE文件路径')
    parser.add_argument('-o', '--output', help='输出JSON文件路径')
    parser.add_argument('-v', '--verbose', action='store_true', help='详细输出')
    
    args = parser.parse_args()
    
    # 设置日志级别
    if args.verbose:
        logging.basicConfig(level=logging.DEBUG)
    else:
        logging.basicConfig(level=logging.INFO)
    
    try:
        result = process_sse_file(args.input_file, args.output)
        
        # 提取并显示最终内容
        concatenator = SSEDataConcatenator()
        final_content = concatenator.extract_final_content(result)
        
        print("\n=== 拼接结果 ===")
        print(json.dumps(result, ensure_ascii=False, indent=2))
        
        if final_content:
            print(f"\n=== 最终内容 ===")
            print(final_content)
            
    except FileNotFoundError:
        print(f"错误: 找不到文件 {args.input_file}")
    except Exception as e:
        print(f"错误: {e}")


if __name__ == "__main__":
    main()
