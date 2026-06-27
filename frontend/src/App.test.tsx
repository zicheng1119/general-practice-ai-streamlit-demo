import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'

import App from './App'


const fetchMock = vi.fn()
globalThis.fetch = fetchMock as typeof fetch

function renderApp(route = '/') {
  return render(
    <MemoryRouter initialEntries={[route]}>
      <App />
    </MemoryRouter>,
  )
}

describe('App', () => {
  beforeEach(() => {
    fetchMock.mockReset()
    window.sessionStorage.clear()
  })

  test('renders landing page with integration status cards', async () => {
    fetchMock.mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        triage: {
          provider: 'deepseek',
          label: 'DeepSeek deepseek-v4-pro',
          mode: 'live',
          compatibility: 'OpenAI-compatible chat completions / FastChat gateway',
          configured: true,
          docs_url: 'https://api-docs.deepseek.com/',
          details: '当前分诊已连接真实大模型。',
        },
        booking: {
          provider: 'mock',
          label: '本地演示号源',
          mode: 'demo',
          compatibility: 'Easy!Appointments adapter ready',
          configured: true,
          docs_url: 'https://easyappointments.org/documentation/rest-api/',
          details: '当前展示数据来自本地号源表，便于课堂演示完整挂号流程。',
          write_mode: 'local',
        },
        clinical: {
          provider: 'memory',
          label: '本地临床记录',
          mode: 'demo',
          compatibility: 'OpenMRS encounter mapping ready',
          configured: true,
          docs_url: 'https://rest.openmrs.org/',
          details: '当前诊后记录保存在本地内存，用于生成患者白话医嘱和提醒。',
        },
        reminder: {
          provider: 'medtimer',
          label: 'MedTimer 备份桥接',
          mode: 'export',
          compatibility: 'MedTimer JSON backup format',
          configured: true,
          docs_url: 'https://github.com/Futsch1/medTimer',
          details: '可将当前患者的药物提醒导出为 MedTimer 可识别的备份 JSON。',
        },
      }),
    })

    renderApp('/')

    expect(screen.getByRole('heading', { name: '全科智能就医闭环工作台' })).toBeInTheDocument()
    expect(screen.getByText('开源复用状态')).toBeInTheDocument()
    expect(await screen.findByText('DeepSeek deepseek-v4-pro')).toBeInTheDocument()
    expect(screen.getByText(/Easy!Appointments adapter ready/)).toBeInTheDocument()
    expect(screen.getByText('MedTimer 备份桥接')).toBeInTheDocument()
  })

  test('shows validation hint on patient intake route before required fields are filled', async () => {
    fetchMock.mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        triage: {
          provider: 'deepseek',
          label: 'DeepSeek deepseek-v4-pro',
          mode: 'live',
          compatibility: 'OpenAI-compatible chat completions / FastChat gateway',
          configured: true,
          docs_url: 'https://api-docs.deepseek.com/',
          details: '当前分诊已连接真实大模型。',
        },
        booking: {
          provider: 'mock',
          label: '本地演示号源',
          mode: 'demo',
          compatibility: 'Easy!Appointments adapter ready',
          configured: true,
          docs_url: 'https://easyappointments.org/documentation/rest-api/',
          details: '当前展示数据来自本地号源表，便于课堂演示完整挂号流程。',
          write_mode: 'local',
        },
        clinical: {
          provider: 'memory',
          label: '本地临床记录',
          mode: 'demo',
          compatibility: 'OpenMRS encounter mapping ready',
          configured: true,
          docs_url: 'https://rest.openmrs.org/',
          details: '当前诊后记录保存在本地内存，用于生成患者白话医嘱和提醒。',
        },
        reminder: {
          provider: 'medtimer',
          label: 'MedTimer 备份桥接',
          mode: 'export',
          compatibility: 'MedTimer JSON backup format',
          configured: true,
          docs_url: 'https://github.com/Futsch1/medTimer',
          details: '可将当前患者的药物提醒导出为 MedTimer 可识别的备份 JSON。',
        },
      }),
    })

    renderApp('/')
    await userEvent.click(screen.getByRole('link', { name: '进入患者端' }))

    expect(screen.getByRole('button', { name: '进入 AI 分诊页' })).toBeDisabled()
    expect(screen.getByText('先填写患者姓名和主诉，系统才能开始分诊。')).toBeInTheDocument()
  })

  test('keeps patient and doctor portals isolated while completing the full handoff flow', async () => {
    fetchMock.mockImplementation(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = typeof input === 'string' ? input : input.toString()

      if (url.endsWith('/integration/status')) {
        return {
          ok: true,
          json: async () => ({
            triage: {
              provider: 'deepseek',
              label: 'DeepSeek deepseek-v4-pro',
              mode: 'live',
              compatibility: 'OpenAI-compatible chat completions / FastChat gateway',
              configured: true,
              docs_url: 'https://api-docs.deepseek.com/',
              details: '当前分诊已连接真实大模型，并启用 FastChat 作为第二路分诊复核。',
            },
            booking: {
              provider: 'mock',
              label: '本地演示号源',
              mode: 'demo',
              compatibility: 'Easy!Appointments adapter ready',
              configured: true,
              docs_url: 'https://easyappointments.org/documentation/rest-api/',
              details: '当前展示数据来自本地号源表，便于课堂演示完整挂号流程。',
              write_mode: 'local',
            },
            clinical: {
              provider: 'memory',
              label: '本地临床记录',
              mode: 'demo',
              compatibility: 'OpenMRS encounter mapping ready',
              configured: true,
              docs_url: 'https://rest.openmrs.org/',
              details: '当前诊后记录保存在本地内存，用于生成患者白话医嘱和提醒。',
            },
            reminder: {
              provider: 'medtimer',
              label: 'MedTimer 备份桥接',
              mode: 'export',
              compatibility: 'MedTimer JSON backup format',
              configured: true,
              docs_url: 'https://github.com/Futsch1/medTimer',
              details: '可将当前患者的药物提醒导出为 MedTimer 可识别的备份 JSON。',
            },
          }),
        }
      }

      if (url.endsWith('/triage/intake')) {
        return {
          ok: true,
          json: async () => ({
            triage_id: 'triage-001',
            question: '请补充是否有黄痰、胸痛或呼吸困难。',
            emergency: false,
            disclaimer: '仅供辅助参考，以医生判断为准。',
          }),
        }
      }

      if (url.endsWith('/triage/triage-001/result')) {
        return {
          ok: true,
          json: async () => ({
            recommended_department: '呼吸内科',
            urgency: '24小时内就诊',
            confidence: 0.86,
            explanation: '建议先到呼吸内科进一步评估。',
            emergency: false,
            risk_flags: [],
            suggested_hospital_type: '综合医院或社区专科门诊',
            disclaimer: '仅供辅助参考，以医生判断为准。',
            consensus_summary: 'DeepSeek 与 FastChat 都认为需要门诊就诊，综合建议优先呼吸内科。',
            disagreement_note: 'FastChat 更偏向全科接诊，但当前症状标签更贴近呼吸内科。',
            validation_results: [
              {
                source: 'deepseek',
                label: 'DeepSeek 分诊',
                status: 'available',
                note: '主分诊模型',
                result: {
                  recommended_department: '呼吸内科',
                  urgency: '24小时内就诊',
                  confidence: 0.86,
                  explanation: '建议先到呼吸内科进一步评估。',
                  emergency: false,
                  risk_flags: [],
                  suggested_hospital_type: '综合医院或社区专科门诊',
                  disclaimer: '仅供辅助参考，以医生判断为准。',
                },
              },
              {
                source: 'fastchat',
                label: 'FastChat 开源分诊',
                status: 'available',
                note: 'GitHub 开源项目复核',
                result: {
                  recommended_department: '全科医学科',
                  urgency: '建议近三天内就诊',
                  confidence: 0.74,
                  explanation: 'FastChat 建议先由全科接诊。',
                  emergency: false,
                  risk_flags: [],
                  suggested_hospital_type: '社区医疗中心',
                  disclaimer: '仅供辅助参考，以医生判断为准。',
                },
              },
            ],
          }),
        }
      }

      if (url.includes('/booking/recommendations')) {
        return {
          ok: true,
          json: async () => ({
            items: [
              {
                hospital_id: 'hosp-001',
                hospital_name: '滨海市第一人民医院',
                department: '呼吸内科',
                doctor_name: '王医生',
                slot: '2026-06-12 10:00',
                distance_km: 3.2,
                label: '三甲综合医院',
                score: 0.91,
                ai_reason: '综合两个分诊结果后，这个号源最适合尽快完成门诊初诊，且时段较早。',
              },
            ],
          }),
        }
      }

      if (url.endsWith('/booking/appointments')) {
        return {
          ok: true,
          json: async () => ({
            appointment_id: 'appt-001',
            triage_id: 'triage-001',
            hospital_id: 'hosp-001',
            hospital_name: '滨海市第一人民医院',
            department: '呼吸内科',
            doctor_name: '王医生',
            slot: '2026-06-12 10:00',
            status: 'confirmed',
            encounter_id: 'enc-001',
            notes: ['请携带身份证和既往检查结果。'],
          }),
        }
      }

      if (url.endsWith('/encounters/enc-001/doctor-note')) {
        return {
          ok: true,
          json: async () => ({
            encounter_id: 'enc-001',
            status: 'saved',
          }),
        }
      }

      if (url.endsWith('/encounters/enc-001/patient-advice')) {
        return {
          ok: true,
          json: async () => ({
            encounter_id: 'enc-001',
            original_summary: '上呼吸道感染',
            plain_language_advice: '右美沙芬片 15mg，每天 3 次，饭后服用，连续服用 5 天。',
            advice_generation_mode: 'ai',
            lifestyle_tips: ['按时监测症状变化'],
            reminders: [
              {
                id: 'rem-001',
                encounter_id: 'enc-001',
                title: '服用右美沙芬片',
                description: '右美沙芬片 15mg，每天 3 次，饭后服用，连续服用 5 天。',
                due_at: '2026-06-12 08:00',
                status: 'pending',
                kind: 'medication',
              },
            ],
          }),
        }
      }

      if (url.endsWith('/reminders')) {
        return {
          ok: true,
          json: async () => ({
            items: [
              {
                id: 'rem-001',
                encounter_id: 'enc-001',
                title: '服用右美沙芬片',
                description: '右美沙芬片 15mg，每天 3 次，饭后服用，连续服用 5 天。',
                due_at: '2026-06-12 08:00',
                status: 'pending',
                kind: 'medication',
              },
            ],
          }),
        }
      }

      if (url.endsWith('/reminders/rem-001/complete')) {
        return {
          ok: true,
          json: async () => ({
            id: 'rem-001',
            encounter_id: 'enc-001',
            title: '服用右美沙芬片',
            description: '右美沙芬片 15mg，每天 3 次，饭后服用，连续服用 5 天。',
            due_at: '2026-06-12 08:00',
            status: 'done',
            kind: 'medication',
          }),
        }
      }

      if (url.endsWith('/followup/feedback')) {
        expect(init?.method).toBe('POST')
        return {
          ok: true,
          json: async () => ({
            encounter_id: 'enc-001',
            reminder_id: 'rem-001',
            medication_status: 'done',
            symptom_status: 'same',
            note: '夜间咳嗽仍然偏重，希望提前复诊。',
            care_status: 'stable',
            ai_summary: '已按时服药，目前症状未明显恶化，可继续观察。',
            next_step: '继续按医嘱服药，若两天内无改善则提前复诊。',
          }),
        }
      }

      if (url.endsWith('/followup/enc-001/doctor-reply')) {
        expect(init?.method).toBe('POST')
        return {
          ok: true,
          json: async () => ({
            encounter_id: 'enc-001',
            reminder_id: 'rem-001',
            medication_status: 'done',
            symptom_status: 'same',
            note: '夜间咳嗽仍然偏重，希望提前复诊。',
            care_status: 'stable',
            ai_summary: '已按时服药，目前症状未明显恶化，可继续观察。',
            next_step: '继续按医嘱服药，若两天内无改善则提前复诊。',
            doctor_reply: {
              message: '今晚继续按原方案服药，若明晚仍影响睡眠，请提前复诊。',
              replied_at: '2026-06-12 18:30',
            },
          }),
        }
      }

      throw new Error(`Unhandled request: ${url}`)
    })

    renderApp('/')

    await userEvent.click(screen.getByRole('link', { name: '进入患者端' }))
    expect(screen.queryByText('医生端')).not.toBeInTheDocument()

    await userEvent.type(screen.getByLabelText('患者姓名'), '李同学')
    await userEvent.type(screen.getByLabelText('主诉'), '发热咳嗽两天')
    await userEvent.click(screen.getByRole('button', { name: '进入 AI 分诊页' }))

    expect(await screen.findByRole('heading', { name: 'AI 分诊结果' })).toBeInTheDocument()
    expect(screen.getAllByText('呼吸内科').length).toBeGreaterThan(0)
    expect(screen.getByText('DeepSeek 分诊')).toBeInTheDocument()
    expect(screen.getByText('FastChat 开源分诊')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: '刷新分诊结果' })).toBeDisabled()

    await userEvent.click(screen.getByRole('button', { name: '进入挂号推荐页' }))
    expect(await screen.findByRole('heading', { name: '智能挂号推荐' })).toBeInTheDocument()
    expect(screen.getByText('综合两个分诊结果后，这个号源最适合尽快完成门诊初诊，且时段较早。')).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: '预约该号源' }))

    expect(await screen.findByRole('heading', { name: '预约确认' })).toBeInTheDocument()
    expect(screen.queryByText('医生端')).not.toBeInTheDocument()
    await userEvent.click(screen.getAllByRole('link', { name: '返回入口切换角色' })[0])

    expect(await screen.findByRole('heading', { name: '全科智能就医闭环工作台' })).toBeInTheDocument()
    await userEvent.click(screen.getByRole('link', { name: '进入医生端' }))

    expect(await screen.findByRole('heading', { name: '诊后录入与医嘱生成' })).toBeInTheDocument()
    expect(screen.queryByText('患者录入')).not.toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: '生成患者版医嘱' }))

    expect(await screen.findByRole('heading', { name: '医生端 AI 预览' })).toBeInTheDocument()
    expect(screen.getAllByText('右美沙芬片 15mg，每天 3 次，饭后服用，连续服用 5 天。').length).toBeGreaterThan(0)
    await userEvent.click(screen.getAllByRole('link', { name: '返回入口切换角色' })[0])

    expect(await screen.findByRole('heading', { name: '全科智能就医闭环工作台' })).toBeInTheDocument()
    await userEvent.click(screen.getByRole('link', { name: '查看患者提醒页' }))

    expect(await screen.findByRole('heading', { name: '白话医嘱与提醒中心' })).toBeInTheDocument()
    expect(screen.getByText('服用右美沙芬片')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: '导出 MedTimer 备份' })).toBeInTheDocument()

    await userEvent.click(screen.getByRole('button', { name: '已服药' }))
    await userEvent.click(screen.getByRole('button', { name: '提交随访反馈' }))

    expect(await screen.findByText('当前照护状态：stable')).toBeInTheDocument()
    expect(screen.getByText('已按时服药，目前症状未明显恶化，可继续观察。')).toBeInTheDocument()

    await userEvent.click(screen.getAllByRole('link', { name: '返回入口切换角色' })[0])
    await userEvent.click(await screen.findByRole('link', { name: '进入医生端' }))
    await userEvent.click(await screen.findByRole('link', { name: 'AI 预览' }))
    expect(await screen.findByRole('heading', { name: '患者随访待回复' })).toBeInTheDocument()
    await userEvent.type(
      screen.getByLabelText('医生回复'),
      '今晚继续按原方案服药，若明晚仍影响睡眠，请提前复诊。',
    )
    await userEvent.click(screen.getByRole('button', { name: '发送医生回复' }))

    expect((await screen.findAllByText('医生已回复患者随访。')).length).toBeGreaterThan(0)
    await userEvent.click(screen.getAllByRole('link', { name: '返回入口切换角色' })[0])
    await userEvent.click(await screen.findByRole('link', { name: '查看患者提醒页' }))
    expect(await screen.findByText('医生回复')).toBeInTheDocument()
    expect(screen.getByText('今晚继续按原方案服药，若明晚仍影响睡眠，请提前复诊。')).toBeInTheDocument()
  })

  test('redirects direct doctor access back to role selection when no role is chosen', async () => {
    fetchMock.mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        triage: {
          provider: 'deepseek',
          label: 'DeepSeek deepseek-v4-pro',
          mode: 'live',
          compatibility: 'OpenAI-compatible chat completions / FastChat gateway',
          configured: true,
          docs_url: 'https://api-docs.deepseek.com/',
          details: '当前分诊已连接真实大模型。',
        },
        booking: {
          provider: 'mock',
          label: '本地演示号源',
          mode: 'demo',
          compatibility: 'Easy!Appointments adapter ready',
          configured: true,
          docs_url: 'https://easyappointments.org/documentation/rest-api/',
          details: '当前展示数据来自本地号源表，便于课堂演示完整挂号流程。',
          write_mode: 'local',
        },
        clinical: {
          provider: 'memory',
          label: '本地临床记录',
          mode: 'demo',
          compatibility: 'OpenMRS encounter mapping ready',
          configured: true,
          docs_url: 'https://rest.openmrs.org/',
          details: '当前诊后记录保存在本地内存，用于生成患者白话医嘱和提醒。',
        },
        reminder: {
          provider: 'medtimer',
          label: 'MedTimer 备份桥接',
          mode: 'export',
          compatibility: 'MedTimer JSON backup format',
          configured: true,
          docs_url: 'https://github.com/Futsch1/medTimer',
          details: '可将当前患者的药物提醒导出为 MedTimer 可识别的备份 JSON。',
        },
      }),
    })

    renderApp('/doctor/encounter')

    expect(await screen.findByText('请先从欢迎页选择患者端或医生端入口。')).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: '全科智能就医闭环工作台' })).toBeInTheDocument()
  })

  test('shows emergency booking recommendations and fallback triage messaging', async () => {
    fetchMock
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          triage: {
            provider: 'deepseek',
            label: 'DeepSeek deepseek-v4-pro',
            mode: 'live',
            compatibility: 'OpenAI-compatible chat completions / FastChat gateway',
            configured: true,
            docs_url: 'https://api-docs.deepseek.com/',
            details: '当前分诊已连接真实大模型。',
          },
          booking: {
            provider: 'mock',
            label: '本地演示号源',
            mode: 'demo',
            compatibility: 'Easy!Appointments adapter ready',
            configured: true,
            docs_url: 'https://easyappointments.org/documentation/rest-api/',
            details: '当前展示数据来自本地号源表，便于课堂演示完整挂号流程。',
            write_mode: 'local',
          },
          clinical: {
            provider: 'memory',
            label: '本地临床记录',
            mode: 'demo',
            compatibility: 'OpenMRS encounter mapping ready',
            configured: true,
            docs_url: 'https://rest.openmrs.org/',
            details: '当前诊后记录保存在本地内存，用于生成患者白话医嘱和提醒。',
          },
          reminder: {
            provider: 'medtimer',
            label: 'MedTimer 备份桥接',
            mode: 'export',
            compatibility: 'MedTimer JSON backup format',
            configured: true,
            docs_url: 'https://github.com/Futsch1/medTimer',
            details: '可将当前患者的药物提醒导出为 MedTimer 可识别的备份 JSON。',
          },
        }),
      })
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          triage_id: 'triage-urgent-001',
          question: null,
          emergency: true,
          disclaimer: '仅供辅助参考，以医生判断为准。',
        }),
      })
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          recommended_department: '急诊医学科',
          urgency: '立即急诊',
          confidence: 0.99,
          explanation: '检测到红旗症状，建议立即前往急诊进一步排查。',
          emergency: true,
          risk_flags: ['胸痛'],
          suggested_hospital_type: '具备急诊能力的综合医院',
          disclaimer: '仅供辅助参考，以医生判断为准。',
          consensus_summary: 'FastChat 开源分诊当前不可用，系统已自动切换为 DeepSeek 分诊输出建议，以保证分诊流程不中断。',
          disagreement_note: null,
          validation_results: [
            {
              source: 'fastchat',
              label: 'FastChat 开源分诊',
              status: 'unavailable',
              note: '主分诊当前不可用：HTTPStatusError',
              result: null,
            },
            {
              source: 'deepseek',
              label: 'DeepSeek 分诊',
              status: 'available',
              note: 'GitHub 开源项目复核',
              result: {
                recommended_department: '急诊医学科',
                urgency: '立即急诊',
                confidence: 0.99,
                explanation: '检测到红旗症状，建议立即前往急诊进一步排查。',
                emergency: true,
                risk_flags: ['胸痛'],
                suggested_hospital_type: '具备急诊能力的综合医院',
                disclaimer: '仅供辅助参考，以医生判断为准。',
              },
            },
          ],
        }),
      })
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          items: [
            {
              hospital_id: 'hosp-001',
              hospital_name: '滨海市第一人民医院',
              department: '急诊医学科',
              doctor_name: '急诊分诊台',
              slot: '2026-06-12 08:10',
              distance_km: 3.2,
              label: '三甲综合医院 · 24 小时急诊绿色通道',
              score: 0.97,
              ai_reason: '当前存在红旗症状，建议直接前往具备急诊能力的综合医院优先分诊。',
            },
          ],
        }),
      })

    renderApp('/')
    await userEvent.click(screen.getByRole('link', { name: '进入患者端' }))

    await userEvent.type(screen.getByLabelText('患者姓名'), '张阿姨')
    await userEvent.type(screen.getByLabelText('主诉'), '胸痛并伴有呼吸困难')
    await userEvent.click(screen.getByRole('button', { name: '进入 AI 分诊页' }))

    expect(await screen.findByRole('heading', { name: 'AI 分诊结果' })).toBeInTheDocument()
    expect(screen.getByText('FastChat 开源分诊')).toBeInTheDocument()
    expect(
      screen.getAllByText('FastChat 主分诊不可用，已切换到 DeepSeek 分诊继续流程。').length,
    ).toBeGreaterThan(0)
    expect(screen.getByText('主分诊当前不可用：HTTPStatusError')).toBeInTheDocument()
    expect(screen.getByText(/自动切换为 DeepSeek 分诊输出建议/)).toBeInTheDocument()

    await userEvent.click(screen.getByRole('button', { name: '查看急诊推荐页' }))
    expect(await screen.findByRole('heading', { name: '智能挂号推荐' })).toBeInTheDocument()
    expect(screen.getByText(/当前推荐科室：/)).toBeInTheDocument()
    expect(screen.getByText('滨海市第一人民医院')).toBeInTheDocument()
    expect(screen.getByText('当前存在红旗症状，建议直接前往具备急诊能力的综合医院优先分诊。')).toBeInTheDocument()
  })
})
