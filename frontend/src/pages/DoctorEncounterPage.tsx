import { Link, useNavigate } from 'react-router-dom'

import { useDemoFlow } from '../flow/DemoFlowContext'


export function DoctorEncounterPage() {
  const { selectedBooking, doctorNote, updateDoctorNote, submitDoctorEntry, statusMessage } = useDemoFlow()
  const navigate = useNavigate()

  if (!selectedBooking) {
    return (
      <section className="content-card">
        <div className="section-heading">
          <p className="section-kicker">医生端</p>
          <h2>尚无可录入的就诊记录</h2>
        </div>
        <p className="muted-copy">当前还没有待接诊的 encounter。请先完成预约，再从欢迎页切回医生角色。</p>
        <Link className="primary-link" to="/">
          返回角色入口
        </Link>
      </section>
    )
  }

  async function handleSubmit() {
    const ok = await submitDoctorEntry()
    if (ok) {
      navigate('/doctor/preview')
    }
  }

  return (
    <section className="content-card">
      <div className="section-heading">
        <p className="section-kicker">医生端 / 第 4 步</p>
        <h2>诊后录入与医嘱生成</h2>
      </div>

      <div className="booking-banner">
        <strong>{selectedBooking.hospital_name}</strong>
        <p>
          {selectedBooking.department} · {selectedBooking.doctor_name} · {selectedBooking.slot}
        </p>
      </div>

      <label className="wide">
        <span>诊断摘要</span>
        <textarea
          value={doctorNote.diagnosis_summary}
          onChange={(event) =>
            updateDoctorNote({ ...doctorNote, diagnosis_summary: event.target.value })
          }
        />
      </label>

      <div className="medication-grid">
        <label>
          <span>药品名称</span>
          <input
            value={doctorNote.medications[0].name}
            onChange={(event) =>
              updateDoctorNote({
                ...doctorNote,
                medications: [{ ...doctorNote.medications[0], name: event.target.value }],
              })
            }
          />
        </label>
        <label>
          <span>剂量</span>
          <input
            value={doctorNote.medications[0].dose}
            onChange={(event) =>
              updateDoctorNote({
                ...doctorNote,
                medications: [{ ...doctorNote.medications[0], dose: event.target.value }],
              })
            }
          />
        </label>
        <label>
          <span>频次</span>
          <input
            value={doctorNote.medications[0].frequency}
            onChange={(event) =>
              updateDoctorNote({
                ...doctorNote,
                medications: [{ ...doctorNote.medications[0], frequency: event.target.value }],
              })
            }
          />
        </label>
        <label>
          <span>疗程</span>
          <input
            type="number"
            value={doctorNote.medications[0].duration_days}
            onChange={(event) =>
              updateDoctorNote({
                ...doctorNote,
                medications: [
                  {
                    ...doctorNote.medications[0],
                    duration_days: Number(event.target.value) || 1,
                  },
                ],
              })
            }
          />
        </label>
      </div>

      <label className="wide">
        <span>用药说明</span>
        <textarea
          value={doctorNote.medications[0].instruction}
          onChange={(event) =>
            updateDoctorNote({
              ...doctorNote,
              medications: [{ ...doctorNote.medications[0], instruction: event.target.value }],
            })
          }
        />
      </label>
      <label className="wide">
        <span>医嘱补充</span>
        <textarea
          value={doctorNote.doctor_advice}
          onChange={(event) => updateDoctorNote({ ...doctorNote, doctor_advice: event.target.value })}
        />
      </label>
      <label>
        <span>复诊日期</span>
        <input
          value={doctorNote.follow_up_date}
          onChange={(event) => updateDoctorNote({ ...doctorNote, follow_up_date: event.target.value })}
        />
      </label>

      <div className="action-row">
        <button className="primary-button" onClick={handleSubmit} type="button">
          生成患者版医嘱
        </button>
        <p className="muted-copy">{statusMessage}</p>
      </div>
    </section>
  )
}
