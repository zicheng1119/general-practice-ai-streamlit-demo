import { Link } from 'react-router-dom'

import { getMedTimerExportUrl } from '../api'
import { useDemoFlow } from '../flow/DemoFlowContext'


export function PatientAdvicePage() {
  const {
    advice,
    reminders,
    selectedBooking,
    feedbackState,
    feedbackNote,
    followupResult,
    setFeedbackState,
    setFeedbackNote,
    completeReminder,
    submitFollowup,
  } = useDemoFlow()

  if (!advice) {
    return (
      <section className="content-card">
        <div className="section-heading">
          <p className="section-kicker">患者端 / 第 5 步</p>
          <h2>尚未生成患者版医嘱</h2>
        </div>
        <p className="muted-copy">诊后记录尚未同步完成，请稍后刷新，或返回入口切换角色继续演示。</p>
        <Link className="primary-link" to="/">
          返回角色入口
        </Link>
      </section>
    )
  }

  return (
    <section className="content-card">
      <div className="section-heading">
        <p className="section-kicker">患者端 / 第 5 步</p>
        <h2>白话医嘱与提醒中心</h2>
      </div>

      <div className="advice-card">
        <span className="alert-chip">
          {advice.advice_generation_mode === 'ai' ? 'AI 白话医嘱' : '患者可读版'}
        </span>
        <h3>{advice.original_summary}</h3>
        <p>{advice.plain_language_advice}</p>
        {advice.caution ? <p className="caution">{advice.caution}</p> : null}
      </div>

      <div className="tips-list">
        {advice.lifestyle_tips.map((tip) => (
          <span key={tip}>{tip}</span>
        ))}
      </div>

      {selectedBooking ? (
        <div className="action-row">
          <a
            className="ghost-link"
            href={getMedTimerExportUrl(selectedBooking.encounter_id)}
            rel="noreferrer"
            target="_blank"
          >
            导出 MedTimer 备份
          </a>
          <p className="muted-copy">可将当前药物与提醒桥接到 MedTimer 的 JSON 备份格式。</p>
        </div>
      ) : null}

      <div className="reminder-list">
        {reminders.map((reminder) => (
          <article className="reminder-card" key={reminder.id}>
            <div className="recommendation-header">
              <div>
                <strong>{reminder.title}</strong>
                <p>{reminder.description}</p>
              </div>
              <span>{reminder.status}</span>
            </div>
            <p>{reminder.due_at}</p>
            <div className="reminder-actions">
              <button className="ghost-button compact" onClick={() => completeReminder(reminder.id, 'done')} type="button">
                已服药
              </button>
              <button className="ghost-button compact" onClick={() => completeReminder(reminder.id, 'snoozed')} type="button">
                稍后提醒
              </button>
              <button className="ghost-button compact danger" onClick={() => completeReminder(reminder.id, 'missed')} type="button">
                漏服
              </button>
            </div>
          </article>
        ))}
      </div>

      <div className="feedback-card">
        <label>
          <span>症状变化</span>
          <select
            value={feedbackState}
            onChange={(event) => setFeedbackState(event.target.value as 'better' | 'same' | 'worse')}
          >
            <option value="better">已好转</option>
            <option value="same">无明显变化</option>
            <option value="worse">症状加重</option>
          </select>
        </label>
        <label className="wide">
          <span>随访备注</span>
          <textarea value={feedbackNote} onChange={(event) => setFeedbackNote(event.target.value)} />
        </label>
        <button className="primary-button" onClick={submitFollowup} type="button">
          提交随访反馈
        </button>
        {followupResult ? <p className="followup-state">当前照护状态：{followupResult.care_status}</p> : null}
        {followupResult?.ai_summary ? <p>{followupResult.ai_summary}</p> : null}
        {followupResult?.next_step ? <p className="muted-copy">{followupResult.next_step}</p> : null}
        {followupResult?.doctor_reply ? (
          <div className="advice-card">
            <span className="alert-chip">医生回复</span>
            <p>{followupResult.doctor_reply.message}</p>
            <p className="muted-copy">{followupResult.doctor_reply.replied_at}</p>
          </div>
        ) : null}
      </div>
    </section>
  )
}
