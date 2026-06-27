from __future__ import annotations

import json
from datetime import datetime
from typing import Any
from urllib.parse import urlparse

import httpx

from app.models import (
    BookingRecommendation,
    DoctorNoteRequest,
    MedicationInput,
    PatientAdvice,
    ReminderTask,
    TriageAssessment,
    TriageResult,
    TriageValidationResult,
)
from app.settings import settings
from app.store import store


DISCLAIMER = "仅供辅助参考，以医生判断为准。"

RED_FLAG_MAP = {
    "胸痛": "胸痛",
    "呼吸困难": "呼吸困难",
    "晕厥": "意识障碍",
    "抽搐": "抽搐",
    "意识障碍": "意识障碍",
}

DEPARTMENT_RULES = [
    ("呼吸内科", {"发热", "咳嗽", "黄痰", "乏力", "咽痛"}),
    ("消化内科", {"胃痛", "反酸", "腹胀", "恶心", "腹泻"}),
    ("皮肤科", {"皮疹", "瘙痒"}),
    ("心血管内科", {"头晕", "血压升高", "心悸"}),
]

HOSPITALS = [
    {
        "hospital_id": "hosp-001",
        "hospital_name": "滨海市第一人民医院",
        "label": "三甲综合医院",
        "distance_km": 3.2,
        "slots": {
            "急诊医学科": [("急诊分诊台", "2026-06-12 08:10"), ("急诊值班医生", "2026-06-12 08:40")],
            "心血管内科": [("陈医生", "2026-06-12 09:00"), ("李医生", "2026-06-12 14:30")],
            "呼吸内科": [("王医生", "2026-06-12 11:00")],
            "消化内科": [("刘医生", "2026-06-12 13:30")],
        },
        "tag_score": 0.95,
    },
    {
        "hospital_id": "hosp-002",
        "hospital_name": "江南社区医疗中心",
        "label": "社区友好，排队短",
        "distance_km": 1.6,
        "slots": {
            "急诊医学科": [("急诊绿色通道", "2026-06-12 08:20")],
            "呼吸内科": [("周医生", "2026-06-12 10:30"), ("孙医生", "2026-06-12 15:00")],
            "全科医学科": [("林医生", "2026-06-12 09:20")],
            "消化内科": [("赵医生", "2026-06-12 16:00")],
        },
        "tag_score": 0.82,
    },
    {
        "hospital_id": "hosp-003",
        "hospital_name": "东城专科联盟门诊",
        "label": "专病门诊，可加急",
        "distance_km": 4.5,
        "slots": {
            "急诊医学科": [("夜间急诊接诊台", "2026-06-12 08:30")],
            "呼吸内科": [("高医生", "2026-06-12 09:40")],
            "消化内科": [("何医生", "2026-06-12 09:10"), ("许医生", "2026-06-12 17:00")],
        },
        "tag_score": 0.9,
    },
]


def _find_risk_flags(symptoms: list[str], complaint: str, companions: list[str]) -> list[str]:
    combined = set(symptoms + companions)
    complaint_text = complaint or ""
    flags = [label for keyword, label in RED_FLAG_MAP.items() if keyword in combined or keyword in complaint_text]
    return sorted(set(flags))


def _match_department(symptoms: list[str], complaint: str) -> tuple[str, float]:
    combined = set(symptoms)
    complaint_text = complaint or ""
    best_department = "全科医学科"
    best_score = 0.62

    for department, keywords in DEPARTMENT_RULES:
        overlap = sum(1 for keyword in keywords if keyword in combined or keyword in complaint_text)
        if overlap:
            score = min(0.62 + overlap * 0.12, 0.94)
            if score > best_score:
                best_department = department
                best_score = score

    return best_department, round(best_score, 2)


def _triage_label(provider: str, model: str) -> str:
    if provider == "deepseek":
        return "DeepSeek 分诊"
    if provider == "fastchat":
        return "FastChat 开源分诊"
    if provider == "kimi":
        return "Kimi API 复核"
    if provider == "external":
        return "外部分诊接口"
    return "本地规则分诊"


def _primary_ai_task_config() -> dict[str, str] | None:
    provider = settings.triage_provider or settings.triage_mode
    if provider in {"deepseek", "kimi"}:
        if not settings.triage_base_url:
            return None
        return {
            "api_key": settings.triage_api_key,
            "model": settings.triage_model,
            "base_url": settings.triage_base_url,
            "reasoning_effort": settings.triage_reasoning_effort,
            "thinking_mode": settings.triage_thinking_mode,
        }
    if provider == "fastchat":
        if not settings.triage_base_url:
            return None
        return {
            "api_key": settings.triage_api_key,
            "model": settings.triage_model,
            "base_url": settings.triage_base_url,
            "reasoning_effort": settings.triage_reasoning_effort,
            "thinking_mode": settings.triage_thinking_mode,
        }
    return None


def _request_openai_compatible_json(
    *,
    system_prompt: str,
    user_payload: dict[str, Any],
    api_key: str,
    model: str,
    base_url: str,
    reasoning_effort: str = "high",
    thinking_mode: str = "disabled",
    provider: str = "openai_compatible",
    max_tokens: int = 900,
) -> dict[str, Any]:
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    parsed_base_url = urlparse(base_url)
    is_local_fastchat = parsed_base_url.hostname in {"127.0.0.1", "localhost", "::1"}

    payload: dict[str, Any] = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": json.dumps(user_payload, ensure_ascii=False)},
        ],
        "stream": False,
        "max_tokens": max_tokens,
    }
    if not is_local_fastchat and provider != "kimi":
        payload["response_format"] = {"type": "json_object"}
        payload["reasoning_effort"] = "max" if reasoning_effort == "xhigh" else reasoning_effort
        payload["thinking"] = {"type": thinking_mode}

    timeout_seconds = 90.0 if is_local_fastchat else 30.0
    with httpx.Client(timeout=timeout_seconds) as client:
        response = client.post(f"{base_url.rstrip('/')}/chat/completions", json=payload, headers=headers)
        response.raise_for_status()

    data = response.json()
    content = data["choices"][0]["message"]["content"]
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        return _extract_first_json_object(content)


def _is_local_openai_gateway(base_url: str) -> bool:
    parsed_base_url = urlparse(base_url)
    return parsed_base_url.hostname in {"127.0.0.1", "localhost", "::1"}


def _extract_first_json_object(content: str) -> dict[str, Any]:
    start = content.find("{")
    if start < 0:
        raise json.JSONDecodeError("No JSON object found", content, 0)

    depth = 0
    in_string = False
    escaped = False
    for index in range(start, len(content)):
        char = content[index]
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            continue

        if char == '"':
            in_string = True
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return json.loads(content[start : index + 1])

    raise json.JSONDecodeError("Incomplete JSON object", content, start)


def _build_rule_triage_result(session: dict) -> TriageAssessment:
    risk_flags = _find_risk_flags(
        session["symptoms"],
        session["chief_complaint"],
        session["companions"],
    )
    if risk_flags:
        return TriageAssessment(
            recommended_department="急诊医学科",
            urgency="立即急诊",
            confidence=0.99,
            explanation="检测到红旗症状，建议优先前往急诊排查严重心肺或神经系统风险。",
            emergency=True,
            risk_flags=risk_flags,
            suggested_hospital_type="具备急诊能力的综合医院",
            disclaimer=DISCLAIMER,
        )

    department, confidence = _match_department(session["symptoms"], session["chief_complaint"])
    urgency = "24小时内就诊" if session["severity"] != "轻" else "建议近三天内就诊"
    explanation = f"根据主诉、症状与补充回答，当前更适合先到{department}进一步评估。"

    return TriageAssessment(
        recommended_department=department,
        urgency=urgency,
        confidence=confidence,
        explanation=explanation,
        emergency=False,
        risk_flags=[],
        suggested_hospital_type="综合医院或社区专科门诊",
        disclaimer=DISCLAIMER,
    )


def _run_configured_triage(
    session: dict,
    *,
    provider: str,
    api_key: str,
    model: str,
    base_url: str,
    reasoning_effort: str,
    thinking_mode: str,
) -> TriageAssessment:
    if provider == "deepseek":
        result = request_deepseek_triage(
            session,
            api_key=api_key,
            model=model,
            base_url=base_url,
            reasoning_effort=reasoning_effort,
            thinking_mode=thinking_mode,
        )
        return TriageAssessment(**result.model_dump())
    if provider == "kimi":
        result = request_kimi_triage(
            session,
            api_key=api_key,
            model=model,
            base_url=base_url,
            reasoning_effort=reasoning_effort,
            thinking_mode=thinking_mode,
        )
        return TriageAssessment(**result.model_dump())
    if provider == "fastchat":
        result = request_openai_compatible_triage(
            session,
            api_key=api_key,
            model=model,
            base_url=base_url,
            reasoning_effort=reasoning_effort,
            thinking_mode=thinking_mode,
        )
        return TriageAssessment(**result.model_dump())
    if provider == "external" and settings.triage_url:
        result = request_external_triage(session)
        return TriageAssessment(**result.model_dump())
    return _build_rule_triage_result(session)


def generate_triage_result(session: dict) -> TriageResult:
    primary_provider = settings.triage_provider or settings.triage_mode or "mock"
    primary_label = _triage_label(primary_provider, settings.triage_model)
    primary_result: TriageAssessment | None = None
    primary_error: Exception | None = None
    validation_results: list[TriageValidationResult] = []
    try:
        primary_result = _run_configured_triage(
            session,
            provider=primary_provider,
            api_key=settings.triage_api_key,
            model=settings.triage_model,
            base_url=settings.triage_base_url,
            reasoning_effort=settings.triage_reasoning_effort,
            thinking_mode=settings.triage_thinking_mode,
        )
        validation_results.append(
            TriageValidationResult(
                source=primary_provider,
                label=primary_label,
                status="available",
                note="主分诊模型",
                result=primary_result,
            )
        )
    except Exception as error:
        primary_error = error
        validation_results.append(
            TriageValidationResult(
                source=primary_provider,
                label=primary_label,
                status="unavailable",
                note=f"主分诊当前不可用：{type(error).__name__}",
            )
        )

    secondary_provider = getattr(settings, "triage_secondary_provider", "")
    secondary_result: TriageAssessment | None = None
    secondary_label = ""
    if secondary_provider:
        secondary_model = getattr(settings, "triage_secondary_model", "secondary-model")
        secondary_label = _triage_label(secondary_provider, secondary_model)
        secondary_base_url = getattr(settings, "triage_secondary_base_url", "")
        missing_config = secondary_provider in {"deepseek", "fastchat", "kimi"} and not secondary_base_url
        if missing_config:
            validation_results.append(
                TriageValidationResult(
                    source=secondary_provider,
                    label=secondary_label,
                    status="unavailable",
                    note="未配置开源复核网关地址，当前无法完成第二路分诊校验。",
                )
            )
        else:
            try:
                secondary_result = _run_configured_triage(
                    session,
                    provider=secondary_provider,
                    api_key=getattr(settings, "triage_secondary_api_key", ""),
                    model=secondary_model,
                    base_url=secondary_base_url,
                    reasoning_effort=getattr(settings, "triage_secondary_reasoning_effort", "high"),
                    thinking_mode=getattr(settings, "triage_secondary_thinking_mode", "disabled"),
                )
                validation_results.append(
                    TriageValidationResult(
                        source=secondary_provider,
                        label=secondary_label,
                        status="available",
                        note="GitHub 开源项目复核",
                        result=secondary_result,
                    )
                )
            except Exception as error:
                validation_results.append(
                    TriageValidationResult(
                        source=secondary_provider,
                        label=secondary_label,
                        status="unavailable",
                        note=f"第二路分诊当前不可用：{type(error).__name__}",
                    )
                )

    effective_result = primary_result
    consensus_summary = "当前综合建议以主分诊结果为准。"
    disagreement_note = None
    if not effective_result and secondary_result:
        effective_result = secondary_result
        consensus_summary = (
            f"{primary_label} 当前不可用，系统已自动切换为 {secondary_label} 输出建议，"
            "以保证分诊流程不中断。"
        )
    if not effective_result:
        effective_result = _build_rule_triage_result(session)
        validation_results.append(
            TriageValidationResult(
                source="rules",
                label="本地规则引擎",
                status="available",
                note="外部分诊不可用时的本地兜底结果",
                result=effective_result,
            )
        )
        if primary_error:
            consensus_summary = "当前外部分诊暂不可用，系统已切换到本地规则引擎兜底输出。"

    if primary_result and secondary_result:
        if primary_result.emergency or secondary_result.emergency:
            consensus_summary = "双分诊结果中任一路提示存在风险时，系统优先保守处理并建议尽快线下评估。"
        elif primary_result.recommended_department == secondary_result.recommended_department:
            consensus_summary = (
                f"{primary_label} 与 {secondary_label} 对推荐科室基本一致，"
                f"当前综合建议仍为 {primary_result.recommended_department}。"
            )
        else:
            disagreement_note = (
                f"{secondary_label} 更倾向 {secondary_result.recommended_department}，"
                f"但当前系统仍优先采用 {primary_result.recommended_department} 作为挂号主建议。"
            )
            consensus_summary = "系统已展示双重分诊结果，最终建议默认采用主分诊模型并保留开源分诊复核意见。"

    return TriageResult(
        **effective_result.model_dump(),
        validation_results=validation_results,
        consensus_summary=consensus_summary,
        disagreement_note=disagreement_note,
    )


def generate_follow_up_question(session: dict) -> str:
    if any(symptom in session["symptoms"] for symptom in ("发热", "咳嗽")):
        return "请补充是否有黄痰、胸痛或呼吸困难。"
    if any(symptom in session["symptoms"] for symptom in ("胃痛", "反酸")):
        return "请补充疼痛与进食是否相关，是否伴有黑便或呕吐。"
    if any(symptom in session["symptoms"] for symptom in ("头晕", "血压升高")):
        return "请补充近期最高血压值，以及是否伴有胸闷、头痛。"
    return "请补充症状加重时段、诱因以及是否影响日常生活。"


def score_booking(department: str, distance_km: float, slot: str, tag_score: float) -> float:
    department_score = 1.0
    earliest = datetime.strptime(slot, "%Y-%m-%d %H:%M")
    baseline = datetime.strptime("2026-06-12 09:00", "%Y-%m-%d %H:%M")
    hours_delta = max((earliest - baseline).total_seconds() / 3600, 0)
    slot_score = max(0.3, 1 - hours_delta / 12)
    distance_score = max(0.2, 1 - distance_km / 10)
    total = department_score * 0.5 + slot_score * 0.2 + distance_score * 0.2 + tag_score * 0.1
    return round(total, 3)


def booking_recommendations(department: str) -> list[BookingRecommendation]:
    items: list[BookingRecommendation] = []
    for hospital in HOSPITALS:
        for doctor_name, slot in hospital["slots"].get(department, []):
            items.append(
                BookingRecommendation(
                    hospital_id=hospital["hospital_id"],
                    hospital_name=hospital["hospital_name"],
                    department=department,
                    doctor_name=doctor_name,
                    slot=slot,
                    distance_km=hospital["distance_km"],
                    label=hospital["label"],
                    score=score_booking(
                        department,
                        hospital["distance_km"],
                        slot,
                        hospital["tag_score"],
                    ),
                )
            )
    if not items:
        fallback_departments = ["全科医学科", "急诊医学科", "呼吸内科"]
        for hospital in HOSPITALS:
            fallback_slots = []
            for fallback_department in fallback_departments:
                fallback_slots = hospital["slots"].get(fallback_department, [])
                if fallback_slots:
                    break
            for doctor_name, slot in fallback_slots[:1]:
                items.append(
                    BookingRecommendation(
                        hospital_id=hospital["hospital_id"],
                        hospital_name=hospital["hospital_name"],
                        department=department,
                        doctor_name=f"{doctor_name}（全科兜底）",
                        slot=slot,
                        distance_km=hospital["distance_km"],
                        label=f"{hospital['label']} · 兜底号源",
                        score=score_booking(
                            department,
                            hospital["distance_km"],
                            slot,
                            hospital["tag_score"] * 0.92,
                        ),
                    )
                )

    return sorted(items, key=lambda item: item.score, reverse=True)


def _fallback_booking_reason(session: dict, recommendation: BookingRecommendation) -> str:
    return (
        f"基于当前主诉“{session['chief_complaint']}”和分诊建议，"
        f"{recommendation.hospital_name} 的 {recommendation.department} 号源可较早就诊，"
        f"距离约 {recommendation.distance_km} km，适合作为当前优先预约选择。"
    )


def enrich_booking_recommendations(session: dict, items: list[BookingRecommendation]) -> list[BookingRecommendation]:
    if not items:
        return items

    ai_reason = None
    ai_config = _primary_ai_task_config()
    if ai_config:
        try:
            payload = _request_openai_compatible_json(
                system_prompt="""
你是全科门诊预约推荐助手。请根据症状摘要、分诊结论和首选号源，生成一个简洁中文说明，解释为什么当前最推荐这个预约方案。

只输出一个 JSON 对象，字段：
- ai_reason: string
""".strip(),
                user_payload={
                    "chief_complaint": session["chief_complaint"],
                    "symptoms": session["symptoms"],
                    "primary_recommendation": items[0].model_dump(),
                },
                max_tokens=220,
                **ai_config,
            )
            ai_reason = str(payload.get("ai_reason", "")).strip() or None
        except Exception:
            ai_reason = None

    enriched: list[BookingRecommendation] = []
    for index, item in enumerate(items):
        reason = ai_reason if index == 0 and ai_reason else _fallback_booking_reason(session, item)
        enriched.append(item.model_copy(update={"ai_reason": reason}))
    return enriched


def request_external_triage(session: dict) -> TriageResult:
    headers = {"Content-Type": "application/json"}
    if settings.triage_api_key:
        headers["Authorization"] = f"Bearer {settings.triage_api_key}"

    payload = {
        "patient_profile": {
            "age": session["age"],
            "gender": session["gender"],
            "chronic_conditions": session["chronic_conditions"],
            "allergies": session["allergies"],
            "medications": session["medications"],
        },
        "symptom_intake": {
            "chief_complaint": session["chief_complaint"],
            "symptoms": session["symptoms"],
            "duration": session["duration"],
            "severity": session["severity"],
            "companions": session["companions"],
            "answers": session["answers"],
        },
    }

    with httpx.Client(timeout=30.0) as client:
        response = client.post(settings.triage_url, json=payload, headers=headers)
        response.raise_for_status()

    data = response.json()
    return TriageResult(
        recommended_department=data["recommended_department"],
        urgency=data["urgency"],
        confidence=float(data["confidence"]),
        explanation=data["explanation"],
        emergency=bool(data["emergency"]),
        risk_flags=list(data.get("risk_flags", [])),
        suggested_hospital_type=data.get("suggested_hospital_type", "综合医院"),
        disclaimer=data.get("disclaimer", DISCLAIMER),
    )


def request_deepseek_triage(
    session: dict,
    *,
    api_key: str,
    model: str,
    base_url: str,
    reasoning_effort: str = "high",
    thinking_mode: str = "disabled",
) -> TriageResult:
    return request_openai_compatible_triage(
        session,
        api_key=api_key,
        model=model,
        base_url=base_url,
        reasoning_effort=reasoning_effort,
        thinking_mode=thinking_mode,
        provider="deepseek",
    )


def request_kimi_triage(
    session: dict,
    *,
    api_key: str,
    model: str,
    base_url: str,
    reasoning_effort: str = "high",
    thinking_mode: str = "disabled",
) -> TriageResult:
    return request_openai_compatible_triage(
        session,
        api_key=api_key,
        model=model,
        base_url=base_url,
        reasoning_effort=reasoning_effort,
        thinking_mode=thinking_mode,
        provider="kimi",
    )


def request_openai_compatible_triage(
    session: dict,
    *,
    api_key: str,
    model: str,
    base_url: str,
    reasoning_effort: str = "high",
    thinking_mode: str = "disabled",
    provider: str = "openai_compatible",
) -> TriageResult:
    rule_result = _build_rule_triage_result(session)
    system_prompt = """
你是全科门诊 AI 分诊助手。你的任务不是下正式诊断，而是根据患者资料输出安全、克制、结构化的就医建议。

必须只输出一个 JSON 对象，不要输出 Markdown，不要输出解释性前缀。
JSON 字段必须包含：
- recommended_department: string
- urgency: string
- confidence: number (0 到 1)
- explanation: string
- emergency: boolean
- risk_flags: string[]
- suggested_hospital_type: string
- disclaimer: string

规则：
1. 如果出现胸痛、呼吸困难、晕厥、抽搐、意识障碍等红旗症状，emergency 必须为 true，recommended_department 必须为“急诊医学科”，urgency 必须为“立即急诊”。
2. 只做分诊建议，不给病名诊断结论。
3. disclaimer 固定为“仅供辅助参考，以医生判断为准。”
4. explanation 用中文，简洁说明依据。
""".strip()
    try:
        parsed = _request_openai_compatible_json(
            system_prompt=system_prompt,
            user_payload={
                "patient_profile": {
                    "age": session["age"],
                    "gender": session["gender"],
                    "chronic_conditions": session["chronic_conditions"],
                    "allergies": session["allergies"],
                    "medications": session["medications"],
                },
                "symptom_intake": {
                    "chief_complaint": session["chief_complaint"],
                    "symptoms": session["symptoms"],
                    "duration": session["duration"],
                    "severity": session["severity"],
                    "companions": session["companions"],
                    "answers": session["answers"],
                },
            },
            api_key=api_key,
            model=model,
            base_url=base_url,
            reasoning_effort=reasoning_effort,
            thinking_mode=thinking_mode,
            provider=provider,
            max_tokens=512 if provider == "kimi" else 256,
        )
    except json.JSONDecodeError:
        if not _is_local_openai_gateway(base_url):
            raise
        return TriageResult(
            **rule_result.model_copy(
                update={
                    "explanation": (
                        f"FastChat 网关已连通，但本地模型输出非结构化；"
                        f"系统已用安全规则整理为：{rule_result.explanation}"
                    ),
                    "confidence": min(rule_result.confidence, 0.72),
                }
            ).model_dump()
        )

    recommended_department = str(parsed.get("recommended_department") or "").strip()
    if recommended_department in {"", "内科", "外科", "门诊"}:
        recommended_department = rule_result.recommended_department

    emergency_raw = parsed.get("emergency", rule_result.emergency)
    if isinstance(emergency_raw, str):
        emergency = emergency_raw.strip().lower() in {"true", "1", "yes", "是"}
    else:
        emergency = bool(emergency_raw)

    risk_flags_raw = parsed.get("risk_flags", [])
    if isinstance(risk_flags_raw, list):
        risk_flags = [str(item) for item in risk_flags_raw if str(item).strip()]
    else:
        risk_flags = []

    # If the local model marks an emergency without matching red-flag evidence,
    # fall back to the rule-engine result to keep triage conservative but sane.
    if emergency and not _find_risk_flags(session["symptoms"], session["chief_complaint"], session["companions"]):
        emergency = rule_result.emergency
        recommended_department = rule_result.recommended_department
        risk_flags = rule_result.risk_flags

    explanation = str(parsed.get("explanation") or "").strip() or rule_result.explanation
    urgency = str(parsed.get("urgency") or "").strip() or rule_result.urgency
    suggested_hospital_type = str(parsed.get("suggested_hospital_type") or "").strip() or rule_result.suggested_hospital_type
    disclaimer = str(parsed.get("disclaimer") or "").strip() or DISCLAIMER

    try:
        confidence = float(parsed.get("confidence", rule_result.confidence))
    except (TypeError, ValueError):
        confidence = rule_result.confidence
    confidence = min(max(confidence, 0.0), 1.0)

    return TriageResult(
        recommended_department=recommended_department,
        urgency=urgency,
        confidence=confidence,
        explanation=explanation,
        emergency=emergency,
        risk_flags=risk_flags,
        suggested_hospital_type=suggested_hospital_type,
        disclaimer=disclaimer,
    )


def _normalize_frequency(frequency: str) -> str:
    return (
        frequency.replace("每日", "每天 ")
        .replace("每日 ", "每天 ")
        .replace("1次", "1 次")
        .replace("2次", "2 次")
        .replace("3次", "3 次")
    )


def _fallback_plain_language_advice(encounter: dict, medication_lines: list[str]) -> str:
    return "；".join(medication_lines + [encounter["doctor_advice"]])


def create_patient_advice(encounter_id: str, encounter: dict) -> PatientAdvice:
    medication_lines: list[str] = []
    reminders: list[ReminderTask] = []

    for medication in encounter["medications"]:
        reminder_id = store.next_id("rem")
        line = (
            f"{medication['name']} {medication['dose']}，"
            f"{_normalize_frequency(medication['frequency'])}，"
            f"{medication['instruction']}，连续服用 {medication['duration_days']} 天。"
        )
        medication_lines.append(line)
        reminders.append(
            ReminderTask(
                id=reminder_id,
                encounter_id=encounter_id,
                title=f"服用{medication['name']}",
                description=line,
                due_at="2026-06-12 08:00",
                status="pending",
                kind="medication",
            )
        )

    follow_up_id = store.next_id("rem")
    reminders.append(
        ReminderTask(
            id=follow_up_id,
            encounter_id=encounter_id,
            title="复诊提醒",
            description=f"请于 {encounter['follow_up_date']} 前后复诊，带上近期监测记录。",
            due_at=f"{encounter['follow_up_date']} 09:00",
            status="pending",
            kind="follow_up",
        )
    )

    caution = None
    if any("如" in encounter["doctor_advice"] and "及时就诊" in encounter["doctor_advice"] for _ in [0]):
        caution = "如出现胸闷、头痛加重或其他明显不适，请及时线下就医。"

    plain_language_advice = _fallback_plain_language_advice(encounter, medication_lines)
    advice_generation_mode: str = "fallback"
    ai_config = _primary_ai_task_config()
    if ai_config:
        try:
            payload = _request_openai_compatible_json(
                system_prompt="""
你是全科门诊患者沟通助手。请把医生专业医嘱改写成患者容易理解的大白话，不要夸张，不要新增诊断。

只输出一个 JSON 对象，字段：
- plain_language_advice: string
- lifestyle_tips: string[]
""".strip(),
                user_payload={
                    "diagnosis_summary": encounter["diagnosis_summary"],
                    "medications": encounter["medications"],
                    "doctor_advice": encounter["doctor_advice"],
                    "follow_up_date": encounter["follow_up_date"],
                },
                max_tokens=420,
                **ai_config,
            )
            ai_text = str(payload.get("plain_language_advice", "")).strip()
            ai_tips = payload.get("lifestyle_tips", [])
            if ai_text:
                plain_language_advice = ai_text
                advice_generation_mode = "ai"
            lifestyle_tips = [str(item) for item in ai_tips if str(item).strip()] or [
                "按时监测症状变化",
                "保持饮水与休息",
                "如不适加重尽快复诊",
            ]
        except Exception:
            lifestyle_tips = ["按时监测症状变化", "保持饮水与休息", "如不适加重尽快复诊"]
    else:
        lifestyle_tips = ["按时监测症状变化", "保持饮水与休息", "如不适加重尽快复诊"]

    return PatientAdvice(
        encounter_id=encounter_id,
        original_summary=encounter["diagnosis_summary"],
        plain_language_advice=plain_language_advice,
        lifestyle_tips=lifestyle_tips,
        reminders=reminders,
        caution=caution,
        advice_generation_mode=advice_generation_mode,
    )


def serialize_medications(medications: list[MedicationInput]) -> list[dict]:
    return [medication.model_dump() for medication in medications]


def serialize_doctor_note(note: DoctorNoteRequest) -> dict:
    return {
        "diagnosis_summary": note.diagnosis_summary,
        "medications": serialize_medications(note.medications),
        "doctor_advice": note.doctor_advice,
        "follow_up_date": note.follow_up_date,
    }


def summarize_followup_feedback(encounter: dict, reminder: dict, payload: dict, care_status: str) -> dict[str, str]:
    fallback = {
        "ai_summary": (
            f"当前反馈显示患者用药状态为 {payload['medication_status']}，"
            f"症状变化为 {payload['symptom_status']}，系统建议继续结合线下医生意见观察。"
        ),
        "next_step": "继续按提醒执行；如果症状加重或持续无改善，请提前复诊。",
    }

    if care_status == "needs_manual_followup":
        fallback["next_step"] = "建议尽快联系医生或门诊复诊，必要时安排人工随访。"

    ai_config = _primary_ai_task_config()
    if not ai_config:
        return fallback

    try:
        result = _request_openai_compatible_json(
            system_prompt="""
你是全科门诊随访助手。请根据患者用药状态、症状变化和医生原始医嘱，输出简洁中文随访总结。

只输出一个 JSON 对象，字段：
- ai_summary: string
- next_step: string
""".strip(),
            user_payload={
                "diagnosis_summary": encounter["diagnosis_summary"],
                "doctor_advice": encounter["doctor_advice"],
                "reminder_title": reminder["title"],
                "medication_status": payload["medication_status"],
                "symptom_status": payload["symptom_status"],
                "patient_note": payload["note"],
                "care_status": care_status,
            },
            max_tokens=260,
            **ai_config,
        )
        ai_summary = str(result.get("ai_summary", "")).strip()
        next_step = str(result.get("next_step", "")).strip()
        if ai_summary and next_step:
            return {"ai_summary": ai_summary, "next_step": next_step}
    except Exception:
        pass

    return fallback
