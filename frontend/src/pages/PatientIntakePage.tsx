import { useNavigate } from 'react-router-dom'

import { useDemoFlow } from '../flow/DemoFlowContext'


const splitTags = (value: string) =>
  value
    .split(/[、，,]/)
    .map((item) => item.trim())
    .filter(Boolean)


export function PatientIntakePage() {
  const { intake, updateIntake, canSubmitIntake, restoreDemoCase, submitIntake, submitting } =
    useDemoFlow()
  const navigate = useNavigate()

  async function handleSubmit() {
    const ok = await submitIntake()
    if (ok) {
      navigate('/patient/triage')
    }
  }

  return (
    <section className="content-card">
      <div className="section-heading">
        <p className="section-kicker">患者端 / 第 1 步</p>
        <h2>症状录入与基础资料</h2>
      </div>

      <div className="form-grid">
        <label>
          <span>患者姓名</span>
          <input
            value={intake.name}
            onChange={(event) => updateIntake({ name: event.target.value })}
            placeholder="例如：李同学"
          />
        </label>
        <label>
          <span>年龄</span>
          <input
            type="number"
            value={intake.age}
            onChange={(event) => updateIntake({ age: Number(event.target.value) || 0 })}
          />
        </label>
        <label>
          <span>性别</span>
          <select
            value={intake.gender}
            onChange={(event) => updateIntake({ gender: event.target.value as typeof intake.gender })}
          >
            <option value="female">女</option>
            <option value="male">男</option>
            <option value="other">其他</option>
          </select>
        </label>
        <label>
          <span>病程</span>
          <input
            value={intake.duration}
            onChange={(event) => updateIntake({ duration: event.target.value })}
            placeholder="例如：2天"
          />
        </label>
        <label className="wide">
          <span>主诉</span>
          <textarea
            value={intake.chief_complaint}
            onChange={(event) => updateIntake({ chief_complaint: event.target.value })}
            placeholder="例如：发热咳嗽两天，夜里加重"
          />
        </label>
        <label>
          <span>严重程度</span>
          <select
            value={intake.severity}
            onChange={(event) => updateIntake({ severity: event.target.value as typeof intake.severity })}
          >
            <option value="轻">轻</option>
            <option value="中等">中等</option>
            <option value="严重">严重</option>
          </select>
        </label>
        <label>
          <span>症状标签</span>
          <input
            value={intake.symptoms.join('、')}
            onChange={(event) => updateIntake({ symptoms: splitTags(event.target.value) })}
          />
        </label>
        <label>
          <span>伴随症状</span>
          <input
            value={intake.companions.join('、')}
            onChange={(event) => updateIntake({ companions: splitTags(event.target.value) })}
          />
        </label>
        <label>
          <span>慢病史</span>
          <input
            value={intake.chronic_conditions.join('、')}
            onChange={(event) => updateIntake({ chronic_conditions: splitTags(event.target.value) })}
          />
        </label>
        <label>
          <span>过敏史</span>
          <input
            value={intake.allergies.join('、')}
            onChange={(event) => updateIntake({ allergies: splitTags(event.target.value) })}
          />
        </label>
        <label>
          <span>正在用药</span>
          <input
            value={intake.medications.join('、')}
            onChange={(event) => updateIntake({ medications: splitTags(event.target.value) })}
          />
        </label>
      </div>

      <div className="action-row">
        <button
          className="primary-button"
          disabled={submitting || !canSubmitIntake}
          onClick={handleSubmit}
          type="button"
        >
          {submitting ? '正在生成分诊...' : '进入 AI 分诊页'}
        </button>
        <button className="ghost-button" onClick={restoreDemoCase} type="button">
          恢复演示病例
        </button>
      </div>

      {!canSubmitIntake ? (
        <p className="hint-text">先填写患者姓名和主诉，系统才能开始分诊。</p>
      ) : null}
    </section>
  )
}
