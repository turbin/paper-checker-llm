import os
from flask import Flask, request, jsonify
from docx import Document
import requests
from dotenv import load_dotenv
from flask_cors import CORS

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
        raise FileNotFoundError(f'模板文件 {ruler_file} 不存在')
    
    # 读取并返回文件内容
    with open(ruler_file, 'r', encoding='utf-8') as f:
        return f.read().strip()

def extract_docx_info(file):
    """从docx文件中提取格式信息"""
    doc = Document(file.name)
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
        return jsonify({'error': '请上传文件'}), 400
    
    file = request.files['file']
    template = request.form.get('template', 'sunshine')
    
    try:
        format_info = extract_docx_info(file)
        
        prefix=get_prompt(template)

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
            
            return jsonify({'result': analysis})
        else:
            return jsonify({'error': f"API请求失败：{response.status_code} - {response.text}"}), 500
        
    except Exception as e:
        return jsonify({'error': f"处理文件时出错：{str(e)}"}), 500

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000, debug=True)