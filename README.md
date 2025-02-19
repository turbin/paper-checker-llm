# 论文格式检查工具

这是一个基于AI的论文格式检查工具，可以自动检查论文是否符合阳光学院本科生毕业论文(设计)的排版要求。

## 功能特点

- 自动检查论文格式是否符合规范
- 支持docx格式文件
- 提供详细的格式分析报告
- Web界面操作，使用简单

## 部署方法

### 使用Docker部署（推荐）

1. 确保已安装Docker
2. 克隆项目到本地：
   ```bash
   git clone [项目地址]
   cd paper-checker-llm
   ```
3. 创建.env文件并配置以下环境变量：
   ```
   OPENAI_API_KEY=你的OpenAI API密钥
   OPENAI_API_BASE=你的API基础URL
   MODEL_NAME=你要使用的模型名称
   ```
4. 构建Docker镜像：
   ```bash
   docker build -t paper-checker .
   ```
5. 运行容器：
   ```bash
   docker run -d -p 7860:7860 --env-file .env paper-checker
   ```
6. 访问 http://localhost:7860 即可使用

### 本地部署

1. 确保安装Python 3.9或更高版本
2. 克隆项目并进入目录：
   ```bash
   git clone [项目地址]
   cd paper-checker-llm
   ```
3. 安装依赖：
   ```bash
   pip install -r requirements.txt
   ```
4. 配置环境变量（同Docker部署步骤3）
5. 启动应用：
   ```bash
   python app.py
   ```
6. 访问 http://localhost:7860 使用工具

## 使用说明

1. 打开工具网页界面
2. 点击上传按钮，选择要检查的论文文件（.docx格式）
3. 等待系统分析完成
4. 查看分析结果，根据建议修改论文格式

## 注意事项

- 仅支持.docx格式的文件
- 需要有效的OpenAI API密钥
- 确保网络能够访问OpenAI API
- 建议使用Chrome或Firefox浏览器访问

## 技术栈

- Python 3.9
- Gradio
- python-docx
- OpenAI API
- Docker

## 许可证

MIT License