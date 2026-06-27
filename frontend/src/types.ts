export type Perspective = 'patient' | 'doctor'

export type TriageIntakePayload = {
  name: string
  age: number
  gender: 'male' | 'female' | 'other'
  chronic_conditions: string[]
  allergies: string[]
  medications: string[]
  chief_complaint: string
  symptoms: string[]
  duration: string
  severity: '轻' | '中等' | '严重'
  companions: string[]
}

export type TriageSession = {
  triage_id: string
  question: string | null
  emergency: boolean
  disclaimer: string
}

export type TriageResult = {
  recommended_department: string
  urgency: string
  confidence: number
  explanation: string
  emergency: boolean
  risk_flags: string[]
  suggested_hospital_type: string
  disclaimer: string
  validation_results?: Array<{
    source: string
    label: string
    status: 'available' | 'unavailable'
    note?: string | null
    result?: {
      recommended_department: string
      urgency: string
      confidence: number
      explanation: string
      emergency: boolean
      risk_flags: string[]
      suggested_hospital_type: string
      disclaimer: string
    } | null
  }>
  consensus_summary?: string | null
  disagreement_note?: string | null
}

export type BookingRecommendation = {
  hospital_id: string
  hospital_name: string
  department: string
  doctor_name: string
  slot: string
  distance_km: number
  label: string
  score: number
  ai_reason?: string | null
}

export type BookingRecord = {
  appointment_id: string
  triage_id: string
  hospital_id: string
  hospital_name: string
  department: string
  doctor_name: string
  slot: string
  status: 'confirmed' | 'pending'
  encounter_id: string
  notes: string[]
}

export type MedicationInput = {
  name: string
  dose: string
  frequency: string
  duration_days: number
  instruction: string
}

export type DoctorNotePayload = {
  diagnosis_summary: string
  medications: MedicationInput[]
  doctor_advice: string
  follow_up_date: string
}

export type ReminderTask = {
  id: string
  encounter_id: string
  title: string
  description: string
  due_at: string
  status: 'pending' | 'done' | 'missed' | 'snoozed'
  kind: 'medication' | 'follow_up'
}

export type PatientAdvice = {
  encounter_id: string
  original_summary: string
  plain_language_advice: string
  lifestyle_tips: string[]
  reminders: ReminderTask[]
  caution?: string | null
  advice_generation_mode?: 'ai' | 'fallback'
}

export type FollowupFeedbackResponse = {
  encounter_id: string
  reminder_id: string
  medication_status: 'done' | 'missed' | 'snoozed'
  symptom_status: 'better' | 'same' | 'worse'
  note: string
  care_status: string
  ai_summary?: string
  next_step?: string
  doctor_reply?: {
    message: string
    replied_at: string
  } | null
}

export type IntegrationNode = {
  provider: string
  label: string
  mode: string
  compatibility: string
  configured: boolean
  docs_url: string
  details: string
  write_mode?: string
}

export type IntegrationStatus = {
  triage: IntegrationNode
  booking: IntegrationNode
  clinical: IntegrationNode
  reminder: IntegrationNode
}
