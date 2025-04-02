"""
测试Word文档格式解析
"""
import os
import json
import sys
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from backend.utils.docx_format_parser import DocxFormatParser

# 文档路径
doc_path = os.path.join(os.path.dirname(__file__), 'docs', 'test.docx')
print(f"测试文件路径: {doc_path}")
print(f"文件是否存在: {os.path.exists(doc_path)}")

# 创建格式解析器
parser = DocxFormatParser(doc_path)

# 获取主题颜色
print("\n主题颜色:")
for name, color in parser.theme_colors.items():
    print(f"  {name}: #{color}")

# 打印样式映射
print("\n样式定义:")
for name, props in parser.style_map.items():
    print(f"  {name}: 字体={props['font']}, 字号={props['size']}, 颜色={props['color']}")
    if props['parent']:
        print(f"    继承自: {props['parent']}")

# 分析几个段落作为示例
print("\n段落格式示例:")
for i, para in enumerate(parser.document.paragraphs[:5]):
    if not para.text.strip():
        continue
        
    format_info = parser.get_paragraph_format(para)
    print(f"\n段落 {i+1}: {format_info['text'][:30]}...")
    print(f"  样式链: {format_info['style_chain']}")
    print(f"  字体: {format_info['font']}")
    print(f"  字号: {format_info['size']}")
    print(f"  颜色: {format_info['color']}")
    
    # 打印Run级别格式
    for j, run_format in enumerate(format_info['runs']):
        print(f"  Run {j+1}: {run_format['text'][:20]}...")
        print(f"    字体: {run_format['font']}")
        print(f"    字号: {run_format['size']}")
        print(f"    颜色: {run_format['color']}")
        print(f"    粗体: {run_format['bold']}")
        print(f"    斜体: {run_format['italic']}")

# 保存完整分析结果到JSON
doc_info = parser.analyze_document()
output_path = os.path.join(os.path.dirname(__file__), 'doc_format_analysis.json')
with open(output_path, 'w', encoding='utf-8') as f:
    json.dump(doc_info, f, ensure_ascii=False, indent=2)
    
print(f"\n完整分析结果已保存到 {output_path}") 