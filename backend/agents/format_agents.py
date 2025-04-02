import os
from typing import Any, Dict, List
from .base_agent import BaseAgent
from backend.utils.logger_config import logger
from backend.utils.config import Config
from backend.utils.format_parser import FormatParser
from backend.utils.docx_format_parser import DocxFormatParser
import json

class CoverAgent(BaseAgent):
    """封面格式解析Agent"""
    
    def __init__(self):
        super().__init__("cover_agent")
        
    def validate_input(self, input_data: Dict[str, Any]) -> bool:
        return "cover_content" in input_data or "document" in input_data
        
    def run(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        try:
            if not self.validate_input(input_data):
                raise ValueError("缺少封面内容或文档对象")
                
            rules = self._load_rules(input_data)
            
            result = {
                "status": "success",
                "agent": self.name,
                "issues": [],
                "suggestions": []
            }
            
            # 使用FormatParser获取完整格式信息
            if "document" in input_data:
                # 使用普通FormatParser还是XML/OOXML规范的DocxFormatParser
                if "use_docx_parser" in input_data and input_data["use_docx_parser"]:
                    # 使用XML/OOXML格式解析
                    if "document_path" in input_data:
                        parser = DocxFormatParser(input_data["document_path"])
                        # 继续使用DocxFormatParser的功能
                        # ...
                    else:
                        # DocxFormatParser需要文件路径
                        logger.warning("未提供document_path，无法使用DocxFormatParser")
                else:
                    # 使用原来的FormatParser
                    parser = FormatParser(input_data["document"])
                    cover_format = {}
                    
                    # 查找封面相关段落
                    for paragraph in parser.document.paragraphs:
                        if not paragraph.text.strip():
                            continue
                            
                        para_format = parser.get_paragraph_format(paragraph)
                        style_name = para_format.get("style", "")
                        
                        # 根据样式或文本内容判断是否为封面部分
                        if (style_name and "封面" in style_name) or self._is_cover_paragraph(paragraph.text):
                            # 提取封面段落格式
                            if "title" in cover_format and "标题" in style_name:
                                self._check_title_format(para_format, rules.get("title", {}), result)
                            elif "author" in cover_format and ("姓名" in style_name or "作者" in paragraph.text):
                                self._check_author_format(para_format, rules.get("author", {}), result)
                            else:
                                self._check_other_info_format(para_format, rules.get("other_info", {}), result)
            elif "cover_content" in input_data:
                # 兼容旧版API，直接检查传入的格式信息
                cover_content = input_data["cover_content"]
                if "title" in cover_content:
                    self._check_title_format(cover_content["title"], rules.get("title", {}), result)
                    
                # 检查作者信息格式
                if "author" in cover_content:
                    self._check_author_format(cover_content["author"], rules.get("author", {}), result)
                    
                # 检查其他信息格式
                if "other_info" in cover_content:
                    self._check_other_info_format(cover_content["other_info"], rules.get("other_info", {}), result)
                
            return result
            
        except Exception as e:
            logger.error(f"封面格式解析失败: {str(e)}", exc_info=True)
            return self.handle_error(e)
            
    def _is_cover_paragraph(self, text: str) -> bool:
        """判断段落是否属于封面"""
        cover_keywords = [
            "学校编码", "学号", "专业", "题目", "作者", "指导教师", 
            "摘要", "关键词", "学位论文", "毕业论文", "大学"
        ]
        return any(keyword in text for keyword in cover_keywords)
            
    def _load_rules(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """加载封面格式规则"""
        try:
            # 首先尝试从input_data中获取规则文件路径
            if "ruler_path" in input_data:
                ruler_path = input_data["ruler_path"]
            else:
                # 否则使用Config获取路径
                ruler_path = Config.get_instance().get_prompts_path() + "/promots/xmu.ruler"
                
            with open(ruler_path, "r", encoding="utf-8") as f:
                rules = json.load(f)
                return rules.get("cover", {})
        except Exception as e:
            logger.error(f"加载封面规则失败: {str(e)}")
            raise
            
    def _check_title_format(self, title_format: Dict[str, Any], rules: Dict[str, Any], result: Dict[str, Any]) -> None:
        """检查标题格式"""
        # 字体大小检查
        if rules.get("font_size"):
            rule_size = float(rules["font_size"])
            actual_size = title_format.get("size")
            if actual_size is not None:
                actual_size = float(actual_size)
                if abs(actual_size - rule_size) > 0.5:
                    result["issues"].append("封面标题字体大小不符合要求")
                    result["suggestions"].append(f"将封面标题字体大小修改为 {rule_size}pt")
        
        # 字体检查
        if rules.get("font") and title_format.get("font") != rules["font"]:
            result["issues"].append("封面标题字体不符合要求")
            result["suggestions"].append(f"将封面标题字体修改为 {rules['font']}")
            
        # 对齐方式检查
        if rules.get("alignment") is not None:
            rule_alignment = rules["alignment"]
            actual_alignment = title_format.get("alignment")
            if actual_alignment is not None and actual_alignment != rule_alignment:
                result["issues"].append("封面标题对齐方式不符合要求")
                result["suggestions"].append(f"将封面标题对齐方式修改为 {self._get_alignment_name(rule_alignment)}")
    
    def _check_author_format(self, author_format: Dict[str, Any], rules: Dict[str, Any], result: Dict[str, Any]) -> None:
        """检查作者信息格式"""
        # 字体大小检查
        if rules.get("font_size"):
            rule_size = float(rules["font_size"])
            actual_size = author_format.get("size")
            if actual_size is not None:
                actual_size = float(actual_size)
                if abs(actual_size - rule_size) > 0.5:
                    result["issues"].append("作者信息字体大小不符合要求")
                    result["suggestions"].append(f"将作者信息字体大小修改为 {rule_size}pt")
        
        # 字体检查
        if rules.get("font") and author_format.get("font") != rules["font"]:
            result["issues"].append("作者信息字体不符合要求")
            result["suggestions"].append(f"将作者信息字体修改为 {rules['font']}")
            
        # 对齐方式检查
        if rules.get("alignment") is not None:
            rule_alignment = rules["alignment"]
            actual_alignment = author_format.get("alignment")
            if actual_alignment is not None and actual_alignment != rule_alignment:
                result["issues"].append("作者信息对齐方式不符合要求")
                result["suggestions"].append(f"将作者信息对齐方式修改为 {self._get_alignment_name(rule_alignment)}")
    
    def _check_other_info_format(self, info_format: Dict[str, Any], rules: Dict[str, Any], result: Dict[str, Any]) -> None:
        """检查其他信息格式"""
        # 字体大小检查
        if rules.get("font_size"):
            rule_size = float(rules["font_size"])
            actual_size = info_format.get("size")
            if actual_size is not None:
                actual_size = float(actual_size)
                if abs(actual_size - rule_size) > 0.5:
                    result["issues"].append("其他封面信息字体大小不符合要求")
                    result["suggestions"].append(f"将其他封面信息字体大小修改为 {rule_size}pt")
        
        # 字体检查
        if rules.get("font") and info_format.get("font") != rules["font"]:
            result["issues"].append("其他封面信息字体不符合要求")
            result["suggestions"].append(f"将其他封面信息字体修改为 {rules['font']}")
            
        # 对齐方式检查
        if rules.get("alignment") is not None:
            rule_alignment = rules["alignment"]
            actual_alignment = info_format.get("alignment")
            if actual_alignment is not None and actual_alignment != rule_alignment:
                result["issues"].append("其他封面信息对齐方式不符合要求")
                result["suggestions"].append(f"将其他封面信息对齐方式修改为 {self._get_alignment_name(rule_alignment)}")
    
    def _get_alignment_name(self, alignment_value: int) -> str:
        """将对齐方式数值转换为名称"""
        alignment_map = {
            0: "左对齐",
            1: "居中",
            2: "右对齐",
            3: "两端对齐",
            4: "分散对齐"
        }
        return alignment_map.get(alignment_value, f"对齐方式{alignment_value}")

class ChapterAgent(BaseAgent):
    """章节内容格式解析Agent"""
    
    def __init__(self):
        super().__init__("chapter_agent")
        
    def validate_input(self, input_data: Dict[str, Any]) -> bool:
        return "chapters" in input_data or "document" in input_data
        
    def run(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        try:
            if not self.validate_input(input_data):
                raise ValueError("缺少章节内容或文档对象")
                
            rules = self._load_rules(input_data)
            
            result = {
                "status": "success",
                "agent": self.name,
                "issues": [],
                "suggestions": []
            }
            
            # 使用格式解析器获取完整格式信息
            if "document" in input_data:
                # 判断使用哪种解析器
                if "use_docx_parser" in input_data and input_data["use_docx_parser"] and "document_path" in input_data:
                    # 使用XML/OOXML格式解析
                    parser = DocxFormatParser(input_data["document_path"])
                    # 使用DocxFormatParser的方法提取章节
                    # ...
                else:
                    # 使用原来的FormatParser
                    parser = FormatParser(input_data["document"])
                    chapter_formats = self._extract_chapters(parser)
                    
                    # 检查每个章节的格式
                    for chapter_name, chapter_content in chapter_formats.items():
                        self._check_chapter_format(chapter_name, chapter_content, rules, result)
            else:
                # 兼容旧版API
                chapters = input_data["chapters"]
                for chapter_name, chapter_content in chapters.items():
                    self._check_chapter_format(chapter_name, chapter_content, rules, result)
                
            return result
            
        except Exception as e:
            logger.error(f"章节格式解析失败: {str(e)}", exc_info=True)
            return self.handle_error(e)
            
    def _extract_chapters(self, parser: FormatParser) -> Dict[str, Any]:
        """从文档中提取章节结构和格式信息"""
        chapters = {}
        current_chapter = None
        chapter_content = []
        
        # 遍历所有段落，按照标题级别组织章节结构
        for i, para in enumerate(parser.document.paragraphs):
            if not para.text.strip():
                continue
                
            para_format = parser.get_paragraph_format(para)
            style_name = para_format.get("style", "")
            
            # 判断是否为章节标题
            if style_name and ("Heading" in style_name or "标题" in style_name):
                # 如果已经有章节，保存前一章节
                if current_chapter:
                    chapters[current_chapter] = {
                        "title": chapter_title,
                        "content": chapter_content
                    }
                
                # 开始新章节
                current_chapter = para.text
                chapter_title = para_format
                chapter_content = []
            elif current_chapter:
                # 添加到当前章节内容
                chapter_content.append(para_format)
            
        # 保存最后一个章节
        if current_chapter:
            chapters[current_chapter] = {
                "title": chapter_title,
                "content": chapter_content
            }
            
        return chapters
            
    def _load_rules(self, input_data: Dict[str, Any] = None) -> Dict[str, Any]:
        """加载章节格式规则"""
        try:
            # 首先尝试从input_data中获取规则文件路径
            if input_data and "ruler_path" in input_data:
                ruler_path = input_data["ruler_path"]
            else:
                # 否则使用Config获取路径
                ruler_path = Config.get_instance().get_prompts_path() + "/promots/xmu.ruler"
                
            with open(ruler_path, "r", encoding="utf-8") as f:
                rules = json.load(f)
                return rules.get("chapter", {})
        except Exception as e:
            logger.error(f"加载章节规则失败: {str(e)}")
            raise
            
    def _check_chapter_format(self, chapter_name: str, chapter_content: Dict[str, Any], rules: Dict[str, Any], result: Dict[str, Any]) -> None:
        """检查章节格式"""
        # 检查标题格式
        if "title" in rules and "title" in chapter_content:
            title_format = chapter_content["title"]
            title_rules = rules["title"]
            
            # 标题字体检查
            if title_rules.get("font") and title_format.get("font") != title_rules["font"]:
                result["issues"].append(f"章节标题 '{chapter_name}' 字体不符合要求")
                result["suggestions"].append(f"将章节标题 '{chapter_name}' 字体修改为 {title_rules['font']}")
                
            # 标题字号检查
            if title_rules.get("font_size"):
                rule_size = float(title_rules["font_size"])
                actual_size = title_format.get("size")
                if actual_size is not None:
                    actual_size = float(actual_size)
                    if abs(actual_size - rule_size) > 0.5:
                        result["issues"].append(f"章节标题 '{chapter_name}' 字体大小不符合要求")
                        result["suggestions"].append(f"将章节标题 '{chapter_name}' 字体大小修改为 {rule_size}pt")
                
            # 标题对齐方式检查
            if title_rules.get("alignment") is not None:
                rule_alignment = title_rules["alignment"]
                actual_alignment = title_format.get("alignment")
                if actual_alignment is not None and actual_alignment != rule_alignment:
                    result["issues"].append(f"章节标题 '{chapter_name}' 对齐方式不符合要求")
                    result["suggestions"].append(f"将章节标题 '{chapter_name}' 对齐方式修改为 {self._get_alignment_name(rule_alignment)}")
        
        # 检查正文格式
        if "content" in rules and "content" in chapter_content:
            content_rules = rules["content"]
            
            for paragraph in chapter_content["content"]:
                # 字体检查
                if content_rules.get("font") and paragraph.get("font") != content_rules["font"]:
                    result["issues"].append(f"章节 '{chapter_name}' 正文字体不符合要求")
                    result["suggestions"].append(f"将章节 '{chapter_name}' 正文字体修改为 {content_rules['font']}")
                    break
                    
                # 字号检查
                if content_rules.get("font_size"):
                    rule_size = float(content_rules["font_size"])
                    actual_size = paragraph.get("size")
                    if actual_size is not None:
                        actual_size = float(actual_size)
                        if abs(actual_size - rule_size) > 0.5:
                            result["issues"].append(f"章节 '{chapter_name}' 正文字体大小不符合要求")
                            result["suggestions"].append(f"将章节 '{chapter_name}' 正文字体大小修改为 {rule_size}pt")
                            break
                    
                # 行距检查
                if content_rules.get("line_spacing"):
                    rule_spacing = float(content_rules["line_spacing"])
                    actual_spacing = paragraph.get("line_spacing")
                    if actual_spacing is not None:
                        actual_spacing = float(actual_spacing)
                        if abs(actual_spacing - rule_spacing) > 0.1:
                            result["issues"].append(f"章节 '{chapter_name}' 段落行距不符合要求")
                            result["suggestions"].append(f"将章节 '{chapter_name}' 段落行距修改为 {rule_spacing}")
                            break
                    
                # 对齐方式检查
                if content_rules.get("alignment") is not None:
                    rule_alignment = content_rules["alignment"]
                    actual_alignment = paragraph.get("alignment")
                    if actual_alignment is not None and actual_alignment != rule_alignment:
                        result["issues"].append(f"章节 '{chapter_name}' 段落对齐方式不符合要求")
                        result["suggestions"].append(f"将章节 '{chapter_name}' 段落对齐方式修改为 {self._get_alignment_name(rule_alignment)}")
                        break
                        
    def _get_alignment_name(self, alignment_value: int) -> str:
        """将对齐方式数值转换为名称"""
        alignment_map = {
            0: "左对齐",
            1: "居中",
            2: "右对齐",
            3: "两端对齐",
            4: "分散对齐"
        }
        return alignment_map.get(alignment_value, f"对齐方式{alignment_value}")

class HeaderFooterAgent(BaseAgent):
    """页眉页脚格式解析Agent"""
    
    def __init__(self):
        super().__init__("header_footer_agent")
        
    def validate_input(self, input_data: Dict[str, Any]) -> bool:
        return "header_footer" in input_data or "document" in input_data
        
    def run(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        try:
            if not self.validate_input(input_data):
                raise ValueError("缺少页眉页脚内容或文档对象")
                
            rules = self._load_rules(input_data)
            
            result = {
                "status": "success",
                "agent": self.name,
                "issues": [],
                "suggestions": []
            }
            
            # 使用FormatParser获取完整格式信息
            if "document" in input_data:
                parser = FormatParser(input_data["document"])
                header_footer = parser.get_header_footer_format()
                
                # 检查页眉格式
                if header_footer["header"]["has_header"]:
                    for paragraph in header_footer["header"]["paragraphs"]:
                        self._check_header_format(paragraph, rules.get("header", {}), result)
                
                # 检查页脚格式
                if header_footer["footer"]["has_footer"]:
                    for paragraph in header_footer["footer"]["paragraphs"]:
                        self._check_footer_format(paragraph, rules.get("footer", {}), result)
            else:
                # 兼容旧版API
                header_footer = input_data["header_footer"]
                
                # 检查页眉格式
                if "header" in header_footer:
                    self._check_header_format(header_footer["header"], rules.get("header", {}), result)
                    
                # 检查页脚格式
                if "footer" in header_footer:
                    self._check_footer_format(header_footer["footer"], rules.get("footer", {}), result)
                
            return result
            
        except Exception as e:
            logger.error(f"页眉页脚格式解析失败: {str(e)}", exc_info=True)
            return self.handle_error(e)
            
    def _load_rules(self, input_data: Dict[str, Any] = None) -> Dict[str, Any]:
        """加载页眉页脚格式规则"""
        try:
            # 首先尝试从input_data中获取规则文件路径
            if input_data and "ruler_path" in input_data:
                ruler_path = input_data["ruler_path"]
            else:
                # 否则使用Config获取路径
                ruler_path = Config.get_instance().get_prompts_path() + "/promots/xmu.ruler"
                
            with open(ruler_path, "r", encoding="utf-8") as f:
                rules = json.load(f)
                return rules.get("header_footer", {})
        except Exception as e:
            logger.error(f"加载页眉页脚规则失败: {str(e)}")
            raise
            
    def _check_header_format(self, header: Dict[str, Any], rules: Dict[str, Any], result: Dict[str, Any]) -> None:
        """检查页眉格式"""
        # 字体大小检查
        if rules.get("font_size"):
            rule_size = float(rules["font_size"])
            actual_size = header.get("size")
            if actual_size is not None:
                actual_size = float(actual_size)
                if abs(actual_size - rule_size) > 0.5:
                    result["issues"].append("页眉字体大小不符合要求")
                    result["suggestions"].append(f"将页眉字体大小修改为 {rule_size}pt")
        
        # 字体检查
        if rules.get("font") and header.get("font") != rules["font"]:
            result["issues"].append("页眉字体不符合要求")
            result["suggestions"].append(f"将页眉字体修改为 {rules['font']}")
            
        # 对齐方式检查
        if rules.get("alignment") is not None:
            rule_alignment = rules["alignment"]
            actual_alignment = header.get("alignment")
            if actual_alignment is not None and actual_alignment != rule_alignment:
                result["issues"].append("页眉对齐方式不符合要求")
                result["suggestions"].append(f"将页眉对齐方式修改为 {self._get_alignment_name(rule_alignment)}")
                
        # 内容检查
        if rules.get("content") and header.get("text") != rules["content"]:
            result["issues"].append("页眉内容不符合要求")
            result["suggestions"].append(f"将页眉内容修改为 '{rules['content']}'")
    
    def _check_footer_format(self, footer: Dict[str, Any], rules: Dict[str, Any], result: Dict[str, Any]) -> None:
        """检查页脚格式"""
        # 字体大小检查
        if rules.get("font_size"):
            rule_size = float(rules["font_size"])
            actual_size = footer.get("size")
            if actual_size is not None:
                actual_size = float(actual_size)
                if abs(actual_size - rule_size) > 0.5:
                    result["issues"].append("页脚字体大小不符合要求")
                    result["suggestions"].append(f"将页脚字体大小修改为 {rule_size}pt")
        
        # 字体检查
        if rules.get("font") and footer.get("font") != rules["font"]:
            result["issues"].append("页脚字体不符合要求")
            result["suggestions"].append(f"将页脚字体修改为 {rules['font']}")
            
        # 对齐方式检查
        if rules.get("alignment") is not None:
            rule_alignment = rules["alignment"]
            actual_alignment = footer.get("alignment")
            if actual_alignment is not None and actual_alignment != rule_alignment:
                result["issues"].append("页脚对齐方式不符合要求")
                result["suggestions"].append(f"将页脚对齐方式修改为 {self._get_alignment_name(rule_alignment)}")
                
        # 内容检查
        if rules.get("content") and footer.get("text") != rules["content"]:
            result["issues"].append("页脚内容不符合要求")
            result["suggestions"].append(f"将页脚内容修改为 '{rules['content']}'")
            
    def _get_alignment_name(self, alignment_value: int) -> str:
        """将对齐方式数值转换为名称"""
        alignment_map = {
            0: "左对齐",
            1: "居中",
            2: "右对齐",
            3: "两端对齐",
            4: "分散对齐"
        }
        return alignment_map.get(alignment_value, f"对齐方式{alignment_value}")

class TableAgent(BaseAgent):
    """表格格式解析Agent"""
    
    def __init__(self):
        super().__init__("table_agent")
        
    def validate_input(self, input_data: Dict[str, Any]) -> bool:
        return "tables" in input_data or "document" in input_data
        
    def run(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        try:
            if not self.validate_input(input_data):
                raise ValueError("缺少表格内容或文档对象")
                
            rules = self._load_rules(input_data)
            
            result = {
                "status": "success",
                "agent": self.name,
                "issues": [],
                "suggestions": []
            }
            
            # 使用FormatParser获取完整格式信息
            if "document" in input_data:
                parser = FormatParser(input_data["document"])
                doc_info = parser.analyze_document()
                
                for i, table_info in enumerate(doc_info["tables"]):
                    self._check_table_format(table_info, rules, result, i+1)
            else:
                # 兼容旧版API
                tables = input_data["tables"]
                
                for i, table in enumerate(tables):
                    self._check_table_format(table, rules, result, i+1)
                
            return result
            
        except Exception as e:
            logger.error(f"表格格式解析失败: {str(e)}", exc_info=True)
            return self.handle_error(e)
            
    def _load_rules(self, input_data: Dict[str, Any] = None) -> Dict[str, Any]:
        """加载表格格式规则"""
        try:
            # 首先尝试从input_data中获取规则文件路径
            if input_data and "ruler_path" in input_data:
                ruler_path = input_data["ruler_path"]
            else:
                # 否则使用Config获取路径
                ruler_path = Config.get_instance().get_prompts_path() + "/promots/xmu.ruler"
                
            with open(ruler_path, "r", encoding="utf-8") as f:
                rules = json.load(f)
                return rules.get("table", {})
        except Exception as e:
            logger.error(f"加载表格规则失败: {str(e)}")
            raise
            
    def _check_table_format(self, table: Dict[str, Any], rules: Dict[str, Any], result: Dict[str, Any], table_index: int) -> None:
        """检查表格格式"""
        # 表格样式检查
        if rules.get("style") and table.get("style") != rules["style"]:
            result["issues"].append(f"表格 {table_index} 样式不符合要求")
            result["suggestions"].append(f"将表格 {table_index} 样式修改为 {rules['style']}")
        
        # 检查表格内容格式
        content_rules = rules.get("content", {})
        
        # 检查单元格内容
        for cell in table.get("cells", []):
            # 检查单元格中的段落
            for paragraph in cell.get("paragraphs", []):
                # 字体大小检查
                if content_rules.get("font_size"):
                    rule_size = float(content_rules["font_size"])
                    actual_size = paragraph.get("size")
                    if actual_size is not None:
                        actual_size = float(actual_size)
                        if abs(actual_size - rule_size) > 0.5:
                            result["issues"].append(f"表格 {table_index} 内容字体大小不符合要求")
                            result["suggestions"].append(f"将表格 {table_index} 内容字体大小修改为 {rule_size}pt")
                            break
                
                # 字体检查
                if content_rules.get("font") and paragraph.get("font") != content_rules["font"]:
                    result["issues"].append(f"表格 {table_index} 内容字体不符合要求")
                    result["suggestions"].append(f"将表格 {table_index} 内容字体修改为 {content_rules['font']}")
                    break
                    
                # 对齐方式检查
                if content_rules.get("alignment") is not None:
                    rule_alignment = content_rules["alignment"]
                    actual_alignment = paragraph.get("alignment")
                    if actual_alignment is not None and actual_alignment != rule_alignment:
                        result["issues"].append(f"表格 {table_index} 内容对齐方式不符合要求")
                        result["suggestions"].append(f"将表格 {table_index} 内容对齐方式修改为 {self._get_alignment_name(rule_alignment)}")
                        break
        
        # 表格编号格式检查
        caption_rules = rules.get("caption", {})
        if "caption" in table:
            caption = table["caption"]
            
            # 字体大小检查
            if caption_rules.get("font_size"):
                rule_size = float(caption_rules["font_size"])
                actual_size = caption.get("size")
                if actual_size is not None:
                    actual_size = float(actual_size)
                    if abs(actual_size - rule_size) > 0.5:
                        result["issues"].append(f"表格 {table_index} 编号字体大小不符合要求")
                        result["suggestions"].append(f"将表格 {table_index} 编号字体大小修改为 {rule_size}pt")
            
            # 字体检查
            if caption_rules.get("font") and caption.get("font") != caption_rules["font"]:
                result["issues"].append(f"表格 {table_index} 编号字体不符合要求")
                result["suggestions"].append(f"将表格 {table_index} 编号字体修改为 {caption_rules['font']}")
                
            # 对齐方式检查
            if caption_rules.get("alignment") is not None:
                rule_alignment = caption_rules["alignment"]
                actual_alignment = caption.get("alignment")
                if actual_alignment is not None and actual_alignment != rule_alignment:
                    result["issues"].append(f"表格 {table_index} 编号对齐方式不符合要求")
                    result["suggestions"].append(f"将表格 {table_index} 编号对齐方式修改为 {self._get_alignment_name(rule_alignment)}")
                    
            # 格式检查（例如：表3-1）
            if caption_rules.get("format") and "text" in caption:
                import re
                pattern = re.compile(caption_rules["format"])
                if not pattern.match(caption["text"]):
                    result["issues"].append(f"表格 {table_index} 编号格式不符合要求")
                    result["suggestions"].append(f"表格编号应符合格式: {caption_rules['format']}")
                    
    def _get_alignment_name(self, alignment_value: int) -> str:
        """将对齐方式数值转换为名称"""
        alignment_map = {
            0: "左对齐",
            1: "居中",
            2: "右对齐",
            3: "两端对齐",
            4: "分散对齐"
        }
        return alignment_map.get(alignment_value, f"对齐方式{alignment_value}")

class TableOfContentsAgent(BaseAgent):
    """目录格式解析Agent"""
    
    def __init__(self):
        super().__init__("toc_agent")
        
    def validate_input(self, input_data: Dict[str, Any]) -> bool:
        return "table_of_contents" in input_data
        
    def run(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        try:
            if not self.validate_input(input_data):
                raise ValueError("缺少目录内容")
                
            toc_content = input_data["table_of_contents"]
            rules = self._load_rules()
            
            result = {
                "status": "success",
                "agent": self.name,
                "issues": [],
                "suggestions": []
            }
            
            # 检查目录标题格式
            if "title" in toc_content:
                self._check_title_format(toc_content["title"], rules.get("title", {}), result)
                
            # 检查目录条目格式
            if "entries" in toc_content:
                self._check_entries_format(toc_content["entries"], rules.get("entries", {}), result)
                
            # 检查目录结构
            if "structure" in rules:
                self._check_structure(toc_content, rules["structure"], result)
                
            return result
            
        except Exception as e:
            return self.handle_error(e)
            
    def _load_rules(self) -> Dict[str, Any]:
        """加载目录格式规则"""
        try:
            with open(Config.get_prompts_path() + "/promots/xmu.ruler", "r", encoding="utf-8") as f:
                rules = json.load(f)
                return rules.get("table_of_contents", {})
        except Exception as e:
            logger.error(f"加载目录规则失败: {str(e)}")
            raise
            
    def _check_title_format(self, title: Dict[str, Any], rules: Dict[str, Any], result: Dict[str, Any]) -> None:
        """检查目录标题格式"""
        if rules.get("font_size") and title.get("font_size") != rules["font_size"]:
            result["issues"].append("目录标题字体大小不符合要求")
            result["suggestions"].append(f"将目录标题字体大小修改为 {rules['font_size']}pt")
            
        if rules.get("alignment") and title.get("alignment") != rules["alignment"]:
            result["issues"].append("目录标题对齐方式不符合要求")
            result["suggestions"].append(f"将目录标题对齐方式修改为 {rules['alignment']}")
            
    def _check_entries_format(self, entries: List[Dict[str, Any]], rules: Dict[str, Any], result: Dict[str, Any]) -> None:
        """检查目录条目格式"""
        for entry in entries:
            # 检查字体大小
            if rules.get("font_size") and entry.get("font_size") != rules["font_size"]:
                result["issues"].append(f"目录条目 '{entry.get('text', '')}' 字体大小不符合要求")
                result["suggestions"].append(f"将目录条目字体大小修改为 {rules['font_size']}pt")
                
            # 检查缩进
            if rules.get("indentation") and entry.get("level"):
                expected_indent = rules["indentation"] * entry["level"]
                if entry.get("indentation", 0) != expected_indent:
                    result["issues"].append(f"目录条目 '{entry.get('text', '')}' 缩进不符合要求")
                    result["suggestions"].append(f"将目录条目缩进修改为 {expected_indent}pt")
                    
            # 检查页码格式
            if rules.get("page_number_format") and entry.get("page_number"):
                if not self._validate_page_number(entry["page_number"], rules["page_number_format"]):
                    result["issues"].append(f"目录条目 '{entry.get('text', '')}' 页码格式不符合要求")
                    result["suggestions"].append(f"将页码格式修改为 {rules['page_number_format']}")
                    
    def _check_structure(self, toc_content: Dict[str, Any], rules: Dict[str, Any], result: Dict[str, Any]) -> None:
        """检查目录结构"""
        required_sections = rules.get("required_sections", [])
        if "entries" in toc_content:
            existing_sections = [entry.get("text", "") for entry in toc_content["entries"]]
            for section in required_sections:
                if section not in existing_sections:
                    result["issues"].append(f"目录缺少必要的章节: {section}")
                    result["suggestions"].append(f"在目录中添加章节: {section}")
                    
    def _validate_page_number(self, page_number: str, format_rule: str) -> bool:
        """验证页码格式"""
        if format_rule == "arabic":
            return page_number.isdigit()
        elif format_rule == "roman":
            # 简单的罗马数字验证
            roman_numerals = {'I', 'V', 'X', 'L', 'C', 'D', 'M'}
            return all(c in roman_numerals for c in page_number)
        return True  # 如果格式规则未指定，则接受任何格式

class OriginalityStatementAgent(BaseAgent):
    """原创性声明格式解析Agent"""
    
    def __init__(self):
        super().__init__("originality_statement_agent")
        
    def validate_input(self, input_data: Dict[str, Any]) -> bool:
        return "originality_statement" in input_data
        
    def run(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        try:
            if not self.validate_input(input_data):
                raise ValueError("缺少原创性声明内容")
                
            statement_content = input_data["originality_statement"]
            rules = self._load_rules()
            
            result = {
                "status": "success",
                "agent": self.name,
                "issues": [],
                "suggestions": []
            }
            
            # 检查标题格式
            if "title" in statement_content:
                self._check_title_format(statement_content["title"], rules.get("title", {}), result)
                
            # 检查声明内容格式
            if "content" in statement_content:
                self._check_content_format(statement_content["content"], rules.get("content", {}), result)
                
            # 检查签名部分格式
            if "signature" in statement_content:
                self._check_signature_format(statement_content["signature"], rules.get("signature", {}), result)
                
            return result
            
        except Exception as e:
            return self.handle_error(e)
            
    def _load_rules(self) -> Dict[str, Any]:
        """加载原创性声明格式规则"""
        try:
            with open(Config.get_prompts_path() + "/promots/xmu.ruler", "r", encoding="utf-8") as f:
                rules = json.load(f)
                return rules.get("originality_statement", {})
        except Exception as e:
            logger.error(f"加载原创性声明规则失败: {str(e)}")
            raise
            
    def _check_title_format(self, title: Dict[str, Any], rules: Dict[str, Any], result: Dict[str, Any]) -> None:
        """检查标题格式"""
        if rules.get("font_size") and title.get("font_size") != rules["font_size"]:
            result["issues"].append("原创性声明标题字体大小不符合要求")
            result["suggestions"].append(f"将原创性声明标题字体大小修改为 {rules['font_size']}pt")
            
        if rules.get("alignment") and title.get("alignment") != rules["alignment"]:
            result["issues"].append("原创性声明标题对齐方式不符合要求")
            result["suggestions"].append(f"将原创性声明标题对齐方式修改为 {rules['alignment']}")
            
    def _check_content_format(self, content: Dict[str, Any], rules: Dict[str, Any], result: Dict[str, Any]) -> None:
        """检查声明内容格式"""
        if rules.get("font_size") and content.get("font_size") != rules["font_size"]:
            result["issues"].append("原创性声明内容字体大小不符合要求")
            result["suggestions"].append(f"将原创性声明内容字体大小修改为 {rules['font_size']}pt")
            
        if rules.get("line_spacing") and content.get("line_spacing") != rules["line_spacing"]:
            result["issues"].append("原创性声明内容行距不符合要求")
            result["suggestions"].append(f"将原创性声明内容行距修改为 {rules['line_spacing']}")
            
    def _check_signature_format(self, signature: Dict[str, Any], rules: Dict[str, Any], result: Dict[str, Any]) -> None:
        """检查签名部分格式"""
        if rules.get("font_size") and signature.get("font_size") != rules["font_size"]:
            result["issues"].append("签名部分字体大小不符合要求")
            result["suggestions"].append(f"将签名部分字体大小修改为 {rules['font_size']}pt")
            
        if rules.get("alignment") and signature.get("alignment") != rules["alignment"]:
            result["issues"].append("签名部分对齐方式不符合要求")
            result["suggestions"].append(f"将签名部分对齐方式修改为 {rules['alignment']}")

class CopyrightStatementAgent(BaseAgent):
    """著作权使用声明格式解析Agent"""
    
    def __init__(self):
        super().__init__("copyright_statement_agent")
        
    def validate_input(self, input_data: Dict[str, Any]) -> bool:
        return "copyright_statement" in input_data
        
    def run(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        try:
            if not self.validate_input(input_data):
                raise ValueError("缺少著作权使用声明内容")
                
            statement_content = input_data["copyright_statement"]
            rules = self._load_rules()
            
            result = {
                "status": "success",
                "agent": self.name,
                "issues": [],
                "suggestions": []
            }
            
            # 检查标题格式
            if "title" in statement_content:
                self._check_title_format(statement_content["title"], rules.get("title", {}), result)
                
            # 检查声明内容格式
            if "content" in statement_content:
                self._check_content_format(statement_content["content"], rules.get("content", {}), result)
                
            # 检查签名部分格式
            if "signature" in statement_content:
                self._check_signature_format(statement_content["signature"], rules.get("signature", {}), result)
                
            return result
            
        except Exception as e:
            return self.handle_error(e)
            
    def _load_rules(self) -> Dict[str, Any]:
        """加载著作权使用声明格式规则"""
        try:
            with open(Config.get_prompts_path() + "/promots/xmu.ruler", "r", encoding="utf-8") as f:
                rules = json.load(f)
                return rules.get("copyright_statement", {})
        except Exception as e:
            logger.error(f"加载著作权使用声明规则失败: {str(e)}")
            raise
            
    def _check_title_format(self, title: Dict[str, Any], rules: Dict[str, Any], result: Dict[str, Any]) -> None:
        """检查标题格式"""
        if rules.get("font_size") and title.get("font_size") != rules["font_size"]:
            result["issues"].append("著作权使用声明标题字体大小不符合要求")
            result["suggestions"].append(f"将著作权使用声明标题字体大小修改为 {rules['font_size']}pt")
            
        if rules.get("alignment") and title.get("alignment") != rules["alignment"]:
            result["issues"].append("著作权使用声明标题对齐方式不符合要求")
            result["suggestions"].append(f"将著作权使用声明标题对齐方式修改为 {rules['alignment']}")
            
    def _check_content_format(self, content: Dict[str, Any], rules: Dict[str, Any], result: Dict[str, Any]) -> None:
        """检查声明内容格式"""
        if rules.get("font_size") and content.get("font_size") != rules["font_size"]:
            result["issues"].append("著作权使用声明内容字体大小不符合要求")
            result["suggestions"].append(f"将著作权使用声明内容字体大小修改为 {rules['font_size']}pt")
            
        if rules.get("line_spacing") and content.get("line_spacing") != rules["line_spacing"]:
            result["issues"].append("著作权使用声明内容行距不符合要求")
            result["suggestions"].append(f"将著作权使用声明内容行距修改为 {rules['line_spacing']}")
            
    def _check_signature_format(self, signature: Dict[str, Any], rules: Dict[str, Any], result: Dict[str, Any]) -> None:
        """检查签名部分格式"""
        if rules.get("font_size") and signature.get("font_size") != rules["font_size"]:
            result["issues"].append("签名部分字体大小不符合要求")
            result["suggestions"].append(f"将签名部分字体大小修改为 {rules['font_size']}pt")
            
        if rules.get("alignment") and signature.get("alignment") != rules["alignment"]:
            result["issues"].append("签名部分对齐方式不符合要求")
            result["suggestions"].append(f"将签名部分对齐方式修改为 {rules['alignment']}")

class ReferenceAgent(BaseAgent):
    """参考文献格式解析Agent"""
    
    def __init__(self):
        super().__init__("reference_agent")
        
    def validate_input(self, input_data: Dict[str, Any]) -> bool:
        # 待实现
        return True
        
    def run(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        try:
            if not self.validate_input(input_data):
                raise ValueError("输入数据无效")
                
            rules = self._load_rules(input_data)
            
            result = {
                "status": "success",
                "agent": self.name,
                "issues": [],
                "suggestions": []
            }
            
            # 使用FormatParser获取完整格式信息
            if "document" in input_data:
                parser = FormatParser(input_data["document"])
                reference_formats = self._extract_references(parser)
                
                # 检查每个参考文献的格式
                for reference_name, reference_content in reference_formats.items():
                    self._check_reference_format(reference_name, reference_content, rules, result)
            else:
                # 兼容旧版API
                references = input_data["references"]
                for reference_name, reference_content in references.items():
                    self._check_reference_format(reference_name, reference_content, rules, result)
                
            return result
            
        except Exception as e:
            logger.error(f"参考文献格式解析失败: {str(e)}", exc_info=True)
            return self.handle_error(e)
            
    def _load_rules(self, input_data: Dict[str, Any] = None) -> Dict[str, Any]:
        """加载参考文献格式规则"""
        try:
            # 首先尝试从input_data中获取规则文件路径
            if input_data and "ruler_path" in input_data:
                ruler_path = input_data["ruler_path"]
            else:
                # 否则使用Config获取路径
                ruler_path = Config.get_instance().get_prompts_path() + "/promots/xmu.ruler"
                
            with open(ruler_path, "r", encoding="utf-8") as f:
                rules = json.load(f)
                return rules.get("reference", {})
        except Exception as e:
            logger.error(f"加载参考文献规则失败: {str(e)}")
            raise
            
    def _extract_references(self, parser: FormatParser) -> Dict[str, Any]:
        """从文档中提取参考文献结构和格式信息"""
        references = {}
        current_reference = None
        reference_content = []
        
        # 遍历所有段落，按照标题级别组织参考文献结构
        for i, para in enumerate(parser.document.paragraphs):
            if not para.text.strip():
                continue
                
            para_format = parser.get_paragraph_format(para)
            style_name = para_format.get("style", "")
            
            # 判断是否为参考文献标题
            if style_name and ("Heading" in style_name or "标题" in style_name):
                # 如果已经有参考文献，保存前一参考文献
                if current_reference:
                    references[current_reference] = {
                        "title": reference_title,
                        "content": reference_content
                    }
                
                # 开始新参考文献
                current_reference = para.text
                reference_title = para_format
                reference_content = []
            elif current_reference:
                # 添加到当前参考文献内容
                reference_content.append(para_format)
            
        # 保存最后一个参考文献
        if current_reference:
            references[current_reference] = {
                "title": reference_title,
                "content": reference_content
            }
            
        return references
            
    def _check_reference_format(self, reference_name: str, reference_content: Dict[str, Any], rules: Dict[str, Any], result: Dict[str, Any]) -> None:
        """检查参考文献格式"""
        # 检查标题格式
        if "title" in rules and "title" in reference_content:
            title_format = reference_content["title"]
            title_rules = rules["title"]
            
            # 标题字体检查
            if title_rules.get("font") and title_format.get("font") != title_rules["font"]:
                result["issues"].append(f"参考文献 '{reference_name}' 字体不符合要求")
                result["suggestions"].append(f"将参考文献 '{reference_name}' 字体修改为 {title_rules['font']}")
                
            # 标题字号检查
            if title_rules.get("font_size"):
                rule_size = float(title_rules["font_size"])
                actual_size = title_format.get("size")
                if actual_size is not None:
                    actual_size = float(actual_size)
                    if abs(actual_size - rule_size) > 0.5:
                        result["issues"].append(f"参考文献 '{reference_name}' 字体大小不符合要求")
                        result["suggestions"].append(f"将参考文献 '{reference_name}' 字体大小修改为 {rule_size}pt")
                
            # 标题对齐方式检查
            if title_rules.get("alignment") is not None:
                rule_alignment = title_rules["alignment"]
                actual_alignment = title_format.get("alignment")
                if actual_alignment is not None and actual_alignment != rule_alignment:
                    result["issues"].append(f"参考文献 '{reference_name}' 对齐方式不符合要求")
                    result["suggestions"].append(f"将参考文献 '{reference_name}' 对齐方式修改为 {self._get_alignment_name(rule_alignment)}")
        
        # 检查正文格式
        if "content" in rules and "content" in reference_content:
            content_rules = rules["content"]
            
            for paragraph in reference_content["content"]:
                # 字体检查
                if content_rules.get("font") and paragraph.get("font") != content_rules["font"]:
                    result["issues"].append(f"参考文献 '{reference_name}' 正文字体不符合要求")
                    result["suggestions"].append(f"将参考文献 '{reference_name}' 正文字体修改为 {content_rules['font']}")
                    break
                    
                # 字号检查
                if content_rules.get("font_size"):
                    rule_size = float(content_rules["font_size"])
                    actual_size = paragraph.get("size")
                    if actual_size is not None:
                        actual_size = float(actual_size)
                        if abs(actual_size - rule_size) > 0.5:
                            result["issues"].append(f"参考文献 '{reference_name}' 正文字体大小不符合要求")
                            result["suggestions"].append(f"将参考文献 '{reference_name}' 正文字体大小修改为 {rule_size}pt")
                            break
                    
                # 对齐方式检查
                if content_rules.get("alignment") is not None:
                    rule_alignment = content_rules["alignment"]
                    actual_alignment = paragraph.get("alignment")
                    if actual_alignment is not None and actual_alignment != rule_alignment:
                        result["issues"].append(f"参考文献 '{reference_name}' 段落对齐方式不符合要求")
                        result["suggestions"].append(f"将参考文献 '{reference_name}' 段落对齐方式修改为 {self._get_alignment_name(rule_alignment)}")
                        break
        
        # 参考文献编号格式检查
        caption_rules = rules.get("caption", {})
        if "caption" in reference_content:
            caption = reference_content["caption"]
            
            # 字体大小检查
            if caption_rules.get("font_size"):
                rule_size = float(caption_rules["font_size"])
                actual_size = caption.get("size")
                if actual_size is not None:
                    actual_size = float(actual_size)
                    if abs(actual_size - rule_size) > 0.5:
                        result["issues"].append(f"参考文献 '{reference_name}' 编号字体大小不符合要求")
                        result["suggestions"].append(f"将参考文献 '{reference_name}' 编号字体大小修改为 {rule_size}pt")
            
            # 字体检查
            if caption_rules.get("font") and caption.get("font") != caption_rules["font"]:
                result["issues"].append(f"参考文献 '{reference_name}' 编号字体不符合要求")
                result["suggestions"].append(f"将参考文献 '{reference_name}' 编号字体修改为 {caption_rules['font']}")
                
            # 对齐方式检查
            if caption_rules.get("alignment") is not None:
                rule_alignment = caption_rules["alignment"]
                actual_alignment = caption.get("alignment")
                if actual_alignment is not None and actual_alignment != rule_alignment:
                    result["issues"].append(f"参考文献 '{reference_name}' 编号对齐方式不符合要求")
                    result["suggestions"].append(f"将参考文献 '{reference_name}' 编号对齐方式修改为 {self._get_alignment_name(rule_alignment)}")
                    
            # 格式检查（例如：文献[1]）
            if caption_rules.get("format") and "text" in caption:
                import re
                pattern = re.compile(caption_rules["format"])
                if not pattern.match(caption["text"]):
                    result["issues"].append(f"参考文献 '{reference_name}' 编号格式不符合要求")
                    result["suggestions"].append(f"参考文献编号应符合格式: {caption_rules['format']}")
                    
    def _get_alignment_name(self, alignment_value: int) -> str:
        """将对齐方式数值转换为名称"""
        alignment_map = {
            0: "左对齐",
            1: "居中",
            2: "右对齐",
            3: "两端对齐",
            4: "分散对齐"
        }
        return alignment_map.get(alignment_value, f"对齐方式{alignment_value}")

class FigureAgent(BaseAgent):
    """图表格式解析Agent"""
    
    def __init__(self):
        super().__init__("figure_agent")
        
    def validate_input(self, input_data: Dict[str, Any]) -> bool:
        # 待实现
        return True
        
    def run(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        try:
            if not self.validate_input(input_data):
                raise ValueError("输入数据无效")
                
            rules = self._load_rules(input_data)
            
            result = {
                "status": "success",
                "agent": self.name,
                "issues": [],
                "suggestions": []
            }
            
            # 使用FormatParser获取完整格式信息
            if "document" in input_data:
                parser = FormatParser(input_data["document"])
                figure_formats = self._extract_figures(parser)
                
                # 检查每个图表的格式
                for figure_name, figure_content in figure_formats.items():
                    self._check_figure_format(figure_name, figure_content, rules, result)
            else:
                # 兼容旧版API
                figures = input_data["figures"]
                for figure_name, figure_content in figures.items():
                    self._check_figure_format(figure_name, figure_content, rules, result)
                
            return result
            
        except Exception as e:
            logger.error(f"图表格式解析失败: {str(e)}", exc_info=True)
            return self.handle_error(e)
            
    def _load_rules(self, input_data: Dict[str, Any] = None) -> Dict[str, Any]:
        """加载图表格式规则"""
        try:
            # 首先尝试从input_data中获取规则文件路径
            if input_data and "ruler_path" in input_data:
                ruler_path = input_data["ruler_path"]
            else:
                # 否则使用Config获取路径
                ruler_path = Config.get_instance().get_prompts_path() + "/promots/xmu.ruler"
                
            with open(ruler_path, "r", encoding="utf-8") as f:
                rules = json.load(f)
                return rules.get("figure", {})
        except Exception as e:
            logger.error(f"加载图表规则失败: {str(e)}")
            raise
            
    def _extract_figures(self, parser: FormatParser) -> Dict[str, Any]:
        """从文档中提取图表结构和格式信息"""
        figures = {}
        current_figure = None
        figure_content = []
        
        # 遍历所有段落，按照标题级别组织图表结构
        for i, para in enumerate(parser.document.paragraphs):
            if not para.text.strip():
                continue
                
            para_format = parser.get_paragraph_format(para)
            style_name = para_format.get("style", "")
            
            # 判断是否为图表标题
            if style_name and ("Heading" in style_name or "标题" in style_name):
                # 如果已经有图表，保存前一图表
                if current_figure:
                    figures[current_figure] = {
                        "title": figure_title,
                        "content": figure_content
                    }
                
                # 开始新图表
                current_figure = para.text
                figure_title = para_format
                figure_content = []
            elif current_figure:
                # 添加到当前图表内容
                figure_content.append(para_format)
            
        # 保存最后一个图表
        if current_figure:
            figures[current_figure] = {
                "title": figure_title,
                "content": figure_content
            }
            
        return figures
            
    def _check_figure_format(self, figure_name: str, figure_content: Dict[str, Any], rules: Dict[str, Any], result: Dict[str, Any]) -> None:
        """检查图表格式"""
        # 检查标题格式
        if "title" in rules and "title" in figure_content:
            title_format = figure_content["title"]
            title_rules = rules["title"]
            
            # 标题字体检查
            if title_rules.get("font") and title_format.get("font") != title_rules["font"]:
                result["issues"].append(f"图表 '{figure_name}' 字体不符合要求")
                result["suggestions"].append(f"将图表 '{figure_name}' 字体修改为 {title_rules['font']}")
                
            # 标题字号检查
            if title_rules.get("font_size"):
                rule_size = float(title_rules["font_size"])
                actual_size = title_format.get("size")
                if actual_size is not None:
                    actual_size = float(actual_size)
                    if abs(actual_size - rule_size) > 0.5:
                        result["issues"].append(f"图表 '{figure_name}' 字体大小不符合要求")
                        result["suggestions"].append(f"将图表 '{figure_name}' 字体大小修改为 {rule_size}pt")
                
            # 标题对齐方式检查
            if title_rules.get("alignment") is not None:
                rule_alignment = title_rules["alignment"]
                actual_alignment = title_format.get("alignment")
                if actual_alignment is not None and actual_alignment != rule_alignment:
                    result["issues"].append(f"图表 '{figure_name}' 对齐方式不符合要求")
                    result["suggestions"].append(f"将图表 '{figure_name}' 对齐方式修改为 {self._get_alignment_name(rule_alignment)}")
        
        # 检查正文格式
        if "content" in rules and "content" in figure_content:
            content_rules = rules["content"]
            
            for paragraph in figure_content["content"]:
                # 字体检查
                if content_rules.get("font") and paragraph.get("font") != content_rules["font"]:
                    result["issues"].append(f"图表 '{figure_name}' 正文字体不符合要求")
                    result["suggestions"].append(f"将图表 '{figure_name}' 正文字体修改为 {content_rules['font']}")
                    break
                    
                # 字号检查
                if content_rules.get("font_size"):
                    rule_size = float(content_rules["font_size"])
                    actual_size = paragraph.get("size")
                    if actual_size is not None:
                        actual_size = float(actual_size)
                        if abs(actual_size - rule_size) > 0.5:
                            result["issues"].append(f"图表 '{figure_name}' 正文字体大小不符合要求")
                            result["suggestions"].append(f"将图表 '{figure_name}' 正文字体大小修改为 {rule_size}pt")
                            break
                    
                # 对齐方式检查
                if content_rules.get("alignment") is not None:
                    rule_alignment = content_rules["alignment"]
                    actual_alignment = paragraph.get("alignment")
                    if actual_alignment is not None and actual_alignment != rule_alignment:
                        result["issues"].append(f"图表 '{figure_name}' 段落对齐方式不符合要求")
                        result["suggestions"].append(f"将图表 '{figure_name}' 段落对齐方式修改为 {self._get_alignment_name(rule_alignment)}")
                        break
        
        # 图表编号格式检查
        caption_rules = rules.get("caption", {})
        if "caption" in figure_content:
            caption = figure_content["caption"]
            
            # 字体大小检查
            if caption_rules.get("font_size"):
                rule_size = float(caption_rules["font_size"])
                actual_size = caption.get("size")
                if actual_size is not None:
                    actual_size = float(actual_size)
                    if abs(actual_size - rule_size) > 0.5:
                        result["issues"].append(f"图表 '{figure_name}' 编号字体大小不符合要求")
                        result["suggestions"].append(f"将图表 '{figure_name}' 编号字体大小修改为 {rule_size}pt")
            
            # 字体检查
            if caption_rules.get("font") and caption.get("font") != caption_rules["font"]:
                result["issues"].append(f"图表 '{figure_name}' 编号字体不符合要求")
                result["suggestions"].append(f"将图表 '{figure_name}' 编号字体修改为 {caption_rules['font']}")
                
            # 对齐方式检查
            if caption_rules.get("alignment") is not None:
                rule_alignment = caption_rules["alignment"]
                actual_alignment = caption.get("alignment")
                if actual_alignment is not None and actual_alignment != rule_alignment:
                    result["issues"].append(f"图表 '{figure_name}' 编号对齐方式不符合要求")
                    result["suggestions"].append(f"将图表 '{figure_name}' 编号对齐方式修改为 {self._get_alignment_name(rule_alignment)}")
                    
            # 格式检查（例如：图1-1）
            if caption_rules.get("format") and "text" in caption:
                import re
                pattern = re.compile(caption_rules["format"])
                if not pattern.match(caption["text"]):
                    result["issues"].append(f"图表 '{figure_name}' 编号格式不符合要求")
                    result["suggestions"].append(f"图表编号应符合格式: {caption_rules['format']}")
                    
    def _get_alignment_name(self, alignment_value: int) -> str:
        """将对齐方式数值转换为名称"""
        alignment_map = {
            0: "左对齐",
            1: "居中",
            2: "右对齐",
            3: "两端对齐",
            4: "分散对齐"
        }
        return alignment_map.get(alignment_value, f"对齐方式{alignment_value}") 