"""
分析DOCX文档格式的测试工具
"""
from docx import Document
from docx.oxml.ns import qn
import os

# 读取文档
file_path = os.path.join(os.path.dirname(__file__), 'docs', 'test.docx')
doc = Document(file_path)

# 检查第一个非空段落
for p in doc.paragraphs:
    if p.text.strip():
        para = p
        break

print(f'段落文本: {para.text}')
print(f'段落样式: {para.style.name}')

# 检查直接XML内容
print('\nXML属性:')
for r in para.runs:
    if not r.text.strip():
        continue
    print(f'  Run: "{r.text}"')
    if hasattr(r, '_element') and r._element is not None:
        # 字体名称
        font_elems = r._element.xpath('.//w:rFonts')
        if font_elems:
            for attr in ['w:ascii', 'w:eastAsia', 'w:hAnsi']:
                val = font_elems[0].get(qn(attr))
                if val:
                    print(f'    {attr}: {val}')
        
        # 字号
        sz_elems = r._element.xpath('.//w:sz')
        if sz_elems:
            val = sz_elems[0].get(qn('w:val'))
            print(f'    字号(半点值): {val} (等于{int(val)/2}pt)')
        
        # 颜色
        color_elems = r._element.xpath('.//w:color')
        if color_elems:
            val = color_elems[0].get(qn('w:val'))
            print(f'    颜色: {val}')
            
        # 主题颜色
        theme_elems = r._element.xpath('.//*[contains(local-name(), "theme")]')
        for elem in theme_elems:
            for attr_name in elem.keys():
                print(f'    主题属性: {attr_name}={elem.get(attr_name)}')
                
        # 粗体、斜体等
        b_elems = r._element.xpath('.//w:b')
        if b_elems:
            print(f'    粗体: {b_elems[0].get(qn("w:val"), "true")}')
            
        i_elems = r._element.xpath('.//w:i')
        if i_elems:
            print(f'    斜体: {i_elems[0].get(qn("w:val"), "true")}')

# 打印样式继承关系
print("\n样式继承关系:")
style = para.style
while style:
    print(f"  {style.name}")
    if hasattr(style, "base_style") and style.base_style:
        style = style.base_style
    else:
        break

# 查看文档主题设置
print("\n文档主题设置:")
try:
    theme_parts = doc.part.package.parts
    for part in theme_parts:
        if "theme" in part.partname.lower():
            print(f"  主题名称: {part.partname}")
except Exception as e:
    print(f"  无法读取主题: {str(e)}") 