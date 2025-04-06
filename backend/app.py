import os
from datetime import datetime
from flask import Flask, request, jsonify, send_file
from docx import Document
import requests
from dotenv import load_dotenv
from flask_cors import CORS
import io
import zipfile
from logger_config import logger
import threading
import time
import json
import uuid
from werkzeug.utils import secure_filename
from abc import ABC, abstractmethod
from lxml import etree
import re
from io import BytesIO
import traceback

# 获取当前文件所在目录的上级目录
base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# 构建.env文件的绝对路径
env_path = os.path.join(base_dir, '.env')

# 加载环境变量
logger.info(f'尝试加载环境变量文件: {env_path}')
if os.path.exists(env_path):
    load_dotenv(env_path)
    logger.info('成功加载环境变量文件')
else:
    logger.warning(f'环境变量文件不存在: {env_path}')

# 获取API配置
API_KEY = os.getenv('OPENAI_API_KEY')
API_BASE = os.getenv('OPENAI_API_BASE', 'https://api.moonshot.cn/v1')  # 默认使用 Kimi API
MODEL_NAME = os.getenv('MODEL_NAME', 'moonshot-v1-8k')  # 默认使用 Kimi 模型

# 记录API配置信息（注意不要记录完整的API密钥）
if API_KEY:
    # 只记录 API 密钥的前 6 位，其余用 * 代替
    masked_key = API_KEY[:6] + '*' * (len(API_KEY) - 6) if len(API_KEY) > 6 else '******'
    logger.info(f'API密钥已设置，前6位: {API_KEY[:6]}...')
else:
    logger.warning('API密钥未设置')
logger.info(f'API基础URL: {API_BASE}')
logger.info(f'模型名称: {MODEL_NAME}')

# 创建并发请求限制信号量，限制最大4个请求
request_semaphore = threading.Semaphore(4)
# 记录当前活跃请求数
active_requests = 0
# 保护活跃请求计数的锁
request_count_lock = threading.Lock()

# 创建上传会话存储
upload_sessions = {}

app = Flask(__name__)
CORS(app)

# 添加样式继承处理辅助函数

def extract_xml_style_info(paragraph):
    """
    从段落的XML数据中提取样式信息
    """
    if not hasattr(paragraph, '_p'):
        return {}
    
    try:
        xml_string = etree.tostring(paragraph._p, encoding='unicode', pretty_print=True)
        style_info = {}
        
        # 提取样式ID
        style_match = re.search(r'w:pStyle\s+w:val="([^"]+)"', xml_string)
        if style_match:
            style_info['style_id'] = style_match.group(1)
        
        # 提取行间距信息
        spacing_match = re.search(r'w:spacing\s+([^/]+?)/>', xml_string)
        if spacing_match:
            spacing_attrs = spacing_match.group(1)
            
            # 提取特定行间距属性
            line_rule_match = re.search(r'w:lineRule="([^"]+)"', spacing_attrs)
            if line_rule_match:
                style_info['line_rule'] = line_rule_match.group(1)
            
            line_match = re.search(r'w:line="([^"]+)"', spacing_attrs)
            if line_match:
                # Office Open XML中行间距单位是1/240英寸
                # 转换为1.5行距等更常见的格式
                line_value = int(line_match.group(1))
                if style_info.get('line_rule') == 'auto':
                    style_info['line_spacing'] = line_value / 240
                elif style_info.get('line_rule') == 'exact':
                    style_info['line_spacing_exact'] = line_value / 20  # 转换为磅值
                
            before_match = re.search(r'w:before="([^"]+)"', spacing_attrs)
            if before_match:
                style_info['space_before'] = int(before_match.group(1)) / 20  # 转换为磅值
                
            after_match = re.search(r'w:after="([^"]+)"', spacing_attrs)
            if after_match:
                style_info['space_after'] = int(after_match.group(1)) / 20  # 转换为磅值
        
        # 提取缩进信息
        indent_match = re.search(r'w:ind\s+([^/]+?)/>', xml_string)
        if indent_match:
            indent_attrs = indent_match.group(1)
            
            first_line_match = re.search(r'w:firstLine="([^"]+)"', indent_attrs)
            if first_line_match:
                # 单位是1/20磅
                style_info['first_line_indent'] = int(first_line_match.group(1)) / 20
            
            hanging_match = re.search(r'w:hanging="([^"]+)"', indent_attrs)
            if hanging_match:
                style_info['hanging_indent'] = int(hanging_match.group(1)) / 20
                
            left_match = re.search(r'w:left="([^"]+)"', indent_attrs)
            if left_match:
                style_info['left_indent'] = int(left_match.group(1)) / 20
                
            right_match = re.search(r'w:right="([^"]+)"', indent_attrs)
            if right_match:
                style_info['right_indent'] = int(right_match.group(1)) / 20
        
        # 提取直接应用的字体信息
        rpr_match = re.search(r'<w:rPr>(.*?)</w:rPr>', xml_string, re.DOTALL)
        if rpr_match:
            rpr_content = rpr_match.group(1)
            
            # 字体
            font_match = re.search(r'w:rFonts[^/>]*?w:ascii="([^"]+)"', rpr_content)
            if font_match:
                style_info['font_ascii'] = font_match.group(1)
                
            # 字体大小
            size_match = re.search(r'w:sz\s+w:val="([^"]+)"', rpr_content)
            if size_match:
                # 单位是半磅
                style_info['font_size'] = int(size_match.group(1)) / 2
            
            # 粗体
            bold_match = re.search(r'<w:b/>', rpr_content)
            if bold_match:
                style_info['bold'] = True
            
            # 斜体
            italic_match = re.search(r'<w:i/>', rpr_content)
            if italic_match:
                style_info['italic'] = True
        
        return style_info
    except Exception as e:
        logger.warning(f"提取XML样式信息失败: {str(e)}")
        return {}

def get_style_inheritance(style):
    """
    获取样式的继承链
    """
    if style is None:
        return []
    
    try:
        hierarchy = [style.name]
        
        # 检查样式类型和属性存在性
        if hasattr(style, 'base_style') and style.base_style is not None:
            hierarchy.extend(get_style_inheritance(style.base_style))
        
        return hierarchy
    except Exception as e:
        logger.warning(f"获取样式继承链失败: {str(e)}")
        return [getattr(style, 'name', '未知样式')] 

def get_merged_style_attributes(style):
    """
    获取样式属性，包括从继承的样式中合并的属性
    """
    if style is None:
        return {}
    
    try:
        # 获取基本样式属性
        attributes = {}
        
        # 首先检查样式类型，确保它支持我们要访问的属性
        style_type = type(style).__name__
        
        # 某些样式类型（如_NumberingStyle）没有base_style属性
        # 或者其他我们需要的属性，应该跳过这些属性的处理
        if hasattr(style, 'base_style') and style.base_style is not None:
            # 递归获取基础样式的属性
            base_attributes = get_merged_style_attributes(style.base_style)
            
            # 合并基础样式属性到当前属性集
            attributes.update(base_attributes)
        
        # 添加当前样式的属性，覆盖任何从基础样式继承的属性
        
        # 段落格式
        if hasattr(style, 'paragraph_format'):
            paragraph_format = {}
            
            # 对齐方式
            if hasattr(style.paragraph_format, 'alignment') and style.paragraph_format.alignment is not None:
                paragraph_format['alignment'] = style.paragraph_format.alignment
            
            # 首行缩进
            if hasattr(style.paragraph_format, 'first_line_indent') and style.paragraph_format.first_line_indent is not None:
                paragraph_format['first_line_indent'] = style.paragraph_format.first_line_indent.pt
            
            # 左缩进
            if hasattr(style.paragraph_format, 'left_indent') and style.paragraph_format.left_indent is not None:
                paragraph_format['left_indent'] = style.paragraph_format.left_indent.pt
            
            # 右缩进
            if hasattr(style.paragraph_format, 'right_indent') and style.paragraph_format.right_indent is not None:
                paragraph_format['right_indent'] = style.paragraph_format.right_indent.pt
            
            # 段前间距
            if hasattr(style.paragraph_format, 'space_before') and style.paragraph_format.space_before is not None:
                paragraph_format['space_before'] = style.paragraph_format.space_before.pt
            
            # 段后间距
            if hasattr(style.paragraph_format, 'space_after') and style.paragraph_format.space_after is not None:
                paragraph_format['space_after'] = style.paragraph_format.space_after.pt
            
            # 行间距
            if hasattr(style.paragraph_format, 'line_spacing') and style.paragraph_format.line_spacing is not None:
                paragraph_format['line_spacing'] = style.paragraph_format.line_spacing
            
            # 行间距规则
            if hasattr(style.paragraph_format, 'line_spacing_rule') and style.paragraph_format.line_spacing_rule is not None:
                paragraph_format['line_spacing_rule'] = style.paragraph_format.line_spacing_rule
            
            if paragraph_format:
                attributes['paragraph_format'] = paragraph_format
        
        # 字体格式
        if hasattr(style, 'font'):
            font = {}
            
            # 字体名称
            if hasattr(style.font, 'name') and style.font.name is not None:
                font['name'] = style.font.name
            
            # 字体大小
            if hasattr(style.font, 'size') and style.font.size is not None:
                font['size'] = style.font.size.pt
            
            # 粗体
            if hasattr(style.font, 'bold') and style.font.bold is not None:
                font['bold'] = style.font.bold
            
            # 斜体
            if hasattr(style.font, 'italic') and style.font.italic is not None:
                font['italic'] = style.font.italic
            
            # 下划线
            if hasattr(style.font, 'underline') and style.font.underline is not None:
                font['underline'] = style.font.underline
            
            # 颜色
            if hasattr(style.font, 'color') and style.font.color and hasattr(style.font.color, 'rgb'):
                font['color'] = style.font.color.rgb
            
            if font:
                attributes['font'] = font
        
        return attributes
    except Exception as e:
        logger.warning(f"获取样式继承属性失败: {str(e)}")
        return {}

def get_effective_paragraph_format(paragraph, doc):
    """
    获取段落的有效格式，考虑样式继承和直接格式设置
    """
    format_info = {
        'font_name': None,
        'font_size': None,
        'line_spacing': None,
        'first_line_indent': None,
        'paragraph_style': None
    }
    
    try:
        # 获取段落样式及其继承信息
        if hasattr(paragraph, 'style') and paragraph.style:
            # 保存样式名称
            format_info['paragraph_style'] = paragraph.style.name
            
            # 检查样式类型是否支持继承
            style_type = type(paragraph.style).__name__
            if style_type != '_NumberingStyle' and hasattr(paragraph.style, 'base_style'):
                # 获取合并后的样式属性
                style_attrs = get_merged_style_attributes(paragraph.style)
                
                # 提取字体信息
                if 'font' in style_attrs:
                    format_info['font_name'] = style_attrs['font'].get('name')
                    format_info['font_size'] = style_attrs['font'].get('size')
                
                # 提取段落格式
                if 'paragraph_format' in style_attrs:
                    format_info['line_spacing'] = style_attrs['paragraph_format'].get('line_spacing')
                    format_info['first_line_indent'] = style_attrs['paragraph_format'].get('first_line_indent')
        
        # 尝试从XML中获取直接格式设置
        xml_style = extract_xml_style_info(paragraph)
        
        # XML格式优先于样式设置
        if 'line_spacing' in xml_style:
            format_info['line_spacing'] = xml_style['line_spacing']
        
        if 'first_line_indent' in xml_style:
            format_info['first_line_indent'] = xml_style['first_line_indent']
        
        if 'font_size' in xml_style:
            format_info['font_size'] = xml_style['font_size']
        
        if 'font_ascii' in xml_style:
            format_info['font_name'] = xml_style['font_ascii']
        
        # 检查运行级别的格式
        run_fonts = set()
        run_sizes = set()
        
        for run in paragraph.runs:
            if not run.text.strip():
                continue
                
            # 收集运行级别的字体信息
            if hasattr(run, 'font') and hasattr(run.font, 'name') and run.font.name:
                run_fonts.add(run.font.name)
            
            if hasattr(run, 'font') and hasattr(run.font, 'size') and run.font.size:
                try:
                    run_sizes.add(run.font.size.pt)
                except:
                    pass
        
        # 如果所有运行使用相同的字体，则更新段落字体
        if len(run_fonts) == 1:
            format_info['font_name'] = next(iter(run_fonts))
        
        # 如果所有运行使用相同的字体大小，则更新段落字体大小
        if len(run_sizes) == 1:
            format_info['font_size'] = next(iter(run_sizes))
        
        # 直接从段落格式获取缩进和行间距（如果可用）
        if hasattr(paragraph, 'paragraph_format'):
            if (hasattr(paragraph.paragraph_format, 'first_line_indent') and 
                paragraph.paragraph_format.first_line_indent is not None and 
                format_info['first_line_indent'] is None):
                try:
                    format_info['first_line_indent'] = paragraph.paragraph_format.first_line_indent.pt
                except:
                    pass
            
            if (hasattr(paragraph.paragraph_format, 'line_spacing') and 
                paragraph.paragraph_format.line_spacing is not None and 
                format_info['line_spacing'] is None):
                format_info['line_spacing'] = paragraph.paragraph_format.line_spacing
    except Exception as e:
        logger.warning(f"获取段落有效格式失败: {str(e)}")
    
    return format_info

# 添加格式检查器的抽象基类
class FormatChecker(ABC):
    """
    论文格式检查器抽象基类
    """
    def __init__(self, template_name):
        self.template_name = template_name
        self.ruler_content = self._get_ruler_content()
        
    def _get_ruler_content(self):
        """获取对应模板的ruler文件内容"""
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        ruler_file = os.path.join(base_dir, 'promots', f'{self.template_name}.ruler')
        
        if not os.path.exists(ruler_file):
            logger.error(f'模板文件 {ruler_file} 不存在')
            raise FileNotFoundError(f'模板文件 {ruler_file} 不存在')
        
        with open(ruler_file, 'r', encoding='utf-8') as f:
            content = f.read().strip()
            logger.debug(f'已加载模板文件 {ruler_file}')
            return content
    
    @abstractmethod
    def extract_format_info(self, docx_content):
        """提取文档的格式信息"""
        pass
    
    @abstractmethod
    def generate_user_prompt(self, format_info):
        """生成用户提示词"""
        pass
    
    def get_system_prompt(self):
        """获取system角色的提示词"""
        return self.ruler_content
    
    def check_format(self, docx_content):
        """
        检查文档格式
        返回: (system_prompt, user_prompt)
        """
        format_info = self.extract_format_info(docx_content)
        user_prompt = self.generate_user_prompt(format_info)
        return self.get_system_prompt(), user_prompt, format_info

# 厦门大学论文格式检查器
class XmuFormatChecker(FormatChecker):
    """厦门大学论文格式检查器"""
    
    def extract_format_info(self, docx_content):
        """提取论文格式信息"""
        logger.info("开始提取论文格式信息")
        
        # 初始化格式信息
        format_info = {
            "has_cover": False,
            "has_blind_cover": False,
            "cover_info": {},
            "cover_page": 1,  # 默认封面在第一页
            "title": "",
            "abstract": "",
            "abstract_word_count": 0,
            "abstract_paragraphs": [],
            "abstract_title_position": -1,
            "abstract_keywords_position": -1,
            "eng_abstract": "",
            "eng_abstract_length": 0,
            "eng_abstract_word_count": 0,
            "eng_abstract_paragraphs": [],
            "eng_abstract_title_position": -1,
            "eng_abstract_keywords_position": -1,
            "abstract_keywords": [],
            "eng_keywords": [],
            "has_toc": False,
            "toc_info": {
                "type": "",
                "position": -1,
                "items": [],
                "items_detail": [],
                "eng_position": -1,
                "eng_items": [],
                "eng_items_detail": [],
                "items_count": 0,
                "eng_items_count": 0
            },
            "fonts": set(),
            "font_sizes": set(),
            "line_spacing": set(),
            "first_line_indents": set(),
            "typical_paragraph_format": {},
            "heading_counts": {"h1": 0, "h2": 0, "h3": 0},
            "has_references": False,
            "references_count": 0,
            "has_appendix": False,
            "has_acknowledgement": False,
            "acknowledgement_text": "",
            "tables_count": 0,
            "figures_count": 0,
            "equations_count": 0,
            "tables_info": [],
            "figures_info": [],
            "equations_info": [],
            "headers": [],
            "footers": [],
            "page_margins": {},
            "header_compliance": {},
            "paragraph_styles": {},
            "chapter_titles": [],
            "section_titles": [],
            "subsection_titles": [],
            "spacing": []
        }
        
        try:
            # 将二进制内容转换为BytesIO对象（如果还不是）
            if isinstance(docx_content, BytesIO):
                doc = Document(docx_content)
            else:
                docx_file = BytesIO(docx_content)
                doc = Document(docx_file)
            
            # 提取文档信息
            logger.debug(f"文档段落数: {len(doc.paragraphs)}")
            logger.debug(f"文档表格数: {len(doc.tables)}")
            logger.debug(f"文档页面数: {len(doc.sections)}")
            
            # 使用专门方法提取封面信息
            self._extract_cover_info(doc, format_info)
            
            # 使用专门方法提取目录信息
            self._extract_toc_info(doc, format_info)
            
            # 使用专门方法提取摘要信息
            self._extract_abstract_info(doc, format_info)
            
            # 使用专门方法提取图表信息
            self._extract_figures_tables_info(doc, format_info)
            
            # 使用专门方法提取公式信息
            self._extract_equations_info(doc, format_info)
            
            # 使用专门方法提取标题信息
            self._extract_heading_info(doc, format_info)
            
            # 使用专门方法提取参考文献信息
            self._extract_references_info(doc, format_info)
            
            # 使用专门方法提取致谢信息
            self._extract_acknowledgement_info(doc, format_info)
            
            # 使用专门方法提取格式信息
            self._extract_formatting_info(doc, format_info)
            
            # 转换集合为列表，方便JSON序列化
            format_info["fonts"] = list(format_info["fonts"])
            format_info["font_sizes"] = list(format_info["font_sizes"])
            format_info["line_spacing"] = list(format_info["line_spacing"])
            format_info["first_line_indents"] = list(format_info["first_line_indents"])
            
            return format_info
            
        except Exception as e:
            logger.error(f"提取论文格式信息时出错: {str(e)}")
            logger.error(traceback.format_exc())
            return format_info
    
    def _extract_figures_tables_info(self, doc, format_info):
        """
        提取文档中的图表信息
        
        Args:
            doc: Document对象
            format_info: 格式信息字典
        """
        logger.info("提取图表信息")
        
        # 正则表达式模式
        figure_pattern = re.compile(r'图\s*(\d+(?:[\.﹒-]\d+)?)\s*(.*)')
        table_pattern = re.compile(r'表\s*(\d+(?:[\.﹒-]\d+)?)\s*(.*)')
        
        # 用于过滤的引用性词语
        reference_words = ['所示', '如图', '如表', '见图', '见表', '中', '可见', '可以看出', '引用']
        
        for i, p in enumerate(doc.paragraphs):
            text = p.text.strip()
            if not text:
                continue
            
            # 识别表格
            table_match = table_pattern.search(text)
            if table_match:
                table_num = table_match.group(1)
                table_title = table_match.group(2).strip()
                
                # 过滤掉引用性质的内容，如"表4-1 所示。"
                is_reference = False
                if any(word in text for word in reference_words) or len(table_title) < 3:
                    # 如果包含引用词语或标题过短，可能是引用而非实际表格标题
                    is_reference = True
                    logger.debug(f"过滤引用内容: '{text}'")
                    continue
                
                # 过滤句子中间出现的"表4-1"这样的引用
                if not text.startswith('表') or '。' in text[:10] or '，' in text[:10] or '；' in text[:10]:
                    logger.debug(f"过滤非标题开头的表格引用: '{text}'")
                    continue
                
                format_info["tables_count"] += 1
                
                # 记录日志
                logger.debug(f"在第{i}段找到表格: 表{table_num} {table_title}")
                
                # 检查格式是否符合要求
                is_centered = p.alignment == 1  # 1表示居中对齐
                is_bold = any(run.font.bold for run in p.runs if hasattr(run.font, 'bold') and run.font.bold)
                
                # 记录表格格式
                if is_centered:
                    logger.debug(f"表格标题居中: 是")
                else:
                    logger.debug(f"表格标题居中: 否")
                    
                if is_bold:
                    logger.debug(f"表格标题加粗: 是")
                else:
                    logger.debug(f"表格标题加粗: 否")
                
                format_info["tables_info"].append({
                    "position": i,
                    "number": table_num,
                    "title": table_title,
                    "is_centered": is_centered,
                    "is_bold": is_bold,
                    "full_text": text
                })
            
            # 识别图形
            figure_match = figure_pattern.search(text)
            if figure_match:
                figure_num = figure_match.group(1)
                figure_title = figure_match.group(2).strip()
                
                # 过滤掉引用性质的内容，如"图4-1 所示。"
                is_reference = False
                if any(word in text for word in reference_words) or len(figure_title) < 3:
                    # 如果包含引用词语或标题过短，可能是引用而非实际图形标题
                    is_reference = True
                    logger.debug(f"过滤引用内容: '{text}'")
                    continue
                
                # 过滤句子中间出现的"图4-1"这样的引用
                if not text.startswith('图') or '。' in text[:10] or '，' in text[:10] or '；' in text[:10]:
                    logger.debug(f"过滤非标题开头的图形引用: '{text}'")
                    continue
                
                format_info["figures_count"] += 1
                
                # 记录日志
                logger.debug(f"在第{i}段找到图形: 图{figure_num} {figure_title}")
                
                # 检查格式是否符合要求
                is_centered = p.alignment == 1  # 1表示居中对齐
                is_bold = any(run.font.bold for run in p.runs if hasattr(run.font, 'bold') and run.font.bold)
                
                # 记录图形格式
                if is_centered:
                    logger.debug(f"图形标题居中: 是")
                else:
                    logger.debug(f"图形标题居中: 否")
                    
                if is_bold:
                    logger.debug(f"图形标题加粗: 是")
                else:
                    logger.debug(f"图形标题加粗: 否")
                
                format_info["figures_info"].append({
                    "position": i,
                    "number": figure_num,
                    "title": figure_title,
                    "is_centered": is_centered,
                    "is_bold": is_bold,
                    "full_text": text
                })
        
        logger.info(f"找到图形数量: {format_info['figures_count']}, 表格数量: {format_info['tables_count']}")
    
    def _extract_equations_info(self, doc, format_info):
        """
        提取文档中的公式信息
        
        Args:
            doc: Document对象
            format_info: 格式信息字典
        """
        logger.info("提取公式信息")
        
        # 正则表达式模式
        equation_pattern = re.compile(r'\(\s*\d+[\.﹒-]\d+\s*\)')
        
        # 排除词语列表 - 用于过滤非公式内容
        exclusion_words = ['请在', '填写', '打勾', '打"√"', '选择', '说明', '涉密', '厦门大学', '学位论文', 
                           '委员会', '审定', '公开', '声明', '默认', '上述', '授权', '知识产权']
        
        for i, p in enumerate(doc.paragraphs):
            text = p.text.strip()
            if not text:
                continue
            
            # 检查文本是否包含排除词语，如果包含则跳过
            if any(word in text for word in exclusion_words):
                logger.debug(f"跳过包含排除词语的内容: '{text[:50]}...'")
                continue
                
            # 文本长度过长可能不是公式（真正的公式通常较短）
            if len(text) > 150 and '=' not in text:
                continue
            
            # 增强公式识别逻辑
            if ('公式' in text or equation_pattern.search(text)) and not text.startswith('（请'):
                # 验证是否确实是公式而非普通文本
                if '=' in text or re.search(r'[+\-*/^]', text):
                    format_info["equations_count"] += 1
                    equation_match = equation_pattern.search(text)
                    equation_num = equation_match.group(0) if equation_match else ""
                    
                    logger.debug(f"在第{i}段找到公式: '{text}'")
                    if equation_num:
                        logger.debug(f"公式编号: {equation_num}")
                    
                    format_info["equations_info"].append({
                        "position": i,
                        "text": text,
                        "number": equation_num
                    })
            # 识别带有数学符号的公式，同时检查是否为真正的公式
            elif any(symbol in text for symbol in ['∑', '∫', '∏', '√', '∞', '∂', '∇', '∆', '≠', '≥', '≤']):
                # 确保文本不是普通说明文字
                if not any(word in text for word in exclusion_words) and len(text) < 150:
                    # 进一步验证是否确实是公式
                    has_math_content = (
                        '=' in text or 
                        re.search(r'[+\-*/^]', text) or
                        re.search(r'\b[a-zA-Z]\s*[=<>]\s*\d', text) or  # 变量赋值形式
                        text.count('(') + text.count('（') <= 3  # 限制括号数量
                    )
                    
                    if has_math_content:
                        format_info["equations_count"] += 1
                        logger.debug(f"在第{i}段找到数学符号公式: '{text}'")
                        
                        format_info["equations_info"].append({
                            "position": i,
                            "text": text,
                            "number": ""
                        })
                    else:
                        logger.debug(f"跳过包含数学符号但可能不是公式的内容: '{text[:50]}...'")
        
        logger.info(f"找到公式数量: {format_info['equations_count']}")
    
    def _extract_abstract_info(self, doc, format_info):
        """
        提取文档中的摘要信息
        
        Args:
            doc: Document对象
            format_info: 格式信息字典
        """
        logger.info("提取摘要信息")
        
        abstract_found = False
        eng_abstract_found = False
        
        for i, p in enumerate(doc.paragraphs):
            text = p.text.strip()
            if not text:
                continue
            
            # 检测中文摘要
            # 中文摘要信息以"摘　要"起始，以"关键词"结束，在"关键词"之前的段落都是中文摘要
            if not abstract_found and (text == '摘要' or text == '摘  要' or text == '摘　要' or text.startswith('摘要')):
                abstract_found = True
                logger.debug(f"在第{i}段找到中文摘要标题: '{text}'")
                format_info["abstract_title_position"] = i  # 记录摘要标题位置
                continue
                
            if abstract_found and not eng_abstract_found:
                # 如果已找到摘要标题，判断是否已到关键词部分
                if '关键词' in text:
                    # 中文摘要结束
                    format_info["abstract_keywords_position"] = i  # 记录关键词位置
                    
                    keywords_text = text.split('关键词', 1)[1].strip()
                    if keywords_text.startswith('：') or keywords_text.startswith(':'):
                        keywords_text = keywords_text[1:].strip()
                    # 分割关键词并清理空格
                    keywords = [k.strip() for k in re.split(r'[,，;；]', keywords_text) if k.strip()]
                    format_info["abstract_keywords"] = keywords
                    logger.debug(f"中文关键词: {keywords}")
                    
                # 如果遇到英文摘要标记，则退出中文摘要收集
                elif text.startswith('Abstract') or text == 'Abstract' or text == 'ABSTRACT':
                    eng_abstract_found = True
                    format_info["eng_abstract_title_position"] = i  # 记录英文摘要标题位置
                    logger.debug(f"在第{i}段找到英文摘要标题: '{text}'")
                    continue
                    
                # 否则，将当前段落添加到摘要中
                elif len(text) > 5:  # 避免收集太短的段落
                    format_info["abstract"] += text + "\n"
                    format_info["abstract_paragraphs"].append({
                        "text": text,
                        "position": i,
                        "is_bold": any(run.font.bold for run in p.runs if hasattr(run.font, 'bold') and run.font.bold),
                        "is_centered": p.alignment == 1 if hasattr(p, 'alignment') else False
                    })
                    logger.debug(f"添加中文摘要段落: '{text[:30]}...'")
            
            # 检测英文摘要
            elif eng_abstract_found:
                # 如果已找到英文摘要标题，判断是否已到关键词部分
                if 'Key words' in text or 'Keywords' in text or 'KEYWORDS' in text:
                    format_info["eng_abstract_keywords_position"] = i  # 记录英文关键词位置
                    
                    keywords_text = text.lower().replace('key words', '').replace('keywords', '').strip()
                    if keywords_text.startswith('：') or keywords_text.startswith(':'):
                        keywords_text = keywords_text[1:].strip()
                    # 分割关键词并清理空格
                    keywords = [k.strip() for k in re.split(r'[,，;；]', keywords_text) if k.strip()]
                    format_info["eng_keywords"] = keywords
                    logger.debug(f"英文关键词: {keywords}")
                    break  # 找到英文关键词后，摘要部分结束
                    
                # 如果遇到目录标记，则退出英文摘要收集
                elif text == '目录' or text == 'Contents' or text.lower() == 'contents':
                    logger.debug(f"在第{i}段遇到目录标题，英文摘要收集结束")
                    break
                    
                # 否则，将当前段落添加到英文摘要中
                elif len(text) > 5 and not text.startswith('Chapter') and not re.match(r'^\d+\.\s', text):
                    format_info["eng_abstract"] += text + "\n"
                    format_info["eng_abstract_paragraphs"].append({
                        "text": text,
                        "position": i,
                        "is_bold": any(run.font.bold for run in p.runs if hasattr(run.font, 'bold') and run.font.bold),
                        "is_centered": p.alignment == 1 if hasattr(p, 'alignment') else False
                    })
                    logger.debug(f"添加英文摘要段落: '{text[:30]}...'")
        
        # 计算摘要字数
        format_info["abstract_word_count"] = len(format_info["abstract"].replace('\n', ''))
        format_info["eng_abstract_word_count"] = len(re.findall(r'\b\w+\b', format_info["eng_abstract"]))
        format_info["eng_abstract_length"] = len(format_info["eng_abstract"])
        
        # 如果没有在初始化时添加这些字段，需要添加
        if "abstract_paragraphs" not in format_info:
            format_info["abstract_paragraphs"] = []
        if "eng_abstract_paragraphs" not in format_info:
            format_info["eng_abstract_paragraphs"] = []
        
        logger.info(f"中文摘要字数: {format_info['abstract_word_count']}")
        logger.info(f"英文摘要单词数: {format_info['eng_abstract_word_count']}")
        
        # 检查摘要格式是否符合要求
        if format_info["abstract_word_count"] < 200:
            logger.warning(f"中文摘要字数不足200字，当前字数: {format_info['abstract_word_count']}")
        if format_info["eng_abstract_word_count"] < 50:
            logger.warning(f"英文摘要单词数不足50个，当前单词数: {format_info['eng_abstract_word_count']}")
        
        # 检查关键词
        if len(format_info["abstract_keywords"]) < 3:
            logger.warning(f"中文关键词数量少于3个，当前数量: {len(format_info['abstract_keywords'])}")
        if len(format_info["eng_keywords"]) < 3:
            logger.warning(f"英文关键词数量少于3个，当前数量: {len(format_info['eng_keywords'])}")
    
    def _extract_heading_info(self, doc, format_info):
        """
        提取文档中的标题信息
        
        Args:
            doc: Document对象
            format_info: 格式信息字典
        """
        logger.info("提取标题信息")
        
        # 正则表达式模式
        heading1_pattern = re.compile(r'^第[一二三四五六七八九十\d]+章\s+\S+')
        heading2_pattern = re.compile(r'^第[一二三四五六七八九十\d]+节\s+\S+')
        heading3_pattern = re.compile(r'^[一二三四五六七八九十\d]+、\s*\S+')
        
        for i, p in enumerate(doc.paragraphs):
            text = p.text.strip()
            if not text:
                continue
            
            # 检查标题层级
            if heading1_pattern.match(text):
                format_info["heading_counts"]["h1"] += 1
                format_info["chapter_titles"].append({"position": i, "title": text})
                logger.debug(f"在第{i}段找到一级标题: '{text}'")
            elif heading2_pattern.match(text):
                format_info["heading_counts"]["h2"] += 1
                format_info["section_titles"].append({"position": i, "title": text})
                logger.debug(f"在第{i}段找到二级标题: '{text}'")
            elif heading3_pattern.match(text):
                format_info["heading_counts"]["h3"] += 1
                format_info["subsection_titles"].append({"position": i, "title": text})
                logger.debug(f"在第{i}段找到三级标题: '{text}'")
        
        logger.info(f"一级标题数量: {format_info['heading_counts']['h1']}")
        logger.info(f"二级标题数量: {format_info['heading_counts']['h2']}")
        logger.info(f"三级标题数量: {format_info['heading_counts']['h3']}")
    
    def _extract_references_info(self, doc, format_info):
        """
        提取文档中的参考文献信息
        
        Args:
            doc: Document对象
            format_info: 格式信息字典
        """
        logger.info("提取参考文献信息")
        
        references_found = False
        ref_items = []
        
        for i, p in enumerate(doc.paragraphs):
            text = p.text.strip()
            if not text:
                continue
            
            # 检测参考文献部分
            if not references_found and (text == '参考文献' or text == 'References' or text.startswith('参考文献')):
                references_found = True
                format_info["has_references"] = True
                logger.debug(f"在第{i}段找到参考文献标题: '{text}'")
                continue
                
            if references_found:
                # 如果遇到附录或致谢，则参考文献部分结束
                if text == '附录' or text == 'Appendix' or text == '致谢' or text == 'Acknowledgment':
                    break
                    
                # 检查是否是参考文献条目
                is_ref_item = re.match(r'^\[\d+\]', text) or re.match(r'^\d+\.', text)
                if is_ref_item:
                    ref_items.append(text)
                    logger.debug(f"添加参考文献项: '{text}'")
                    format_info["references_count"] += 1
        
        logger.info(f"参考文献数量: {format_info['references_count']}")
    
    def _extract_acknowledgement_info(self, doc, format_info):
        """
        提取文档中的致谢信息
        
        Args:
            doc: Document对象
            format_info: 格式信息字典
        """
        logger.info("提取致谢信息")
        
        acknowledgement_found = False
        
        for i, p in enumerate(doc.paragraphs):
            text = p.text.strip()
            if not text:
                continue
            
            # 检测致谢部分
            if not acknowledgement_found and (text == '致谢' or text == 'Acknowledgment' or text.startswith('致谢')):
                acknowledgement_found = True
                format_info["has_acknowledgement"] = True
                logger.debug(f"在第{i}段找到致谢标题: '{text}'")
                continue
                
            if acknowledgement_found:
                # 如果遇到附录或参考文献，则致谢部分结束
                if text == '附录' or text == 'Appendix' or text == '参考文献' or text == 'References':
                    break
                    
                # 添加致谢内容
                if len(text) > 5:
                    format_info["acknowledgement_text"] += text + "\n"
                    logger.debug(f"添加致谢内容: '{text[:30]}...'")
        
        if format_info["has_acknowledgement"]:
            logger.info(f"找到致谢内容，长度: {len(format_info['acknowledgement_text'])}")
    
    def _extract_formatting_info(self, doc, format_info):
        """
        提取文档中的格式信息，如字体、行距等
        
        Args:
            doc: Document对象
            format_info: 格式信息字典
        """
        logger.info("提取格式信息")
        
        # 收集页面边距信息
        for section in doc.sections:
            if section.top_margin and section.bottom_margin and section.left_margin and section.right_margin:
                margins = {
                    "top": section.top_margin.cm,
                    "bottom": section.bottom_margin.cm,
                    "left": section.left_margin.cm,
                    "right": section.right_margin.cm
                }
                format_info["page_margins"] = margins
                logger.debug(f"页面边距: 上={margins['top']}cm, 下={margins['bottom']}cm, 左={margins['left']}cm, 右={margins['right']}cm")
        
        # 收集页眉页脚信息
        for section in doc.sections:
            if section.header:
                for p in section.header.paragraphs:
                    if p.text.strip():
                        format_info["headers"].append(p.text.strip())
                        logger.debug(f"页眉: '{p.text.strip()}'")
            
            if section.footer:
                for p in section.footer.paragraphs:
                    if p.text.strip():
                        format_info["footers"].append(p.text.strip())
                        logger.debug(f"页脚: '{p.text.strip()}'")
        
        # 收集字体和段落格式信息
        for p in doc.paragraphs:
            if not p.text.strip():
                continue
                
            # 收集字体信息
            for run in p.runs:
                if run.font.name:
                    format_info["fonts"].add(run.font.name)
                if run.font.size and hasattr(run.font.size, 'pt'):
                    format_info["font_sizes"].add(run.font.size.pt)
            
            # 收集段落格式信息
            if p.paragraph_format:
                if p.paragraph_format.line_spacing:
                    format_info["line_spacing"].add(p.paragraph_format.line_spacing)
                
                if p.paragraph_format.first_line_indent and hasattr(p.paragraph_format.first_line_indent, 'pt'):
                    format_info["first_line_indents"].add(round(p.paragraph_format.first_line_indent.pt, 1))
        
        logger.info(f"字体种类: {len(format_info['fonts'])}")
        logger.info(f"字号种类: {len(format_info['font_sizes'])}")
        logger.info(f"行距种类: {len(format_info['line_spacing'])}")
        logger.info(f"首行缩进种类: {len(format_info['first_line_indents'])}")

    def generate_user_prompt(self, format_info):
        """生成厦门大学论文格式检查的用户提示词"""
        # 处理字体大小格式
        font_sizes_str = ', '.join(map(str, format_info.get('font_sizes', []))) if format_info.get('font_sizes') else '未检测到'
        
        # 处理首行缩进格式  
        first_line_indents_str = ', '.join(map(str, format_info.get('first_line_indents', []))) if format_info.get('first_line_indents') else '未检测到'
        
        # 处理常见页边距信息
        common_margins = format_info.get('common_margins', {})
        common_margins_str = ""
        if common_margins:
            try:
                # 确保sections是有效的列表或数组类型
                sections_count = format_info.get('sections', 0)
                if isinstance(sections_count, int):
                    sections_total = sections_count
                else:
                    sections_total = len(sections_count)
                
                common_margins_str = f"（最常见设置：左{common_margins.get('left')}cm, 右{common_margins.get('right')}cm，占{common_margins.get('sections_count')}/{sections_total}个章节）"
            except (TypeError, AttributeError):
                common_margins_str = f"（最常见设置：左{common_margins.get('left')}cm, 右{common_margins.get('right')}cm）"
        
        # 获取合规性检查结果
        compliance = format_info.get('compliance', {})
        compliant_items = compliance.get('compliant_items', [])
        non_compliant_items = compliance.get('non_compliant_items', [])
        unknown_items = compliance.get('unknown_items', [])
        
        # 构建合规性报告部分
        compliance_report = ""
        if compliant_items:
            compliance_report += "\n\n符合规范的项目："
            for item in compliant_items:
                compliance_report += f"\n- {item}"
                
        if non_compliant_items:
            compliance_report += "\n\n不符合规范的项目："
            for item in non_compliant_items:
                compliance_report += f"\n- {item}"
                
        if unknown_items:
            compliance_report += "\n\n未能判断的项目："
            for item in unknown_items:
                compliance_report += f"\n- {item}"
        
        prompt = f"""请根据厦门大学学位论文格式规范，分析以下论文格式信息，判断是否符合要求：

        1. 基本信息：
        - 总段落数：{format_info.get('paragraphs', '未检测到')}
        - 章节数：{format_info.get('sections', '未检测到')}
        
        2. 字体与样式：
        - 使用的样式：{', '.join(format_info.get('styles', ['未检测到']))}
        - 使用的字体：{', '.join(format_info.get('fonts', ['未检测到']))}
        - 字体大小：{font_sizes_str}
        
        3. 段落格式：
        - 行间距：{', '.join(map(str, format_info.get('spacing', ['未检测到'])))}
        - 首行缩进：{first_line_indents_str}
        
        4. 页面设置：
        - 页眉信息：{', '.join(format_info.get('headers', [])) if format_info.get('headers') else '无'}
        - 页脚信息：{', '.join(format_info.get('footers', [])) if format_info.get('footers') else '无'}
        - 页边距：上{format_info.get('page_margins', {}).get('top', '未检测到')}cm, 下{format_info.get('page_margins', {}).get('bottom', '未检测到')}cm, 左{format_info.get('page_margins', {}).get('left', '未检测到')}cm, 右{format_info.get('page_margins', {}).get('right', '未检测到')}cm {common_margins_str}

        5. 标题层级：
        - 章标题示例：{format_info.get('chapter_titles', ['未检测到'])[0] if format_info.get('chapter_titles') else '未检测到'}
        - 节标题示例：{format_info.get('section_titles', ['未检测到'])[0] if format_info.get('section_titles') else '未检测到'}
        - 子标题示例：{format_info.get('subsection_titles', ['未检测到'])[0] if format_info.get('subsection_titles') else '未检测到'}
        - 一级标题数量：{len(format_info.get('chapter_titles', []))}个
        - 二级标题数量：{len(format_info.get('section_titles', []))}个
        - 三级标题数量：{len(format_info.get('subsection_titles', []))}个

        6. 摘要和关键词：
        - 中文摘要：{format_info.get('abstract', '')[:100] + '...' if format_info.get('abstract') else '未检测到'}
        - 中文摘要字数：{format_info.get('abstract_word_count', 0)}字
        - 中文关键词：{', '.join(format_info.get('abstract_keywords', [])) if format_info.get('abstract_keywords') else '未检测到'}
        - 英文摘要：{format_info.get('eng_abstract', '')[:100] + '...' if format_info.get('eng_abstract') else '未检测到'}
        - 英文摘要长度：{format_info.get('eng_abstract_length', 0)}字符
        - 英文摘要单词数：{format_info.get('eng_abstract_word_count', 0)}个单词
        - 英文关键词：{', '.join(format_info.get('eng_keywords', [])) if format_info.get('eng_keywords') else '未检测到'}
        
        7. 目录信息：
        - 目录类型：{format_info.get('toc_info', {}).get('type', '未检测到')}
        
        8. 图表与公式：
        - 表格数量：{format_info.get('tables_count', 0)}个
        - 图形数量：{format_info.get('figures_count', 0)}个
        - 公式数量：{format_info.get('equations_count', 0)}个
        
        9. 参考文献与附录：
        - 参考文献：{'已提供' if format_info.get('has_references') else '未检测到'}
        - 附录：{'已提供' if format_info.get('has_appendix') else '未检测到'}
        - 致谢：{'已提供' if format_info.get('has_acknowledgement') else '未检测到'}
        {compliance_report}

        请详细说明该论文是否符合厦门大学学位论文格式规范，如有不符合的地方，请具体指出并给出修改建议。按照封面格式、摘要与关键词、目录、正文格式、图表格式、参考文献等方面逐一分析。"""
                
        return prompt

    def _analyze_figures_tables_format(self, format_info):
        """分析图表格式是否符合规范"""
        result = {
            "tables": {
                "count": format_info["tables_count"],
                "centered_count": 0,
                "bold_count": 0,
                "format_compliant": False,
                "sample_info": []
            },
            "figures": {
                "count": format_info["figures_count"],
                "centered_count": 0,
                "bold_count": 0,
                "format_compliant": False,
                "sample_info": []
            }
        }
        
        # 分析表格格式
        for table_info in format_info.get("tables_info", [])[:5]:  # 只取前5个作为样本
            if table_info.get("is_centered", False):
                result["tables"]["centered_count"] += 1
            if table_info.get("is_bold", False):
                result["tables"]["bold_count"] += 1
            
            result["tables"]["sample_info"].append({
                "number": table_info.get("number", ""),
                "title": table_info.get("title", ""),
                "is_centered": table_info.get("is_centered", False),
                "is_bold": table_info.get("is_bold", False)
            })
        
        # 分析图形格式
        for figure_info in format_info.get("figures_info", [])[:5]:  # 只取前5个作为样本
            if figure_info.get("is_centered", False):
                result["figures"]["centered_count"] += 1
            if figure_info.get("is_bold", False):
                result["figures"]["bold_count"] += 1
            
            result["figures"]["sample_info"].append({
                "number": figure_info.get("number", ""),
                "title": figure_info.get("title", ""),
                "is_centered": figure_info.get("is_centered", False),
                "is_bold": figure_info.get("is_bold", False)
            })
        
        # 判断是否符合格式要求
        if format_info["tables_count"] > 0:
            centered_ratio = result["tables"]["centered_count"] / min(5, format_info["tables_count"])
            bold_ratio = result["tables"]["bold_count"] / min(5, format_info["tables_count"])
            result["tables"]["format_compliant"] = centered_ratio > 0.5 and bold_ratio > 0.5
        
        if format_info["figures_count"] > 0:
            centered_ratio = result["figures"]["centered_count"] / min(5, format_info["figures_count"])
            bold_ratio = result["figures"]["bold_count"] / min(5, format_info["figures_count"])
            result["figures"]["format_compliant"] = centered_ratio > 0.5 and bold_ratio > 0.5
        
        return result

    def _extract_cover_info(self, doc, format_info):
        """
        专门提取论文封面信息的方法
        
        Args:
            doc: Document对象
            format_info: 格式信息字典
        """
        logger.info("提取论文封面信息")
        
        # 厦门大学MBA论文封面关键词列表
        cover_keywords = ['学校编码', '学号', '作者', '专业', '导师', '学位论文', '题目', 
                         '厦门大学', 'MBA', '硕士', '管理学院', '商学院', '院系']
        blind_cover_keywords = ['盲审', '匿名', '评阅']
        
        # 默认设置
        format_info["has_cover"] = False
        format_info["has_blind_cover"] = False
        format_info["cover_page"] = 1  # 假设封面在第一页
        
        # 扩大封面检测范围 - 通常封面在前150段内，优先检查第一页内容
        for i, p in enumerate(doc.paragraphs[:150]):
            text = p.text.strip()
            if not text:
                continue
                
            # 检查是否包含典型的封面信息词语
            for keyword in cover_keywords:
                if keyword in text:
                    # 找到封面信息
                    if not format_info["has_cover"]:
                        format_info["has_cover"] = True
                        logger.debug(f"在第{i}段找到封面信息: '{text}'")
                    
                    # 存储该项封面信息
                    format_info["cover_info"][keyword] = text
                    
                    # 如果是题目相关，可能需要提取论文标题
                    if keyword == '题目' and (':' in text or '：' in text):
                        separator = ':' if ':' in text else '：'
                        title_part = text.split(separator, 1)[1].strip()
                        if title_part:
                            format_info["title"] = title_part
                            logger.debug(f"从封面提取论文标题: '{title_part}'")
                    break
            
            # 检查是否包含盲审封面相关信息
            for keyword in blind_cover_keywords:
                if keyword in text:
                    format_info["has_blind_cover"] = True
                    format_info["cover_info"]["盲审封面"] = text
                    logger.debug(f"在第{i}段找到盲审封面信息: '{text}'")
                    break
                    
            # 尝试从封面识别论文标题（通常是较大字号的文本）
            if not format_info["title"] and len(text) > 5 and len(text) < 100:
                # 检查是否有特殊格式（如加粗或大字号）
                has_special_format = False
                for run in p.runs:
                    # 如果是大字号文本或加粗文本，可能是标题
                    if ((run.font.size and hasattr(run.font.size, 'pt') and run.font.size.pt > 14) or
                        (hasattr(run.font, 'bold') and run.font.bold)):
                        has_special_format = True
                        break
                
                # 检查文本是否符合标题格式（不含特定关键词，不含冒号等）
                is_title_format = (
                    not any(kw in text for kw in ['摘要', 'Abstract', '目录', 'Contents', '第一章']) and
                    ':' not in text and '：' not in text and
                    not any(kw in text for kw in ['学校编码', '学号', '作者', '专业', '导师'])
                )
                
                if has_special_format and is_title_format:
                    format_info["title"] = text
                    logger.debug(f"在第{i}段找到可能的论文标题: '{text}'")
                    
            # 检查是否为MBA专业论文
            if '管理学院' in text or 'MBA' in text or '商学院' in text:
                format_info["cover_info"]["学院"] = "管理学院/商学院"
                format_info["cover_info"]["专业类型"] = "MBA"
                logger.debug(f"识别为MBA专业论文: '{text}'")
        
        # 记录封面信息的详细内容，便于调试
        if format_info["has_cover"]:
            logger.info(f"已找到封面信息: {format_info['cover_info']}")
            if format_info["title"]:
                logger.info(f"论文标题: {format_info['title']}")
        else:
            logger.warning("未找到有效的封面信息，请确认文档是否包含完整封面")

    def _extract_toc_info(self, doc, format_info):
        """
        专门提取中文目录信息的方法
        
        Args:
            doc: Document对象
            format_info: 格式信息字典
        """
        logger.info("提取中文目录信息")
        
        # 默认设置
        format_info["has_toc"] = False
        
        # 目录标题的各种可能格式 - 特别处理全角空格
        toc_pattern = re.compile(r'^[\s\u200b]*目[\s\u200b]*录[\s\u200b]*$')
        
        # 遍历文档查找目录 - 中文目录信息以"目　录"起始，以contents为结束
        for i, p in enumerate(doc.paragraphs):
            text = p.text.strip()
            if not text:
                continue
                
            # 判断是否是目录标题 - 特别处理"目　录"（含全角空格）
            is_toc_title = (
                toc_pattern.match(text) or 
                text.strip() in ['目录', '目  录', '目   录', '目　录'] or
                (text.startswith('目') and text.endswith('录') and len(text) < 10)
            )
            
            if is_toc_title:
                format_info["has_toc"] = True
                format_info["toc_info"]["type"] = "中文目录"
                format_info["toc_info"]["position"] = i
                format_info["toc_info"]["title_text"] = text
                logger.debug(f"在第{i}段找到中文目录标题: '{text}'")
                
                # 检查目录标题格式
                is_bold = any(run.font.bold for run in p.runs if hasattr(run.font, 'bold') and run.font.bold)
                is_centered = p.alignment == 1 if hasattr(p, 'alignment') else False
                format_info["toc_info"]["title_is_bold"] = is_bold
                format_info["toc_info"]["title_is_centered"] = is_centered
                
                # 记录格式判断结果
                if is_bold:
                    logger.debug("目录标题已加粗")
                else:
                    logger.warning("目录标题未加粗")
                
                if is_centered:
                    logger.debug("目录标题已居中")
                else:
                    logger.warning("目录标题未居中")
                
                # 收集目录内容
                toc_items = []
                contents_found = False
                
                # 扩大检查范围，找到所有目录项直到"Contents"或其他章节标记
                for j in range(1, 100):  # 增大检查范围到100个段落
                    if i + j >= len(doc.paragraphs):
                        break
                        
                    next_para = doc.paragraphs[i + j].text.strip()
                    if not next_para:
                        continue  # 跳过空行
                        
                    # 如果遇到"Contents"，说明中文目录结束，英文目录开始
                    if (next_para.lower() in ['contents', 'abstract'] or 
                        next_para.lower().startswith('contents') or
                        'contents' in next_para.lower()):
                        contents_found = True
                        format_info["toc_info"]["eng_position"] = i + j
                        format_info["toc_info"]["eng_title_text"] = next_para
                        logger.debug(f"在第{i+j}段找到英文目录标题 '{next_para}'，中文目录结束")
                        break
                        
                    # 如果遇到其他章节标记，也认为目录结束
                    if (next_para in ['摘要', '致谢', '参考文献', '附录'] or 
                        next_para.startswith('第一章') or 
                        re.match(r'^第[一二三四五六七八九十\d]+章', next_para)):
                        logger.debug(f"在第{i+j}段遇到新章节标记'{next_para}'，中文目录结束")
                        break
                        
                    # 检查是否是目录项 - 目录通常有明显的缩进和页码
                    is_toc_item = (
                        # 标题...页码 格式
                        re.search(r'.*\.*\s*\d+$', next_para) or 
                        # 章节标题格式
                        re.search(r'^第[一二三四五六七八九十\d]+[章节]', next_para) or
                        # 其他可能的目录项
                        re.search(r'^[一二三四五六七八九十][、\s]', next_para) or
                        re.search(r'^[0-9]+(\.[0-9]+)*\s', next_para) or
                        # MBA论文中常见的目录项格式
                        re.search(r'^[一二三四五六七八九十]\s+[^0-9]+', next_para) or
                        re.search(r'^[A-Z]+\s+[^0-9]+', next_para)
                    )
                    
                    if is_toc_item:
                        # 获取缩进和页码信息
                        indent = get_paragraph_indent(doc.paragraphs[i + j])
                        page_num_match = re.search(r'\d+$', next_para)
                        page_num = page_num_match.group() if page_num_match else None
                        
                        # 记录目录项内容和格式信息
                        toc_format = {
                            "text": next_para,
                            "indent": indent,
                            "is_bold": any(run.font.bold for run in doc.paragraphs[i + j].runs 
                                          if hasattr(run.font, 'bold') and run.font.bold),
                            "position": i + j,
                            "page_num": page_num
                        }
                        toc_items.append(toc_format)
                        logger.debug(f"添加目录项: '{next_para}' 缩进: {indent}pt 页码: {page_num}")
                    elif len(toc_items) > 0 and not re.search(r'contents', next_para.lower()):
                        # 可能是目录项的延续 - 不要包含可能的英文目录标题
                        prev_item = toc_items[-1]
                        prev_item["text"] += " " + next_para
                        logger.debug(f"添加目录项延续内容: '{next_para}'")
                
                # 如果找到了英文目录标题，提取英文目录项
                if contents_found:
                    self._extract_english_toc(doc, format_info, i + j + 1)
                
                # 保存目录项和计数
                format_info["toc_info"]["items"] = [item["text"] for item in toc_items]
                format_info["toc_info"]["items_count"] = len(toc_items)
                format_info["toc_info"]["items_detail"] = toc_items
                
                # 分析目录结构，检查层次和格式
                self._analyze_toc_structure(format_info)
                
                logger.info(f"找到中文目录项数量: {len(toc_items)}")
                break  # 找到一个目录后退出
        
        if not format_info["has_toc"]:
            logger.warning("未找到有效的目录信息，请确认文档是否包含完整目录")
            
    def _analyze_toc_structure(self, format_info):
        """分析目录结构和层次"""
        if not format_info["has_toc"] or len(format_info["toc_info"]["items_detail"]) == 0:
            return
            
        # 获取所有缩进值并按频率排序
        indents = [item["indent"] for item in format_info["toc_info"]["items_detail"] if "indent" in item]
        if not indents:
            return
            
        # 统计缩进频率
        indent_count = {}
        for indent in indents:
            rounded_indent = round(indent, 1)  # 四舍五入到小数点后1位
            indent_count[rounded_indent] = indent_count.get(rounded_indent, 0) + 1
            
        # 按频率排序缩进值
        sorted_indents = sorted(indent_count.items(), key=lambda x: x[1], reverse=True)
        
        # 推测不同层级的缩进值
        level_indents = [i[0] for i in sorted_indents]
        
        # 保存缩进分析结果
        format_info["toc_info"]["indent_analysis"] = {
            "all_indents": indents,
            "indent_frequency": indent_count,
            "level_indents": level_indents[:min(3, len(level_indents))]  # 最多取前3个层级
        }
        
        # 计算每个层级的目录项数量
        if len(level_indents) > 0:
            level_counts = {}
            for item in format_info["toc_info"]["items_detail"]:
                if "indent" in item:
                    rounded_indent = round(item["indent"], 1)
                    # 找到最接近的缩进层级
                    closest_level = min(level_indents, key=lambda x: abs(x - rounded_indent))
                    level_idx = level_indents.index(closest_level)
                    level_name = f"level_{level_idx + 1}"
                    level_counts[level_name] = level_counts.get(level_name, 0) + 1
                    
                    # 将层级信息添加到目录项
                    item["level"] = level_idx + 1
            
            format_info["toc_info"]["level_counts"] = level_counts
            
        logger.info(f"目录层级分析完成，识别出 {len(level_indents)} 个层级")

    def _extract_english_toc(self, doc, format_info, start_pos):
        """
        提取英文目录信息
        
        Args:
            doc: Document对象
            format_info: 格式信息字典
            start_pos: 开始位置（英文目录标题位置之后）
        """
        eng_toc_items = []
        
        # 从英文目录标题位置之后开始遍历
        for j in range(100):  # 最多查找100个段落
            if start_pos + j >= len(doc.paragraphs):
                break
                
            next_para = doc.paragraphs[start_pos + j].text.strip()
            if not next_para:
                continue  # 跳过空行
                
            # 如果遇到章节标记，说明英文目录结束
            if (next_para in ['摘要', 'Abstract', '致谢', '参考文献', '附录'] or 
                next_para.startswith('Chapter') or
                re.search(r'^第[一二三四五六七八九十\d]+章', next_para)):
                logger.debug(f"在第{start_pos+j}段遇到新章节标记'{next_para}'，英文目录结束")
                break
                
            # 检查是否是英文目录项
            is_eng_toc_item = (
                # 标题...页码 格式
                re.search(r'.*\.*\s*\d+$', next_para) or 
                # 章节标题格式
                re.search(r'^Chapter\s+\d+', next_para) or
                re.search(r'^CHAPTER\s+\d+', next_para) or
                # 其他可能的目录项
                re.search(r'^[A-Z][a-z]', next_para) or
                re.search(r'^[0-9]+(\.[0-9]+)*\s', next_para) or
                # MBA论文中常见的目录项格式
                re.search(r'^[IVX]+\.\s+', next_para) or
                re.search(r'^[A-Z]+\.\s+', next_para)
            )
            
            if is_eng_toc_item:
                # 记录目录项内容和格式信息
                toc_format = {
                    "text": next_para,
                    "indent": get_paragraph_indent(doc.paragraphs[start_pos + j]),
                    "is_bold": any(run.font.bold for run in doc.paragraphs[start_pos + j].runs 
                                  if hasattr(run.font, 'bold') and run.font.bold),
                    "position": start_pos + j
                }
                eng_toc_items.append(toc_format)
                logger.debug(f"添加英文目录项: '{next_para}'")
            elif len(eng_toc_items) > 0:
                # 可能是目录项的延续
                prev_item = eng_toc_items[-1]
                prev_item["text"] += " " + next_para
                logger.debug(f"添加英文目录项延续内容: '{next_para}'")
        
        # 保存英文目录项和计数
        format_info["toc_info"]["eng_items"] = [item["text"] for item in eng_toc_items]
        format_info["toc_info"]["eng_items_count"] = len(eng_toc_items)
        format_info["toc_info"]["eng_items_detail"] = eng_toc_items
        
        logger.info(f"找到英文目录项数量: {len(eng_toc_items)}")

def get_paragraph_indent(paragraph):
    """获取段落的缩进值"""
    if paragraph.paragraph_format and paragraph.paragraph_format.left_indent:
        try:
            return paragraph.paragraph_format.left_indent.pt
        except:
            pass
    return 0.0

# 阳光学院论文格式检查器
class SunshineFormatChecker(FormatChecker):
    """阳光学院论文格式检查器"""
    
    def extract_format_info(self, docx_content):
        """从docx文件流中提取格式信息"""
        doc = Document(docx_content)
        format_info = {
            "paragraphs": len(doc.paragraphs),
            "sections": len(doc.sections),
            "styles": [],
            "style_inheritance": {},  # 记录样式继承关系
            "fonts": set(),
            "font_sizes": set(),
            "spacing": [],
            "headers": [],
            "footers": [],
            "paragraph_styles": {},   # 记录各种段落样式的使用情况
            "abstract": "",
            "eng_abstract": "",
            "page_margins": {}
        }
        
        # 记录所有样式的继承关系
        logger.debug("分析文档样式继承关系")
        for style in doc.styles:
            try:
                style_name = style.name
                if style_name not in format_info["styles"]:
                    format_info["styles"].append(style_name)
                
                # 检查样式类型
                style_type = type(style).__name__
                # 跳过不支持的样式类型，如_NumberingStyle
                if style_type == '_NumberingStyle' or not hasattr(style, 'base_style'):
                    continue
                
                # 获取样式继承链
                inheritance = get_style_inheritance(style)
                if len(inheritance) > 1:  # 如果有继承关系
                    format_info["style_inheritance"][style_name] = inheritance[1:]  # 排除自身
                
                # 获取合并样式属性
                style_attrs = get_merged_style_attributes(style)
                
                # 如果有字体定义，记录下来
                if 'font' in style_attrs and style_attrs['font'].get('name'):
                    format_info["fonts"].add(style_attrs['font'].get('name'))
                
                # 如果有字体大小定义，记录下来
                if 'font' in style_attrs and style_attrs['font'].get('size'):
                    size = style_attrs['font'].get('size')
                    if size and 5 < size < 100:  # 合理的字体大小范围
                        format_info["font_sizes"].add(size)
                
                # 如果有行间距定义，记录下来
                if ('paragraph_format' in style_attrs and 
                    style_attrs['paragraph_format'].get('line_spacing')):
                    spacing = style_attrs['paragraph_format'].get('line_spacing')
                    if spacing and 0 < spacing < 10:  # 合理的行间距范围
                        format_info["spacing"].append(spacing)
            except Exception as e:
                logger.warning(f"分析样式 {getattr(style, 'name', '未知')} 失败: {str(e)}")
        
        # 遍历所有段落
        logger.debug("分析文档段落格式")
        for i, paragraph in enumerate(doc.paragraphs):
            if not paragraph.text.strip():
                continue
            
            # 记录段落样式使用情况
            if hasattr(paragraph, 'style') and paragraph.style:
                style_name = paragraph.style.name
                format_info["paragraph_styles"][style_name] = format_info["paragraph_styles"].get(style_name, 0) + 1
            
            # 获取段落的有效格式信息
            para_format = get_effective_paragraph_format(paragraph, doc)
            
            # 收集字体信息
            if para_format.get('font_name'):
                format_info["fonts"].add(para_format['font_name'])
            
            # 收集字体大小信息
            if para_format.get('font_size'):
                font_size = para_format['font_size']
                if font_size and 5 < font_size < 100:  # 过滤不合理的字体大小
                    format_info["font_sizes"].add(font_size)
            
            # 收集行间距信息
            if para_format.get('line_spacing'):
                line_spacing = para_format['line_spacing']
                if line_spacing and 0 < line_spacing < 10:  # 过滤不合理的行间距
                    if line_spacing not in format_info["spacing"]:
                        format_info["spacing"].append(line_spacing)
            
            # 处理运行级别的格式（用于补充继承样式可能漏掉的信息）
            for run in paragraph.runs:
                if not run.text.strip():
                    continue
                
                # 收集字体信息
                if run.font.name:
                    format_info["fonts"].add(run.font.name)
                
                # 收集字体大小信息
                if run.font.size:
                    try:
                        size = run.font.size.pt if hasattr(run.font.size, 'pt') else None
                        if size and 5 < size < 100:  # 过滤不合理的字体大小
                            format_info["font_sizes"].add(size)
                    except:
                        pass
            
            # 尝试识别摘要
            if '摘要' in paragraph.text[:10] and len(paragraph.text) < 20:
                # 直接使用遍历时的索引
                if i + 1 < len(doc.paragraphs):
                    abstract_content = doc.paragraphs[i + 1].text
                    if len(abstract_content) > 50:  # 假设摘要至少有50个字符
                        format_info["abstract"] = abstract_content
            
            # 尝试识别英文摘要
            if 'Abstract' in paragraph.text[:15] and len(paragraph.text) < 20:
                # 直接使用遍历时的索引
                if i + 1 < len(doc.paragraphs):
                    abstract_content = doc.paragraphs[i + 1].text
                    if len(abstract_content) > 30:  # 英文摘要通常较短
                        format_info["eng_abstract"] = abstract_content
        
        # 提取页眉页脚和页面设置信息
        logger.debug("分析文档页眉页脚和页面设置")
        for i, section in enumerate(doc.sections):
            # 页面设置信息
            if i == 0 or not format_info["page_margins"]:
                try:
                    format_info["page_margins"] = {
                        "top": section.top_margin.cm if hasattr(section.top_margin, 'cm') else None,
                        "bottom": section.bottom_margin.cm if hasattr(section.bottom_margin, 'cm') else None,
                        "left": section.left_margin.cm if hasattr(section.left_margin, 'cm') else None,
                        "right": section.right_margin.cm if hasattr(section.right_margin, 'cm') else None
                    }
                except:
                    logger.warning("无法获取页边距信息")
            
            # 提取页眉
            try:
                header = section.header
                if not header.is_linked_to_previous:
                    header_text = '\n'.join(paragraph.text for paragraph in header.paragraphs if paragraph.text)
                    if header_text and header_text not in format_info["headers"]:
                        format_info["headers"].append(header_text)
            except:
                logger.warning("提取页眉信息失败")
                
            # 提取页脚
            try:
                footer = section.footer
                if not footer.is_linked_to_previous:
                    footer_text = '\n'.join(paragraph.text for paragraph in footer.paragraphs if paragraph.text)
                    if footer_text and footer_text not in format_info["footers"]:
                        format_info["footers"].append(footer_text)
            except:
                logger.warning("提取页脚信息失败")
        
        # 将字体集合转换为列表
        format_info["fonts"] = list(format_info["fonts"])
        if "font_sizes" in format_info:
            format_info["font_sizes"] = sorted(list(format_info["font_sizes"]))
        
        return format_info
        
    def generate_user_prompt(self, format_info):
        """生成阳光学院论文格式检查的用户提示词"""
        # 处理字体大小格式
        font_sizes_str = ', '.join(map(str, format_info.get('font_sizes', []))) if format_info.get('font_sizes') else '未检测到'
        
        # 处理样式继承关系摘要
        inheritance_summary = []
        if format_info.get('style_inheritance'):
            # 选择一些有代表性的样式继承关系作为示例
            for style_name, base_styles in list(format_info.get('style_inheritance', {}).items())[:3]:
                if base_styles:  # 确保有继承关系
                    inheritance_summary.append(f"{style_name} 继承自 {' -> '.join(base_styles)}")
        
        inheritance_str = '; '.join(inheritance_summary) if inheritance_summary else '未检测到明确的样式继承关系'
        
        # 处理段落样式使用情况
        popular_styles = []
        if format_info.get('paragraph_styles'):
            # 按使用频率排序，获取前5个最常用的样式
            sorted_styles = sorted(format_info.get('paragraph_styles', {}).items(), 
                                 key=lambda x: x[1], reverse=True)[:5]
            for style_name, count in sorted_styles:
                popular_styles.append(f"{style_name}({count}段)")
        
        popular_styles_str = ', '.join(popular_styles) if popular_styles else '未检测到'
        
        prompt = f"""请分析以下论文格式信息，并判断是否符合阳光学院学术论文规范：

        1. 基本信息：
        - 总段落数：{format_info.get('paragraphs', '未检测到')}
        - 章节数：{format_info.get('sections', '未检测到')}
        
        2. 样式信息：
        - 使用的样式总数：{len(format_info.get('styles', []))}
        - 最常用的段落样式：{popular_styles_str}
        - 样式继承关系示例：{inheritance_str}
        
        3. 字体与格式：
        - 使用的字体：{', '.join(format_info.get('fonts', ['未检测到']))}
        - 字体大小：{font_sizes_str}
        - 行间距：{', '.join(map(str, format_info.get('spacing', ['未检测到'])))}
        
        4. 页面设置：
        - 页眉信息：{', '.join(format_info.get('headers', [])) if format_info.get('headers') else '无'}
        - 页脚信息：{', '.join(format_info.get('footers', [])) if format_info.get('footers') else '无'}
        - 页边距：上{format_info.get('page_margins', {}).get('top', '未检测到')}cm, 下{format_info.get('page_margins', {}).get('bottom', '未检测到')}cm, 左{format_info.get('page_margins', {}).get('left', '未检测到')}cm, 右{format_info.get('page_margins', {}).get('right', '未检测到')}cm
        
        5. 摘要信息：
        - 中文摘要：{format_info.get('abstract', '')[:100] + '...' if format_info.get('abstract') else '未检测到'}
        - 英文摘要：{format_info.get('eng_abstract', '')[:100] + '...' if format_info.get('eng_abstract') else '未检测到'}

        请详细说明该论文是否符合阳光学院学术论文规范，如有不符合的地方，请具体指出并给出修改建议。"""
        
        return prompt

# 格式检查器工厂类
class FormatCheckerFactory:
    """论文格式检查器工厂类"""
    
    @staticmethod
    def create_checker(template):
        """
        根据模板类型创建相应的格式检查器
        参数:
            template: 模板名称，如 'xmu', 'sunshine'
        返回:
            FormatChecker实例
        """
        if template == 'xmu':
            return XmuFormatChecker(template)
        elif template == 'sunshine':
            return SunshineFormatChecker(template)
        else:
            # 默认使用阳光学院模板
            logger.warning(f'未知模板类型: {template}，使用默认模板sunshine')
            return SunshineFormatChecker('sunshine')

# 替换原有的get_prompt函数
def get_prompt(template):
    """
    获取模板提示词，保持向后兼容
    注意：这是过渡函数，应尽量使用FormatCheckerFactory创建检查器
    """
    checker = FormatCheckerFactory.create_checker(template)
    return checker.get_system_prompt()

# 更新app路由，使用新的格式检查器工厂
@app.route('/api/upload', methods=['POST'])
def check_paper_format():
    """检查论文格式API"""
    global active_requests

    # 尝试获取信号量，如果队列已满则返回429错误
    if not request_semaphore.acquire(blocking=False):
        logger.warning(f'请求队列已满，当前活跃请求数: {active_requests}，拒绝新请求')
        return jsonify({
            'error': '请求队列已满，请稍后再试',
            'code': 429,
            'detail': '系统当前正在处理其他请求，请等待几分钟后重试'
        }), 429

    # 更新活跃请求计数
    with request_count_lock:
        active_requests += 1
        current_active = active_requests
    
    logger.info(f'接受新请求，当前活跃请求数: {current_active}/4')
    
    try:
        if 'file' not in request.files:
            logger.warning('未上传文件')
            return jsonify({'error': '请上传文件'}), 400
        
        file = request.files['file']
        template = request.form.get('template', 'sunshine')
        logger.info(f'收到文件上传请求：{file.filename}, 使用模板：{template}')
        
        try:
            # 读取zip文件内容
            zip_data = io.BytesIO(file.read())
            with zipfile.ZipFile(zip_data) as zip_file:
                # 获取第一个docx文件
                docx_files = [f for f in zip_file.namelist() if f.endswith('.docx')]
                if not docx_files:
                    logger.warning('压缩包中未找到.docx文件')
                    return jsonify({'error': '压缩包中未找到.docx文件'}), 400
                
                logger.debug(f'找到docx文件：{docx_files[0]}')
                # 读取docx文件内容
                docx_content = io.BytesIO(zip_file.read(docx_files[0]))
                
                # 使用工厂创建格式检查器并检查格式
                format_checker = FormatCheckerFactory.create_checker(template)
                system_prompt, user_prompt, format_info = format_checker.check_format(docx_content)
                
                logger.debug(f'提取到的格式信息：{format_info}')
                
                # 记录上传的文件信息到日志
                log_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'logs')
                os.makedirs(log_dir, exist_ok=True)
                log_file = os.path.join(log_dir, 'upload_file_content.log')
                
                with open(log_file, 'a', encoding='utf-8') as f:
                    f.write(f"\n{'='*50}\n")
                    f.write(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                    f.write(f"File name: {file.filename}\n")
                    f.write(f"File size: {len(file.read())} bytes\n")
                    f.write(f"Content type: {file.content_type}\n")
                    f.write(f"Template: {template}\n")
                    file.seek(0)  # 重置文件指针
        except Exception as e:
            logger.error(f"处理ZIP文件时出错: {str(e)}", exc_info=True)
            return jsonify({'error': f'处理文件时出错: {str(e)}'}), 400
            
        logger.debug('准备发送API请求')
        # 准备API请求数据
        headers = {
            "Authorization": f"Bearer {API_KEY}",
            "Content-Type": "application/json"
        }
        
        # 检查 API_KEY 是否为空或格式不正确
        if not API_KEY:
            error_msg = "API密钥未设置，请检查环境变量"
            logger.error(error_msg)
            return jsonify({
                'error': error_msg,
                'code': 401,
                'detail': '请在 .env 文件中设置有效的 OPENAI_API_KEY'
            }), 401
        
        # 检查 API_BASE 是否为空或格式不正确
        if not API_BASE or ' ' in API_BASE:
            error_msg = f"API基础URL格式不正确: '{API_BASE}'"
            logger.error(error_msg)
            return jsonify({
                'error': error_msg,
                'code': 500,
                'detail': '请在 .env 文件中设置正确的 OPENAI_API_BASE，不要包含多余的空格'
            }), 500
        
        # 检查 MODEL_NAME 是否为空
        if not MODEL_NAME:
            error_msg = "模型名称未设置，请检查环境变量"
            logger.error(error_msg)
            return jsonify({
                'error': error_msg,
                'code': 500,
                'detail': '请在 .env 文件中设置正确的 MODEL_NAME'
            }), 500
        
        # 记录请求信息（不包含敏感数据）
        logger.debug(f"请求URL: {API_BASE}/chat/completions")
        logger.debug(f"使用模型: {MODEL_NAME}")
        
        # 构建符合 Kimi API 的请求数据，将规则文件内容作为system角色，用户提示作为user角色
        data = {
            "model": MODEL_NAME,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            "stream": False,
            "max_tokens": 4096,
            "temperature": 0,
            "top_p": 1,
            "top_k": 1
        }
        
        # 发送API请求
        try:
            logger.debug(f"发送请求到 Kimi API: {API_BASE}/chat/completions")
            response = requests.post(
                f"{API_BASE}/chat/completions",
                headers=headers,
                json=data,
                timeout=60  # 设置超时时间为60秒
            )
            
            logger.debug(f'API响应状态码: {response.status_code}')
            
            # 检查API响应状态码
            if response.status_code == 200:
                try:
                    result = response.json()
                    if 'choices' in result and len(result['choices']) > 0 and 'message' in result['choices'][0]:
                        analysis = result['choices'][0]['message']['content']
                        logger.info('成功获取分析结果')
                        
                        # 定义结果文件路径
                        output_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'output')
                        os.makedirs(output_dir, exist_ok=True)
                        result_file = os.path.join(output_dir, 'format_analysis_result.txt')
                        
                        # 如果文件存在则删除
                        if os.path.exists(result_file):
                            os.remove(result_file)
                        
                        # 创建新文件并写入分析结果
                        with open(result_file, 'w', encoding='utf-8') as f:
                            f.write(analysis)
                        logger.debug(f'分析结果已保存到文件：{result_file}')
                        
                        return jsonify({'result': analysis})
                    else:
                        error_msg = "API响应格式不正确，缺少必要的字段"
                        logger.error(f"{error_msg}: {result}")
                        return jsonify({
                            'error': error_msg,
                            'code': 500,
                            'detail': '服务器返回的数据格式不符合预期'
                        }), 500
                except Exception as e:
                    error_msg = f"解析API响应时出错: {str(e)}"
                    logger.error(error_msg)
                    return jsonify({
                        'error': error_msg,
                        'code': 500,
                        'detail': '无法解析服务器返回的数据'
                    }), 500
            elif response.status_code == 401:
                # 处理401未授权错误
                error_detail = "API密钥无效或已过期"
                try:
                    error_response = response.json()
                    if 'error' in error_response:
                        error_detail = error_response['error'].get('message', error_detail)
                except:
                    pass
                
                error_msg = f"API认证失败: {error_detail}"
                logger.error(error_msg)
                return jsonify({
                    'error': error_msg,
                    'code': 401,
                    'detail': '请检查API密钥是否有效，或者联系管理员重新配置API密钥'
                }), 401
            elif response.status_code == 429:
                # 处理429请求过多错误
                error_msg = "API请求过于频繁，请稍后再试"
                logger.error(error_msg)
                return jsonify({
                    'error': error_msg,
                    'code': 429,
                    'detail': '已达到API请求限制，请稍后再试'
                }), 429
            else:
                # 处理其他错误
                error_detail = f"状态码: {response.status_code}"
                try:
                    error_response = response.json()
                    if 'error' in error_response:
                        error_detail = error_response['error'].get('message', error_detail)
                except:
                    pass
                
                error_msg = f"API请求失败: {error_detail}"
                logger.error(error_msg)
                return jsonify({
                    'error': error_msg,
                    'code': response.status_code,
                    'detail': '请求处理失败，请稍后再试或联系管理员'
                }), response.status_code
                
        except requests.exceptions.Timeout:
            error_msg = "API请求超时"
            logger.error(error_msg)
            return jsonify({
                'error': error_msg,
                'code': 504,
                'detail': '远程服务响应超时，请稍后重试'
            }), 504
        except requests.exceptions.ConnectionError:
            error_msg = "无法连接到API服务"
            logger.error(error_msg)
            return jsonify({
                'error': error_msg,
                'code': 503,
                'detail': '无法连接到远程服务，请检查网络连接或联系管理员'
            }), 503
        except Exception as e:
            error_msg = f"API请求异常: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return jsonify({
                'error': error_msg,
                'code': 500,
                'detail': '请求处理过程中发生异常，请联系管理员'
            }), 500
            
    except Exception as e:
        error_msg = f"处理文件时出错: {str(e)}"
        logger.error(error_msg, exc_info=True)
        return jsonify({
            'error': error_msg,
            'code': 500,
            'detail': '文件处理过程中发生异常，请检查文件格式或联系管理员'
        }), 500
    finally:
        # 更新活跃请求计数并释放信号量
        with request_count_lock:
            active_requests -= 1
            current_active = active_requests
        request_semaphore.release()
        logger.info(f'请求处理完成，当前活跃请求数: {current_active}/4')

# 添加API端点查询当前队列状态
@app.route('/api/queue-status', methods=['GET'])
def queue_status():
    """返回当前请求队列状态"""
    with request_count_lock:
        return jsonify({
            'active_requests': active_requests,
            'max_requests': 4,
            'queue_available': active_requests < 4,
            'timestamp': datetime.now().isoformat()
        })

@app.route('/api/upload/init', methods=['POST'])
def init_upload():
    try:
        data = request.get_json()
        session_id = str(uuid.uuid4())
        
        # 创建临时目录存储分片
        temp_dir = os.path.join(app.config['UPLOAD_FOLDER'], 'temp', session_id)
        os.makedirs(temp_dir, exist_ok=True)
        
        # 保存会话信息
        upload_sessions[session_id] = {
            'filename': secure_filename(data['filename']),
            'total_size': data['totalSize'],
            'total_chunks': data['totalChunks'],
            'uploaded_chunks': set(),
            'temp_dir': temp_dir,
            'created_at': datetime.now()
        }
        
        return jsonify({
            'success': True,
            'sessionId': session_id
        })
    except Exception as e:
        logger.error(f'初始化上传会话失败: {str(e)}')
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/upload/chunk', methods=['POST'])
def upload_chunk():
    try:
        session_id = request.form.get('sessionId')
        chunk_index = int(request.form.get('chunkIndex'))
        total_chunks = int(request.form.get('totalChunks'))
        
        if session_id not in upload_sessions:
            return jsonify({
                'success': False,
                'error': '无效的会话ID'
            }), 400
        
        session = upload_sessions[session_id]
        if chunk_index >= total_chunks:
            return jsonify({
                'success': False,
                'error': '无效的分片索引'
            }), 400
        
        # 保存分片文件
        chunk_file = request.files['file']
        chunk_path = os.path.join(session['temp_dir'], f'chunk_{chunk_index}')
        chunk_file.save(chunk_path)
        
        # 更新已上传分片记录
        session['uploaded_chunks'].add(chunk_index)
        
        return jsonify({
            'success': True,
            'message': f'分片 {chunk_index + 1}/{total_chunks} 上传成功'
        })
    except Exception as e:
        logger.error(f'上传分片失败: {str(e)}')
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/upload/complete', methods=['POST'])
def complete_upload():
    try:
        session_id = request.json.get('sessionId')
        if session_id not in upload_sessions:
            return jsonify({
                'success': False,
                'error': '无效的会话ID'
            }), 400
        
        session = upload_sessions[session_id]
        
        # 检查是否所有分片都已上传
        if len(session['uploaded_chunks']) != session['total_chunks']:
            return jsonify({
                'success': False,
                'error': '文件上传不完整'
            }), 400
        
        # 合并所有分片
        final_path = os.path.join(app.config['UPLOAD_FOLDER'], session['filename'])
        with open(final_path, 'wb') as outfile:
            for i in range(session['total_chunks']):
                chunk_path = os.path.join(session['temp_dir'], f'chunk_{i}')
                with open(chunk_path, 'rb') as infile:
                    outfile.write(infile.read())
        
        # 清理临时文件
        import shutil
        shutil.rmtree(session['temp_dir'])
        
        # 删除会话信息
        del upload_sessions[session_id]
        
        # 处理上传完成的文件
        process_uploaded_file(final_path)
        
        return jsonify({
            'success': True,
            'message': '文件上传完成'
        })
    except Exception as e:
        logger.error(f'完成上传失败: {str(e)}')
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

# 清理过期的上传会话
def cleanup_expired_sessions():
    while True:
        current_time = datetime.now()
        expired_sessions = []
        
        for session_id, session in upload_sessions.items():
            # 如果会话超过1小时未完成，则清理
            if (current_time - session['created_at']).total_seconds() > 3600:
                expired_sessions.append(session_id)
                # 清理临时文件
                import shutil
                shutil.rmtree(session['temp_dir'])
        
        for session_id in expired_sessions:
            del upload_sessions[session_id]
        
        time.sleep(300)  # 每5分钟检查一次

# 启动清理线程
cleanup_thread = threading.Thread(target=cleanup_expired_sessions, daemon=True)
cleanup_thread.start()

if __name__ == "__main__":
    logger.info('启动Flask应用服务器')
    app.run(host='0.0.0.0', port=5300, debug=True)