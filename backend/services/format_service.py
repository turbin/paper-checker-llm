import os
from backend.utils.logger_config import logger
from backend.utils.config import Config

from typing import Dict, Any, List



class FormatService:
    @staticmethod
    def parse_format_rules(template: str) -> Dict[str, Any]:
        """解析格式规则文件"""

        ruler_file = os.path.join(Config.get_prompts_path(), 'promots', f'{template}.ruler')
    
        # 检查文件是否存在
        if not os.path.exists(ruler_file):
            logger.error(f'模板文件 {ruler_file} 不存在')
            raise FileNotFoundError(f'模板文件 {ruler_file} 不存在')
        
        # 读取并返回文件内容
        with open(ruler_file, 'r', encoding='utf-8') as f:
            content = f.read().strip()
            logger.debug(f'已加载模板文件 {ruler_file}')
            return content

    @staticmethod
    def analyze_format(doc_content: Dict[str, List[Dict[str, Any]]], format_rules: Dict[str, Any]) -> Dict[str, Any]:
        """分析文档格式是否符合规则"""
        result = {
            "is_compliant": True,
            "issues": [],
            "suggestions": []
        }
        
        # 检查文档结构
        FormatService._check_structure(doc_content, format_rules, result)
        
        # 检查段落格式
        FormatService._check_paragraph_format(doc_content, format_rules, result)
        
        # 检查字体设置
        FormatService._check_font_settings(doc_content, format_rules, result)
        
        return result

    @staticmethod
    def _check_structure(doc_content: Dict[str, List[Dict[str, Any]]], rules: Dict[str, Any], result: Dict[str, Any]) -> None:
        """检查文档结构"""
        required_sections = rules.get("structure", {}).get("required_sections", [])
        for section in required_sections:
            if section not in doc_content:
                result["is_compliant"] = False
                result["issues"].append(f"缺少必要的章节: {section}")
                result["suggestions"].append(f"请添加章节: {section}")

    @staticmethod
    def _check_paragraph_format(doc_content: Dict[str, List[Dict[str, Any]]], rules: Dict[str, Any], result: Dict[str, Any]) -> None:
        """检查段落格式"""
        format_rules = rules.get("format", {})
        for section, paragraphs in doc_content.items():
            for para in paragraphs:
                # 检查段落样式
                if format_rules.get("style") and para["style"] != format_rules["style"]:
                    result["is_compliant"] = False
                    result["issues"].append(f"章节 '{section}' 中的段落样式不符合要求")
                    result["suggestions"].append(f"将段落样式修改为: {format_rules['style']}")
                
                # 检查对齐方式
                if format_rules.get("alignment") and para["alignment"] != format_rules["alignment"]:
                    result["is_compliant"] = False
                    result["issues"].append(f"章节 '{section}' 中的段落对齐方式不符合要求")
                    result["suggestions"].append(f"将段落对齐方式修改为: {format_rules['alignment']}")

    @staticmethod
    def _check_font_settings(doc_content: Dict[str, List[Dict[str, Any]]], rules: Dict[str, Any], result: Dict[str, Any]) -> None:
        """检查字体设置"""
        font_rules = rules.get("font", {})
        for section, paragraphs in doc_content.items():
            for para in paragraphs:
                # 检查字体大小
                if font_rules.get("size") and para["font_size"] != font_rules["size"]:
                    result["is_compliant"] = False
                    result["issues"].append(f"章节 '{section}' 中的字体大小不符合要求")
                    result["suggestions"].append(f"将字体大小修改为: {font_rules['size']}pt") 