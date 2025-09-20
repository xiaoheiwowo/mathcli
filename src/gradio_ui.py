import gradio as gr
import os
import datetime
import json

from src.generator import PracticePaperGenerator
from src.question.model import questions
from src.session import *


def generate_math_questions_interface(prompt):
    global current_session_path
    
    if not prompt.strip():
        return "请输入提示词", None, None, []

    try:
        # 创建会话目录
        session_path = create_session()
        current_session_path = session_path

        # 获取题目数据
        questions_data = questions.get("questions", [])

        # 保存会话数据
        save_session_data(session_path, prompt, questions_data)

        # 生成PDF
        pdf_path = PracticePaperGenerator().generate_pdf(questions_data, session_path)

        # 格式化显示结果
        result_text = f"成功生成 {len(questions_data)} 道数学题目！\n\n"
        result_text += f"提示词: {prompt}\n\n"

        for i, q in enumerate(questions_data, 1):
            result_text += f"题目 {i}:\n{q.get('question', '')}\n"
            if q.get("solution"):
                result_text += f"解答: {q['solution']}\n"
            if q.get("answer"):
                result_text += f"答案: {q['answer']}\n"
            result_text += "\n" + "=" * 50 + "\n\n"

        return result_text, pdf_path, f"会话目录: {os.path.basename(session_path)}", []

    except Exception as e:
        return f"生成题目时出错: {str(e)}", None, None, []


def get_sessions_list():
    sessions = get_all_sessions()
    if not sessions:
        return "暂无会话记录"

    result = "所有会话记录:\n\n"
    for session in sessions:
        result += f"📁 {session['name']}\n"
        result += f"   创建时间: {session['created_at']}\n"
        if "prompt" in session:
            result += f"   提示词: {session['prompt'][:50]}...\n"
        result += f"   路径: {session['path']}\n\n"

    return result


def refresh_sessions():
    """刷新会话列表"""
    return get_sessions_list()


def get_sessions_for_dropdown():
    """获取会话列表供下拉选择使用"""
    sessions = get_all_sessions()
    if not sessions:
        return gr.Dropdown(choices=[], value=None, label="历史会话")

    choices = []
    for session in sessions:
        display_name = f"### {session['name']} - {session.get('prompt', '无提示词')}"
        choices.append((display_name, session["path"]))

    return gr.Dropdown(
        choices=choices,
        value=None,
        label="选择历史会话",
    )


def load_session_data(session_path):
    """加载指定会话的数据"""
    global current_session_path
    
    if not session_path:
        return "", "", None, "", [], ""

    try:
        # 更新当前会话路径
        current_session_path = session_path
        
        json_path = os.path.join(session_path, "session_data.json")
        if not os.path.exists(json_path):
            return "会话数据不存在", "", None, "", [], ""

        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        # 恢复生成题目的数据
        prompt = data.get("prompt", "")
        questions_data = data.get("questions", [])

        # 格式化题目显示
        if questions_data:
            result_text = f"恢复的题目数据 ({len(questions_data)} 道题):\n\n"
            for i, q in enumerate(questions_data, 1):
                result_text += f"题目 {i}:\n{q.get('question', '')}\n"
                if q.get("solution"):
                    result_text += f"解答: {q['solution']}\n"
                if q.get("answer"):
                    result_text += f"答案: {q['answer']}\n"
                result_text += "\n" + "=" * 50 + "\n\n"
        else:
            result_text = "该会话没有题目数据"

        # 检查是否有PDF文件
        pdf_files = [f for f in os.listdir(session_path) if f.endswith(".pdf")]
        pdf_path = os.path.join(session_path, pdf_files[0]) if pdf_files else None

        # 恢复批改数据
        grading_data = data.get("type") == "grading"
        if grading_data:
            grading_report = f"恢复的批改数据:\n"
            grading_report += f"批改时间: {data.get('created_at', '未知')}\n"
            grading_report += f"图片数量: {data.get('images_count', 0)}\n"
            grading_report += f"总题数: {data.get('total_questions', 0)}\n"
            grading_report += f"正确数: {data.get('correct_answers', 0)}\n"
            grading_report += f"正确率: {data.get('overall_accuracy', 0)}%\n\n"

            results = data.get("results", [])
            for result in results:
                grading_report += f"👤 {result.get('student', '未知学生')}\n"
                grading_report += f"   得分: {result.get('score', 0)}%\n"
                grading_report += f"   正确: {result.get('correct_answers', 0)}/{result.get('total_questions', 0)}\n\n"
        else:
            grading_report = "该会话不是批改数据"

        # 加载 session 中的图片
        session_images = get_session_images(session_path)

        session_info = f"会话: {os.path.basename(session_path)}\n创建时间: {data.get('created_at', '未知')}"

        return prompt, result_text, pdf_path, grading_report, session_images, session_info

    except Exception as e:
        return f"加载会话数据时出错: {str(e)}", "", None, "", [], ""


def grade_student_answers(images, reference_answers=None):
    """批改学生答题结果"""
    if not images:
        return "请上传学生答题图片", None

    try:
        # 创建批改会话目录
        session_path = create_session()

        # 模拟批改结果（这里需要根据实际需求实现）
        grading_results = []
        total_questions = 0
        correct_answers = 0

        for i, image in enumerate(images, 1):
            # 这里应该调用实际的图片识别和批改逻辑
            # 目前使用模拟数据
            student_name = f"学生{i}"
            questions_count = 5  # 假设每张图片有5道题
            correct_count = 3 + (i % 3)  # 模拟正确题数

            grading_results.append(
                {
                    "student": student_name,
                    "total_questions": questions_count,
                    "correct_answers": correct_count,
                    "score": round(correct_count / questions_count * 100, 1),
                    "image_path": image,
                }
            )

            total_questions += questions_count
            correct_answers += correct_count

        # 生成批改报告
        report = f"📊 批改报告\n"
        report += f"{'='*50}\n\n"
        report += f"批改时间: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        report += f"批改图片数量: {len(images)}\n"
        report += f"总题数: {total_questions}\n"
        report += f"总正确数: {correct_answers}\n"
        report += f"整体正确率: {round(correct_answers/total_questions*100, 1)}%\n\n"

        report += f"📝 详细结果:\n"
        report += f"{'='*50}\n"
        for result in grading_results:
            report += f"👤 {result['student']}\n"
            report += f"   正确题数: {result['correct_answers']}/{result['total_questions']}\n"
            report += f"   得分: {result['score']}%\n"
            report += f"   图片: {os.path.basename(result['image_path'])}\n\n"

        # 保存批改结果
        grading_data = {
            "type": "grading",
            "images_count": len(images),
            "total_questions": total_questions,
            "correct_answers": correct_answers,
            "overall_accuracy": round(correct_answers / total_questions * 100, 1),
            "results": grading_results,
            "created_at": datetime.datetime.now().isoformat(),
        }

        save_session_data(session_path, "图片批改", [], grading_data)

        return report, f"批改会话: {os.path.basename(session_path)}"

    except Exception as e:
        return f"批改过程中出错: {str(e)}", None


# 移除全局变量，改为 session 级别存储
# image_library = []

# 全局变量跟踪当前会话
current_session_path = None


def add_image_to_library(image, session_path=None):
    """添加图片到图片库"""
    if image is None:
        return [], None, "请先选择或拍摄图片"

    if not session_path:
        return [], None, "请先创建或选择会话"

    # 创建 images 子目录
    images_dir = os.path.join(session_path, "images")
    os.makedirs(images_dir, exist_ok=True)

    # 保存图片到 session 目录
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]
    image_filename = f"image_{timestamp}.jpg"
    image_path = os.path.join(images_dir, image_filename)
    
    # 保存图片
    image.save(image_path, "JPEG")
    
    # 获取当前 session 中的所有图片
    current_images = get_session_images(session_path)

    return current_images, None, f"已添加图片，当前共有 {len(current_images)} 张图片"


def clear_image_library(session_path=None):
    """清空图片库"""
    if not session_path:
        return [], "请先创建或选择会话"
    
    # 清空 images 目录
    images_dir = os.path.join(session_path, "images")
    if os.path.exists(images_dir):
        for file in os.listdir(images_dir):
            file_path = os.path.join(images_dir, file)
            if os.path.isfile(file_path):
                os.remove(file_path)
    
    return [], "图片库已清空"


def get_session_images(session_path):
    """获取指定 session 中的所有图片"""
    if not session_path:
        return []
    
    images_dir = os.path.join(session_path, "images")
    if not os.path.exists(images_dir):
        return []
    
    image_files = []
    for file in os.listdir(images_dir):
        if file.lower().endswith(('.jpg', '.jpeg', '.png', '.gif', '.bmp')):
            image_files.append(os.path.join(images_dir, file))
    
    # 按文件名排序
    image_files.sort()
    return image_files


def add_image_wrapper(image):
    """包装函数，使用当前会话路径添加图片"""
    global current_session_path
    return add_image_to_library(image, current_session_path)


def clear_image_wrapper():
    """包装函数，使用当前会话路径清空图片"""
    global current_session_path
    return clear_image_library(current_session_path)


def grade_all_images_wrapper():
    """包装函数，使用当前会话路径批改图片"""
    global current_session_path
    return grade_all_images(current_session_path)


def grade_all_images(session_path=None):
    """批改图片库中的所有图片"""
    if not session_path:
        return "请先创建或选择会话", None

    # 获取当前 session 中的所有图片
    image_paths = get_session_images(session_path)
    
    if not image_paths:
        return "图片库为空，请先添加图片", None

    try:
        # 调用批改函数，直接使用保存的图片路径
        report, session_info = grade_student_answers(image_paths)

        return report, session_info

    except Exception as e:
        return f"批改过程中出错: {str(e)}", None


# 创建Gradio界面
with gr.Blocks(title="AIMath Helper", theme=gr.themes.Soft()) as demo:
    gr.Markdown("# 🧮 AIMath Helper")

    with gr.Row():
        session_dropdown = gr.Dropdown(
            choices=[], value=None, label="选择历史会话", scale=4
        )
        refresh_sessions_btn = gr.Button("刷新会话列表", variant="secondary", scale=1)

    current_session_info = gr.Textbox(label="当前会话信息", interactive=False, lines=2)

    # 分隔线
    gr.Markdown("---")

    prompt_input = gr.Textbox(
        label="提示词",
        placeholder="输入提示词，将为您生成数学题目并输出 PDF 文件, 例如：生成5道关于二次方程的题目，难度中等",
        lines=3,
    )

    generate_btn = gr.Button("生成题目", variant="primary")

    result_output = gr.Textbox(label="生成的题目", lines=20, interactive=False)

    pdf_output = gr.File(label="PDF 文件", file_count="single")

    gr.Markdown("---")

    image_input = gr.Image(
        label="上传或拍摄图片",
        sources=["webcam", "upload", "clipboard"],
        type="pil",
        height=400,
    )

    images_gallery = gr.Gallery(
        label="已保存的图片",
        show_label=True,
        elem_id="images_gallery",
        columns=4,
        rows=3,
        height=200,
        object_fit="cover",
    )

    clear_images_btn = gr.Button("清空图片", variant="secondary")

    grade_btn = gr.Button("批改", variant="primary")

    grading_report = gr.Textbox(label="批改报告", lines=25, interactive=False)

    regenerate_btn = gr.Button("重新生成题目", variant="primary")

    # 事件绑定
    generate_btn.click(
        fn=generate_math_questions_interface,
        inputs=[prompt_input],
        outputs=[result_output, pdf_output, current_session_info, images_gallery],
    )

    # 图片选择时自动添加到图片库
    image_input.change(
        fn=add_image_wrapper,
        inputs=[image_input],
        outputs=[images_gallery, image_input, grading_report],
    )

    # 清空图片库
    clear_images_btn.click(
        fn=clear_image_wrapper,
        inputs=[],
        outputs=[images_gallery, grading_report],
    )

    # 批改所有图片
    grade_btn.click(
        fn=grade_all_images_wrapper,
        inputs=[],
        outputs=[grading_report, current_session_info],
    )

    # 会话选择事件
    session_dropdown.change(
        fn=load_session_data,
        inputs=[session_dropdown],
        outputs=[
            prompt_input,
            result_output,
            pdf_output,
            grading_report,
            images_gallery,
            current_session_info,
        ],
    )

    # 刷新会话列表
    refresh_sessions_btn.click(fn=get_sessions_for_dropdown, outputs=[session_dropdown])

    # 页面加载时初始化会话列表
    demo.load(fn=get_sessions_for_dropdown, outputs=[session_dropdown])
