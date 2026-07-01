from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def _load_env_file() -> None:
    env_path = Path(__file__).resolve().parents[1] / ".env"
    if not env_path.exists():
        return

    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip())


_load_env_file()


def _env(*keys: str, default: str = "") -> str:
    for key in keys:
        value = os.getenv(key, "").strip()
        if value:
            return value
    return default


@dataclass(frozen=True)
class Settings:
    triage_mode: str = os.getenv("AI_TRIAGE_MODE", "mock")
    triage_provider: str = os.getenv("AI_TRIAGE_PROVIDER", "")
    triage_url: str = os.getenv("AI_TRIAGE_URL", "")
    triage_api_key: str = _env("AI_TRIAGE_API_KEY", "DEEPSEEK_API_KEY", "deepseek_api_key")
    triage_model: str = os.getenv("AI_TRIAGE_MODEL", "deepseek-v4-pro")
    triage_base_url: str = os.getenv("AI_TRIAGE_BASE_URL", "https://api.deepseek.com")
    triage_reasoning_effort: str = os.getenv("AI_TRIAGE_REASONING_EFFORT", "high")
    triage_thinking_mode: str = os.getenv("AI_TRIAGE_THINKING_MODE", "disabled")
    triage_secondary_provider: str = os.getenv("AI_TRIAGE_SECONDARY_PROVIDER", "")
    triage_secondary_api_key: str = _env(
        "AI_TRIAGE_SECONDARY_API_KEY",
        "KIMI_API_KEY",
        "MOONSHOT_API_KEY",
        "kimi_api_key",
        "moonshot_api_key",
    )
    triage_secondary_model: str = os.getenv("AI_TRIAGE_SECONDARY_MODEL", "vicuna-13b")
    triage_secondary_base_url: str = os.getenv("AI_TRIAGE_SECONDARY_BASE_URL", "")
    triage_secondary_reasoning_effort: str = os.getenv("AI_TRIAGE_SECONDARY_REASONING_EFFORT", "high")
    triage_secondary_thinking_mode: str = os.getenv("AI_TRIAGE_SECONDARY_THINKING_MODE", "disabled")
    booking_provider: str = os.getenv("BOOKING_PROVIDER", "mock")
    booking_base_url: str = os.getenv("BOOKING_BASE_URL", "")
    booking_api_key: str = os.getenv("BOOKING_API_KEY", "")
    booking_username: str = os.getenv("BOOKING_USERNAME", "")
    booking_password: str = os.getenv("BOOKING_PASSWORD", "")
    clinical_provider: str = os.getenv("CLINICAL_PROVIDER", "memory")
    clinical_base_url: str = os.getenv("CLINICAL_BASE_URL", "")
    clinical_api_key: str = os.getenv("CLINICAL_API_KEY", "")
    clinical_username: str = os.getenv("CLINICAL_USERNAME", "")
    clinical_password: str = os.getenv("CLINICAL_PASSWORD", "")
    openmrs_patient_uuid: str = os.getenv("OPENMRS_PATIENT_UUID", "")
    openmrs_provider_uuid: str = os.getenv("OPENMRS_PROVIDER_UUID", "")
    openmrs_location_uuid: str = os.getenv("OPENMRS_LOCATION_UUID", "")
    openmrs_encounter_type_uuid: str = os.getenv("OPENMRS_ENCOUNTER_TYPE_UUID", "")
    openmrs_encounter_role_uuid: str = os.getenv("OPENMRS_ENCOUNTER_ROLE_UUID", "")
    openmrs_visit_uuid: str = os.getenv("OPENMRS_VISIT_UUID", "")
    openmrs_summary_concept_uuid: str = os.getenv("OPENMRS_SUMMARY_CONCEPT_UUID", "")
    openmrs_advice_concept_uuid: str = os.getenv("OPENMRS_ADVICE_CONCEPT_UUID", "")
    openmrs_medication_plan_concept_uuid: str = os.getenv("OPENMRS_MEDICATION_PLAN_CONCEPT_UUID", "")
    reminder_provider: str = os.getenv("REMINDER_PROVIDER", "medtimer")


settings = Settings()
