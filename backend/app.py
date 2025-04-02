import os
import io
import json
from flask import Flask, request, jsonify
from flask_cors import CORS
from backend.agents.agent_manager import AgentManager
from backend.services.document_service import DocumentService
from backend.utils.config import Config
from backend.utils.logger_config import logger
import tempfile
from datetime import datetime

app = Flask(__name__)
CORS(app)

# 初始化服务
document_service = DocumentService()
agent_manager = AgentManager()

@app.route('/api/upload', methods=['POST'])
def upload_file():
    """文件上传接口，支持docx和zip格式
    
    文件会被解析并进行格式检查，返回检查结果
    """
    try:
        if 'file' not in request.files:
            return jsonify({'status': 'error', 'message': '未找到文件'}), 400
            
        file = request.files['file']
        
        if file.filename == '':
            return jsonify({'status': 'error', 'message': '未选择文件'}), 400
            
        # 获取模板参数，默认使用xmu模板
        template = request.form.get('template', 'xmu')
        
        # 使用优化的XML/OOXML解析
        use_xml_parser = request.form.get('use_xml_parser', 'false').lower() == 'true'
        
        # 读取文档，如果使用XML解析则同时保存临时文件
        result = document_service.read_document(file, save_temp=use_xml_parser)
        
        # 根据返回类型处理文档对象和路径
        document = None
        document_path = None
        if isinstance(result, dict):
            document = result["document"]
            document_path = result["document_path"]
        else:
            document = result
        
        # 提取文档内容（使用对应的解析器）
        content = None
        if use_xml_parser and document_path:
            # 使用基于XML/OOXML的解析器
            content = document_service.extract_docx_content_with_xml(document_path)
        else:
            # 使用标准解析器
            content = document_service.extract_docx_content(document)
        
        # 如果开启了调试模式，保存提取的内容
        if Config.get_debug_mode():
            timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
            debug_file = f"debug_content_{timestamp}.json"
            output_path = os.path.join(os.getcwd(), "debug", debug_file)
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            document_service.save_extracted_content(content, output_path)
            logger.debug(f"已保存调试内容到: {output_path}")
        
        # 运行所有格式检查Agent
        input_data = {
            'document': document,
            'template': template,
        }
        
        # 如果使用XML解析器，添加相关参数
        if use_xml_parser and document_path:
            input_data['document_path'] = document_path
            input_data['use_docx_parser'] = True
        
        # 添加提取的结构化内容
        input_data['structured_content'] = content
        
        # 运行所有格式检查Agent
        results = agent_manager.run_all(input_data)
        
        # 清理临时文件
        if use_xml_parser and document_path and os.path.exists(document_path):
            try:
                os.remove(document_path)
                logger.debug(f"已删除临时文件: {document_path}")
            except Exception as e:
                logger.warning(f"删除临时文件失败: {str(e)}")
        
        return jsonify(results)
        
    except Exception as e:
        logger.error(f"处理上传文件时发生错误: {str(e)}", exc_info=True)
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/test', methods=['GET'])
def test():
    """测试接口"""
    return jsonify({'status': 'success', 'message': 'API正常工作'})

@app.route('/api/templates', methods=['GET'])
def get_templates():
    """获取可用的论文模板"""
    templates = [
        {
            'id': 'xmu',
            'name': '厦门大学学术论文',
            'description': '适用于厦门大学本科毕业论文'
        },
        {
            'id': 'custom',
            'name': '自定义模板',
            'description': '使用自定义格式要求'
        }
    ]
    return jsonify({'status': 'success', 'templates': templates})

@app.route('/api/health', methods=['GET'])
def health_check():
    """健康检查接口"""
    return jsonify({
        'status': 'healthy',
        'version': '1.0.0'
    })

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5300, debug=True)