"""
测试工具运行脚本
"""
import os
import sys
import argparse
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

def run_analyze_docx():
    """运行DOCX格式分析工具"""
    print("运行DOCX格式分析工具...")
    import analyze_docx
    
def run_format_test():
    """运行格式解析器测试"""
    print("运行DOCX格式解析器测试...")
    import test_docx_format
    
def main():
    parser = argparse.ArgumentParser(description="运行测试工具")
    parser.add_argument('tool', choices=['analyze', 'format', 'all'], 
                       help='要运行的工具: analyze=DOCX分析工具, format=格式解析器, all=全部')
    
    args = parser.parse_args()
    
    # 切换到脚本所在目录
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    
    if args.tool in ['analyze', 'all']:
        run_analyze_docx()
        
    if args.tool in ['format', 'all']:
        run_format_test()
        
if __name__ == "__main__":
    main() 