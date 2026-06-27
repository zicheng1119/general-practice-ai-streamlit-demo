# 全科智能就医闭环 Web Demo 提交说明

## 在线演示

- Render 线上地址：<https://general-practice-ai-demo.onrender.com/>
- 健康检查：<https://general-practice-ai-demo.onrender.com/health>
- 前端深链接示例：<https://general-practice-ai-demo.onrender.com/patient/intake>

## 项目简介

本项目是一个面向全科医学课程展示的智能就医闭环 Web Demo。系统从患者症状录入开始，经过 AI 分诊、挂号推荐、医生诊后记录、患者白话医嘱、用药提醒和随访反馈，模拟一次完整的基层/全科就医辅助流程。

## 主要功能

- 患者端症状采集与 AI 初筛。
- DeepSeek 主分诊与 Kimi 二路复核配置。
- 红旗症状安全规则兜底，出现胸痛、呼吸困难等高危信息时优先提示急诊风险。
- 智能挂号推荐，默认使用本地演示号源，并保留 Easy!Appointments 适配层。
- 医生诊后记录，默认本地内存保存，并保留 OpenMRS encounter 映射。
- 患者白话医嘱、用药提醒、随访反馈与 MedTimer JSON 导出。
- React + FastAPI 单站部署，Render 公网地址同时承载前端页面和后端 API。

## 技术栈

- 前端：React、Vite、TypeScript。
- 后端：FastAPI、Pydantic、Uvicorn。
- AI 接口：OpenAI-compatible Chat Completions 方式接入 DeepSeek/Kimi。
- 部署：Dockerfile + Render Web Service / Blueprint。

## 本地运行

后端：

```bash
cd backend
python3 -m pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

前端：

```bash
cd frontend
npm install
cp .env.example .env
npm run dev
```

本地默认地址：

- 前端：<http://127.0.0.1:5173>
- 后端：<http://127.0.0.1:8000>

## Render 部署说明

本仓库根目录已提供：

- `Dockerfile`
- `render.yaml`
- `.dockerignore`

Render 部署时选择 GitHub 仓库的 `main` 分支即可。需要在 Render 的 Environment 中配置：

```env
AI_TRIAGE_API_KEY=your-deepseek-api-key
AI_TRIAGE_SECONDARY_API_KEY=your-kimi-api-key
```

真实 API Key 不应提交到仓库或压缩包。

## 验收建议

1. 打开 <https://general-practice-ai-demo.onrender.com/>，确认首页可以展示。
2. 进入患者端，填写姓名、年龄、主诉和症状，完成 AI 分诊。
3. 使用胸痛、呼吸困难等红旗症状测试急诊风险提示。
4. 按页面流程继续完成挂号推荐、医生诊后记录和患者医嘱生成。
5. 打开 <https://general-practice-ai-demo.onrender.com/health>，确认后端 API 正常返回 `{"status":"ok"}`。

## 安全与隐私说明

- 压缩包和 GitHub 仓库不包含真实 `.env`、`.streamlit/secrets.toml` 或 API Key。
- 项目为课程展示与辅助决策 Demo，不替代真实医生诊断。
- 页面内医学建议均应以线下医生判断为准。
