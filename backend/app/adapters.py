from __future__ import annotations

import base64
from datetime import datetime, timedelta
import json
import re
from uuid import uuid4

import httpx

from app.models import BookingCreateRequest, BookingRecommendation
from app.services import HOSPITALS, booking_recommendations, score_booking
from app.settings import settings


def _auth_headers(*, api_key: str, username: str, password: str) -> dict[str, str]:
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    elif username and password:
        token = base64.b64encode(f"{username}:{password}".encode("utf-8")).decode("utf-8")
        headers["Authorization"] = f"Basic {token}"
    return headers


def _extract_items(payload: object) -> list[dict]:
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if isinstance(payload, dict):
        if isinstance(payload.get("results"), list):
            return [item for item in payload["results"] if isinstance(item, dict)]
        if isinstance(payload.get("items"), list):
            return [item for item in payload["items"] if isinstance(item, dict)]
        if isinstance(payload.get("data"), list):
            return [item for item in payload["data"] if isinstance(item, dict)]
        if isinstance(payload.get("response"), list):
            return [item for item in payload["response"] if isinstance(item, dict)]
    return []


def _split_patient_name(name: str) -> tuple[str, str]:
    trimmed = name.strip() or "患者"
    if len(trimmed) == 1:
        return trimmed, "患者"
    return trimmed[:1], trimmed[1:]


def _extract_easyappointments_ids(hospital_id: str) -> tuple[int | None, int | None]:
    match = re.fullmatch(r"ea-provider-(\d+)-service-(\d+)", hospital_id)
    if not match:
        return None, None
    provider_id, service_id = match.groups()
    return int(provider_id), int(service_id)


def _format_easyappointments_window(slot: str, duration_minutes: int) -> tuple[str, str]:
    start = datetime.strptime(slot, "%Y-%m-%d %H:%M")
    end = start + timedelta(minutes=duration_minutes)
    return start.strftime("%Y-%m-%d %H:%M:%S"), end.strftime("%Y-%m-%d %H:%M:%S")


def _medication_plan_line(medication: dict) -> str:
    return (
        f"{medication['name']} {medication['dose']}，"
        f"{medication['frequency']}，"
        f"{medication['instruction']}，连续服用 {medication['duration_days']} 天。"
    )


def _easyappointments_api_base_url() -> str:
    base_url = settings.booking_base_url.rstrip("/")
    if base_url.endswith("/api/v1") or base_url.endswith("/index.php/api/v1"):
        return base_url
    return f"{base_url}/index.php/api/v1"


def _openmrs_api_base_url() -> str:
    base_url = settings.clinical_base_url.rstrip("/")
    if base_url.endswith("/openmrs/ws/rest/v1"):
        return base_url
    if base_url.endswith("/openmrs"):
        return f"{base_url}/ws/rest/v1"
    return f"{base_url}/openmrs/ws/rest/v1"


def _provider_name(provider: dict) -> str:
    for first_key, last_key in (
        ("firstName", "lastName"),
        ("first_name", "last_name"),
    ):
        first = str(provider.get(first_key, "")).strip()
        last = str(provider.get(last_key, "")).strip()
        if first or last:
            return f"{last}{first}".strip()

    for key in ("name", "displayName", "display_name"):
        value = str(provider.get(key, "")).strip()
        if value:
            return value
    return f"Provider {provider.get('id', 'unknown')}"


class MockBookingProvider:
    provider = "mock"

    def status(self) -> dict[str, object]:
        return {
            "provider": self.provider,
            "label": "本地演示号源",
            "mode": "demo",
            "compatibility": "Easy!Appointments adapter ready",
            "configured": True,
            "write_mode": "local",
            "docs_url": "https://easyappointments.org/documentation/rest-api/",
            "details": "当前展示数据来自本地号源表，便于课堂演示完整挂号流程。",
        }

    def list_recommendations(self, department: str) -> list[BookingRecommendation]:
        return booking_recommendations(department)

    def create_booking(
        self,
        payload: BookingCreateRequest,
        *,
        triage_id: str,
        appointment_id: str,
        encounter_id: str,
        triage_session: dict,
    ) -> dict:
        hospital_name = next(
            hospital["hospital_name"]
            for hospital in HOSPITALS
            if hospital["hospital_id"] == payload.hospital_id
        )
        return {
            "appointment_id": appointment_id,
            "triage_id": triage_id,
            "hospital_id": payload.hospital_id,
            "hospital_name": hospital_name,
            "department": payload.department,
            "doctor_name": payload.doctor_name,
            "slot": payload.slot,
            "status": "confirmed",
            "encounter_id": encounter_id,
            "notes": ["请携带身份证和既往检查结果。", "如症状明显加重，请提前就诊。"],
            "integration": {
                "provider": self.provider,
                "write_mode": "local",
            },
        }


class EasyAppointmentsBookingProvider:
    provider = "easyappointments"

    @staticmethod
    def _local_mirror_booking(
        payload: BookingCreateRequest,
        *,
        appointment_id: str,
        encounter_id: str,
        triage_id: str,
        note: str,
    ) -> dict:
        hospital_name = next(
            (hospital["hospital_name"] for hospital in HOSPITALS if hospital["hospital_id"] == payload.hospital_id),
            "演示预约中心",
        )
        return {
            "appointment_id": appointment_id,
            "triage_id": triage_id,
            "hospital_id": payload.hospital_id,
            "hospital_name": hospital_name,
            "department": payload.department,
            "doctor_name": payload.doctor_name,
            "slot": payload.slot,
            "status": "confirmed",
            "encounter_id": encounter_id,
            "notes": [
                note,
                "当前已自动切换为本地镜像预约，后续诊后录入、医嘱生成和提醒流程不受影响。",
            ],
            "integration": {
                "provider": "easyappointments",
                "write_mode": "local_mirror",
            },
        }

    def status(self) -> dict[str, object]:
        configured = bool(settings.booking_base_url)
        writable = bool(
            configured
            and (
                settings.booking_api_key
                or (settings.booking_username and settings.booking_password)
            )
        )
        return {
            "provider": self.provider,
            "label": "Easy!Appointments 兼容适配层",
            "mode": "live" if configured else "compatible",
            "compatibility": "Easy!Appointments REST API v1",
            "configured": configured,
            "write_mode": "live" if writable else "local_mirror",
            "docs_url": "https://easyappointments.org/documentation/rest-api/",
            "details": (
                "已按官方 REST API 的 services/providers/availabilities 结构读取号源。"
                if configured
                else "适配器已就绪，配置 BOOKING_BASE_URL 后可读取 Easy!Appointments 号源。"
            ),
        }

    def list_recommendations(self, department: str) -> list[BookingRecommendation]:
        if not settings.booking_base_url:
            return booking_recommendations(department)

        headers = _auth_headers(
            api_key=settings.booking_api_key,
            username=settings.booking_username,
            password=settings.booking_password,
        )
        base_url = _easyappointments_api_base_url()
        target_date = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")

        try:
            with httpx.Client(timeout=20.0, headers=headers, follow_redirects=True, trust_env=False) as client:
                services_response = client.get(
                    f"{base_url}/services",
                    params={"q": department},
                )
                services_response.raise_for_status()
                providers_response = client.get(f"{base_url}/providers")
                providers_response.raise_for_status()

                services = _extract_items(services_response.json())
                if not services:
                    fallback_services_response = client.get(f"{base_url}/services")
                    fallback_services_response.raise_for_status()
                    services = _extract_items(fallback_services_response.json())
                providers = _extract_items(providers_response.json())

                if not services or not providers:
                    return booking_recommendations(department)

                service = services[0]
                service_id = service.get("id")
                if service_id is None:
                    return booking_recommendations(department)
                duration = int(service.get("duration") or 30)
                location = str(service.get("location") or "Easy!Appointments 门诊")

                items: list[BookingRecommendation] = []
                for provider in providers[:8]:
                    provider_id = provider.get("id")
                    if provider_id is None:
                        continue
                    provider_services = provider.get("services") or []
                    if provider_services and service_id not in provider_services:
                        continue

                    availability_response = client.get(
                        f"{base_url}/availabilities",
                        params={
                            "providerId": provider_id,
                            "serviceId": service_id,
                            "date": target_date,
                        },
                    )
                    availability_response.raise_for_status()
                    slots = availability_response.json()
                    if not isinstance(slots, list):
                        continue

                    for slot in slots[:2]:
                        if not isinstance(slot, str):
                            continue
                        full_slot = f"{target_date} {slot}"
                        items.append(
                            BookingRecommendation(
                                hospital_id=f"ea-provider-{provider_id}-service-{service_id}",
                                hospital_name="Easy!Appointments 预约中心",
                                department=department,
                                doctor_name=_provider_name(provider),
                                slot=full_slot,
                                distance_km=2.5,
                                label=f"来自 Easy!Appointments 可用时段 · {location} · {duration} 分钟",
                                score=score_booking(department, 2.5, full_slot, 0.88),
                            )
                        )

                return sorted(items, key=lambda item: item.score, reverse=True)
        except httpx.HTTPError:
            return booking_recommendations(department)

    def create_booking(
        self,
        payload: BookingCreateRequest,
        *,
        triage_id: str,
        appointment_id: str,
        encounter_id: str,
        triage_session: dict,
    ) -> dict:
        if not settings.booking_base_url:
            return {
                "appointment_id": appointment_id,
                "triage_id": triage_id,
                "hospital_id": payload.hospital_id,
                "hospital_name": "Easy!Appointments 预约中心",
                "department": payload.department,
                "doctor_name": payload.doctor_name,
                "slot": payload.slot,
                "status": "confirmed",
                "encounter_id": encounter_id,
                "notes": ["当前为 Easy!Appointments 兼容模式。", "课堂演示默认使用本地确认与后续流程镜像。"],
                "integration": {
                    "provider": self.provider,
                    "write_mode": "local_mirror",
                },
            }

        provider_id, service_id = _extract_easyappointments_ids(payload.hospital_id)
        if provider_id is None or service_id is None:
            return self._local_mirror_booking(
                payload,
                appointment_id=appointment_id,
                encounter_id=encounter_id,
                triage_id=triage_id,
                note="当前号源来自本地回退推荐，未写入外部 Easy!Appointments。",
            )

        headers = _auth_headers(
            api_key=settings.booking_api_key,
            username=settings.booking_username,
            password=settings.booking_password,
        )
        base_url = _easyappointments_api_base_url()
        service_duration = 30
        service_location = payload.department

        try:
            with httpx.Client(timeout=20.0, headers=headers, follow_redirects=True, trust_env=False) as client:
                service_response = client.get(f"{base_url}/services/{service_id}")
                service_response.raise_for_status()
                service_data = service_response.json()
                service_duration = int(service_data.get("duration") or 30)
                service_location = str(service_data.get("location") or payload.department)

                last_name, first_name = _split_patient_name(str(triage_session.get("name", "")))
                unique_suffix = uuid4().hex[:8]
                customer_payload = {
                    "firstName": first_name,
                    "lastName": last_name,
                    "email": f"{triage_id}-{unique_suffix}@example.com",
                    "phone": "0000000000",
                    "city": "Demo",
                    "timezone": "UTC",
                    "language": "english",
                    "notes": f"Generated from triage {triage_id}",
                }
                customer_response = client.post(f"{base_url}/customers", json=customer_payload)
                customer_response.raise_for_status()
                customer_id = int(customer_response.json()["id"])

                start, end = _format_easyappointments_window(payload.slot, service_duration)
                appointment_payload = {
                    "start": start,
                    "end": end,
                    "location": service_location,
                    "status": "Booked",
                    "notes": f"Triage {triage_id} / Encounter {encounter_id}",
                    "customerId": customer_id,
                    "providerId": provider_id,
                    "serviceId": service_id,
                }
                appointment_response = client.post(
                    f"{base_url}/appointments",
                    json=appointment_payload,
                )
                appointment_response.raise_for_status()
                appointment_id_remote = int(appointment_response.json()["id"])
        except httpx.HTTPError:
            return self._local_mirror_booking(
                payload,
                appointment_id=appointment_id,
                encounter_id=encounter_id,
                triage_id=triage_id,
                note="外部 Easy!Appointments 当前不可用，已自动回退为本地镜像预约。",
            )

        return {
            "appointment_id": appointment_id,
            "triage_id": triage_id,
            "hospital_id": payload.hospital_id,
            "hospital_name": "Easy!Appointments 预约中心",
            "department": payload.department,
            "doctor_name": payload.doctor_name,
            "slot": payload.slot,
            "status": "confirmed",
            "encounter_id": encounter_id,
            "notes": ["预约已同步到 Easy!Appointments。", f"外部预约 ID: {appointment_id_remote}"],
            "integration": {
                "provider": self.provider,
                "write_mode": "live",
                "external_id": appointment_id_remote,
                "customer_id": customer_id,
            },
        }


class MemoryClinicalProvider:
    provider = "memory"

    def status(self) -> dict[str, object]:
        return {
            "provider": self.provider,
            "label": "本地临床记录",
            "mode": "demo",
            "compatibility": "OpenMRS encounter mapping ready",
            "configured": True,
            "docs_url": "https://rest.openmrs.org/",
            "details": "当前诊后记录保存在本地内存，用于生成患者白话医嘱和提醒。",
        }

    def sync_doctor_note(self, encounter_id: str, encounter: dict) -> dict:
        return {
            "provider": self.provider,
            "status": "stored_locally",
            "encounter_id": encounter_id,
        }


class OpenMRSClinicalProvider:
    provider = "openmrs"

    def status(self) -> dict[str, object]:
        has_core = bool(settings.clinical_base_url and settings.openmrs_location_uuid and settings.openmrs_encounter_type_uuid)
        has_obs_mapping = bool(
            settings.openmrs_summary_concept_uuid
            and settings.openmrs_advice_concept_uuid
            and settings.openmrs_medication_plan_concept_uuid
        )
        return {
            "provider": self.provider,
            "label": "OpenMRS 兼容临床记录",
            "mode": "live" if has_core else "compatible",
            "compatibility": "OpenMRS REST /openmrs/ws/rest/v1/encounter",
            "configured": has_core,
            "docs_url": "https://rest.openmrs.org/",
            "details": (
                "已按 OpenMRS encounter 结构生成并可回写诊后记录，当前包含摘要/医嘱/用药 obs。"
                if has_core and has_obs_mapping
                else "已可写入 OpenMRS encounter 主体；补齐 concept UUID 后可同时回写摘要、医嘱和用药 obs。"
                if has_core
                else "适配器已就绪，补齐 OpenMRS UUID 与 CLINICAL_BASE_URL 后可回写 encounter。"
            ),
        }

    def sync_doctor_note(self, encounter_id: str, encounter: dict) -> dict:
        payload = self._build_encounter_payload(encounter)
        sync_meta = {
            "provider": self.provider,
            "status": "payload_generated",
            "encounter_id": encounter_id,
            "resource_path": "/openmrs/ws/rest/v1/encounter",
            "payload_preview": payload,
        }

        if not (
            settings.clinical_base_url
            and settings.openmrs_location_uuid
            and settings.openmrs_encounter_type_uuid
        ):
            return sync_meta

        headers = _auth_headers(
            api_key=settings.clinical_api_key,
            username=settings.clinical_username,
            password=settings.clinical_password,
        )

        try:
            with httpx.Client(timeout=20.0, headers=headers, follow_redirects=True, trust_env=False) as client:
                patient_uuid = self._resolve_patient_uuid(client, encounter)
                encounter_role_uuid = self._resolve_encounter_role_uuid(client)
                payload["patient"] = patient_uuid
                if settings.openmrs_provider_uuid and encounter_role_uuid:
                    payload["encounterProviders"] = [
                        {
                            "provider": settings.openmrs_provider_uuid,
                            "encounterRole": encounter_role_uuid,
                        }
                    ]
                response = client.post(
                    f"{_openmrs_api_base_url()}/encounter",
                    json=payload,
                )
                response.raise_for_status()
        except httpx.HTTPError as error:
            sync_meta["status"] = "local_mirror"
            sync_meta["warning"] = f"OpenMRS sync unavailable: {type(error).__name__}"
            return sync_meta

        body = response.json()
        sync_meta["status"] = "synced"
        sync_meta["external_id"] = body.get("uuid") or body.get("encounterUuid")
        return sync_meta

    def _build_encounter_payload(self, encounter: dict) -> dict:
        obs = []
        if settings.openmrs_summary_concept_uuid:
            obs.append(
                {
                    "concept": settings.openmrs_summary_concept_uuid,
                    "value": encounter["diagnosis_summary"],
                }
            )
        if settings.openmrs_advice_concept_uuid:
            obs.append(
                {
                    "concept": settings.openmrs_advice_concept_uuid,
                    "value": encounter["doctor_advice"],
                }
            )
        if settings.openmrs_medication_plan_concept_uuid:
            obs.append(
                {
                    "concept": settings.openmrs_medication_plan_concept_uuid,
                    "value": "；".join(_medication_plan_line(medication) for medication in encounter["medications"]),
                }
            )

        payload = {
            "patient": settings.openmrs_patient_uuid or "demo-patient-uuid",
            "location": settings.openmrs_location_uuid or "demo-location-uuid",
            "encounterType": settings.openmrs_encounter_type_uuid or "demo-encounter-type-uuid",
            "encounterDatetime": datetime.now().strftime("%Y-%m-%dT%H:%M:%S.000+0800"),
            "obs": obs,
        }
        if settings.openmrs_visit_uuid:
            payload["visit"] = settings.openmrs_visit_uuid
        return payload

    def _resolve_patient_uuid(self, client: httpx.Client, encounter: dict) -> str:
        if settings.openmrs_patient_uuid:
            return settings.openmrs_patient_uuid

        patient_name = str(encounter.get("patient_name", "")).strip()
        if not patient_name:
            return "demo-patient-uuid"

        response = client.get(
            f"{_openmrs_api_base_url()}/patient",
            params={"q": patient_name, "limit": 1, "v": "default"},
        )
        response.raise_for_status()
        items = _extract_items(response.json())
        if items:
            return str(items[0].get("uuid") or "demo-patient-uuid")
        return "demo-patient-uuid"

    def _resolve_encounter_role_uuid(self, client: httpx.Client) -> str | None:
        if settings.openmrs_encounter_role_uuid:
            return settings.openmrs_encounter_role_uuid

        response = client.get(
            f"{_openmrs_api_base_url()}/encounterrole",
            params={"limit": 1, "v": "default"},
        )
        response.raise_for_status()
        items = _extract_items(response.json())
        if items:
            return str(items[0].get("uuid"))
        return None


class LocalReminderProvider:
    provider = "local"

    def status(self) -> dict[str, object]:
        return {
            "provider": self.provider,
            "label": "本地提醒中心",
            "mode": "demo",
            "compatibility": "Web reminder center",
            "configured": True,
            "docs_url": "",
            "details": "当前提醒在 Web 页面内完成打卡与随访闭环。",
        }

    def export_backup(self, encounter: dict, reminders: list[dict], feedback: list[dict]) -> dict[str, object]:
        return MedTimerReminderProvider().export_backup(encounter, reminders, feedback)


class MedTimerReminderProvider:
    provider = "medtimer"

    def status(self) -> dict[str, object]:
        return {
            "provider": self.provider,
            "label": "MedTimer 备份桥接",
            "mode": "export",
            "compatibility": "MedTimer JSON backup format",
            "configured": True,
            "docs_url": "https://github.com/Futsch1/medTimer",
            "details": "可将当前患者的药物提醒导出为 MedTimer 可识别的备份 JSON。",
        }

    def export_backup(self, encounter: dict, reminders: list[dict], feedback: list[dict]) -> dict[str, object]:
        medicine_name = encounter["medications"][0]["name"] if encounter["medications"] else encounter["diagnosis_summary"]
        medicines = [
            {
                "medicine": {
                    "name": medicine_name,
                    "color": 0,
                    "useColor": False,
                    "notificationImportance": 3,
                    "iconId": 0,
                    "amount": 0.0,
                    "refillSizes": [],
                    "unit": "片",
                    "sortOrder": 1.0,
                    "notes": encounter["doctor_advice"],
                    "showNotificationAsAlarm": False,
                    "productionDate": 0,
                    "expirationDate": 0,
                    "cannotBeSkipped": False,
                },
                "tags": [{"name": "全科闭环"}],
                "reminders": [
                    self._to_medtimer_reminder(index + 1, medication, reminder)
                    for index, (medication, reminder) in enumerate(zip(encounter["medications"], reminders, strict=False))
                ],
            }
        ]
        if not medicines[0]["reminders"]:
            medicines[0]["reminders"] = [self._to_medtimer_reminder(1, encounter["medications"][0], reminders[0])]

        events = [self._to_medtimer_event(index + 1, medicine_name, reminder) for index, reminder in enumerate(reminders)]
        for entry in feedback:
            events.append(
                {
                    "medicineName": medicine_name,
                    "amount": "",
                    "color": 0,
                    "useColor": False,
                    "status": "ACKNOWLEDGED",
                    "remindedTimestamp": 0,
                    "processedTimestamp": 0,
                    "reminderId": 0,
                    "iconId": 0,
                    "tags": ["全科闭环"],
                    "lastIntervalReminderTimeInMinutes": 0,
                    "notes": entry["note"],
                    "reminderType": "TIME_BASED",
                }
            )

        return {
            "medicines": {"version": 1, "list": medicines},
            "events": {"version": 1, "list": events},
            "settings": self._default_settings(),
        }

    def _to_medtimer_reminder(self, reminder_id: int, medication: dict, reminder: dict) -> dict[str, object]:
        due_at = datetime.strptime(reminder["due_at"], "%Y-%m-%d %H:%M")
        return {
            "reminderId": reminder_id,
            "timeInMinutes": due_at.hour * 60 + due_at.minute,
            "consecutiveDays": 1,
            "pauseDays": 0,
            "instructions": medication["instruction"],
            "cycleStartDay": 0,
            "amount": medication["dose"],
            "days": [True, True, True, True, True, True, True],
            "active": True,
            "periodStart": 0,
            "periodEnd": 0,
            "activeDaysOfMonth": -1,
            "linkedReminderId": 0,
            "intervalStart": 0,
            "intervalStartsFromProcessed": False,
            "variableAmount": False,
            "automaticallyTaken": False,
            "intervalStartTimeOfDay": 480,
            "intervalEndTimeOfDay": 1320,
            "windowedInterval": False,
            "outOfStockThreshold": 0.0,
            "outOfStockReminderType": "OFF",
            "expirationReminderType": "OFF",
            "notificationImportance": "SAME_AS_MEDICINE",
        }

    def _to_medtimer_event(self, reminder_id: int, medicine_name: str, reminder: dict) -> dict[str, object]:
        due_at = datetime.strptime(reminder["due_at"], "%Y-%m-%d %H:%M")
        status_map = {
            "pending": "RAISED",
            "done": "TAKEN",
            "missed": "SKIPPED",
            "snoozed": "ACKNOWLEDGED",
        }
        timestamp_ms = int(due_at.timestamp() * 1000)
        return {
            "medicineName": medicine_name,
            "amount": "",
            "color": 0,
            "useColor": False,
            "status": status_map.get(reminder["status"], "RAISED"),
            "remindedTimestamp": timestamp_ms,
            "processedTimestamp": timestamp_ms if reminder["status"] != "pending" else 0,
            "reminderId": reminder_id,
            "iconId": 0,
            "tags": ["全科闭环"],
            "lastIntervalReminderTimeInMinutes": due_at.hour * 60 + due_at.minute,
            "notes": reminder["description"],
            "reminderType": "TIME_BASED",
        }

    def _default_settings(self) -> dict[str, object]:
        return {
            "weekendStartTimeMinutes": 480,
            "weekendEndTimeMinutes": 1320,
            "weekendMode": False,
            "weekendDays": [],
            "exactReminders": False,
            "repeatReminders": True,
            "numberOfRepetitions": 3,
            "repeatDelayMinutes": 15,
            "snoozeDurationMinutes": 15,
            "overrideDnd": False,
            "stickyOnLockscreen": False,
            "dismissNotificationAction": "NONE",
            "cannotSkipReminders": False,
            "bigNotifications": True,
            "combineNotifications": False,
            "useRelativeDateTime": True,
            "showTakenTimeInOverview": True,
            "systemLocale": True,
            "theme": "SYSTEM",
            "hideMedicineName": False,
            "appAuthentication": False,
            "useSecureWindow": False,
            "disableWidget": False,
            "alarmRingtone": None,
            "noAlarmSoundWhenSilent": False,
            "noVibrationWhenSilent": False,
            "automaticBackupInterval": "NEVER",
            "automaticBackupDirectory": None,
            "locationBasedSnooze": False,
            "homeLatitude": None,
            "homeLongitude": None,
            "homeRadiusMeters": None,
        }


def get_booking_provider() -> MockBookingProvider | EasyAppointmentsBookingProvider:
    if settings.booking_provider == "easyappointments":
        return EasyAppointmentsBookingProvider()
    return MockBookingProvider()


def get_clinical_provider() -> MemoryClinicalProvider | OpenMRSClinicalProvider:
    if settings.clinical_provider == "openmrs":
        return OpenMRSClinicalProvider()
    return MemoryClinicalProvider()


def get_reminder_provider() -> LocalReminderProvider | MedTimerReminderProvider:
    if settings.reminder_provider == "local":
        return LocalReminderProvider()
    return MedTimerReminderProvider()


def get_integration_status() -> dict[str, object]:
    triage_provider = settings.triage_provider or settings.triage_mode or "mock"
    secondary_provider = getattr(settings, "triage_secondary_provider", "")
    secondary_model = getattr(settings, "triage_secondary_model", "")
    triage_mode = "live" if triage_provider in {"deepseek", "fastchat", "kimi"} else "demo"
    if triage_provider == "deepseek":
        triage_label = f"DeepSeek {settings.triage_model}"
        triage_docs = "https://api-docs.deepseek.com/"
        triage_details = "当前分诊已连接真实大模型。"
    elif triage_provider == "fastchat":
        triage_label = f"FastChat {settings.triage_model}"
        triage_docs = "https://github.com/lm-sys/FastChat"
        triage_details = "当前分诊已连接 FastChat 的 OpenAI 兼容网关。"
    elif triage_provider == "kimi":
        triage_label = f"Kimi {settings.triage_model}"
        triage_docs = "https://platform.moonshot.cn/docs"
        triage_details = "当前分诊已连接 Kimi 的 OpenAI 兼容接口。"
    else:
        triage_label = "本地规则分诊"
        triage_docs = ""
        triage_details = "当前使用本地规则引擎，可替换为 FastChat 或其他 OpenAI 兼容网关。"

    if secondary_provider:
        secondary_label = secondary_provider
        if secondary_provider == "fastchat":
            secondary_label = f"FastChat {secondary_model}".strip()
        elif secondary_provider == "kimi":
            secondary_label = f"Kimi {secondary_model}".strip()
        elif secondary_model:
            secondary_label = f"{secondary_provider} {secondary_model}".strip()
        triage_details = f"{triage_details.rstrip('。')}，并启用 {secondary_label} 作为第二路分诊复核。"

    return {
        "triage": {
            "provider": triage_provider,
            "label": triage_label,
            "mode": triage_mode,
            "compatibility": "OpenAI-compatible chat completions / FastChat gateway",
            "configured": bool(settings.triage_base_url) if triage_provider == "fastchat" else (triage_provider in {"deepseek", "kimi"} and bool(settings.triage_api_key) or triage_provider not in {"deepseek", "fastchat", "kimi"}),
            "docs_url": triage_docs,
            "details": triage_details,
        },
        "booking": get_booking_provider().status(),
        "clinical": get_clinical_provider().status(),
        "reminder": get_reminder_provider().status(),
    }
