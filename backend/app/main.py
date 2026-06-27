from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app.adapters import (
    get_booking_provider,
    get_clinical_provider,
    get_integration_status,
    get_reminder_provider,
)
from app.models import (
    BookingCreateRequest,
    DoctorFollowupReplyRequest,
    DoctorNoteRequest,
    FollowupFeedbackRequest,
    ReminderCompletionRequest,
    TriageAnswerRequest,
    TriageIntakeRequest,
)
from app.services import (
    DISCLAIMER,
    create_patient_advice,
    enrich_booking_recommendations,
    generate_follow_up_question,
    generate_triage_result,
    serialize_doctor_note,
    summarize_followup_feedback,
)
from app.store import store


FRONTEND_DIST = Path(__file__).resolve().parents[2] / "frontend" / "dist"
FRONTEND_INDEX = FRONTEND_DIST / "index.html"

app = FastAPI(title="全科智能就医闭环 Demo API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

if (FRONTEND_DIST / "assets").exists():
    app.mount("/assets", StaticFiles(directory=FRONTEND_DIST / "assets"), name="frontend-assets")


def _frontend_file_response(path: str) -> FileResponse:
    if not FRONTEND_INDEX.exists():
        raise HTTPException(status_code=404, detail="frontend build not found")

    dist_root = FRONTEND_DIST.resolve()
    candidate = (FRONTEND_DIST / path).resolve()
    if candidate.is_file() and candidate.is_relative_to(dist_root):
        return FileResponse(candidate)
    return FileResponse(FRONTEND_INDEX)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/integration/status")
def integration_status() -> dict[str, object]:
    return get_integration_status()


@app.post("/triage/intake")
def triage_intake(payload: TriageIntakeRequest) -> dict:
    triage_id = store.next_id("triage")
    session = payload.model_dump()
    session["triage_id"] = triage_id
    session["answers"] = []
    store.triage_sessions[triage_id] = session
    result = generate_triage_result(session)
    question = None if result.emergency else generate_follow_up_question(session)
    return {
        "triage_id": triage_id,
        "question": question,
        "emergency": result.emergency,
        "disclaimer": DISCLAIMER,
    }


@app.post("/triage/{triage_id}/next")
def triage_next(triage_id: str, payload: TriageAnswerRequest) -> dict:
    session = store.triage_sessions.get(triage_id)
    if not session:
        raise HTTPException(status_code=404, detail="triage session not found")
    session["answers"].append(payload.answer)
    return {"status": "answered", "triage_id": triage_id}


@app.get("/triage/{triage_id}/result")
def triage_result(triage_id: str) -> dict:
    session = store.triage_sessions.get(triage_id)
    if not session:
        raise HTTPException(status_code=404, detail="triage session not found")
    result = generate_triage_result(session)
    return result.model_dump()


@app.get("/booking/recommendations")
def booking_list(triage_id: str, department: str) -> dict:
    session = store.triage_sessions.get(triage_id)
    if not session:
        raise HTTPException(status_code=404, detail="triage session not found")
    items = enrich_booking_recommendations(session, get_booking_provider().list_recommendations(department))
    items = [item.model_dump() for item in items]
    return {"items": items}


@app.post("/booking/appointments")
def booking_create(payload: BookingCreateRequest) -> dict:
    triage = store.triage_sessions.get(payload.triage_id)
    if not triage:
        raise HTTPException(status_code=404, detail="triage session not found")

    appointment_id = store.next_id("appt")
    encounter_id = store.next_id("enc")
    record = get_booking_provider().create_booking(
        payload,
        triage_id=payload.triage_id,
        appointment_id=appointment_id,
        encounter_id=encounter_id,
        triage_session=triage,
    )
    store.appointments[appointment_id] = record
    store.encounters[encounter_id] = {
        "encounter_id": encounter_id,
        "triage_id": payload.triage_id,
        "patient_name": triage["name"],
    }
    return record


@app.post("/encounters/{encounter_id}/doctor-note")
def doctor_note(encounter_id: str, payload: DoctorNoteRequest) -> dict:
    if encounter_id not in store.encounters:
        raise HTTPException(status_code=404, detail="encounter not found")
    encounter = store.encounters[encounter_id] | serialize_doctor_note(payload)
    encounter["integration"] = get_clinical_provider().sync_doctor_note(encounter_id, encounter)
    store.encounters[encounter_id] = encounter
    return {"encounter_id": encounter_id, "status": "saved"}


@app.post("/encounters/{encounter_id}/patient-advice")
def patient_advice(encounter_id: str) -> dict:
    encounter = store.encounters.get(encounter_id)
    if not encounter or "diagnosis_summary" not in encounter:
        raise HTTPException(status_code=404, detail="doctor note not found")
    advice = create_patient_advice(encounter_id, encounter)
    for reminder in advice.reminders:
        store.reminders[reminder.id] = reminder.model_dump()
    return advice.model_dump()


@app.get("/reminders")
def reminder_list() -> dict:
    items = sorted(store.reminders.values(), key=lambda item: item["due_at"])
    return {"items": items}


@app.get("/reminders/export/medtimer/{encounter_id}")
def reminder_export_medtimer(encounter_id: str) -> JSONResponse:
    encounter = store.encounters.get(encounter_id)
    if not encounter or "diagnosis_summary" not in encounter:
        raise HTTPException(status_code=404, detail="encounter not found")

    reminders = [item for item in store.reminders.values() if item["encounter_id"] == encounter_id]
    payload = get_reminder_provider().export_backup(
        encounter,
        sorted(reminders, key=lambda item: item["due_at"]),
        store.feedback.get(encounter_id, []),
    )
    return JSONResponse(
        content=payload,
        headers={
            "Content-Disposition": f'attachment; filename="MedTimer_Backup_{encounter_id}.json"',
        },
    )


@app.post("/reminders/{reminder_id}/complete")
def reminder_complete(reminder_id: str, payload: ReminderCompletionRequest) -> dict:
    reminder = store.reminders.get(reminder_id)
    if not reminder:
        raise HTTPException(status_code=404, detail="reminder not found")
    reminder["status"] = payload.status
    return reminder


@app.post("/followup/feedback")
def followup_feedback(payload: FollowupFeedbackRequest) -> dict:
    encounter = store.encounters.get(payload.encounter_id)
    if not encounter:
        raise HTTPException(status_code=404, detail="encounter not found")
    reminder = store.reminders.get(payload.reminder_id)
    if not reminder:
        raise HTTPException(status_code=404, detail="reminder not found")

    care_status = "stable"
    if payload.medication_status == "missed" and payload.symptom_status == "worse":
        care_status = "needs_manual_followup"

    ai_summary = summarize_followup_feedback(encounter, reminder, payload.model_dump(), care_status)
    feedback = payload.model_dump() | {"care_status": care_status} | ai_summary
    store.feedback[payload.encounter_id].append(feedback)
    return feedback


@app.post("/followup/{encounter_id}/doctor-reply")
def doctor_followup_reply(encounter_id: str, payload: DoctorFollowupReplyRequest) -> dict:
    encounter = store.encounters.get(encounter_id)
    if not encounter:
        raise HTTPException(status_code=404, detail="encounter not found")
    feedback_items = store.feedback.get(encounter_id, [])
    if not feedback_items:
        raise HTTPException(status_code=404, detail="followup feedback not found")

    latest = feedback_items[-1]
    latest["doctor_reply"] = {
        "message": payload.message,
        "replied_at": "2026-06-12 18:30",
    }
    latest["care_status"] = "doctor_replied"
    return latest


@app.get("/{full_path:path}", include_in_schema=False)
def serve_frontend(full_path: str) -> FileResponse:
    return _frontend_file_response(full_path)
