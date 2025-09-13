#!/usr/bin/env python3
"""
SSE数据拼接脚本使用示例
"""

from sse_parser import SSEDataConcatenator, process_sse_file
import json


def create_sample_sse_data():
    """创建示例SSE数据"""
    sample_data = '''data: {"choices":[{"index":0,"delta":{"role":"assistant","content":"","refusal":null},"logprobs":null,"finish_reason":null}]}

data: {"choices":[{"index":0,"delta":{"content":"{\""},"logprobs":null,"finish_reason":null}]}

data: {"choices":[{"index":0,"delta":{"content":"practice"},"logprobs":null,"finish_reason":null}]}

data: {"choices":[{"index":0,"delta":{"content":"_test"},"logprobs":null,"finish_reason":null}]}

data: {"choices":[{"index":0,"delta":{"content":"\":{\""},"logprobs":null,"finish_reason":null}]}

data: {"choices":[{"index":0,"delta":{"content":"questions"},"logprobs":null,"finish_reason":null}]}

data: {"choices":[{"index":0,"delta":{"content":"\":["},"logprobs":null,"finish_reason":null}]}

data: {"choices":[{"index":0,"delta":{"content":"{\""},"logprobs":null,"finish_reason":null}]}

data: {"choices":[{"index":0,"delta":{"content":"question"},"logprobs":null,"finish_reason":null}]}

data: {"choices":[{"index":0,"delta":{"content":"\":\"What is 2+2?\"},"logprobs":null,"finish_reason":null}]}

data: {"choices":[{"index":0,"delta":{"content":",\"answer\":\"4\"},"logprobs":null,"finish_reason":null}]}

data: {"choices":[{"index":0,"delta":{"content":"}],\"difficulty\":\"easy\"},"logprobs":null,"finish_reason":null}]}

data: {"choices":[{"index":0,"delta":{"content":""},"logprobs":null,"finish_reason":"stop"}]}

data: [DONE]'''
    
    return sample_data


def test_sse_concatenation():
    """测试SSE数据拼接功能"""
    print("=== SSE数据拼接测试 ===\n")
    
    # 创建示例数据
    sample_data = create_sample_sse_data()
    
    # 保存示例数据到文件
    with open('sample_sse.txt', 'w', encoding='utf-8') as f:
        f.write(sample_data)
    
    print("1. 原始SSE数据:")
    print(sample_data)
    print("\n" + "="*50 + "\n")
    
    # 使用拼接器处理数据
    concatenator = SSEDataConcatenator()
    result = concatenator.concatenate_sse_data(sample_data)
    
    print("2. 拼接后的完整JSON:")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    print("\n" + "="*50 + "\n")
    
    # 提取最终内容
    final_content = concatenator.extract_final_content(result)
    print("3. 提取的最终内容:")
    print(final_content)
    print("\n" + "="*50 + "\n")
    
    # 尝试解析最终内容为JSON
    try:
        parsed_content = json.loads(final_content)
        print("4. 解析后的JSON内容:")
        print(json.dumps(parsed_content, ensure_ascii=False, indent=2))
    except json.JSONDecodeError as e:
        print(f"4. 内容不是有效的JSON格式: {e}")
        print(f"   原始内容: {final_content}")
    
    return result


def test_file_processing():
    """测试文件处理功能"""
    print("\n=== 文件处理测试 ===\n")
    
    try:
        # 处理示例文件
        result = process_sse_file('sample_sse.txt', 'output_result.json')
        
        print("文件处理完成!")
        print(f"结果已保存到: output_result.json")
        
        # 显示结果摘要
        if 'choices' in result and result['choices']:
            choice = result['choices'][0]
            if 'delta' in choice and 'content' in choice['delta']:
                content_length = len(choice['delta']['content'])
                print(f"拼接的内容长度: {content_length} 字符")
        
    except Exception as e:
        print(f"文件处理出错: {e}")


def test_edge_cases():
    """测试边界情况"""
    print("\n=== 边界情况测试 ===\n")
    
    concatenator = SSEDataConcatenator()
    
    # 测试空数据
    print("1. 测试空数据:")
    empty_result = concatenator.concatenate_sse_data("")
    print(f"空数据结果: {empty_result}")
    
    # 测试无效JSON
    print("\n2. 测试无效JSON:")
    invalid_data = '''data: {"invalid": json}
data: {"choices":[{"index":0,"delta":{"content":"test"}}]}'''
    invalid_result = concatenator.concatenate_sse_data(invalid_data)
    print(f"无效JSON结果: {invalid_result}")
    
    # 测试多个choice
    print("\n3. 测试多个choice:")
    multi_choice_data = '''data: {"choices":[{"index":0,"delta":{"content":"Hello"},"finish_reason":null},{"index":1,"delta":{"content":"World"},"finish_reason":null}]}
data: {"choices":[{"index":0,"delta":{"content":" "},"finish_reason":null},{"index":1,"delta":{"content":"!"},"finish_reason":"stop"}]}'''
    multi_result = concatenator.concatenate_sse_data(multi_choice_data)
    print(f"多choice结果: {json.dumps(multi_result, ensure_ascii=False, indent=2)}")


if __name__ == "__main__":
    # 运行所有测试
    test_sse_concatenation()
    test_file_processing()
    test_edge_cases()
    
    print("\n=== 测试完成 ===")


