import { Link } from 'react-router-dom'

import { useDemoFlow } from '../flow/DemoFlowContext'


export function DoctorPreviewPage() {
  const {
    advice,
    doctorNote,
    doctorReplyDraft,
    followupResult,
    reminders,
    selectedBooking,
    setDoctorReplyDraft,
    statusMessage,
    submitting,
    submitDoctorReply,
  } = useDemoFlow()

  if (!selectedBooking) {
    return (
      <section className="content-card">
        <div className="section-heading">
          <p className="section-kicker">医生端 / AI 预览</p>
          <h2>当前没有可预览的 encounter</h2>
        </div>
        <p className="muted-copy">请先完成预约并录入诊后信息。</p>
        <Link className="primary-link" to="/doctor/encounter">
          返回医生录入页
        </Link>
      </section>
    )
  }

  if (!advice) {
    return (
      <section className="content-card">
        <div className="section-heading">
          <p className="section-kicker">医生端 / AI 预览</p>
          <h2>患者版医嘱尚未生成</h2>
        </div>
        <p className="muted-copy">请先在医生录入页提交诊断摘要和用药方案。</p>
        <Link className="primary-link" to="/doctor/encounter">
          返回医生录入页
        </Link>
      </section>
    )
  }

  return (
    <section className="content-card">
      <div className="section-heading">
        <p className="section-kicker">医生端 / 第 5 步</p>
        <h2>医生端 AI 预览</h2>
        <p className="muted-copy">当前页面用于确认患者可见的白话医嘱和提醒是否准确。</p>
      </div>

      <div className="booking-banner">
        <strong>{selectedBooking.hospital_name}</strong>
        <p>
          {selectedBooking.department} · {selectedBooking.doctor_name} · {selectedBooking.slot}
        </p>
      </div>

      <div className="page-grid">
        <article className="content-card standalone">
          <div className="section-heading">
            <p className="section-kicker">医生专业版</p>
            <h3>{doctorNote.diagnosis_summary}</h3>
          </div>
          <div className="tips-list">
            {doctorNote.medications.map((item) => (
              <span key={`${item.name}-${item.dose}`}>
                {item.name} {item.dose} · {item.frequency} · {item.duration_days} 天 · {item.instruction}
              </span>
            ))}
          </div>
          <p>{doctorNote.doctor_advice}</p>
          <p className="muted-copy">复诊日期：{doctorNote.follow_up_date}</p>
        </article>

        <article className="content-card standalone">
          <div className="section-heading">
            <p className="section-kicker">患者可见版</p>
            <h3>{advice.original_summary}</h3>
          </div>
          <p>{advice.plain_language_advice}</p>
          {advice.caution ? <p className="caution">{advice.caution}</p> : null}
          <div className="tips-list">
            {advice.lifestyle_tips.map((tip) => (
              <span key={tip}>{tip}</span>
            ))}
          </div>
        </article>
      </div>

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
          </article>
        ))}
      </div>

      {followupResult ? (
        <div className="feedback-card">
          <div className="section-heading compact-heading">
            <p className="section-kicker">患者随访</p>
            <h3>患者随访待回复</h3>
          </div>
          <p>{followupResult.note}</p>
          {followupResult.ai_summary ? <p className="muted-copy">{followupResult.ai_summary}</p> : null}
          {followupResult.doctor_reply ? (
            <div className="advice-card">
              <span className="alert-chip">已回复</span>
              <p>{followupResult.doctor_reply.message}</p>
              <p className="muted-copy">{followupResult.doctor_reply.replied_at}</p>
            </div>
          ) : (
            <>
              <label className="wide">
                <span>医生回复</span>
                <textarea
                  value={doctorReplyDraft}
                  onChange={(event) => setDoctorReplyDraft(event.target.value)}
                  placeholder="例如：继续观察，若夜间咳嗽仍影响睡眠，请提前复诊。"
                />
              </label>
              <button
                className="primary-button"
                disabled={submitting || !doctorReplyDraft.trim()}
                onClick={submitDoctorReply}
                type="button"
              >
                发送医生回复
              </button>
            </>
          )}
        </div>
      ) : null}

      <div className="action-row">
        <Link className="primary-link" to="/">
          返回入口切换角色
        </Link>
        <p className="muted-copy">{statusMessage}</p>
      </div>
    </section>
  )
}
