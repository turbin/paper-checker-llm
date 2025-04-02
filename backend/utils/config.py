import os
from dotenv import load_dotenv
from backend.utils.logger_config import logger

class Config:
    _instance = None
    
    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = Config()
        return cls._instance
    
    def __init__(self):
        self.base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.env_path = os.path.join(self.base_dir, '.env')
        self.load_env()
        self.setup_api_config()
        self.setup_app_config()
    
    def load_env(self):
        """加载环境变量"""
        logger.info(f'尝试加载环境变量文件: {self.env_path}')
        if os.path.exists(self.env_path):
            load_dotenv(self.env_path)
            logger.info('成功加载环境变量文件')
        else:
            logger.warning(f'环境变量文件不存在: {self.env_path}')
    
    def setup_api_config(self):
        """设置API配置"""
        self.api_key = os.getenv('OPENAI_API_KEY')
        self.api_base = os.getenv('OPENAI_API_BASE', 'https://api.moonshot.cn/v1')
        self.model_name = os.getenv('MODEL_NAME', 'moonshot-v1-8k')
        
        # 记录API配置信息
        if self.api_key:
            masked_key = self.api_key[:6] + '*' * (len(self.api_key) - 6) if len(self.api_key) > 6 else '******'
            logger.info(f'API密钥已设置，前6位: {self.api_key[:6]}...')
        else:
            logger.warning('API密钥未设置')
        logger.info(f'API基础URL: {self.api_base}')
        logger.info(f'模型名称: {self.model_name}')
    
    def setup_app_config(self):
        """设置应用程序配置"""
        self.debug_mode = os.getenv('DEBUG', 'False').lower() in ('true', '1', 'yes')
        logger.info(f'调试模式: {"启用" if self.debug_mode else "禁用"}')
    
    def get_prompts_path(self):
        """获取prompts路径"""
        return os.path.join(self.base_dir, 'prompts')
    
    @staticmethod
    def get_debug_mode():
        """获取调试模式设置"""
        return Config.get_instance().debug_mode