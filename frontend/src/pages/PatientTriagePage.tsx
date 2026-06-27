import { Link, useNavigate } from 'react-router-dom'

import { useDemoFlow } from '../flow/DemoFlowContext'


export function PatientTriagePage() {
  const {
    triageSession,
    triageResult,
    followupAnswer,
    setFollowupAnswer,
    submitFollowupAnswer,
    statusMessage,
    submitting,
  } = useDemoFlow()
  const navigate = useNavigate()

  async function handleNext() {
    navigate('/patient/booking')
  }

  async function handleRefresh() {
    await submitFollowupAnswer()
  }

  if (!triageSession || !triageResult) {
    return (
      <section className="content-card">
        <h2>尚未生成分诊结果</h2>
        <p className="muted-copy">请先回到患者端录入页面生成分诊。</p>
        <Link className="primary-link" to="/patient/intake">
          返回录入页
        </Link>
      </section>
    )
  }

  return (
    <section className="content-card">
      <div className="section-heading">
        <p className="section-kicker">患者端 / 第 2 步</p>
        <h2>AI 分诊结果</h2>
        <p className="muted-copy">
          先看综合建议，再查看 DeepSeek 与 FastChat 两路分诊的可用状态和复核意见。
        </p>
      </div>

      <div className="result-panel standalone">
        <div className="result-topline">
          <span className={triageResult.emergency ? 'alert-chip danger' : 'alert-chip'}>
            {triageResult.urgency}
          </span>
          <span className="confidence-chip">置信度 {Math.round(triageResult.confidence * 100)}%</span>
        </div>
        <h3>{triageResult.recommended_department}</h3>
        <p>{triageResult.explanation}</p>
        <p className="disclaimer">{triageResult.disclaimer}</p>
        {triageResult.risk_flags.length ? (
          <div className="risk-list">
            {triageResult.risk_flags.map((flag) => (
              <span key={flag}>{flag}</span>
            ))}
          </div>
        ) : null}
        {triageResult.consensus_summary ? <p className="muted-copy">{triageResult.consensus_summary}</p> : null}
        {triageResult.disagreement_note ? <p className="caution">{triageResult.disagreement_note}</p> : null}
      </div>

      {triageResult.validation_results?.length ? (
        <div className="triage-validation-block">
          <div className="section-heading compact-heading">
            <p className="section-kicker">双路分诊校验</p>
            <h3>两种分诊方式状态</h3>
          </div>
          <div className="recommendation-list triage-validation-list">
            {triageResult.validation_results.map((item) => (
              <article
                className={
                  item.status === 'available'
                    ? 'recommendation-card validation-card'
                    : 'recommendation-card validation-card unavailable'
                }
                key={`${item.source}-${item.label}`}
              >
                <div className="recommendation-header">
                  <div>
                    <p className="section-kicker">{item.label}</p>
                    <strong>{item.result?.recommended_department ?? '当前不可用'}</strong>
                  </div>
                  <span className={item.status === 'available' ? 'alert-chip' : 'confidence-chip warning-chip'}>
                    {item.status === 'available' ? '可用' : '不可用，已兜底'}
                  </span>
                </div>
                {item.result ? (
                  <div className="recommendation-meta">
                    <span>{item.result.urgency}</span>
                    <span>置信度 {Math.round(item.result.confidence * 100)}%</span>
                  </div>
                ) : null}
                {item.result ? <p>{item.result.explanation}</p> : null}
                {item.note ? <p className="muted-copy">{item.note}</p> : null}
              </article>
            ))}
          </div>
        </div>
      ) : null}

      {triageSession.question ? (
        <div className="followup-card">
          <div>
            <p className="section-kicker">AI 追问</p>
            <strong>{triageSession.question}</strong>
          </div>
          <textarea
            value={followupAnswer}
            onChange={(event) => setFollowupAnswer(event.target.value)}
            placeholder="补充回答会在这里输入"
          />
          <button
            className="ghost-button"
            disabled={submitting || !followupAnswer.trim()}
            onClick={handleRefresh}
            type="button"
          >
            {submitting ? '刷新中...' : '刷新分诊结果'}
          </button>
        </div>
      ) : null}

      <div className="action-row">
        <button className="primary-button" onClick={handleNext} type="button">
          {triageResult.emergency ? '查看急诊推荐页' : '进入挂号推荐页'}
        </button>
        <p className="muted-copy">{statusMessage}</p>
      </div>
    </section>
  )
}
