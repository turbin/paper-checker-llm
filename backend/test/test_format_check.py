"""
测试论文格式检查功能
"""
import os
import sys
import json
from docx import Document
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from backend.services.document_service import DocumentService
from backend.utils.docx_format_parser import DocxFormatParser
from backend.agents.agent_manager import AgentManager
from backend.utils.config import Config
from backend.utils.logger_config import logger

def test_format_check():
    """
    测试论文格式检查功能
    
    此测试用例会：
    1. 读取test/docs目录中的test.docx文件
    2. 解析该文件获取格式信息
    3. 读取promots目录下的xmu.ruler中的论文格式要求
    4. 使用这些要求检查论文是否满足厦门大学管理学院MBA学位论文格式要求
    """
    try:
        # 设置文件路径
        test_dir = os.path.dirname(os.path.abspath(__file__))
        doc_path = os.path.join(test_dir, 'docs', 'test.docx')
        
        # 确认文件存在
        if not os.path.exists(doc_path):
            print(f"测试文件不存在: {doc_path}")
            print(f"当前工作目录: {os.getcwd()}")
            return

        print(f"\n开始测试论文格式检查功能...")
        print(f"使用测试文档: {doc_path}")
        
        # 1. 读取文档
        print("\n1. 读取测试文档...")
        document = Document(doc_path)
        print(f"文档读取成功，段落数: {len(document.paragraphs)}, 表格数: {len(document.tables)}")
        
        # 2. 使用DocxFormatParser解析文档
        print("\n2. 使用DocxFormatParser解析文档...")
        parser = DocxFormatParser(doc_path)
        doc_content = parser.extract_docx_content()
        print(f"文档解析完成，提取了 {len(doc_content['paragraphs'])} 个段落和 {len(doc_content['tables'])} 个表格")
        
        # 保存解析结果以便检查
        debug_dir = os.path.join(test_dir, 'debug')
        os.makedirs(debug_dir, exist_ok=True)
        debug_file = os.path.join(debug_dir, 'doc_analysis.json')
        
        def json_serializer(obj):
            if hasattr(obj, "__dict__"):
                return obj.__dict__
            return str(obj)
        
        with open(debug_file, 'w', encoding='utf-8') as f:
            json.dump(doc_content, f, default=json_serializer, ensure_ascii=False, indent=2)
        print(f"文档分析结果已保存到: {debug_file}")
        
        # 3. 使用DocumentService提取文档内容
        print("\n3. 使用DocumentService提取文档内容...")
        doc_service = DocumentService()
        extracted_content = doc_service.extract_docx_content_with_xml(doc_path)
        print(f"文档内容提取完成")
        
        # 4. 准备格式检查的输入数据
        print("\n4. 准备格式检查数据...")
        # 创建测试用的规则文件(JSON格式)
        project_root = str(Path(__file__).parent.parent.parent)
        source_ruler_path = os.path.join(project_root, "promots", "xmu.ruler")
        
        # 创建一个JSON格式的临时规则文件
        temp_ruler_json = {
            "cover": {
                "title": {
                    "font": "黑体",
                    "font_size": 18,
                    "alignment": 1  # 居中
                },
                "author": {
                    "font": "楷体",
                    "font_size": 14,
                    "alignment": 1  # 居中
                },
                "other_info": {
                    "font": "宋体",
                    "font_size": 12,
                    "alignment": 1  # 居中
                }
            },
            "chapter": {
                "title": {
                    "font": "黑体",
                    "font_size": 16,
                    "alignment": 1  # 居中
                },
                "subtitle": {
                    "font": "黑体",
                    "font_size": 14,
                    "alignment": 0  # 左对齐
                },
                "content": {
                    "font": "宋体",
                    "font_size": 12,
                    "alignment": 0,  # 左对齐
                    "line_spacing": 1.5,
                    "first_line_indent": 24  # 首行缩进2字符
                }
            },
            "header_footer": {
                "header": {
                    "font": "宋体",
                    "font_size": 10.5,
                    "alignment": 1  # 居中
                },
                "footer": {
                    "font": "宋体",
                    "font_size": 10.5,
                    "alignment": 1  # 居中
                }
            },
            "table": {
                "caption": {
                    "font": "宋体",
                    "font_size": 12,
                    "alignment": 1,  # 居中
                    "bold": True
                },
                "content": {
                    "font": "宋体",
                    "font_size": 10.5,
                    "alignment": 0  # 左对齐
                },
                "source": {
                    "font": "宋体",
                    "font_size": 9,
                    "alignment": 0  # 左对齐
                }
            },
            "figure": {
                "caption": {
                    "font": "宋体",
                    "font_size": 12,
                    "alignment": 1,  # 居中
                    "bold": True
                },
                "source": {
                    "font": "宋体",
                    "font_size": 9,
                    "alignment": 0  # 左对齐
                }
            },
            "reference": {
                "title": {
                    "font": "黑体",
                    "font_size": 16,
                    "alignment": 1  # 居中
                },
                "content": {
                    "font": "宋体",
                    "font_size": 10.5,
                    "alignment": 0  # 左对齐
                }
            }
        }
        
        # 保存临时JSON规则文件
        temp_ruler_path = os.path.join(debug_dir, 'xmu_ruler.json')
        with open(temp_ruler_path, 'w', encoding='utf-8') as f:
            json.dump(temp_ruler_json, f, ensure_ascii=False, indent=2)
        print(f"创建临时规则文件: {temp_ruler_path}")
        
        input_data = {
            'document': document,
            'document_path': doc_path,
            'use_docx_parser': True,
            'structured_content': extracted_content,
            'template': 'xmu',  # 使用厦门大学模板
            'ruler_path': temp_ruler_path  # 使用临时JSON规则文件
        }
        
        # 5. 使用AgentManager运行格式检查
        print("\n5. 运行格式检查...")
        agent_manager = AgentManager()
        results = agent_manager.run_all(input_data)
        
        # 6. 保存和输出检查结果
        results_file = os.path.join(debug_dir, 'format_check_results.json')
        with open(results_file, 'w', encoding='utf-8') as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        print(f"格式检查结果已保存到: {results_file}")
        
        # 7. 打印检查结果摘要
        print("\n7. 格式检查结果摘要:")
        print(f"检查状态: {results['status']}")
        print(f"问题总数: {results['total_issues']}")
        if results.get('message'):
            print(f"摘要信息: {results['message']}")
        
        # 打印每个Agent的检查结果
        for result in results.get('results', []):
            agent_name = result.get('agent', 'unknown')
            issues_count = len(result.get('issues', []))
            print(f"\n- {agent_name}: 发现 {issues_count} 个问题")
            
            # 打印问题和建议
            if issues_count > 0:
                print("  问题列表:")
                for i, issue in enumerate(result.get('issues', []), 1):
                    print(f"  {i}. {issue}")
                
                print("  建议列表:")
                for i, suggestion in enumerate(result.get('suggestions', []), 1):
                    print(f"  {i}. {suggestion}")
        
        print("\n格式检查测试完成")
        
    except Exception as e:
        print(f"测试过程中发生错误: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_format_check() 