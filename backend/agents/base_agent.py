from abc import ABC, abstractmethod
from typing import Any, Dict

class BaseAgent(ABC):
    """Agent基类，定义基本接口"""
    
    def __init__(self, name: str):
        self.name = name
        
    @abstractmethod
    def run(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """运行Agent的主要逻辑"""
        pass
    
    @abstractmethod
    def validate_input(self, input_data: Dict[str, Any]) -> bool:
        """验证输入数据"""
        pass
    
    def handle_error(self, error: Exception) -> Dict[str, Any]:
        """处理错误"""
        return {
            "status": "error",
            "agent": self.name,
            "error": str(error)
        } 