import { Link, useNavigate } from 'react-router-dom'

import { useDemoFlow } from '../flow/DemoFlowContext'


export function PatientBookingPage() {
  const { recommendations, confirmBooking, triageResult, selectedBooking, statusMessage, submitting } = useDemoFlow()
  const navigate = useNavigate()

  async function handleBooking(index: number) {
    const ok = await confirmBooking(recommendations[index])
    if (ok) {
      navigate('/patient/booking/confirmed')
    }
  }

  if (!triageResult) {
    return (
      <section className="content-card">
        <h2>请先完成分诊</h2>
        <Link className="primary-link" to="/patient/intake">
          回到患者录入页
        </Link>
      </section>
    )
  }

  return (
    <section className="content-card">
      <div className="section-heading">
        <p className="section-kicker">患者端 / 第 3 步</p>
        <h2>智能挂号推荐</h2>
        <p className="muted-copy">
          当前推荐科室：{triageResult.recommended_department}
          {selectedBooking ? '，已生成预约记录。' : '，请选择一个号源继续。'}
        </p>
      </div>

      {recommendations.length ? (
        <div className="recommendation-list">
          {recommendations.map((item, index) => (
            <article className="recommendation-card" key={`${item.hospital_id}-${item.slot}`}>
              <div className="recommendation-header">
                <div>
                  <strong>{item.hospital_name}</strong>
                  <p>
                    {item.department} · {item.doctor_name}
                  </p>
                </div>
                <span>{Math.round(item.score * 100)} 分</span>
              </div>
              <p>{item.label}</p>
              {item.ai_reason ? <p className="muted-copy">{item.ai_reason}</p> : null}
              <div className="recommendation-meta">
                <span>{item.slot}</span>
                <span>{item.distance_km} km</span>
              </div>
              <button
                className="primary-button compact"
                disabled={submitting}
                onClick={() => handleBooking(index)}
                type="button"
              >
                预约该号源
              </button>
            </article>
          ))}
        </div>
      ) : (
        <p className="muted-copy">当前没有可展示的号源数据。</p>
      )}

      <p className="muted-copy">{statusMessage}</p>
    </section>
  )
}
