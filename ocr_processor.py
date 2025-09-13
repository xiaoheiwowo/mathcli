"""OCR processing module for extracting text from math homework images."""

import cv2
import numpy as np
from PIL import Image
import pytesseract
import base64
import os
from typing import Dict, List, Optional
import logging
from openai import OpenAI


class OCRProcessor:
    """Handles OCR processing for math homework images."""
    
    def __init__(self, lang: str = 'chi_sim+eng'):
        """Initialize OCR processor.
        
        Args:
            lang: Tesseract language configuration
        """
        self.lang = lang
        self.logger = logging.getLogger(__name__)
        
        # Initialize AI OCR client
        try:
            self.ai_client = OpenAI(
                api_key=os.getenv("DASHSCOPE_API_KEY"),
                base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
            )
            self.use_ai_ocr = True
            self.logger.info("AI OCR client initialized successfully")
        except Exception as e:
            self.logger.warning(f"Failed to initialize AI OCR client: {e}. Using traditional OCR only.")
            self.ai_client = None
            self.use_ai_ocr = False
    
    def preprocess_image(self, image_path: str) -> np.ndarray:
        """Preprocess image for better OCR results.
        
        Args:
            image_path: Path to the input image
            
        Returns:
            Preprocessed image as numpy array
        """
        try:
            # Read image
            img = cv2.imread(image_path)
            if img is None:
                raise ValueError(f"Could not load image: {image_path}")
            
            # Convert to grayscale
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            
            # Apply Gaussian blur to reduce noise
            blurred = cv2.GaussianBlur(gray, (3, 3), 0)
            
            # Apply adaptive thresholding
            thresh = cv2.adaptiveThreshold(
                blurred, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
                cv2.THRESH_BINARY, 11, 2
            )
            
            # Morphological operations to clean up
            kernel = np.ones((2, 2), np.uint8)
            cleaned = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel)
            
            return cleaned
            
        except Exception as e:
            self.logger.error(f"Image preprocessing failed: {e}")
            raise
    
    def extract_text(self, image_path: str) -> Dict[str, str]:
        """Extract text from image using OCR.
        
        Args:
            image_path: Path to the input image
            
        Returns:
            Dictionary containing raw OCR text and confidence scores
        """
        # Try AI OCR first if available
        if self.use_ai_ocr and self.ai_client:
            try:
                ai_result = self._extract_text_with_ai(image_path)
                if ai_result and ai_result.get('raw_text'):
                    self.logger.info("Using AI OCR result")
                    return ai_result
                else:
                    self.logger.warning("AI OCR failed, falling back to traditional OCR")
            except Exception as e:
                self.logger.warning(f"AI OCR failed: {e}, falling back to traditional OCR")
        
        # Fallback to traditional OCR
        return self._extract_text_traditional(image_path)
    
    def _extract_text_with_ai(self, image_path: str) -> Dict[str, str]:
        """Extract text using Qwen-VL-OCR model.
        
        Args:
            image_path: Path to the input image
            
        Returns:
            Dictionary containing OCR results from AI model
        """
        try:
            # Encode image to base64
            with open(image_path, "rb") as image_file:
                base64_image = base64.b64encode(image_file.read()).decode('utf-8')
            
            # Log image processing without exposing image data
            self.logger.debug(f"Processing image: {image_path}, size: {len(base64_image)} characters")
            
            # Create prompt for mathematical OCR
            messages = [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": """请仔细识别这张数学作业图片中的所有文字和数学表达式。要求：
1. 准确识别所有数字、运算符号、分数、等号等数学符号
2. 不要使用 latex 语法。
3. 保持原有的排版格式和题目编号
4. 识别中文题目描述和解答过程
5. 对于手写内容，请尽可能准确识别
6. 按照原图的顺序输出内容
7. 注意等号的位置，等号决定了计算步骤的开始。

请直接输出识别的文字内容，不要添加额外的解释。"""
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{base64_image}"
                            }
                        }
                    ]
                }
            ]
            
            # Call Qwen-VL-OCR model
            response = self.ai_client.chat.completions.create(
                model="qwen-vl-ocr",
                messages=messages,
                max_tokens=2000,
                temperature=0.1
            )
            
            raw_text = response.choices[0].message.content
            
            # AI OCR typically has high confidence when it works
            confidence = 85.0 if raw_text and len(raw_text.strip()) > 10 else 30.0
            
            self.logger.info(f"AI OCR completed with confidence: {confidence}")
            self.logger.debug(f"AI OCR result: {raw_text[:200]}...")
            
            return {
                'raw_text': raw_text.strip(),
                'confidence': confidence,
                'method': 'ai_ocr',
                'model': 'qwen-vl-ocr'
            }
            
        except Exception as e:
            self.logger.error(f"AI OCR extraction failed: {e}")
            return {
                'raw_text': '',
                'confidence': 0,
                'error': str(e),
                'method': 'ai_ocr_failed'
            }
    
    def _extract_text_traditional(self, image_path: str) -> Dict[str, str]:
        """Extract text using traditional Tesseract OCR.
        
        Args:
            image_path: Path to the input image
            
        Returns:
            Dictionary containing traditional OCR results
        """
        try:
            # Preprocess image
            processed_img = self.preprocess_image(image_path)
            
            # Configure Tesseract
            custom_config = r'--oem 3 --psm 6 -c tessedit_char_whitelist=0123456789+-×÷=()[]{}.,/\\abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ一二三四五六七八九十百千万亿加减乘除等于解答题目计算过程结果分数小数整数负数正数'
            
            # Extract text with confidence
            data = pytesseract.image_to_data(
                processed_img, 
                lang=self.lang, 
                config=custom_config, 
                output_type=pytesseract.Output.DICT
            )
            
            # Extract raw text
            raw_text = pytesseract.image_to_string(
                processed_img, 
                lang=self.lang, 
                config=custom_config
            )
            
            # Calculate average confidence
            confidences = [int(conf) for conf in data['conf'] if int(conf) > 0]
            avg_confidence = sum(confidences) / len(confidences) if confidences else 0
            
            return {
                'raw_text': raw_text.strip(),
                'confidence': avg_confidence,
                'word_data': data,
                'method': 'traditional_ocr'
            }
            
        except Exception as e:
            self.logger.error(f"Traditional OCR extraction failed: {e}")
            return {
                'raw_text': '',
                'confidence': 0,
                'word_data': {},
                'error': str(e),
                'method': 'traditional_ocr_failed'
            }
    
    def extract_math_expressions(self, ocr_result: Dict[str, str]) -> List[str]:
        """Extract mathematical expressions from OCR text.
        
        Args:
            ocr_result: OCR result dictionary
            
        Returns:
            List of detected mathematical expressions
        """
        import re
        
        text = ocr_result.get('raw_text', '')
        expressions = []
        
        # Pattern for mathematical expressions
        patterns = [
            r'\d+\s*[+\-×÷]\s*\d+\s*=\s*\d+',  # Simple arithmetic
            r'\d+/\d+\s*[+\-×÷]\s*\d+/\d+',    # Fractions
            r'\([^)]+\)\s*[+\-×÷]\s*\([^)]+\)', # Parentheses
            r'x\s*[+\-]\s*\d+\s*=\s*\d+',      # Simple equations
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, text)
            expressions.extend(matches)
        
        return expressions
