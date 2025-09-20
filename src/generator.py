import os
from re import S
from typing import List, Dict, Any
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

# from src.question.model import questions
# import openai


class PracticePaperGenerator:
    def __init__(self):
        # self.openai_client = openai.OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
        self.data_dir = os.getenv("DATA_DIR")
        self.font = self._register_chinese_fonts()
        

    def _register_chinese_fonts(self):
        pdfmetrics.registerFont(TTFont("STHeiti", os.getenv("CHINESE_FONT_PATH")))
        return "STHeiti"

    def generate_pdf(self, questions: List[Dict[str, Any]], session_path: str) -> str:
        """生成PDF文件"""
        pdf_path = os.path.join(session_path, "math_questions.pdf")

        doc = SimpleDocTemplate(pdf_path, pagesize=A4)
        styles = getSampleStyleSheet()
        story = []

        title_style = ParagraphStyle(
            "CustomTitle",
            parent=styles["Heading1"],
            fontName=self.font,
            fontSize=18,
            spaceAfter=30,
            alignment=1,  # 居中
        )

        # 题目样式
        question_style = ParagraphStyle(
            "Question",
            parent=styles["Normal"],
            fontName=self.font,
            fontSize=12,
            spaceAfter=12,
            leftIndent=20,
        )

        # 解答样式
        solution_style = ParagraphStyle(
            "Solution",
            parent=styles["Normal"],
            fontName=self.font,
            fontSize=10,
            spaceAfter=8,
            leftIndent=40,
            textColor="blue",
        )

        # 答案样式
        answer_style = ParagraphStyle(
            "Answer",
            parent=styles["Normal"],
            fontName=self.font,
            fontSize=10,
            spaceAfter=20,
            leftIndent=40,
            textColor="red",
        )

        # 添加标题
        story.append(Paragraph("数学题目练习", title_style))
        story.append(Spacer(1, 20))

        # 添加题目
        for i, q in enumerate(questions, 1):
            story.append(Paragraph(f"题目 {i}:", question_style))
            story.append(Paragraph(q.get("question", ""), question_style))

            if q.get("solution"):
                story.append(Paragraph("解答过程:", solution_style))
                story.append(Paragraph(q["solution"], solution_style))

            if q.get("answer"):
                story.append(Paragraph(f"答案: {q['answer']}", answer_style))

            story.append(Spacer(1, 20))

        # 生成PDF
        doc.build(story)
        return pdf_path


# 创建全局实例
# math_generator = MathQuestionGenerator()
