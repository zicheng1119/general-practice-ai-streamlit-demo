import type {
  BookingRecord,
  BookingRecommendation,
  DoctorNotePayload,
  FollowupFeedbackResponse,
  IntegrationStatus,
  PatientAdvice,
  ReminderTask,
  TriageIntakePayload,
  TriageResult,
  TriageSession,
} from './types'


const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://127.0.0.1:8000'


async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    headers: {
      'Content-Type': 'application/json',
      ...(init?.headers ?? {}),
    },
    ...init,
  })

  if (!response.ok) {
    const message = await response.text()
    throw new Error(message || `Request failed: ${response.status}`)
  }

  return response.json() as Promise<T>
}


export function createTriage(payload: TriageIntakePayload) {
  return request<TriageSession>('/triage/intake', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export function answerTriage(triageId: string, answer: string) {
  return request<{ status: string; triage_id: string }>(`/triage/${triageId}/next`, {
    method: 'POST',
    body: JSON.stringify({ answer }),
  })
}

export function fetchTriageResult(triageId: string) {
  return request<TriageResult>(`/triage/${triageId}/result`)
}

export function fetchRecommendations(triageId: string, department: string) {
  return request<{ items: BookingRecommendation[] }>(
    `/booking/recommendations?triage_id=${triageId}&department=${encodeURIComponent(department)}`,
  )
}

export function createBooking(payload: {
  triage_id: string
  hospital_id: string
  department: string
  doctor_name: string
  slot: string
}) {
  return request<BookingRecord>('/booking/appointments', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export function saveDoctorNote(encounterId: string, payload: DoctorNotePayload) {
  return request<{ encounter_id: string; status: string }>(`/encounters/${encounterId}/doctor-note`, {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export function generatePatientAdvice(encounterId: string) {
  return request<PatientAdvice>(`/encounters/${encounterId}/patient-advice`, {
    method: 'POST',
  })
}

export function fetchReminders() {
  return request<{ items: ReminderTask[] }>('/reminders')
}

export function fetchIntegrationStatus() {
  return request<IntegrationStatus>('/integration/status')
}

export function getMedTimerExportUrl(encounterId: string) {
  return `${API_BASE_URL}/reminders/export/medtimer/${encounterId}`
}

export function updateReminder(reminderId: string, status: 'done' | 'missed' | 'snoozed') {
  return request<ReminderTask>(`/reminders/${reminderId}/complete`, {
    method: 'POST',
    body: JSON.stringify({ status }),
  })
}

export function submitFollowupFeedback(payload: {
  encounter_id: string
  reminder_id: string
  medication_status: 'done' | 'missed' | 'snoozed'
  symptom_status: 'better' | 'same' | 'worse'
  note: string
}) {
  return request<FollowupFeedbackResponse>('/followup/feedback', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export function submitDoctorFollowupReply(encounterId: string, message: string) {
  return request<FollowupFeedbackResponse>(`/followup/${encounterId}/doctor-reply`, {
    method: 'POST',
    body: JSON.stringify({ message }),
  })
}
