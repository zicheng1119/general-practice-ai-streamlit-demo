from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class TriageIntakeRequest(BaseModel):
    name: str
    age: int = Field(ge=0)
    gender: Literal["male", "female", "other"]
    chronic_conditions: list[str]
    allergies: list[str]
    medications: list[str]
    chief_complaint: str
    symptoms: list[str]
    duration: str
    severity: Literal["轻", "中等", "严重"]
    companions: list[str]


class TriageAnswerRequest(BaseModel):
    answer: str


class TriageAssessment(BaseModel):
    recommended_department: str
    urgency: str
    confidence: float
    explanation: str
    emergency: bool
    risk_flags: list[str]
    suggested_hospital_type: str
    disclaimer: str


class TriageValidationResult(BaseModel):
    source: str
    label: str
    status: Literal["available", "unavailable"]
    note: str | None = None
    result: TriageAssessment | None = None


class TriageResult(TriageAssessment):
    validation_results: list[TriageValidationResult] = Field(default_factory=list)
    consensus_summary: str | None = None
    disagreement_note: str | None = None


class BookingRecommendation(BaseModel):
    hospital_id: str
    hospital_name: str
    department: str
    doctor_name: str
    slot: str
    distance_km: float
    label: str
    score: float
    ai_reason: str | None = None


class BookingCreateRequest(BaseModel):
    triage_id: str
    hospital_id: str
    department: str
    doctor_name: str
    slot: str


class BookingRecord(BaseModel):
    appointment_id: str
    triage_id: str
    hospital_id: str
    hospital_name: str
    department: str
    doctor_name: str
    slot: str
    status: Literal["confirmed", "pending"]
    encounter_id: str
    notes: list[str]


class MedicationInput(BaseModel):
    name: str
    dose: str
    frequency: str
    duration_days: int = Field(ge=1)
    instruction: str


class DoctorNoteRequest(BaseModel):
    diagnosis_summary: str
    medications: list[MedicationInput]
    doctor_advice: str
    follow_up_date: str


class ReminderTask(BaseModel):
    id: str
    encounter_id: str
    title: str
    description: str
    due_at: str
    status: Literal["pending", "done", "missed", "snoozed"]
    kind: Literal["medication", "follow_up"]


class EncounterRecord(BaseModel):
    encounter_id: str
    diagnosis_summary: str
    medications: list[MedicationInput]
    doctor_advice: str
    follow_up_date: str


class PatientAdvice(BaseModel):
    encounter_id: str
    original_summary: str
    plain_language_advice: str
    lifestyle_tips: list[str]
    reminders: list[ReminderTask]
    caution: str | None = None
    advice_generation_mode: Literal["ai", "fallback"] = "fallback"


class ReminderCompletionRequest(BaseModel):
    status: Literal["done", "missed", "snoozed"]


class FollowupFeedbackRequest(BaseModel):
    encounter_id: str
    reminder_id: str
    medication_status: Literal["done", "missed", "snoozed"]
    symptom_status: Literal["better", "same", "worse"]
    note: str


class DoctorFollowupReplyRequest(BaseModel):
    message: str
