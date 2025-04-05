import os
import sys
import pytest
from unittest import mock

# 设置项目根目录路径
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, PROJECT_ROOT)
sys.path.insert(0, os.path.join(PROJECT_ROOT, 'backend'))

# 模拟logger模块（需要在导入后端应用前完成）
@pytest.fixture(scope="session", autouse=True)
def mock_logger_config():
    """模拟logger_config模块，避免实际创建日志文件"""
    mock_logger = mock.MagicMock()
    mock_logger.debug = mock.MagicMock()
    mock_logger.info = mock.MagicMock()
    mock_logger.warning = mock.MagicMock()
    mock_logger.error = mock.MagicMock()
    mock_logger.critical = mock.MagicMock()
    
    mock_logger_module = mock.MagicMock()
    mock_logger_module.logger = mock_logger
    mock_logger_module.setup_logger = mock.MagicMock(return_value=mock_logger)
    
    sys.modules['logger_config'] = mock_logger_module
    return mock_logger

@pytest.fixture(scope="session", autouse=True)
def setup_test_environment():
    """设置测试环境，确保必要的目录存在，环境变量设置正确"""
    # 确保必要的目录存在
    backend_path = os.path.join(PROJECT_ROOT, 'backend')
    logs_dir = os.path.join(backend_path, 'logs')
    output_dir = os.path.join(backend_path, 'output')
    os.makedirs(logs_dir, exist_ok=True)
    os.makedirs(output_dir, exist_ok=True)
    
    # 加载环境变量
    env_file = os.path.join(PROJECT_ROOT, '.env')
    if os.path.exists(env_file):
        with open(env_file) as f:
            for line in f:
                if line.strip() and not line.startswith('#'):
                    try:
                        key, value = line.strip().split('=', 1)
                        os.environ[key] = value
                    except ValueError:
                        pass  # 跳过格式不正确的行
    
    # 设置默认API密钥（如果没有在环境变量中）
    if 'OPENAI_API_KEY' not in os.environ:
        os.environ['OPENAI_API_KEY'] = 'test_api_key_for_pytest'
    
    if 'OPENAI_API_BASE' not in os.environ:
        os.environ['OPENAI_API_BASE'] = 'https://api.moonshot.cn/v1'
    
    if 'MODEL_NAME' not in os.environ:
        os.environ['MODEL_NAME'] = 'moonshot-v1-8k'
    
    yield 