import { Link } from 'react-router-dom'

import { useDemoFlow } from '../flow/DemoFlowContext'


export function PatientBookingConfirmationPage() {
  const { selectedBooking, statusMessage } = useDemoFlow()

  if (!selectedBooking) {
    return (
      <section className="content-card">
        <div className="section-heading">
          <p className="section-kicker">患者端 / 第 3 步</p>
          <h2>尚未生成预约确认</h2>
        </div>
        <p className="muted-copy">请先完成分诊并选择号源。</p>
        <Link className="primary-link" to="/patient/booking">
          返回挂号推荐页
        </Link>
      </section>
    )
  }

  return (
    <section className="content-card">
      <div className="section-heading">
        <p className="section-kicker">患者端 / 第 3 步</p>
        <h2>预约确认</h2>
        <p className="muted-copy">预约已提交，当前页面仅展示患者可见信息。</p>
      </div>

      <div className="booking-banner">
        <strong>{selectedBooking.hospital_name}</strong>
        <p>
          {selectedBooking.department} · {selectedBooking.doctor_name} · {selectedBooking.slot}
        </p>
      </div>

      <div className="tips-list">
        {selectedBooking.notes.map((note) => (
          <span key={note}>{note}</span>
        ))}
      </div>

      <div className="action-row">
        <Link className="primary-link" to="/">
          返回入口切换角色
        </Link>
        <p className="muted-copy">{statusMessage}</p>
      </div>
    </section>
  )
}
