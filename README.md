# 论文格式检查系统

这是一个基于 AI 的论文格式检查系统，可以自动分析论文格式是否符合特定的学术规范。

## 功能特点

- 支持多种论文格式模板（阳光学院、厦门大学）
- 自动分析论文格式并提供详细的检查报告
- 支持 .docx 格式的论文文件
- 提供友好的用户界面

## 技术栈

- 前端：Vue 3 + Element Plus
- 后端：Flask
- AI：基于大型语言模型的文本分析
- 部署：Docker + Nginx

## 快速开始

### 使用 Docker 部署

1. 克隆仓库

```bash
git clone https://github.com/yourusername/paper-checker-llm.git
cd paper-checker-llm
```

2. 创建 .env 文件

```bash
cp .env.example .env
```

编辑 .env 文件，设置您的 API 密钥和其他配置：

```
OPENAI_API_KEY=your_api_key_here
OPENAI_API_BASE=https://api.siliconflow.cn/v1
MODEL_NAME=deepseek-ai/DeepSeek-R1-Distill-Qwen-7B
```

3. 使用 Docker Compose 构建和启动服务

```bash
docker-compose up -d
```

4. 访问应用

打开浏览器，访问 http://localhost:8080

### 本地开发

1. 启动后端服务

```bash
cd backend
pip install -r requirements.txt
python app.py
```

2. 启动前端服务

```bash
cd frontend
npm install
npm run dev
```

3. 访问应用

打开浏览器，访问 http://localhost:3000

## 使用说明

1. 选择论文格式模板
2. 上传 .docx 格式的论文文件
3. 点击"开始检查"按钮
4. 等待系统分析完成
5. 查看检查结果和建议

## 注意事项

- 仅支持 .docx 格式的文件
- 每次只能上传一份论文
- 需要有效的 API 密钥才能使用 AI 分析功能

## 许可证

MIT