# SSE 数据拼接脚本

这个脚本用于处理 Server-Sent Events (SSE) 格式的流式数据，特别是AI模型返回的增量内容，将其拼接成完整的JSON对象。

## 功能特性

- 解析SSE格式的流式数据
- 自动拼接增量内容为完整JSON
- 支持多个choice的并行处理
- 提供命令行接口和编程接口
- 包含完整的错误处理机制

## 文件说明

- `sse_parser.py` - 主要的SSE解析和拼接脚本
- `sse_example.py` - 使用示例和测试脚本
- `SSE_README.md` - 本说明文档

## 使用方法

### 1. 命令行使用

```bash
# 基本用法
python sse_parser.py input_file.txt

# 指定输出文件
python sse_parser.py input_file.txt -o output.json

# 详细输出
python sse_parser.py input_file.txt -v
```

### 2. 编程接口使用

```python
from sse_parser import SSEDataConcatenator, process_sse_file

# 方法1: 直接处理字符串
concatenator = SSEDataConcatenator()
result = concatenator.concatenate_sse_data(sse_stream_string)

# 方法2: 处理文件
result = process_sse_file('input.txt', 'output.json')

# 提取最终内容
final_content = concatenator.extract_final_content(result)
```

### 3. 运行示例

```bash
# 运行测试示例
python sse_example.py
```

## 输入数据格式

脚本支持标准的SSE格式，例如：

```
data: {"choices":[{"index":0,"delta":{"role":"assistant","content":"","refusal":null},"logprobs":null,"finish_reason":null}]}

data: {"choices":[{"index":0,"delta":{"content":"{\""},"logprobs":null,"finish_reason":null}]}

data: {"choices":[{"index":0,"delta":{"content":"practice"},"logprobs":null,"finish_reason":null}]}

data: [DONE]
```

## 输出格式

拼接后的数据将包含完整的JSON结构，所有增量内容会被合并：

```json
{
  "choices": [
    {
      "index": 0,
      "delta": {
        "role": "assistant",
        "content": "{\"practice_test\":{\"questions\":[{\"question\":\"What is 2+2?\",\"answer\":\"4\"}],\"difficulty\":\"easy\"}}"
      },
      "logprobs": null,
      "finish_reason": "stop"
    }
  ]
}
```

## 错误处理

脚本包含完善的错误处理机制：

- JSON解析错误会被记录但不会中断处理
- 无效的SSE格式会被跳过
- 缺失的字段会有默认值处理
- 详细的日志记录帮助调试

## 依赖项

- Python 3.6+
- 标准库：json, re, logging, typing, dataclasses

无需安装额外的第三方包。


