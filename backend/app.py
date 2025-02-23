import os
from datetime import datetime
from flask import Flask, request, jsonify
from docx import Document
import requests
from dotenv import load_dotenv
from flask_cors import CORS
import io
import zipfile
from logger_config import logger

# 加载环境变量
load_dotenv()

# 获取API配置
API_KEY = os.getenv('OPENAI_API_KEY')
API_BASE = os.getenv('OPENAI_API_BASE')
MODEL_NAME = os.getenv('MODEL_NAME')

app = Flask(__name__)
CORS(app)

def get_prompt(template):
    """根据模板类型返回对应的提示词"""
    # 获取当前文件所在目录的上级目录
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    # 构建规则文件路径
    ruler_file = os.path.join(base_dir, 'promots', f'{template}.ruler')
    
    # 检查文件是否存在
    if not os.path.exists(ruler_file):
        logger.error(f'模板文件 {ruler_file} 不存在')
        raise FileNotFoundError(f'模板文件 {ruler_file} 不存在')
    
    # 读取并返回文件内容
    with open(ruler_file, 'r', encoding='utf-8') as f:
        content = f.read().strip()
        logger.debug(f'已加载模板文件 {ruler_file}')
        return content

def extract_docx_info(file_stream):
    """从docx文件流中提取格式信息"""
    doc = Document(file_stream)
    format_info = {
        "paragraphs": len(doc.paragraphs),
        "sections": len(doc.sections),
        "styles": [],
        "fonts": set(),
        "spacing": [],
        "headers": [],
        "footers": []
    }
    
    for paragraph in doc.paragraphs:
        if paragraph.style.name not in format_info["styles"]:
            format_info["styles"].append(paragraph.style.name)
        
        # 提取字体信息
        for run in paragraph.runs:
            if run.font.name:
                format_info["fonts"].add(run.font.name)
        
        # 提取段落间距信息
        if paragraph.paragraph_format.line_spacing:
            format_info["spacing"].append(paragraph.paragraph_format.line_spacing)
    
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
    
    return format_info

@app.route('/api/upload', methods=['POST'])
def check_paper_format():
    """检查论文格式API"""
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
            format_info = extract_docx_info(docx_content)
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
        
        prefix = get_prompt(template)
        logger.debug('已获取提示词模板')

        # 构建提示词
        prompt = prefix + f"""请分析以下论文格式信息，并判断是否符合学术论文规范：
        总段落数：{format_info['paragraphs']}
        章节数：{format_info['sections']}
        使用的样式：{', '.join(format_info['styles'])}
        使用的字体：{', '.join(format_info['fonts'])}
        行间距：{', '.join(map(str, format_info['spacing']))}
        页眉信息：{', '.join(format_info['headers']) if format_info['headers'] else '无'}
        页脚信息：{', '.join(format_info['footers']) if format_info['footers'] else '无'}
        请详细说明是否存在格式问题，如有需要改进的地方请给出具体建议。"""
        
        logger.debug('准备发送API请求')
        # 准备API请求数据
        headers = {
            "Authorization": f"Bearer {API_KEY}",
            "Content-Type": "application/json"
        }
        data = {
            "model": MODEL_NAME,
            "messages": [
                {"role": "user", "content": prompt}
            ],
            "stream": False,
            "max_tokens": 2048,
            "stop": [
                "null"
            ],
            "temperature": 0.7,
            "top_p": 0.7,
            "top_k": 50,
            "frequency_penalty": 0.5,
            "n": 1,
            "response_format": {
                "type": "text"
            }
        }
        
        # 发送API请求
        response = requests.post(
            f"{API_BASE}/chat/completions",
            headers=headers,
            json=data
        )
        
        if response.status_code == 200:
            result = response.json()
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
            error_msg = f"API请求失败：{response.status_code} - {response.text}"
            logger.error(error_msg)
            return jsonify({'error': error_msg}), 500
        
    except Exception as e:
        error_msg = f"处理文件时出错：{str(e)}"
        logger.error(error_msg, exc_info=True)
        return jsonify({'error': error_msg}), 500

if __name__ == "__main__":
    logger.info('启动Flask应用服务器')
    app.run(host='0.0.0.0', port=5300, debug=True)