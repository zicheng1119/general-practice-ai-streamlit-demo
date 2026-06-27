import { Link, Navigate, Outlet, Route, Routes, useLocation } from 'react-router-dom'

import './App.css'
import { DemoFlowProvider, useDemoFlow } from './flow/DemoFlowContext'
import { DoctorEncounterPage } from './pages/DoctorEncounterPage'
import { DoctorPreviewPage } from './pages/DoctorPreviewPage'
import { LandingPage } from './pages/LandingPage'
import { PatientAdvicePage } from './pages/PatientAdvicePage'
import { PatientBookingPage } from './pages/PatientBookingPage'
import { PatientBookingConfirmationPage } from './pages/PatientBookingConfirmationPage'
import { PatientIntakePage } from './pages/PatientIntakePage'
import { PatientTriagePage } from './pages/PatientTriagePage'
import type { Perspective } from './types'


const patientNavItems = [
  { to: '/patient/intake', label: '患者录入' },
  { to: '/patient/triage', label: 'AI 分诊' },
  { to: '/patient/booking', label: '智能挂号' },
  { to: '/patient/advice', label: '提醒中心' },
]

const doctorNavItems = [
  { to: '/doctor/encounter', label: '医生接诊' },
  { to: '/doctor/preview', label: 'AI 预览' },
]

function PortalPageLayout() {
  const { statusMessage } = useDemoFlow()

  return (
    <div className="shell">
      <div className="ambient ambient-left" />
      <div className="ambient ambient-right" />

      <header className="app-topbar">
        <Link className="brand-mark" to="/">
          全科智能就医闭环工作台
        </Link>
      </header>

      <div className="summary-strip">
        <div>
          <span>当前页面</span>
          <strong>角色入口</strong>
        </div>
        <div>
          <span>演示模式</span>
          <strong>单一网页分角色展示</strong>
        </div>
        <div>
          <span>流程提示</span>
          <strong>{statusMessage}</strong>
        </div>
      </div>

      <Outlet />
    </div>
  )
}

function SectionLayout({ perspective }: { perspective: Perspective }) {
  const location = useLocation()
  const { clearPerspective, statusMessage, selectedBooking, reminders } = useDemoFlow()
  const navItems = perspective === 'patient' ? patientNavItems : doctorNavItems

  return (
    <div className="shell">
      <div className="ambient ambient-left" />
      <div className="ambient ambient-right" />

      <header className="app-topbar">
        <Link className="brand-mark" to="/">
          全科智能就医闭环工作台
        </Link>
        <nav className="route-nav">
          {navItems.map((item) => (
            <Link
              className={location.pathname === item.to ? 'route-link active' : 'route-link'}
              key={item.to}
              to={item.to}
            >
              {item.label}
            </Link>
          ))}
          <Link className="route-link" onClick={clearPerspective} to="/">
            返回入口切换角色
          </Link>
        </nav>
      </header>

      <div className="summary-strip">
        <div>
          <span>当前页面</span>
          <strong>{navItems.find((item) => item.to === location.pathname)?.label ?? '流程页面'}</strong>
        </div>
        <div>
          <span>预约状态</span>
          <strong>{selectedBooking ? '已确认' : '待生成'}</strong>
        </div>
        <div>
          <span>提醒数量</span>
          <strong>{reminders.length} 条</strong>
        </div>
        <div>
          <span>流程提示</span>
          <strong>{statusMessage}</strong>
        </div>
      </div>

      <Outlet />
    </div>
  )
}

function GuardedSection({ perspective }: { perspective: Perspective }) {
  const { perspective: activePerspective } = useDemoFlow()

  if (activePerspective !== perspective) {
    return (
      <Navigate
        replace
        state={{ guardMessage: '请先从欢迎页选择患者端或医生端入口。', requestedPerspective: perspective }}
        to="/"
      />
    )
  }

  return <SectionLayout perspective={perspective} />
}


function AppRoutes() {
  return (
    <Routes>
      <Route element={<PortalPageLayout />}>
        <Route path="/" element={<LandingPage />} />
      </Route>

      <Route element={<GuardedSection perspective="patient" />}>
        <Route path="/patient/intake" element={<PatientIntakePage />} />
        <Route path="/patient/triage" element={<PatientTriagePage />} />
        <Route path="/patient/booking" element={<PatientBookingPage />} />
        <Route path="/patient/booking/confirmed" element={<PatientBookingConfirmationPage />} />
        <Route path="/patient/advice" element={<PatientAdvicePage />} />
      </Route>

      <Route element={<GuardedSection perspective="doctor" />}>
        <Route path="/doctor/encounter" element={<DoctorEncounterPage />} />
        <Route path="/doctor/preview" element={<DoctorPreviewPage />} />
      </Route>

      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}


function App() {
  return (
    <DemoFlowProvider>
      <AppRoutes />
    </DemoFlowProvider>
  )
}

export default App
