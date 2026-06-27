/* eslint-disable react-refresh/only-export-components */
import {
  createContext,
  useContext,
  useEffect,
  useState,
  type ReactNode,
} from 'react'

import {
  answerTriage,
  createBooking,
  createTriage,
  fetchRecommendations,
  fetchReminders,
  fetchTriageResult,
  generatePatientAdvice,
  saveDoctorNote,
  submitDoctorFollowupReply,
  submitFollowupFeedback,
  updateReminder,
} from '../api'
import type {
  BookingRecord,
  BookingRecommendation,
  DoctorNotePayload,
  FollowupFeedbackResponse,
  PatientAdvice,
  Perspective,
  ReminderTask,
  TriageIntakePayload,
  TriageResult,
  TriageSession,
} from '../types'


const STORAGE_KEY = 'general-medicine-demo-flow'

const intakeSeed: TriageIntakePayload = {
  name: '',
  age: 32,
  gender: 'female',
  chronic_conditions: ['高血压'],
  allergies: ['青霉素'],
  medications: ['缬沙坦'],
  chief_complaint: '',
  symptoms: ['发热', '咳嗽'],
  duration: '2天',
  severity: '中等',
  companions: ['乏力'],
}

const doctorSeed: DoctorNotePayload = {
  diagnosis_summary: '上呼吸道感染，建议短期对症治疗并持续观察症状变化。',
  medications: [
    {
      name: '右美沙芬片',
      dose: '15mg',
      frequency: '每日3次',
      duration_days: 5,
      instruction: '饭后服用',
    },
  ],
  doctor_advice: '多饮温水，规律休息，如出现胸闷或高热不退，请及时复诊。',
  follow_up_date: '2026-06-19',
}

type FlowState = {
  perspective: Perspective | null
  intake: TriageIntakePayload
  triageSession: TriageSession | null
  triageResult: TriageResult | null
  recommendations: BookingRecommendation[]
  selectedBooking: BookingRecord | null
  doctorNote: DoctorNotePayload
  advice: PatientAdvice | null
  reminders: ReminderTask[]
  followupAnswer: string
  feedbackNote: string
  feedbackState: 'better' | 'same' | 'worse'
  doctorReplyDraft: string
  followupResult: FollowupFeedbackResponse | null
  statusMessage: string
  submitting: boolean
}

type DemoFlowContextValue = FlowState & {
  canSubmitIntake: boolean
  enterPerspective: (value: Perspective) => void
  clearPerspective: () => void
  updateIntake: (patch: Partial<TriageIntakePayload>) => void
  updateDoctorNote: (note: DoctorNotePayload) => void
  setFollowupAnswer: (value: string) => void
  setFeedbackNote: (value: string) => void
  setFeedbackState: (value: 'better' | 'same' | 'worse') => void
  setDoctorReplyDraft: (value: string) => void
  restoreDemoCase: () => void
  submitIntake: () => Promise<boolean>
  submitFollowupAnswer: () => Promise<boolean>
  confirmBooking: (item: BookingRecommendation) => Promise<boolean>
  submitDoctorEntry: () => Promise<boolean>
  completeReminder: (reminderId: string, status: 'done' | 'missed' | 'snoozed') => Promise<void>
  submitFollowup: () => Promise<boolean>
  submitDoctorReply: () => Promise<boolean>
}

const initialState: FlowState = {
  perspective: null,
  intake: intakeSeed,
  triageSession: null,
  triageResult: null,
  recommendations: [],
  selectedBooking: null,
  doctorNote: doctorSeed,
  advice: null,
  reminders: [],
  followupAnswer: '',
  feedbackNote: '夜间咳嗽仍然偏重，希望提前复诊。',
  feedbackState: 'same',
  doctorReplyDraft: '',
  followupResult: null,
  statusMessage: '欢迎进入演示站点，请先选择患者端或医生端入口。',
  submitting: false,
}

const DemoFlowContext = createContext<DemoFlowContextValue | null>(null)

function buildTriageStatusMessage(result: TriageResult) {
  const primary = result.validation_results?.[0]
  const secondary = result.validation_results?.[1]
  const sourceName = (source?: string) => {
    if (source === 'deepseek') {
      return 'DeepSeek 分诊'
    }
    if (source === 'fastchat') {
      return 'FastChat 主分诊'
    }
    if (source === 'kimi') {
      return 'Kimi 分诊'
    }
    if (source === 'rules') {
      return '本地规则引擎'
    }
    return '主分诊'
  }

  if (primary?.source === 'deepseek' && primary.status === 'available' && secondary?.source === 'fastchat') {
    if (secondary.status === 'available') {
      return 'DeepSeek 主分诊已完成，FastChat 开源复核结果已同步展示。'
    }

    return 'DeepSeek 主分诊已完成，FastChat 开源复核暂时不可用。'
  }

  if (primary?.source === 'deepseek' && primary.status === 'available' && secondary?.source === 'kimi') {
    if (secondary.status === 'available') {
      return 'DeepSeek 主分诊已完成，Kimi 云端复核结果已同步展示。'
    }

    return 'DeepSeek 主分诊已完成，Kimi 云端复核暂时不可用。'
  }

  if (primary?.source === 'fastchat' && primary.status === 'available' && secondary?.source === 'deepseek') {
    return 'FastChat 主分诊已完成，DeepSeek 复核结果已同步展示。'
  }

  if (primary && primary.status === 'unavailable' && secondary?.status === 'available') {
    return `${sourceName(primary.source)}不可用，已切换到 ${sourceName(secondary.source)}继续流程。`
  }

  if (primary && primary.status === 'unavailable') {
    const fallback = result.validation_results?.find((item) => item.source === 'rules' && item.status === 'available')
    if (fallback) {
      return '外部分诊暂不可用，已使用本地规则引擎继续流程。'
    }
  }

  return '分诊已完成，请继续查看推荐和后续流程。'
}

function loadState(): FlowState {
  if (typeof window === 'undefined') {
    return initialState
  }

  const raw = window.sessionStorage.getItem(STORAGE_KEY)
  if (!raw) {
    return initialState
  }

  try {
    return { ...initialState, ...JSON.parse(raw) }
  } catch {
    return initialState
  }
}

export function DemoFlowProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<FlowState>(loadState)

  useEffect(() => {
    if (typeof window === 'undefined') {
      return
    }

    window.sessionStorage.setItem(STORAGE_KEY, JSON.stringify(state))
  }, [state])

  const canSubmitIntake = Boolean(state.intake.name.trim() && state.intake.chief_complaint.trim())

  function patchState(patch: Partial<FlowState>) {
    setState((current) => ({ ...current, ...patch }))
  }

  function updateIntake(patch: Partial<TriageIntakePayload>) {
    setState((current) => ({ ...current, intake: { ...current.intake, ...patch } }))
  }

  function enterPerspective(value: Perspective) {
    patchState({ perspective: value })
  }

  function clearPerspective() {
    patchState({ perspective: null })
  }

  function updateDoctorNote(note: DoctorNotePayload) {
    patchState({ doctorNote: note })
  }

  function restoreDemoCase() {
    patchState({
      intake: intakeSeed,
      triageSession: null,
      triageResult: null,
      recommendations: [],
      selectedBooking: null,
      advice: null,
      reminders: [],
      followupAnswer: '',
      followupResult: null,
      doctorReplyDraft: '',
      statusMessage: '演示病例已恢复，请从患者端重新开始。',
      doctorNote: doctorSeed,
    })
  }

  async function submitIntake() {
    if (!canSubmitIntake) {
      patchState({ statusMessage: '请先填写患者姓名和主诉。' })
      return false
    }

    patchState({ submitting: true, statusMessage: '正在生成分诊建议...' })
    try {
      const session = await createTriage(state.intake)
      const result = await fetchTriageResult(session.triage_id)
      const recommendationResponse = await fetchRecommendations(session.triage_id, result.recommended_department)

      patchState({
        triageSession: session,
        triageResult: result,
        recommendations: recommendationResponse.items,
        submitting: false,
        statusMessage: buildTriageStatusMessage(result),
      })
      return true
    } catch (error) {
      patchState({
        submitting: false,
        statusMessage: `生成分诊建议失败：${String(error)}`,
      })
      return false
    }
  }

  async function submitFollowupAnswer() {
    if (!state.triageSession || !state.followupAnswer.trim()) {
      return false
    }

    patchState({ submitting: true, statusMessage: '正在根据补充回答刷新分诊结果...' })

    try {
      await answerTriage(state.triageSession.triage_id, state.followupAnswer)
      const result = await fetchTriageResult(state.triageSession.triage_id)
      const recommendationResponse = await fetchRecommendations(
        state.triageSession.triage_id,
        result.recommended_department,
      )

      patchState({
        triageResult: result,
        recommendations: recommendationResponse.items,
        submitting: false,
        statusMessage: result.emergency
          ? `${buildTriageStatusMessage(result)} 已同步刷新急诊推荐号源。`
          : '补充回答已纳入分诊结果。',
      })
      return true
    } catch (error) {
      patchState({
        submitting: false,
        statusMessage: `补充分诊失败：${String(error)}`,
      })
      return false
    }
  }

  async function confirmBooking(item: BookingRecommendation) {
    if (!state.triageSession) {
      patchState({ statusMessage: '请先完成分诊。' })
      return false
    }

    patchState({ submitting: true, statusMessage: '正在锁定号源并生成就诊记录...' })

    try {
      const booking = await createBooking({
        triage_id: state.triageSession.triage_id,
        hospital_id: item.hospital_id,
        department: item.department,
        doctor_name: item.doctor_name,
        slot: item.slot,
      })
      patchState({
        selectedBooking: booking,
        submitting: false,
        statusMessage: '预约成功，诊疗工作台已可录入，请返回入口切换角色继续演示。',
      })
      return true
    } catch (error) {
      patchState({
        submitting: false,
        statusMessage: `预约失败：${String(error)}`,
      })
      return false
    }
  }

  async function submitDoctorEntry() {
    if (!state.selectedBooking) {
      patchState({ statusMessage: '请先完成预约，再进入医生端。' })
      return false
    }

    patchState({ submitting: true, statusMessage: '正在生成患者版医嘱与提醒...' })

    try {
      await saveDoctorNote(state.selectedBooking.encounter_id, state.doctorNote)
      const advice = await generatePatientAdvice(state.selectedBooking.encounter_id)
      const reminderResponse = await fetchReminders()

      patchState({
        advice,
        reminders: reminderResponse.items.filter(
          (item) => item.encounter_id === state.selectedBooking?.encounter_id,
        ),
        submitting: false,
        statusMessage: '患者提醒已生成，请返回入口切换患者视角查看。',
      })
      return true
    } catch (error) {
      patchState({
        submitting: false,
        statusMessage: `医嘱生成失败：${String(error)}`,
      })
      return false
    }
  }

  async function completeReminder(reminderId: string, status: 'done' | 'missed' | 'snoozed') {
    patchState({ submitting: true })

    try {
      const updated = await updateReminder(reminderId, status)
      setState((current) => ({
        ...current,
        reminders: current.reminders.map((item) => (item.id === reminderId ? updated : item)),
        submitting: false,
        statusMessage: '提醒状态已更新。',
      }))
    } catch (error) {
      patchState({
        submitting: false,
        statusMessage: `提醒更新失败：${String(error)}`,
      })
    }
  }

  async function submitFollowup() {
    if (!state.selectedBooking || !state.reminders[0]) {
      patchState({ statusMessage: '请先生成患者提醒后再提交反馈。' })
      return false
    }

    patchState({ submitting: true })

    try {
      const response = await submitFollowupFeedback({
        encounter_id: state.selectedBooking.encounter_id,
        reminder_id: state.reminders[0].id,
        medication_status:
          state.reminders[0].status === 'pending' ? 'snoozed' : state.reminders[0].status,
        symptom_status: state.feedbackState,
        note: state.feedbackNote,
      })
      patchState({
        followupResult: response,
        submitting: false,
        statusMessage: '随访反馈已提交，闭环状态已更新。',
      })
      return true
    } catch (error) {
      patchState({
        submitting: false,
        statusMessage: `随访反馈失败：${String(error)}`,
      })
      return false
    }
  }

  async function submitDoctorReply() {
    if (!state.selectedBooking || !state.followupResult || !state.doctorReplyDraft.trim()) {
      patchState({ statusMessage: '请先等待患者提交随访，并填写医生回复。' })
      return false
    }

    patchState({ submitting: true, statusMessage: '正在发送医生回复...' })

    try {
      const response = await submitDoctorFollowupReply(
        state.selectedBooking.encounter_id,
        state.doctorReplyDraft.trim(),
      )
      patchState({
        followupResult: response,
        doctorReplyDraft: '',
        submitting: false,
        statusMessage: '医生已回复患者随访。',
      })
      return true
    } catch (error) {
      patchState({
        submitting: false,
        statusMessage: `医生回复失败：${String(error)}`,
      })
      return false
    }
  }

  const value: DemoFlowContextValue = {
    ...state,
    canSubmitIntake,
    enterPerspective,
    clearPerspective,
    updateIntake,
    updateDoctorNote,
    setFollowupAnswer: (value) => patchState({ followupAnswer: value }),
    setFeedbackNote: (value) => patchState({ feedbackNote: value }),
    setFeedbackState: (value) => patchState({ feedbackState: value }),
    setDoctorReplyDraft: (value) => patchState({ doctorReplyDraft: value }),
    restoreDemoCase,
    submitIntake,
    submitFollowupAnswer,
    confirmBooking,
    submitDoctorEntry,
    completeReminder,
    submitFollowup,
    submitDoctorReply,
  }

  return <DemoFlowContext.Provider value={value}>{children}</DemoFlowContext.Provider>
}

export function useDemoFlow() {
  const context = useContext(DemoFlowContext)
  if (!context) {
    throw new Error('useDemoFlow must be used within DemoFlowProvider')
  }
  return context
}
