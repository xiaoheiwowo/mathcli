#!/usr/bin/env python3
"""
数学题目生成器启动脚本
"""

import os
import sys
import subprocess

# def check_dependencies():
#     """检查依赖是否安装"""
#     try:
#         import gradio
#         import reportlab
#         import openai
#         import dotenv
#         return True
#     except ImportError as e:
#         print(f"缺少依赖包: {e}")
#         return False

# def install_dependencies():
#     """安装依赖包"""
#     print("正在安装依赖包...")
#     try:
#         subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"])
#         print("依赖包安装完成！")
#         return True
#     except subprocess.CalledProcessError as e:
#         print(f"安装依赖包失败: {e}")
#         return False

# def check_env_file():
#     """检查环境变量文件"""
#     env_file = ".env"
#     if not os.path.exists(env_file):
#         print("未找到 .env 文件，请创建并配置 OpenAI API Key")
#         print("参考 .env.example 文件")
#         return False
#     return True

def main():
    """主函数"""
    print("🧮 数学题目生成器")
    print("=" * 50)
    
    # 检查依赖
    # if not check_dependencies():
    #     print("正在安装依赖包...")
    #     if not install_dependencies():
    #         print("安装失败，请手动运行: pip install -r requirements.txt")
    #         return
    #     print("依赖包安装完成！")
    
    # # 检查环境变量
    # if not check_env_file():
    #     return
    
    # 确保data目录存在
    # os.makedirs("data", exist_ok=True)
    
    # 启动应用
    print("启动数学题目生成器...")
    print("访问地址: http://localhost:7860")
    print("按 Ctrl+C 停止程序")
    print("=" * 50)
    
    # try:
    from dotenv import load_dotenv
    load_dotenv()
    from src.question.model import load_questions
    load_questions()
    from src.gradio_ui import demo
    demo.launch(
        server_name="0.0.0.0",
        server_port=7860,
        debug=True,
        share=True,
        show_error=True,
        inbrowser=True
    )
    # except KeyboardInterrupt:
    #     print("\n程序已停止")
    # except Exception as e:
    #     print(f"启动失败: {e}")

if __name__ == "__main__":
    main()
