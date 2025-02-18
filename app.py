import os
import gradio as gr
from docx import Document
import requests
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

# 获取API配置
API_KEY = os.getenv('OPENAI_API_KEY')
API_BASE = os.getenv('OPENAI_API_BASE')
MODEL_NAME = os.getenv('MODEL_NAME')

def extract_docx_info(file):
    """从docx文件中提取格式信息"""
    doc = Document(file.name)
    format_info = {
        "paragraphs": len(doc.paragraphs),
        "sections": len(doc.sections),
        "styles": [],
        "fonts": set(),
        "spacing": []
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
    
    return format_info

def check_paper_format(file):
    """检查论文格式"""
    if not file:
        return "请上传文件"
    
    try:
        format_info = extract_docx_info(file)
        
        # 构建提示词
        prompt = f"""请分析以下论文格式信息，并判断是否符合学术论文规范：
        总段落数：{format_info['paragraphs']}
        章节数：{format_info['sections']}
        使用的样式：{', '.join(format_info['styles'])}
        使用的字体：{', '.join(format_info['fonts'])}
        行间距：{', '.join(map(str, format_info['spacing']))}
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
            "temperature": 0.7,
            "max_tokens": 1000
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
            return analysis
        else:
            return f"API请求失败：{response.status_code} - {response.text}"
        
    except Exception as e:
        return f"处理文件时出错：{str(e)}"

# 创建Gradio界面
with gr.Blocks(title="论文格式检查工具") as demo:
    gr.Markdown("## 论文格式检查工具\n请上传您的论文文件（.docx格式），系统将自动检查格式是否规范。")
    
    with gr.Row():
        file_input = gr.File(label="上传论文", file_types=[".docx"])
        
    with gr.Row():
        check_button = gr.Button("检查格式")
        
    with gr.Row():
        output = gr.Textbox(label="分析结果", lines=10)
    
    check_button.click(fn=check_paper_format, inputs=[file_input], outputs=[output])

if __name__ == "__main__":
    demo.launch()