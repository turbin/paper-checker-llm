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

def get_promot():
    return ""

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

def check_paper_format(file):
    """检查论文格式"""
    if not file:
        return "请上传文件"
    
    try:
        format_info = extract_docx_info(file)
        
        prefix=f"""Role：你是一名学术专家。
                Background: 用户需要确保其上传的论文格式符合阳光学院本科生毕业论文(设计)的具体排版及打印要求，以保证论文的专业性和规范性。
                Constrains：必须符合下列要求，不得有偏差。
                ### **一、页面设置**

                1.**纸张规格**：A4纸（210×297mm），纵向打印。
                2.**页边距**：
                - 上边距/左边距：2.5厘米
                - 下边距/右边距：2厘米
                3.**输入法状态**：
                    - 除标题、图表/公式编号外，中文内容使用全角输入；
                    - 英文及数字符号使用半角输入。
                ---
                ### **二、封面**
                - 题目、系别、专业等采用**楷体小二号**，居中对齐；
                - 手写签名需用钢笔或签字笔，不可用圆珠笔；
                - 封面右上角需注明“正本”或“副本”（副本加盖“副本”章）。
                ---
                ### **三、摘要格式**
                - **中文摘要**：
                    - 标题“摘要”：黑体小二号，居中，与上下段落间距1行；
                    - 内容：宋体小四号，500-800字，首行缩进2字符，行距固定值20磅；
                    - 关键词：黑体小四号，“关键词”后接3-5个词，词间空2字符。
                - **英文摘要**：格式同中文，字体为Times New Roman。
                ---
                ### **四、目录**
                - 标题“目录”：黑体小二号，居中，与上下段落间距1行；
                - 内容：宋体小四号，仅列至二级标题，行距固定值20磅；
                - 不需包含“摘要”，需包含“附录”。
                ---
                ### **五、正文排版**
                1.**段落格式**：
                - 字体：宋体小四号；
                - 首行缩进2字符，行距固定值20磅；
                - 段落间无额外间距（段前段后距0行）。
                2.**标题层级**：
                    - **一级标题**（如“1 绪论”）：黑体小二号，居中，段前段后距各1行；
                    - **二级标题**（如“1.1 研究背景”）：黑体三号，左对齐顶格，段前段后距各1行；
                    - **三级标题**（如“1.1.1 数据来源”）：黑体小三号，左空2字符，段前段后距各1行；
                    - **四级标题**：黑体小四号，左空3字符，段前段后距各1行。
                ---
                ### **六、页眉与页码**
                - **页眉**：
                    - 从引言（第1章）开始添加；
                    - 奇偶页不同：奇数页为论文题目，偶数页为“阳光学院本科生毕业设计(论文)”；
                    - 宋体五号，居中，下加横线。
                - **页码**：
                    - 摘要、目录等前置部分用罗马数字（Ⅰ、Ⅱ...）；
                    - 正文起用阿拉伯数字（1、2...），居中对齐于页面底部。
                ---
                ### **七、图表与公式**
                - **图表**：
                    - 题注位于图下方/表上方，宋体五号，居中；
                    - 编号按章细分（如“图2-1”、“表3-2”）；
                    - 表格跨页需重复表头并标注“续表XX”。
                - **公式**：
                    - 居中书写，编号右对齐（如“公式(5-1)”）；
                    - 公式与正文间空1行。
                ---
                ### **八、参考文献**
                - 标题“参考文献”：黑体小二号，居中；
                - 内容：宋体五号，每条首行悬挂缩进2字符，行距固定值17磅；
                - 序号用方括号（如“[1]”），采用《GB/T 7714-2015》著录格式；
                - 文献类型标识符需正确标注（如[M]专著、[J]期刊）。
                ---
                ### **九、其他要求**
                1.**装订顺序**：
                - **正本**：封面→摘要→目录→正文→参考文献→附录→致谢；
                - **副本**：封面→目录→任务书→开题报告→诚信承诺书。
                2.**学术规范**：确保无抄袭，查重率理工科≤10%、文科≤15%（优秀论文标准）。
                ---
                ### **检查清单**
                1.是否所有页面边距、字体、行距符合规定？
                2.页眉是否从第1章开始，奇偶页内容是否正确？
                3.图表、公式编号是否连续且符合分章规则？
                4.参考文献列表是否完整，格式是否标准？
                5.是否有缺失的必选材料(如诚信承诺书、任务书)？
            Examples:
                - 例子1：检查封面是否使用楷体小二号字，题目、系别、专业等信息是否符合要求。
                - 例子2：审核摘要部分的论文题目是否居中，小二号黑体，摘要内容是否小四号宋体，行距是否固定值20磅。
                - 例子3：检查正文是否为宋体小四号，每个自然段首行是否缩进两个汉字的位置，行距是否固定值20磅。
                - 例子4：审核一级标题是否居中，黑体小二号，段前段后距是否为1行，行距是否固定值36磅。
                - 例子5：检查图表的标题是否居中，图序与图名是否置于图的下方，宋体五号，段前段后距是否为1行，行距是否固定值20磅。
        """

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
            
            return analysis
        else:
            return f"API请求失败：{response.status_code} - {response.text}"
        
    except Exception as e:
        return f"处理文件时出错：{str(e)}"
# 创建Gradio界面
demo = gr.Interface(
    fn=check_paper_format,
    inputs=gr.File(label="上传论文", file_types=[".docx"]),
    outputs=gr.Markdown(label="分析结果", autoscroll=True, elem_classes="scrollable-output", height=500),
    title="论文格式检查工具",
    description="请上传您的论文文件（.docx格式），系统将自动检查格式是否规范。",
    layout="vertical",
    allow_flagging="never"
)

if __name__ == "__main__":
    demo.launch(share=True)