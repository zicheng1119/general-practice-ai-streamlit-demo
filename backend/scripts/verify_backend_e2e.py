from __future__ import annotations

import argparse
import json
from typing import Any
from urllib.error import HTTPError
from urllib.parse import quote
from urllib.request import Request, urlopen

import httpx


def request_json(base_url: str, method: str, path: str, data: dict[str, Any] | None = None) -> tuple[int, Any]:
    body = None
    headers: dict[str, str] = {}
    if data is not None:
        body = json.dumps(data).encode("utf-8")
        headers["Content-Type"] = "application/json"

    request = Request(f"{base_url}{path}", data=body, headers=headers, method=method)
    try:
        with urlopen(request, timeout=60) as response:
            raw = response.read().decode("utf-8")
            return response.getcode(), json.loads(raw) if raw else None
    except HTTPError as exc:
        raw = exc.read().decode("utf-8")
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            payload = raw
        return exc.code, payload


def fail(step: str, status: int, body: Any) -> None:
    raise SystemExit(f"{step} failed with status {status}: {json.dumps(body, ensure_ascii=False)}")


def scan_openmrs_recent(
    *,
    openmrs_base: str,
    username: str,
    password: str,
    patient_uuid: str,
    encounter_type_uuid: str,
) -> dict[str, Any]:
    with httpx.Client(timeout=30.0, auth=(username, password)) as client:
        response = client.get(
            f"{openmrs_base.rstrip('/')}/encounter",
            params={
                "patient": patient_uuid,
                "encounterType": encounter_type_uuid,
                "limit": 5,
                "v": "custom:(uuid,encounterDatetime,location:(display),encounterType:(display),obs:(uuid,display,value))",
            },
        )
        response.raise_for_status()

    encounters = response.json()["results"]
    for encounter in reversed(encounters):
        displays = " | ".join(str(obs.get("display", "")) for obs in encounter.get("obs") or [])
        if "Text of encounter note" in displays or "General patient note" in displays or "Plan" in displays:
            return {
                "uuid": encounter["uuid"],
                "encounterDatetime": encounter["encounterDatetime"],
                "obs_count": len(encounter.get("obs") or []),
                "obs_preview": displays,
            }

    return {"found": False, "searched": len(encounters)}


def main() -> None:
    parser = argparse.ArgumentParser(description="Verify this project's local backend full flow against configured OSS integrations.")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000", help="Backend base URL, default: http://127.0.0.1:8000")
    parser.add_argument("--openmrs-base", default="https://o3.openmrs.org/openmrs/ws/rest/v1", help="OpenMRS REST base URL")
    parser.add_argument("--openmrs-username", default="admin", help="OpenMRS username")
    parser.add_argument("--openmrs-password", default="Admin123", help="OpenMRS password")
    parser.add_argument("--openmrs-patient-uuid", default="5234b232-e779-4267-98fb-2bdef1e814b7", help="OpenMRS patient UUID used for verification")
    parser.add_argument("--openmrs-encounter-type-uuid", default="0e8230ce-bd1d-43f5-a863-cf44344fa4b0", help="OpenMRS encounter type UUID used for verification")
    args = parser.parse_args()

    results: dict[str, Any] = {}

    status, triage = request_json(
        args.base_url,
        "POST",
        "/triage/intake",
        {
            "name": "王小云",
            "age": 34,
            "gender": "female",
            "chronic_conditions": ["无"],
            "allergies": ["无"],
            "medications": ["无"],
            "chief_complaint": "咳嗽伴低热三天",
            "symptoms": ["咳嗽", "低热", "咽痛"],
            "duration": "3天",
            "severity": "中等",
            "companions": ["咽痛"],
        },
    )
    if status != 200 or not isinstance(triage, dict):
        fail("triage intake", status, triage)
    triage_id = triage["triage_id"]
    results["triage"] = triage

    status, triage_result = request_json(args.base_url, "GET", f"/triage/{triage_id}/result")
    if status != 200 or not isinstance(triage_result, dict):
        fail("triage result", status, triage_result)
    results["triage_result"] = triage_result

    department = quote(triage_result["recommended_department"])
    status, recommendations = request_json(
        args.base_url,
        "GET",
        f"/booking/recommendations?triage_id={triage_id}&department={department}",
    )
    if status != 200 or not isinstance(recommendations, dict) or not recommendations.get("items"):
        fail("booking recommendations", status, recommendations)
    first_recommendation = recommendations["items"][0]
    results["recommendation"] = first_recommendation

    status, booking = request_json(
        args.base_url,
        "POST",
        "/booking/appointments",
        {
            "triage_id": triage_id,
            "hospital_id": first_recommendation["hospital_id"],
            "department": first_recommendation["department"],
            "doctor_name": first_recommendation["doctor_name"],
            "slot": first_recommendation["slot"],
        },
    )
    if status != 200 or not isinstance(booking, dict):
        fail("booking create", status, booking)
    encounter_id = booking["encounter_id"]
    results["booking"] = booking

    status, doctor_note = request_json(
        args.base_url,
        "POST",
        f"/encounters/{encounter_id}/doctor-note",
        {
            "diagnosis_summary": "上呼吸道感染，建议对症治疗并观察体温变化。",
            "medications": [
                {
                    "name": "阿莫西林胶囊",
                    "dose": "0.5g",
                    "frequency": "每日3次",
                    "duration_days": 5,
                    "instruction": "饭后服用",
                },
                {
                    "name": "氨溴索片",
                    "dose": "30mg",
                    "frequency": "每日3次",
                    "duration_days": 5,
                    "instruction": "多饮水",
                },
            ],
            "doctor_advice": "清淡饮食，注意休息，如持续高热请及时复诊。",
            "follow_up_date": "2026-06-18",
        },
    )
    if status != 200:
        fail("doctor note", status, doctor_note)
    results["doctor_note"] = doctor_note

    status, patient_advice = request_json(args.base_url, "POST", f"/encounters/{encounter_id}/patient-advice")
    if status != 200 or not isinstance(patient_advice, dict) or not patient_advice.get("reminders"):
        fail("patient advice", status, patient_advice)
    results["patient_advice"] = {
        "encounter_id": patient_advice["encounter_id"],
        "plain_language_advice": patient_advice["plain_language_advice"],
        "reminder_count": len(patient_advice["reminders"]),
    }

    reminder_id = patient_advice["reminders"][0]["id"]
    status, reminder_complete = request_json(
        args.base_url,
        "POST",
        f"/reminders/{reminder_id}/complete",
        {"status": "done"},
    )
    if status != 200:
        fail("reminder complete", status, reminder_complete)
    results["reminder_complete"] = reminder_complete

    status, followup_feedback = request_json(
        args.base_url,
        "POST",
        "/followup/feedback",
        {
            "encounter_id": encounter_id,
            "reminder_id": reminder_id,
            "medication_status": "done",
            "symptom_status": "same",
            "note": "已按时服药，症状稍有缓解。",
        },
    )
    if status != 200:
        fail("followup feedback", status, followup_feedback)
    results["followup_feedback"] = followup_feedback

    status, medtimer_export = request_json(args.base_url, "GET", f"/reminders/export/medtimer/{encounter_id}")
    if status != 200 or not isinstance(medtimer_export, dict):
        fail("medtimer export", status, medtimer_export)
    results["medtimer_export"] = {
        "medicine_count": len(medtimer_export["medicines"]["list"]),
        "event_count": len(medtimer_export["events"]["list"]),
    }

    results["openmrs_recent"] = scan_openmrs_recent(
        openmrs_base=args.openmrs_base,
        username=args.openmrs_username,
        password=args.openmrs_password,
        patient_uuid=args.openmrs_patient_uuid,
        encounter_type_uuid=args.openmrs_encounter_type_uuid,
    )

    print(json.dumps(results, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
