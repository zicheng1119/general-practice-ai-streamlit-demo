# 全科智能就医闭环 Web Demo

一个用于课程作业展示的多页面 Web 系统，覆盖：

- 症状初筛
- AI 分诊
- 智能挂号推荐
- 医生诊后录入
- 患者白话医嘱
- 用药/复诊提醒与随访反馈

线上演示地址：<https://general-practice-ai-demo.onrender.com/>

## 目录结构

- [frontend](./frontend): React + Vite 多页面前端
- [backend](./backend): FastAPI 编排后端，默认使用本地演示数据，可切换到外部 AI / 预约 / 临床记录提供方

## 当前“开源项目复用”状态

- `AI 分诊`
  当前已真实接入 `DeepSeek` 的 OpenAI 兼容接口。
- `智能挂号`
  默认使用本地演示号源，但后端已补上 `Easy!Appointments REST API` 兼容适配层，并支持真实创建 customer + appointment。
- `临床记录`
  默认使用本地内存记录，但后端已补上 `OpenMRS REST encounter` 兼容映射与回写入口。
- `提醒桥接`
  当前支持导出 `MedTimer` 兼容的备份 JSON，把药物和提醒桥接到开源提醒应用。

课堂答辩时可以如实表述：

- 演示环境默认跑本地闭环，保证流程稳定。
- 架构上已经拆成 `Provider / Adapter`，后续可切换到 `FastChat`、`Easy!Appointments`、`OpenMRS` 和 `MedTimer` 桥接。
- 欢迎页会展示当前实际启用的是 `mock`、`DeepSeek`、`FastChat`、`Easy!Appointments`、`OpenMRS` 还是 `MedTimer` 导出桥。

## 本地运行

### 1. 启动后端

```bash
cd backend
python3 -m pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

默认会使用内置的 mock 分诊规则。

如果你后期要接 DeepSeek V4 Pro：

```bash
cd backend
cp .env.example .env
uvicorn app.main:app --reload --port 8000
```

在 `.env` 中填写：

```env
AI_TRIAGE_MODE=deepseek
AI_TRIAGE_PROVIDER=deepseek
AI_TRIAGE_API_KEY=your-key
AI_TRIAGE_MODEL=deepseek-v4-pro
AI_TRIAGE_BASE_URL=https://api.deepseek.com
AI_TRIAGE_REASONING_EFFORT=high
AI_TRIAGE_THINKING_MODE=disabled
```

如果你要把分诊能力切换到 `FastChat`：

```env
AI_TRIAGE_PROVIDER=fastchat
AI_TRIAGE_MODEL=vicuna-13b
AI_TRIAGE_BASE_URL=http://127.0.0.1:8001/v1
AI_TRIAGE_API_KEY=
```

这里使用的是 `FastChat` 的 OpenAI 兼容网关。建议把 FastChat 网关放在 `8001`，本项目后端继续使用 `8000`，避免两个服务抢同一个端口。

如果你后期要接自己的自定义 AI 网关：

```env
AI_TRIAGE_MODE=external
AI_TRIAGE_URL=https://your-api.example.com/triage
AI_TRIAGE_API_KEY=your-key
```

自定义外部接口需要返回如下 JSON 结构：

```json
{
  "recommended_department": "呼吸内科",
  "urgency": "24小时内就诊",
  "confidence": 0.86,
  "explanation": "建议先到呼吸内科进一步评估。",
  "emergency": false,
  "risk_flags": [],
  "suggested_hospital_type": "综合医院或社区专科门诊",
  "disclaimer": "仅供辅助参考，以医生判断为准。"
}
```

如果你要把挂号能力切换到 `Easy!Appointments` 兼容模式：

```env
BOOKING_PROVIDER=easyappointments
BOOKING_BASE_URL=https://your-ea-installation.example.com
BOOKING_API_KEY=your-api-key
```

如果你要把医生诊后记录切换到 `OpenMRS` 兼容模式：

```env
CLINICAL_PROVIDER=openmrs
CLINICAL_BASE_URL=https://your-openmrs.example.com
CLINICAL_USERNAME=admin
CLINICAL_PASSWORD=Admin123
OPENMRS_PATIENT_UUID=your-patient-uuid
OPENMRS_PROVIDER_UUID=your-provider-uuid
OPENMRS_LOCATION_UUID=your-location-uuid
OPENMRS_ENCOUNTER_TYPE_UUID=your-encounter-type-uuid
OPENMRS_ENCOUNTER_ROLE_UUID=your-encounter-role-uuid
OPENMRS_SUMMARY_CONCEPT_UUID=your-summary-concept-uuid
OPENMRS_ADVICE_CONCEPT_UUID=your-advice-concept-uuid
OPENMRS_MEDICATION_PLAN_CONCEPT_UUID=your-medication-plan-concept-uuid
```

如果你要把提醒桥接到 `MedTimer`：

```env
REMINDER_PROVIDER=medtimer
```

患者端生成医嘱后，可以直接访问：

```bash
curl http://127.0.0.1:8000/reminders/export/medtimer/<encounter_id>
```

这个接口会返回 `MedTimer` 兼容的备份 JSON。

## 公共 Demo 验证

如果你想快速验证开源项目接入，而不是自己先部署整套服务：

```bash
cd backend
cp .env.public-demos.example .env
uvicorn app.main:app --reload --port 8000
```

这个 demo 配置会把：

- `Easy!Appointments` 指向 `https://demo.easyappointments.org`
- `OpenMRS` 指向 `https://o3.openmrs.org`
- `OpenMRS` 默认补上一组可用的文本 concept UUID，用于把摘要、医嘱和用药计划真正写进 `obs`
- `MedTimer` 保持导出桥模式
- `AI 分诊` 默认保持 `mock`，如果你本地自托管了 `FastChat`，再把 triage 段切过去

如果你只想验证公开 demo 本身是否可用，可以运行：

```bash
cd backend
python3 scripts/verify_public_demos.py
```

如果你允许脚本对公开 demo 执行真实写操作：

```bash
python3 scripts/verify_public_demos.py --write-easyappointments --write-openmrs
```

如果你想验证“本项目自己的后端”是否已经把分诊、挂号、诊后记录、提醒和 OpenMRS/MedTimer 串起来，可以在后端启动后运行：

```bash
cd backend
python3 scripts/verify_backend_e2e.py --base-url http://127.0.0.1:8000
```

以上 public demo 凭据和可用性是按 `2026-06-11` 实测的。

查看当前集成状态：

```bash
curl http://127.0.0.1:8000/integration/status
```

### 2. 启动前端

```bash
cd frontend
cp .env.example .env
npm install
npm run dev
```

默认地址：

- 前端：`http://127.0.0.1:5173`
- 后端：`http://127.0.0.1:8000`

## 测试与构建

```bash
cd backend && pytest -q
cd frontend && npm test
cd frontend && npm run lint
cd frontend && npm run build
```

## Streamlit Cloud 部署

本仓库提供了 `streamlit_app.py`，用于在 Streamlit Community Cloud 上部署一个单进程演示版。部署版会复用后端核心服务逻辑，覆盖：

- 患者症状录入
- DeepSeek 主分诊
- Kimi 云端二路复核
- 智能挂号推荐
- 医生诊后医嘱录入
- 患者白话医嘱、提醒与 MedTimer JSON 导出

### 1. GitHub 仓库

将项目推送到 GitHub 后，在 Streamlit Cloud 选择：

- Repository: 当前 GitHub 仓库
- Branch: `main`
- Main file path: `streamlit_app.py`

### 2. Secrets 配置

不要把 API Key 提交到 GitHub。请在 Streamlit Cloud 的 App settings -> Secrets 中粘贴类似配置：

```toml
AI_TRIAGE_API_KEY = "your-deepseek-api-key"
AI_TRIAGE_SECONDARY_API_KEY = "your-kimi-api-key"

AI_TRIAGE_MODE = "deepseek"
AI_TRIAGE_PROVIDER = "deepseek"
AI_TRIAGE_MODEL = "deepseek-v4-pro"
AI_TRIAGE_BASE_URL = "https://api.deepseek.com"

AI_TRIAGE_SECONDARY_PROVIDER = "kimi"
AI_TRIAGE_SECONDARY_MODEL = "moonshot-v1-auto"
AI_TRIAGE_SECONDARY_BASE_URL = "https://api.moonshot.cn/v1"

BOOKING_PROVIDER = "mock"
CLINICAL_PROVIDER = "memory"
REMINDER_PROVIDER = "medtimer"
```

也可以只填两个简写 key，应用会自动使用默认模型配置：

```toml
DEEPSEEK_API_KEY = "your-deepseek-api-key"
KIMI_API_KEY = "your-kimi-api-key"
```

如果把 Secrets 放在 `[general]` 分组里也可以，部署版会自动识别。保存 Secrets 后，请在 Streamlit Cloud 中点击重启或重新部署应用。应用侧边栏会显示 `Secrets 自检`，只显示脱敏后的配置状态，不会展示完整 key。

本地可参考 [.streamlit/secrets.toml.example](./.streamlit/secrets.toml.example)，但真实 `.streamlit/secrets.toml` 已被 `.gitignore` 排除。

## Render 部署

如果你希望线上效果尽量接近本地 React 界面，推荐用 Render 部署本仓库根目录的 `Dockerfile`。这个部署方式会：

- 构建 `frontend` 的 React/Vite 静态文件。
- 用 FastAPI 启动后端。
- 让同一个 Render 网址同时提供前端页面和 API。

### 1. 使用 Blueprint 部署

在 Render 控制台选择：

- New -> Blueprint
- 选择 GitHub 仓库
- Branch: `main`
- Blueprint file: `render.yaml`

也可以选择 New -> Web Service，Runtime 选择 Docker，仓库根目录保持默认即可。

### 2. Environment 配置

不要把真实 API Key 提交到 GitHub。请在 Render 的 Environment 页面填写：

```env
AI_TRIAGE_API_KEY=your-deepseek-api-key
AI_TRIAGE_SECONDARY_API_KEY=your-kimi-api-key
```

`render.yaml` 已经内置以下默认配置：

```env
AI_TRIAGE_MODE=deepseek
AI_TRIAGE_PROVIDER=deepseek
AI_TRIAGE_MODEL=deepseek-v4-pro
AI_TRIAGE_BASE_URL=https://api.deepseek.com
AI_TRIAGE_SECONDARY_PROVIDER=kimi
AI_TRIAGE_SECONDARY_MODEL=moonshot-v1-auto
AI_TRIAGE_SECONDARY_BASE_URL=https://api.moonshot.cn/v1
BOOKING_PROVIDER=mock
CLINICAL_PROVIDER=memory
REMINDER_PROVIDER=medtimer
```

### 3. 验证部署

Render 部署完成后：

- 当前线上演示地址：<https://general-practice-ai-demo.onrender.com/>
- 打开 Render 给出的公网 URL，应该看到 React 版 Web Demo。
- 访问 `<Render URL>/health`，应该返回 `{"status":"ok"}`。
- 前端路由如 `<Render URL>/patient/intake` 会由 FastAPI 回退到 React 页面。

Render 免费实例可能会休眠，第一次打开会慢一些。
