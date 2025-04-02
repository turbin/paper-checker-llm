from typing import Dict, Any, List
from .base_agent import BaseAgent
from .format_agents import (
    CoverAgent, HeaderFooterAgent, TableAgent, ChapterAgent, 
    TableOfContentsAgent, OriginalityStatementAgent, CopyrightStatementAgent
)
from backend.utils.logger_config import logger
from docx import Document
import os

class AgentManager:
    """Agent管理器，用于协调多个Agent的工作"""
    
    def __init__(self):
        self.agents: List[BaseAgent] = [
            CoverAgent(),
            HeaderFooterAgent(),
            TableAgent(),
            ChapterAgent(),
            TableOfContentsAgent(),
            OriginalityStatementAgent(),
            CopyrightStatementAgent()
        ]
        
    def run_all(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """运行所有Agent
        
        Args:
            input_data: 输入数据，可以包含以下字段:
                - document: python-docx Document对象，如果直接传入文档
                - document_path: 文档路径，如果需要从文件加载
                - use_docx_parser: 是否使用DocxFormatParser进行解析
                - structured_content: 从文档提取的结构化内容
                - cover_content: 封面内容
                - header_footer: 页眉页脚内容
                - tables: 表格内容
                - chapters: 章节内容
                - table_of_contents: 目录内容
                - template: 模板类型
        """
        try:
            # 如果提供了document_path但没有document，则加载文档
            if "document_path" in input_data and "document" not in input_data:
                try:
                    input_data["document"] = Document(input_data["document_path"])
                    logger.info(f"已从路径加载文档: {input_data['document_path']}")
                except Exception as e:
                    logger.error(f"从路径加载文档失败: {str(e)}")
            
            # 根据模板类型调整配置
            if "template" not in input_data:
                input_data["template"] = "xmu"  # 默认使用厦门大学模板
            
            results = []
            
            # 运行每个Agent
            for agent in self.agents:
                try:
                    if agent.validate_input(input_data):
                        result = agent.run(input_data)
                        results.append(result)
                except Exception as e:
                    logger.error(f"运行Agent {agent.name} 时出错: {str(e)}", exc_info=True)
                    results.append({
                        "status": "error",
                        "agent": agent.name,
                        "message": str(e)
                    })
            
            # 汇总所有结果
            total_issues = sum(len(result.get("issues", [])) for result in results)
            
            summary = {
                "status": "success" if all(result.get("status") == "success" for result in results) else "partially_success",
                "total_issues": total_issues,
                "results": results
            }
            
            if total_issues == 0:
                summary["message"] = "未发现任何格式问题，文档符合要求。"
            else:
                summary["message"] = f"发现 {total_issues} 个格式问题，详情请查看各Agent结果。"
            
            return summary
            
        except Exception as e:
            logger.error(f"运行所有Agent时出错: {str(e)}", exc_info=True)
            return {
                "status": "error",
                "message": f"运行Agent出错: {str(e)}",
                "results": []
            }
        
    def _merge_results(self, results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """合并所有Agent的结果"""
        merged = {
            "status": "success",
            "total_agents": len(results),
            "successful_agents": 0,
            "failed_agents": 0,
            "issues": [],
            "suggestions": []
        }
        
        for result in results:
            if result["status"] == "success":
                merged["successful_agents"] += 1
            else:
                merged["failed_agents"] += 1
                
            if "issues" in result:
                merged["issues"].extend(result["issues"])
            if "suggestions" in result:
                merged["suggestions"].extend(result["suggestions"])
                
        return merged 
    

    def _get_prompt(self, template):
        """根据模板类型返回对应的提示词"""
        if not template:
            template = "xmu"  # 默认使用厦大模板
            
        # 获取当前文件所在目录的上级目录
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        # 构建规则文件路径
        ruler_file = os.path.join(base_dir, 'promots', f'{template}.ruler')
        
        # 检查文件是否存在
        if not os.path.exists(ruler_file):
            logger.error(f'模板文件 {ruler_file} 不存在')
            raise FileNotFoundError(f'模板文件 {ruler_file} 不存在')
        
        # 读取并返回文件内容
        with open(ruler_file, 'r', encoding='utf-8') as f:
            content = f.read().strip()
            logger.debug(f'已加载模板文件 {ruler_file}')
            return content