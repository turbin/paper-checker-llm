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
        """从docx文件流中提取格式信息"""
        doc = Document(docx_content)
        format_info = {
            "paragraphs": len(doc.paragraphs),
            "sections": len(doc.sections),
            "styles": [],
            "fonts": set(),
            "font_sizes": set(),      # 改为集合以避免重复
            "spacing": [],
            "first_line_indents": set(),  # 改为集合以避免重复
            "headers": [],
            "footers": [],
            "chapter_titles": [],
            "section_titles": [],
            "subsection_titles": [],
            "title": "",
            "abstract": "",
            "eng_abstract": "",
            "eng_abstract_length": 0,  # 新增英文摘要字符长度
            "abstract_keywords": [],
            "eng_keywords": [],
            "page_margins": {},
            "common_margins": {}  # 新增常见页边距统计
        }
        
        # 统计页边距
        margins_count = {}
        
        # 遍历所有段落
        for i, paragraph in enumerate(doc.paragraphs):
            if paragraph.text:
                # 提取段落样式
                if paragraph.style.name not in format_info["styles"]:
                    format_info["styles"].append(paragraph.style.name)
                
                # 提取字体和大小信息
                for run in paragraph.runs:
                    if run.font.name:
                        format_info["fonts"].add(run.font.name)
                    if run.font.size:
                        try:
                            font_size = run.font.size.pt if hasattr(run.font.size, 'pt') else None
                            if font_size and font_size > 0 and font_size < 100:  # 添加合理性检查
                                format_info["font_sizes"].add(font_size)
                        except:
                            pass
                
                # 提取行间距和缩进信息
                if paragraph.paragraph_format:
                    if paragraph.paragraph_format.line_spacing:
                        # 添加合理性检查
                        line_spacing = paragraph.paragraph_format.line_spacing
                        if line_spacing > 0 and line_spacing < 10:  # 通常行间距在1-3之间
                            format_info["spacing"].append(line_spacing)
                    
                    if paragraph.paragraph_format.first_line_indent:
                        try:
                            first_indent = paragraph.paragraph_format.first_line_indent.pt if hasattr(paragraph.paragraph_format.first_line_indent, 'pt') else None
                            if first_indent and first_indent > 0 and first_indent < 300:  # 添加合理性检查
                                format_info["first_line_indents"].add(first_indent)
                        except:
                            pass
                
                # 识别标题级别
                if paragraph.style and ("heading" in paragraph.style.name.lower() or "标题" in paragraph.style.name):
                    heading_level = 0
                    if paragraph.style.name == 'Heading 1' or paragraph.style.name == '标题 1':
                        heading_level = 1
                        format_info["chapter_titles"].append(paragraph.text)
                    elif paragraph.style.name == 'Heading 2' or paragraph.style.name == '标题 2':
                        heading_level = 2
                        format_info["section_titles"].append(paragraph.text)
                    elif paragraph.style.name == 'Heading 3' or paragraph.style.name == '标题 3':
                        heading_level = 3
                        format_info["subsection_titles"].append(paragraph.text)
                    
                    # 如果前几段是空的，可能第一个非空段落是标题
                    if not format_info["title"] and heading_level == 1 and len(format_info["chapter_titles"]) == 1:
                        format_info["title"] = paragraph.text
                
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
                            format_info["eng_abstract_length"] = len(abstract_content)  # 记录字符长度
                
                # 尝试识别关键词
                if '关键词' in paragraph.text[:10]:
                    keywords_text = paragraph.text.replace('关键词', '').replace('：', ':').split(':')[-1].strip()
                    format_info["abstract_keywords"] = [k.strip() for k in keywords_text.split('；') if k.strip()]
                
                # 尝试识别英文关键词
                if 'Keywords' in paragraph.text[:15]:
                    keywords_text = paragraph.text.replace('Keywords', '').replace('：', ':').split(':')[-1].strip()
                    format_info["eng_keywords"] = [k.strip() for k in keywords_text.split(';') if k.strip()]
        
        # 提取页眉页脚信息
        for i, section in enumerate(doc.sections):
            # 页面设置信息
            if i == 0 or not format_info["page_margins"]:
                format_info["page_margins"] = {
                    "top": section.top_margin.cm if hasattr(section.top_margin, 'cm') else None,
                    "bottom": section.bottom_margin.cm if hasattr(section.bottom_margin, 'cm') else None,
                    "left": section.left_margin.cm if hasattr(section.left_margin, 'cm') else None,
                    "right": section.right_margin.cm if hasattr(section.right_margin, 'cm') else None
                }
            
            # 统计页边距
            margin_key = f"{section.left_margin.cm:.2f}_{section.right_margin.cm:.2f}"
            margins_count[margin_key] = margins_count.get(margin_key, 0) + 1
            
            # 页眉
            header = section.header
            if not header.is_linked_to_previous:
                header_text = '\n'.join(paragraph.text for paragraph in header.paragraphs if paragraph.text)
                if header_text:
                    format_info["headers"].append(header_text)
            
            # 页脚
            footer = section.footer
            if not footer.is_linked_to_previous:
                footer_text = '\n'.join(paragraph.text for paragraph in footer.paragraphs if paragraph.text)
                if footer_text:
                    format_info["footers"].append(footer_text)
        
        # 计算最常见的页边距
        if margins_count:
            most_common_margin = max(margins_count.items(), key=lambda x: x[1])[0]
            left, right = most_common_margin.split('_')
            format_info["common_margins"] = {
                "left": float(left),
                "right": float(right),
                "sections_count": margins_count[most_common_margin]
            }
        
        # 将字体集合转换为列表
        format_info["fonts"] = list(format_info["fonts"])
        if "font_sizes" in format_info:
            format_info["font_sizes"] = sorted(list(format_info["font_sizes"]))
        if "first_line_indents" in format_info:
            format_info["first_line_indents"] = sorted(list(format_info["first_line_indents"]))
        
        return format_info
        
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
        - 中文关键词：{', '.join(format_info.get('abstract_keywords', [])) if format_info.get('abstract_keywords') else '未检测到'}
        - 英文摘要：{format_info.get('eng_abstract', '')[:100] + '...' if format_info.get('eng_abstract') else '未检测到'}
        - 英文摘要长度：{format_info.get('eng_abstract_length', 0)}字符
        - 英文关键词：{', '.join(format_info.get('eng_keywords', [])) if format_info.get('eng_keywords') else '未检测到'}

        请详细说明该论文是否符合厦门大学学位论文格式规范，如有不符合的地方，请具体指出并给出修改建议。按照封面格式、摘要与关键词、目录、正文格式、图表格式、参考文献等方面逐一分析。"""
                
        return prompt

# 阳光学院论文格式检查器
class SunshineFormatChecker(FormatChecker):
    """阳光学院论文格式检查器"""
    
    def extract_format_info(self, docx_content):
        """从docx文件流中提取格式信息"""
        # 简单实现，可以根据需要扩展
        doc = Document(docx_content)
        format_info = {
            "paragraphs": len(doc.paragraphs),
            "sections": len(doc.sections),
            "styles": [],
            "fonts": set(),
            "spacing": [],
            "headers": [],
            "footers": []
        }
        
        # 遍历所有段落
        for i, paragraph in enumerate(doc.paragraphs):
            if paragraph.style.name not in format_info["styles"]:
                format_info["styles"].append(paragraph.style.name)
            
            # 提取字体信息
            for run in paragraph.runs:
                if run.font.name:
                    format_info["fonts"].add(run.font.name)
            
            # 提取段落间距信息
            if paragraph.paragraph_format.line_spacing:
                format_info["spacing"].append(paragraph.paragraph_format.line_spacing)
            
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
        
        # 提取页眉页脚信息
        for section in doc.sections:
            # 提取页眉
            header = section.header
            if header.is_linked_to_previous:
                continue
            header_text = '\n'.join(paragraph.text for paragraph in header.paragraphs if paragraph.text)
            if header_text:
                format_info["headers"].append(header_text)
            
            # 提取页脚
            footer = section.footer
            if footer.is_linked_to_previous:
                continue
            footer_text = '\n'.join(paragraph.text for paragraph in footer.paragraphs if paragraph.text)
            if footer_text:
                format_info["footers"].append(footer_text)
        
        # 将字体集合转换为列表
        format_info["fonts"] = list(format_info["fonts"])
        
        return format_info
        
    def generate_user_prompt(self, format_info):
        """生成阳光学院论文格式检查的用户提示词"""
        prompt = f"""请分析以下论文格式信息，并判断是否符合阳光学院学术论文规范：
        总段落数：{format_info['paragraphs']}
        章节数：{format_info['sections']}
        使用的样式：{', '.join(format_info['styles'])}
        使用的字体：{', '.join(format_info['fonts'])}
        行间距：{', '.join(map(str, format_info['spacing']))}
        页眉信息：{', '.join(format_info['headers']) if format_info['headers'] else '无'}
        页脚信息：{', '.join(format_info['footers']) if format_info['footers'] else '无'}
        请详细说明是否存在格式问题，如有需要改进的地方请给出具体建议。"""
        
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