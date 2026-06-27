import { useEffect, useState } from 'react'
import { Link, useLocation } from 'react-router-dom'

import { fetchIntegrationStatus } from '../api'
import { useDemoFlow } from '../flow/DemoFlowContext'
import type { IntegrationStatus } from '../types'


export function LandingPage() {
  const { enterPerspective, statusMessage, selectedBooking, advice, followupResult } = useDemoFlow()
  const location = useLocation()
  const [integration, setIntegration] = useState<IntegrationStatus | null>(null)
  const guardMessage = typeof location.state?.guardMessage === 'string' ? location.state.guardMessage : ''

  useEffect(() => {
    let active = true

    fetchIntegrationStatus()
      .then((result) => {
        if (active) {
          setIntegration(result)
        }
      })
      .catch(() => {
        if (active) {
          setIntegration(null)
        }
      })

    return () => {
      active = false
    }
  }, [])

  return (
    <div className="page-grid landing-grid">
      <section className="hero-panel">
        <div className="hero-copy">
          <p className="eyebrow">General Medicine Integrated Demo</p>
          <h1>全科智能就医闭环工作台</h1>
          <p className="hero-text">
            这是一套面向课程答辩的多页面 Web 演示系统。你可以从欢迎页分流到患者端或医生端，再按真实就医节奏推进后续页面。
          </p>
          {guardMessage ? <p className="caution">{guardMessage}</p> : null}
          <div className="hero-tags">
            <span>欢迎页分流</span>
            <span>患者端多页面</span>
            <span>医生端独立入口</span>
            <span>开源项目适配层</span>
          </div>
        </div>

        <div className="status-card">
          <span className="status-label">当前系统状态</span>
          <strong>{statusMessage}</strong>
          <p>预约状态：{selectedBooking ? '已生成' : '未开始'}</p>
          <p>患者医嘱：{advice ? '已生成' : '未生成'}</p>
          <p>闭环状态：{followupResult?.care_status ?? '演示中'}</p>
        </div>
      </section>

      <section className="choice-grid">
        <article className="choice-card">
          <p className="section-kicker">患者入口</p>
          <h2>从症状录入开始</h2>
          <p>依次进入症状初筛、AI 分诊、智能挂号和患者提醒页面。</p>
          <div className="choice-actions">
            <Link className="primary-link" onClick={() => enterPerspective('patient')} to="/patient/intake">
              进入患者端
            </Link>
            <Link className="ghost-link" onClick={() => enterPerspective('patient')} to="/patient/advice">
              查看患者提醒页
            </Link>
          </div>
        </article>

        <article className="choice-card">
          <p className="section-kicker">医生入口</p>
          <h2>从诊后录入开始</h2>
          <p>预约生成后，医生端可独立进入诊断摘要、药物和医嘱录入页面。</p>
          <div className="choice-actions">
            <Link className="primary-link" onClick={() => enterPerspective('doctor')} to="/doctor/encounter">
              进入医生端
            </Link>
            <Link className="ghost-link" onClick={() => enterPerspective('doctor')} to="/doctor/preview">
              查看 AI 预览页
            </Link>
          </div>
        </article>
      </section>

      <section className="integration-grid">
        <article className="content-card standalone">
          <div className="section-heading">
            <p className="section-kicker">开源复用状态</p>
            <h2>当前不是只做了界面，而是保留了外部项目接入口</h2>
            <p className="muted-copy">
              默认演示环境优先保证流程稳定，但后端已经拆出可切换 Provider，用来兼容 GitHub 开源项目能力。
            </p>
          </div>

          {integration ? (
            <div className="integration-cards">
              {[
                { title: 'AI 分诊', item: integration.triage },
                { title: '智能挂号', item: integration.booking },
                { title: '临床记录', item: integration.clinical },
                { title: '提醒桥接', item: integration.reminder },
              ].map(({ title, item }) => (
                <article className="integration-card" key={title}>
                  <div className="recommendation-header">
                    <div>
                      <p className="section-kicker">{title}</p>
                      <h3>{item.label}</h3>
                    </div>
                    <span className={item.configured ? 'alert-chip' : 'confidence-chip'}>
                      {item.mode}
                    </span>
                  </div>
                  <p>{item.details}</p>
                  <p className="muted-copy">兼容接口：{item.compatibility}</p>
                  {item.write_mode ? <p className="muted-copy">写入模式：{item.write_mode}</p> : null}
                  {item.docs_url ? (
                    <a className="ghost-link inline-link" href={item.docs_url} rel="noreferrer" target="_blank">
                      查看对应官方接口文档
                    </a>
                  ) : null}
                </article>
              ))}
            </div>
          ) : (
            <p className="muted-copy">集成状态读取失败，但不影响本地演示流程。</p>
          )}
        </article>
      </section>
    </div>
  )
}
