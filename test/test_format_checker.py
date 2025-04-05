import os
import sys
import pytest
import io
import zipfile
import json
import requests
from unittest import mock

# 设置项目根目录路径
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, PROJECT_ROOT)

# 在导入应用程序之前，模拟requests.post以避免实际API调用
@pytest.fixture(autouse=True)
def mock_requests_post(monkeypatch):
    """模拟requests.post方法以避免实际的API调用"""
    mock_response = mock.MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "choices": [
            {
                "message": {
                    "content": """
                    论文格式分析结果:
                    
                    1. 格式规范性评估:
                       - 总体符合学术论文格式规范
                       - 字体选择适当，使用了宋体、黑体等标准字体
                       - 行间距设置合理，有利于阅读
                       
                    2. 页面设置:
                       - 页眉页脚设置正确
                       - 页边距符合要求
                       
                    3. 章节结构:
                       - 标题层级清晰
                       - 摘要部分格式规范
                       
                    4. 改进建议:
                       - 建议统一部分段落的行间距
                       - 参考文献格式可以更加规范
                    """
                }
            }
        ]
    }
    
    def mock_post(*args, **kwargs):
        return mock_response
    
    monkeypatch.setattr(requests, "post", mock_post)

# 导入后端应用 (在conftest.py中已经模拟了logger_config)
from backend.app import app, FormatCheckerFactory

@pytest.fixture
def client():
    """创建测试客户端"""
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client

def create_test_zip(docx_path):
    """创建测试用的zip文件（内含docx文件）"""
    memory_file = io.BytesIO()
    
    with zipfile.ZipFile(memory_file, 'w') as zf:
        # 获取docx文件名
        filename = os.path.basename(docx_path)
        
        # 读取docx内容
        with open(docx_path, 'rb') as f:
            docx_content = f.read()
        
        # 将docx内容写入zip
        zf.writestr(filename, docx_content)
    
    # 定位到内存文件开始位置
    memory_file.seek(0)
    return memory_file

def test_format_check_xmu(client):
    """测试厦门大学论文格式检查功能"""
    # 准备测试文件路径
    test_paper_path = os.path.join(PROJECT_ROOT, 'docs', 'test_paper.docx')
    assert os.path.exists(test_paper_path), f"测试文件不存在: {test_paper_path}"
    
    # 创建测试用zip文件
    zip_data = create_test_zip(test_paper_path)
    
    # 构建请求数据
    data = {'template': 'xmu'}  # 使用厦门大学模板
    
    # 发送请求 - 修复文件上传方式
    response = client.post(
        '/api/upload',
        data={
            'template': 'xmu',
            'file': (zip_data, 'test_paper.zip', 'application/zip')
        }
    )
    
    # 检查响应状态
    assert response.status_code == 200, f"API请求失败，状态码: {response.status_code}"
    
    # 解析响应内容
    response_data = json.loads(response.data)
    assert 'result' in response_data, "响应中缺少'result'字段"
    
    # 检查分析结果
    analysis_result = response_data['result']
    assert len(analysis_result) > 100, "分析结果内容过短"
    
    # 确认结果中包含预期的关键词
    key_indicators = ["格式", "规范", "字体", "间距", "页面", "标题", "摘要"]
    for indicator in key_indicators:
        assert indicator in analysis_result, f"分析结果中缺少关键词: {indicator}"
    
    # 测试通过
    assert True

def test_format_check_sunshine(client):
    """测试阳光学院论文格式检查功能"""
    # 准备测试文件路径
    test_paper_path = os.path.join(PROJECT_ROOT, 'docs', 'test_paper.docx')
    assert os.path.exists(test_paper_path), f"测试文件不存在: {test_paper_path}"
    
    # 创建测试用zip文件
    zip_data = create_test_zip(test_paper_path)
    
    # 发送请求 - 修复文件上传方式
    response = client.post(
        '/api/upload',
        data={
            'template': 'sunshine',
            'file': (zip_data, 'test_paper.zip', 'application/zip')
        }
    )
    
    # 检查响应状态
    assert response.status_code == 200, f"API请求失败，状态码: {response.status_code}"
    
    # 解析响应内容
    response_data = json.loads(response.data)
    assert 'result' in response_data, "响应中缺少'result'字段"
    
    # 检查分析结果
    analysis_result = response_data['result']
    assert len(analysis_result) > 100, "分析结果内容过短"
    
    # 确认结果中包含预期的关键词
    key_indicators = ["格式", "规范", "字体", "行间距", "页眉", "页脚"]
    for indicator in key_indicators:
        assert indicator in analysis_result, f"分析结果中缺少关键词: {indicator}"
    
    # 测试通过
    assert True
