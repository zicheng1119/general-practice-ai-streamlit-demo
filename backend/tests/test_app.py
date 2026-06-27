from fastapi.testclient import TestClient
import httpx
import pytest
from types import SimpleNamespace

import app.main as main_module
from app.main import app
from app.adapters import OpenMRSClinicalProvider
from app.services import generate_triage_result, request_deepseek_triage


client = TestClient(app)


def test_react_frontend_routes_fall_back_to_built_index(tmp_path, monkeypatch: pytest.MonkeyPatch):
    dist = tmp_path / "dist"
    dist.mkdir()
    index = dist / "index.html"
    index.write_text("<!doctype html><html><body><div id='root'></div></body></html>", encoding="utf-8")

    monkeypatch.setattr(main_module, "FRONTEND_DIST", dist, raising=False)
    monkeypatch.setattr(main_module, "FRONTEND_INDEX", index, raising=False)

    response = client.get("/patient/intake")

    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "id='root'" in response.text


def test_red_flag_triage_short_circuits_to_emergency():
    response = client.post(
        "/triage/intake",
        json={
            "name": "张阿姨",
            "age": 67,
            "gender": "female",
            "chronic_conditions": ["高血压"],
            "allergies": [],
            "medications": ["氨氯地平"],
            "chief_complaint": "胸痛并伴有呼吸困难",
            "symptoms": ["胸痛", "呼吸困难"],
            "duration": "2小时",
            "severity": "严重",
            "companions": ["出汗"],
        },
    )
    assert response.status_code == 200
    triage_id = response.json()["triage_id"]

    result = client.get(f"/triage/{triage_id}/result")
    assert result.status_code == 200
    payload = result.json()
    assert payload["recommended_department"] == "急诊医学科"
    assert payload["urgency"] == "立即急诊"
    assert payload["emergency"] is True
    assert "胸痛" in payload["risk_flags"]

    recommendations = client.get(
        "/booking/recommendations",
        params={"triage_id": triage_id, "department": payload["recommended_department"]},
    )
    assert recommendations.status_code == 200
    items = recommendations.json()["items"]
    assert len(items) >= 1
    assert items[0]["department"] == "急诊医学科"


def test_triage_follow_up_returns_structured_department_recommendation():
    response = client.post(
        "/triage/intake",
        json={
            "name": "李同学",
            "age": 21,
            "gender": "male",
            "chronic_conditions": [],
            "allergies": [],
            "medications": [],
            "chief_complaint": "发热咳嗽两天",
            "symptoms": ["发热", "咳嗽"],
            "duration": "2天",
            "severity": "中等",
            "companions": ["乏力"],
        },
    )
    triage_id = response.json()["triage_id"]

    next_response = client.post(
        f"/triage/{triage_id}/next",
        json={"answer": "有少量黄痰，没有胸痛，也没有呼吸困难"},
    )
    assert next_response.status_code == 200
    assert next_response.json()["status"] == "answered"

    result = client.get(f"/triage/{triage_id}/result")
    payload = result.json()
    assert payload["recommended_department"] == "呼吸内科"
    assert payload["urgency"] == "24小时内就诊"
    assert payload["emergency"] is False
    assert payload["confidence"] >= 0.7


def test_dual_triage_result_includes_fastchat_validation_panel(monkeypatch: pytest.MonkeyPatch):
    deepseek_result = {
        "recommended_department": "呼吸内科",
        "urgency": "24小时内就诊",
        "confidence": 0.88,
        "explanation": "DeepSeek 建议优先呼吸内科。",
        "emergency": False,
        "risk_flags": [],
        "suggested_hospital_type": "综合医院",
        "disclaimer": "仅供辅助参考，以医生判断为准。",
    }
    fastchat_result = {
        "recommended_department": "全科医学科",
        "urgency": "建议近三天内就诊",
        "confidence": 0.74,
        "explanation": "FastChat 建议先由全科接诊。",
        "emergency": False,
        "risk_flags": [],
        "suggested_hospital_type": "社区医疗中心",
        "disclaimer": "仅供辅助参考，以医生判断为准。",
    }

    monkeypatch.setattr(
        "app.services.settings",
        SimpleNamespace(
            triage_mode="deepseek",
            triage_provider="deepseek",
            triage_api_key="deepseek-key",
            triage_model="deepseek-v4-pro",
            triage_base_url="https://api.deepseek.com",
            triage_reasoning_effort="high",
            triage_thinking_mode="disabled",
            triage_secondary_provider="fastchat",
            triage_secondary_api_key="",
            triage_secondary_model="vicuna-13b",
            triage_secondary_base_url="http://127.0.0.1:8000/v1",
            triage_secondary_reasoning_effort="high",
            triage_secondary_thinking_mode="disabled",
            triage_url="",
        ),
    )
    monkeypatch.setattr(
        "app.services.request_deepseek_triage",
        lambda *args, **kwargs: generate_triage_result.__globals__["TriageResult"](**deepseek_result),
    )
    monkeypatch.setattr(
        "app.services.request_openai_compatible_triage",
        lambda *args, **kwargs: generate_triage_result.__globals__["TriageResult"](**fastchat_result),
    )

    result = generate_triage_result(
        {
            "age": 28,
            "gender": "female",
            "chronic_conditions": [],
            "allergies": [],
            "medications": [],
            "chief_complaint": "咳嗽低热",
            "symptoms": ["咳嗽", "低热"],
            "duration": "3天",
            "severity": "中等",
            "companions": ["咽痛"],
            "answers": [],
        }
    )

    assert result.recommended_department == "呼吸内科"
    assert len(result.validation_results) == 2
    assert result.validation_results[0].source == "deepseek"
    assert result.validation_results[1].source == "fastchat"
    assert result.validation_results[1].result.recommended_department == "全科医学科"
    assert result.disagreement_note is not None


def test_primary_fastchat_can_fallback_to_deepseek_review(monkeypatch: pytest.MonkeyPatch):
    deepseek_result = {
        "recommended_department": "全科医学科",
        "urgency": "建议近三天内就诊",
        "confidence": 0.8,
        "explanation": "DeepSeek 复核建议先由全科接诊。",
        "emergency": False,
        "risk_flags": [],
        "suggested_hospital_type": "社区医疗中心",
        "disclaimer": "仅供辅助参考，以医生判断为准。",
    }

    monkeypatch.setattr(
        "app.services.settings",
        SimpleNamespace(
            triage_mode="fastchat",
            triage_provider="fastchat",
            triage_api_key="",
            triage_model="vicuna-13b",
            triage_base_url="http://127.0.0.1:8000/v1",
            triage_reasoning_effort="high",
            triage_thinking_mode="disabled",
            triage_secondary_provider="deepseek",
            triage_secondary_api_key="deepseek-key",
            triage_secondary_model="deepseek-v4-pro",
            triage_secondary_base_url="https://api.deepseek.com",
            triage_secondary_reasoning_effort="high",
            triage_secondary_thinking_mode="disabled",
            triage_url="",
        ),
    )
    monkeypatch.setattr(
        "app.services.request_openai_compatible_triage",
        lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("fastchat offline")),
    )
    monkeypatch.setattr(
        "app.services.request_deepseek_triage",
        lambda *args, **kwargs: generate_triage_result.__globals__["TriageResult"](**deepseek_result),
    )

    result = generate_triage_result(
        {
            "age": 28,
            "gender": "female",
            "chronic_conditions": [],
            "allergies": [],
            "medications": [],
            "chief_complaint": "咳嗽低热",
            "symptoms": ["咳嗽", "低热"],
            "duration": "3天",
            "severity": "中等",
            "companions": ["咽痛"],
            "answers": [],
        }
    )

    assert result.recommended_department == "全科医学科"
    assert result.validation_results[0].source == "fastchat"
    assert result.validation_results[0].status == "unavailable"
    assert result.validation_results[1].source == "deepseek"
    assert "自动切换" in (result.consensus_summary or "")


def test_booking_recommendations_are_sorted_by_weighted_score():
    triage = client.post(
        "/triage/intake",
        json={
            "name": "王先生",
            "age": 46,
            "gender": "male",
            "chronic_conditions": ["糖尿病"],
            "allergies": [],
            "medications": [],
            "chief_complaint": "反复胃痛伴反酸",
            "symptoms": ["胃痛", "反酸"],
            "duration": "3周",
            "severity": "中等",
            "companions": ["餐后加重"],
        },
    ).json()

    result = client.get(f"/triage/{triage['triage_id']}/result").json()
    response = client.get(
        "/booking/recommendations",
        params={"triage_id": triage["triage_id"], "department": result["recommended_department"]},
    )
    assert response.status_code == 200
    recommendations = response.json()["items"]
    assert len(recommendations) >= 3
    assert recommendations[0]["score"] >= recommendations[1]["score"] >= recommendations[2]["score"]
    assert recommendations[0]["department"] == result["recommended_department"]
    assert recommendations[0]["ai_reason"]


def test_booking_recommendations_fallback_when_department_has_no_direct_slots():
    triage = client.post(
        "/triage/intake",
        json={
            "name": "钱女士",
            "age": 34,
            "gender": "female",
            "chronic_conditions": [],
            "allergies": [],
            "medications": [],
            "chief_complaint": "耳痛伴听力下降",
            "symptoms": ["耳痛", "听力下降"],
            "duration": "1天",
            "severity": "中等",
            "companions": [],
        },
    ).json()

    response = client.get(
        "/booking/recommendations",
        params={"triage_id": triage["triage_id"], "department": "耳鼻喉科"},
    )

    assert response.status_code == 200
    recommendations = response.json()["items"]
    assert recommendations
    assert recommendations[0]["department"] == "耳鼻喉科"
    assert recommendations[0]["ai_reason"]
    assert any("兜底" in item["label"] or "全科" in item["doctor_name"] for item in recommendations)


def test_doctor_note_generates_plain_language_advice_and_reminders():
    triage = client.post(
        "/triage/intake",
        json={
            "name": "赵奶奶",
            "age": 73,
            "gender": "female",
            "chronic_conditions": ["高血压"],
            "allergies": ["青霉素"],
            "medications": ["厄贝沙坦"],
            "chief_complaint": "头晕伴血压波动",
            "symptoms": ["头晕", "血压升高"],
            "duration": "1周",
            "severity": "中等",
            "companions": ["睡眠差"],
        },
    ).json()
    triage_result = client.get(f"/triage/{triage['triage_id']}/result").json()
    booking = client.post(
        "/booking/appointments",
        json={
            "triage_id": triage["triage_id"],
            "hospital_id": "hosp-001",
            "department": triage_result["recommended_department"],
            "doctor_name": "陈医生",
            "slot": "2026-06-12 09:00",
        },
    ).json()

    note = client.post(
        f"/encounters/{booking['encounter_id']}/doctor-note",
        json={
            "diagnosis_summary": "原发性高血压，近期控制欠佳",
            "medications": [
                {
                    "name": "氨氯地平片",
                    "dose": "5mg",
                    "frequency": "每日1次",
                    "duration_days": 14,
                    "instruction": "早餐后服用",
                }
            ],
            "doctor_advice": "低盐饮食，监测晨起血压，如头痛胸闷加重及时就诊。",
            "follow_up_date": "2026-06-19",
        },
    )
    assert note.status_code == 200

    advice = client.post(f"/encounters/{booking['encounter_id']}/patient-advice")
    assert advice.status_code == 200
    payload = advice.json()
    assert "每天 1 次" in payload["plain_language_advice"]
    assert payload["reminders"][0]["kind"] == "medication"
    assert payload["reminders"][-1]["kind"] == "follow_up"
    assert payload["advice_generation_mode"] in {"ai", "fallback"}


def test_reminder_completion_and_followup_feedback_escalate_status():
    triage = client.post(
        "/triage/intake",
        json={
            "name": "孙先生",
            "age": 58,
            "gender": "male",
            "chronic_conditions": ["高血压"],
            "allergies": [],
            "medications": [],
            "chief_complaint": "咳嗽",
            "symptoms": ["咳嗽"],
            "duration": "5天",
            "severity": "轻",
            "companions": [],
        },
    ).json()
    triage_result = client.get(f"/triage/{triage['triage_id']}/result").json()
    booking = client.post(
        "/booking/appointments",
        json={
            "triage_id": triage["triage_id"],
            "hospital_id": "hosp-002",
            "department": triage_result["recommended_department"],
            "doctor_name": "王医生",
            "slot": "2026-06-12 10:30",
        },
    ).json()
    client.post(
        f"/encounters/{booking['encounter_id']}/doctor-note",
        json={
            "diagnosis_summary": "上呼吸道感染",
            "medications": [
                {
                    "name": "右美沙芬片",
                    "dose": "15mg",
                    "frequency": "每日3次",
                    "duration_days": 5,
                    "instruction": "饭后服用",
                }
            ],
            "doctor_advice": "多喝温水，注意休息。",
            "follow_up_date": "2026-06-16",
        },
    )
    advice = client.post(f"/encounters/{booking['encounter_id']}/patient-advice").json()
    reminder_id = advice["reminders"][0]["id"]

    completion = client.post(f"/reminders/{reminder_id}/complete", json={"status": "missed"})
    assert completion.status_code == 200
    assert completion.json()["status"] == "missed"

    followup = client.post(
        "/followup/feedback",
        json={
            "encounter_id": booking["encounter_id"],
            "reminder_id": reminder_id,
            "medication_status": "missed",
            "symptom_status": "worse",
            "note": "咳嗽更重了，夜里睡不着。",
        },
    )
    assert followup.status_code == 200
    assert followup.json()["care_status"] == "needs_manual_followup"
    assert followup.json()["ai_summary"]
    assert followup.json()["next_step"]


def test_doctor_can_reply_after_patient_followup_feedback():
    triage = client.post(
        "/triage/intake",
        json={
            "name": "吴女士",
            "age": 41,
            "gender": "female",
            "chronic_conditions": [],
            "allergies": [],
            "medications": [],
            "chief_complaint": "咳嗽咽痛",
            "symptoms": ["咳嗽", "咽痛"],
            "duration": "4天",
            "severity": "中等",
            "companions": [],
        },
    ).json()
    triage_result = client.get(f"/triage/{triage['triage_id']}/result").json()
    booking = client.post(
        "/booking/appointments",
        json={
            "triage_id": triage["triage_id"],
            "hospital_id": "hosp-002",
            "department": triage_result["recommended_department"],
            "doctor_name": "周医生",
            "slot": "2026-06-12 10:30",
        },
    ).json()
    client.post(
        f"/encounters/{booking['encounter_id']}/doctor-note",
        json={
            "diagnosis_summary": "上呼吸道感染可能",
            "medications": [
                {
                    "name": "右美沙芬片",
                    "dose": "15mg",
                    "frequency": "每日3次",
                    "duration_days": 5,
                    "instruction": "饭后服用",
                }
            ],
            "doctor_advice": "多喝水，注意休息。",
            "follow_up_date": "2026-06-16",
        },
    )
    advice = client.post(f"/encounters/{booking['encounter_id']}/patient-advice").json()
    reminder_id = advice["reminders"][0]["id"]
    followup = client.post(
        "/followup/feedback",
        json={
            "encounter_id": booking["encounter_id"],
            "reminder_id": reminder_id,
            "medication_status": "done",
            "symptom_status": "same",
            "note": "咳嗽还是明显，晚上睡眠一般。",
        },
    ).json()

    reply = client.post(
        f"/followup/{booking['encounter_id']}/doctor-reply",
        json={"message": "继续按原方案服药，若明晚仍影响睡眠，请提前复诊。"},
    )

    assert reply.status_code == 200
    payload = reply.json()
    assert payload["encounter_id"] == booking["encounter_id"]
    assert payload["doctor_reply"]["message"] == "继续按原方案服药，若明晚仍影响睡眠，请提前复诊。"
    assert payload["note"] == followup["note"]


def test_deepseek_triage_parses_openai_compatible_json_response(monkeypatch: pytest.MonkeyPatch):
    captured = {}

    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "choices": [
                    {
                        "message": {
                            "content": """
                            {
                              "recommended_department": "呼吸内科",
                              "urgency": "24小时内就诊",
                              "confidence": 0.91,
                              "explanation": "结合发热和咳嗽，建议先到呼吸内科评估。",
                              "emergency": false,
                              "risk_flags": [],
                              "suggested_hospital_type": "综合医院或社区专科门诊",
                              "disclaimer": "仅供辅助参考，以医生判断为准。"
                            }
                            """
                        }
                    }
                ]
            }

    class FakeClient:
        def __init__(self, timeout: float):
            captured["timeout"] = timeout

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def post(self, url: str, json: dict, headers: dict):
            captured["url"] = url
            captured["json"] = json
            captured["headers"] = headers
            return FakeResponse()

    monkeypatch.setattr("app.services.httpx.Client", FakeClient)

    result = request_deepseek_triage(
        {
            "age": 32,
            "gender": "female",
            "chronic_conditions": ["高血压"],
            "allergies": ["青霉素"],
            "medications": [],
            "chief_complaint": "发热咳嗽两天",
            "symptoms": ["发热", "咳嗽"],
            "duration": "2天",
            "severity": "中等",
            "companions": ["乏力"],
            "answers": [],
        },
        api_key="test-key",
        model="deepseek-v4-pro",
        base_url="https://api.deepseek.com",
    )

    assert captured["url"] == "https://api.deepseek.com/chat/completions"
    assert captured["headers"]["Authorization"] == "Bearer test-key"
    assert captured["json"]["model"] == "deepseek-v4-pro"
    assert captured["json"]["response_format"] == {"type": "json_object"}
    assert result.recommended_department == "呼吸内科"
    assert result.disclaimer == "仅供辅助参考，以医生判断为准。"


def test_fastchat_triage_uses_openai_compatible_gateway(monkeypatch: pytest.MonkeyPatch):
    captured = {}

    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "choices": [
                    {
                        "message": {
                            "content": """
                            {
                              "recommended_department": "全科医学科",
                              "urgency": "建议近三天内就诊",
                              "confidence": 0.74,
                              "explanation": "FastChat 网关建议先由全科接诊。",
                              "emergency": false,
                              "risk_flags": [],
                              "suggested_hospital_type": "社区医疗中心",
                              "disclaimer": "仅供辅助参考，以医生判断为准。"
                            }Human: extra trailing text
                            """
                        }
                    }
                ]
            }

    class FakeClient:
        def __init__(self, timeout: float):
            captured["timeout"] = timeout

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def post(self, url: str, json: dict, headers: dict):
            captured["url"] = url
            captured["json"] = json
            captured["headers"] = headers
            return FakeResponse()

    monkeypatch.setattr("app.services.httpx.Client", FakeClient)
    monkeypatch.setattr(
        "app.services.settings",
        SimpleNamespace(
            triage_mode="gateway",
            triage_provider="fastchat",
            triage_url="",
            triage_api_key="",
            triage_model="vicuna-13b",
            triage_base_url="http://127.0.0.1:8000/v1",
            triage_reasoning_effort="high",
            triage_thinking_mode="disabled",
        ),
    )

    result = generate_triage_result(
        {
            "age": 28,
            "gender": "female",
            "chronic_conditions": [],
            "allergies": [],
            "medications": [],
            "chief_complaint": "嗓子不舒服",
            "symptoms": ["咽痛"],
            "duration": "2天",
            "severity": "轻",
            "companions": [],
            "answers": [],
        }
    )

    assert captured["url"] == "http://127.0.0.1:8000/v1/chat/completions"
    assert captured["json"]["model"] == "vicuna-13b"
    assert "response_format" not in captured["json"]
    assert result.recommended_department == "全科医学科"


def test_kimi_triage_uses_moonshot_api_without_deepseek_extensions(monkeypatch: pytest.MonkeyPatch):
    captured = {}

    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "choices": [
                    {
                        "message": {
                            "content": """
                            {
                              "recommended_department": "呼吸内科",
                              "urgency": "24小时内就诊",
                              "confidence": 0.82,
                              "explanation": "Kimi 建议先到呼吸内科评估。",
                              "emergency": false,
                              "risk_flags": [],
                              "suggested_hospital_type": "综合医院或社区专科门诊",
                              "disclaimer": "仅供辅助参考，以医生判断为准。"
                            }
                            """
                        }
                    }
                ]
            }

    class FakeClient:
        def __init__(self, timeout: float):
            captured["timeout"] = timeout

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def post(self, url: str, json: dict, headers: dict):
            captured["url"] = url
            captured["json"] = json
            captured["headers"] = headers
            return FakeResponse()

    monkeypatch.setattr("app.services.httpx.Client", FakeClient)

    result = request_deepseek_triage.__globals__["request_kimi_triage"](
        {
            "age": 28,
            "gender": "female",
            "chronic_conditions": [],
            "allergies": [],
            "medications": [],
            "chief_complaint": "发热咳嗽两天",
            "symptoms": ["发热", "咳嗽"],
            "duration": "2天",
            "severity": "中等",
            "companions": ["咽痛"],
            "answers": [],
        },
        api_key="kimi-key",
        model="kimi-k2.6",
        base_url="https://api.moonshot.cn/v1",
    )

    assert captured["url"] == "https://api.moonshot.cn/v1/chat/completions"
    assert captured["headers"]["Authorization"] == "Bearer kimi-key"
    assert captured["json"]["model"] == "kimi-k2.6"
    assert "response_format" not in captured["json"]
    assert "reasoning_effort" not in captured["json"]
    assert "thinking" not in captured["json"]
    assert result.recommended_department == "呼吸内科"


def test_local_fastchat_non_json_output_stays_available_with_rule_structuring(monkeypatch: pytest.MonkeyPatch):
    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {"choices": [{"message": {"content": "建议先看呼吸内科，但我没有输出 JSON。"}}]}

    class FakeClient:
        def __init__(self, timeout: float):
            self.timeout = timeout

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def post(self, url: str, json: dict, headers: dict):
            return FakeResponse()

    monkeypatch.setattr("app.services.httpx.Client", FakeClient)
    monkeypatch.setattr(
        "app.services.settings",
        SimpleNamespace(
            triage_mode="fastchat",
            triage_provider="fastchat",
            triage_api_key="",
            triage_model="vicuna-13b",
            triage_base_url="http://127.0.0.1:8001/v1",
            triage_reasoning_effort="high",
            triage_thinking_mode="disabled",
            triage_secondary_provider="",
            triage_url="",
        ),
    )

    result = generate_triage_result(
        {
            "age": 28,
            "gender": "female",
            "chronic_conditions": [],
            "allergies": [],
            "medications": [],
            "chief_complaint": "发热咳嗽两天",
            "symptoms": ["发热", "咳嗽"],
            "duration": "2天",
            "severity": "中等",
            "companions": ["乏力"],
            "answers": [],
        }
    )

    assert result.validation_results[0].source == "fastchat"
    assert result.validation_results[0].status == "available"
    assert result.recommended_department == "呼吸内科"
    assert "FastChat 网关已连通" in result.explanation


def test_fastchat_triage_uses_rule_safety_rail_for_generic_or_incomplete_json(monkeypatch: pytest.MonkeyPatch):
    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "choices": [
                    {
                        "message": {
                            "content": """
                            {"recommended_department":"内科","urgency":"立即急诊","confidence":0.9,"emergency":true,"risk_flags":["发热","咳嗽"],"suggested_hospital_type":"急诊医学科","disclaimer":"仅供辅助参考，以医生判断为准。"}Human: trailing
                            """
                        }
                    }
                ]
            }

    class FakeClient:
        def __init__(self, timeout: float):
            self.timeout = timeout

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def post(self, url: str, json: dict, headers: dict):
            return FakeResponse()

    monkeypatch.setattr("app.services.httpx.Client", FakeClient)

    result = request_deepseek_triage.__globals__["request_openai_compatible_triage"](
        {
            "age": 21,
            "gender": "male",
            "chronic_conditions": [],
            "allergies": [],
            "medications": [],
            "chief_complaint": "发热咳嗽两天",
            "symptoms": ["发热", "咳嗽"],
            "duration": "2天",
            "severity": "中等",
            "companions": ["乏力"],
            "answers": [],
        },
        api_key="",
        model="vicuna-13b",
        base_url="http://127.0.0.1:8000/v1",
    )

    assert result.recommended_department == "呼吸内科"
    assert result.emergency is False
    assert result.explanation


def test_easyappointments_live_provider_books_remote_slot(monkeypatch: pytest.MonkeyPatch):
    recorded_posts: list[tuple[str, dict]] = []

    class FakeResponse:
        def __init__(self, payload: object):
            self.payload = payload

        def raise_for_status(self):
            return None

        def json(self):
            return self.payload

    class FakeClient:
        def __init__(self, timeout: float, headers: dict, **kwargs):
            self.timeout = timeout
            self.headers = headers

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def get(self, url: str, params: dict | None = None):
            if url.endswith("/services"):
                return FakeResponse([{"id": 7, "name": "呼吸内科", "duration": 30, "location": "门诊 A"}])
            if url.endswith("/providers"):
                return FakeResponse([{"id": 3, "firstName": "明", "lastName": "周", "services": [7]}])
            if url.endswith("/availabilities"):
                return FakeResponse(["09:30"])
            if url.endswith("/services/7"):
                return FakeResponse({"id": 7, "duration": 30, "location": "门诊 A"})
            raise AssertionError(f"unexpected GET {url}")

        def post(self, url: str, json: dict):
            recorded_posts.append((url, json))
            if url.endswith("/customers"):
                return FakeResponse({"id": 12})
            if url.endswith("/appointments"):
                return FakeResponse({"id": 99})
            raise AssertionError(f"unexpected POST {url}")

    monkeypatch.setattr("app.adapters.httpx.Client", FakeClient)
    monkeypatch.setattr(
        "app.adapters.settings",
        SimpleNamespace(
            booking_provider="easyappointments",
            booking_base_url="https://ea.example/index.php/api/v1",
            booking_api_key="",
            booking_username="demo",
            booking_password="secret",
            clinical_provider="memory",
            triage_provider="",
            triage_mode="mock",
            triage_model="",
        ),
    )

    triage = client.post(
        "/triage/intake",
        json={
            "name": "李同学",
            "age": 21,
            "gender": "male",
            "chronic_conditions": [],
            "allergies": [],
            "medications": [],
            "chief_complaint": "发热咳嗽两天",
            "symptoms": ["发热", "咳嗽"],
            "duration": "2天",
            "severity": "中等",
            "companions": ["乏力"],
        },
    ).json()
    result = client.get(f"/triage/{triage['triage_id']}/result").json()
    recommendations = client.get(
        "/booking/recommendations",
        params={"triage_id": triage["triage_id"], "department": result["recommended_department"]},
    ).json()["items"]

    booking = client.post(
        "/booking/appointments",
        json={
            "triage_id": triage["triage_id"],
            "hospital_id": recommendations[0]["hospital_id"],
            "department": recommendations[0]["department"],
            "doctor_name": recommendations[0]["doctor_name"],
            "slot": recommendations[0]["slot"],
        },
    )

    assert booking.status_code == 200
    payload = booking.json()
    assert payload["integration"]["provider"] == "easyappointments"
    assert payload["integration"]["external_id"] == 99
    assert recorded_posts[0][0].endswith("/customers")
    assert recorded_posts[1][0].endswith("/appointments")


def test_easyappointments_provider_falls_back_when_department_query_has_no_exact_match(monkeypatch: pytest.MonkeyPatch):
    requests_seen: list[tuple[str, dict | None]] = []

    class FakeResponse:
        def __init__(self, payload: object):
            self.payload = payload

        def raise_for_status(self):
            return None

        def json(self):
            return self.payload

    class FakeClient:
        def __init__(self, timeout: float, headers: dict, **kwargs):
            self.timeout = timeout
            self.headers = headers

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def get(self, url: str, params: dict | None = None):
            requests_seen.append((url, params))
            if url.endswith("/services") and params == {"q": "呼吸内科"}:
                return FakeResponse([])
            if url.endswith("/services") and params is None:
                return FakeResponse([{"id": 7, "name": "General Service", "duration": 30, "location": "门诊 A"}])
            if url.endswith("/providers"):
                return FakeResponse([{"id": 3, "firstName": "明", "lastName": "周", "services": [7]}])
            if url.endswith("/availabilities"):
                return FakeResponse(["09:30"])
            raise AssertionError(f"unexpected GET {url}")

    monkeypatch.setattr("app.adapters.httpx.Client", FakeClient)
    monkeypatch.setattr(
        "app.adapters.settings",
        SimpleNamespace(
            booking_provider="easyappointments",
            booking_base_url="https://ea.example/index.php/api/v1",
            booking_api_key="",
            booking_username="demo",
            booking_password="secret",
        ),
    )

    from app.adapters import EasyAppointmentsBookingProvider

    items = EasyAppointmentsBookingProvider().list_recommendations("呼吸内科")

    assert len(items) == 1
    assert items[0].department == "呼吸内科"
    assert requests_seen[0][1] == {"q": "呼吸内科"}
    assert requests_seen[1][1] is None


def test_easyappointments_provider_falls_back_to_local_when_remote_unavailable(monkeypatch: pytest.MonkeyPatch):
    class FakeClient:
        def __init__(self, timeout: float, headers: dict, **kwargs):
            self.timeout = timeout
            self.headers = headers

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def get(self, url: str, params: dict | None = None):
            raise httpx.ConnectError("remote unavailable")

    monkeypatch.setattr("app.adapters.httpx.Client", FakeClient)
    monkeypatch.setattr(
        "app.adapters.settings",
        SimpleNamespace(
            booking_provider="easyappointments",
            booking_base_url="https://ea.example/index.php/api/v1",
            booking_api_key="",
            booking_username="demo",
            booking_password="secret",
        ),
    )

    from app.adapters import EasyAppointmentsBookingProvider

    items = EasyAppointmentsBookingProvider().list_recommendations("呼吸内科")

    assert len(items) >= 1
    assert items[0].hospital_id.startswith("hosp-")


def test_openmrs_provider_builds_obs_payload_and_resolves_encounter_role(monkeypatch: pytest.MonkeyPatch):
    captured = {}

    class FakeResponse:
        def __init__(self, payload: object):
            self.payload = payload

        def raise_for_status(self):
            return None

        def json(self):
            return self.payload

    class FakeClient:
        def __init__(self, timeout: float, headers: dict, **kwargs):
            self.headers = headers

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def get(self, url: str, params: dict | None = None):
            assert url.endswith("/openmrs/ws/rest/v1/encounterrole")
            return FakeResponse({"results": [{"uuid": "role-uuid"}]})

        def post(self, url: str, json: dict):
            captured["url"] = url
            captured["json"] = json
            return FakeResponse({"uuid": "enc-openmrs-001"})

    monkeypatch.setattr("app.adapters.httpx.Client", FakeClient)
    monkeypatch.setattr(
        "app.adapters.settings",
        SimpleNamespace(
            clinical_base_url="https://openmrs.example.com",
            clinical_api_key="",
            clinical_username="admin",
            clinical_password="Admin123",
            openmrs_patient_uuid="patient-uuid",
            openmrs_provider_uuid="provider-uuid",
            openmrs_location_uuid="location-uuid",
            openmrs_encounter_type_uuid="encounter-type-uuid",
            openmrs_encounter_role_uuid="",
            openmrs_visit_uuid="visit-uuid",
            openmrs_summary_concept_uuid="summary-concept-uuid",
            openmrs_advice_concept_uuid="advice-concept-uuid",
            openmrs_medication_plan_concept_uuid="medication-concept-uuid",
        ),
    )

    provider = OpenMRSClinicalProvider()
    result = provider.sync_doctor_note(
        "enc-001",
        {
            "patient_name": "李同学",
            "diagnosis_summary": "上呼吸道感染",
            "doctor_advice": "多喝温水，注意休息。",
            "follow_up_date": "2026-06-19",
            "medications": [
                {
                    "name": "右美沙芬片",
                    "dose": "15mg",
                    "frequency": "每日3次",
                    "duration_days": 5,
                    "instruction": "饭后服用",
                }
            ],
        },
    )

    assert result["status"] == "synced"
    assert result["external_id"] == "enc-openmrs-001"
    assert captured["json"]["encounterProviders"][0]["encounterRole"] == "role-uuid"
    assert "orders" not in captured["json"]
    assert len(captured["json"]["obs"]) == 3
    assert not captured["json"]["encounterDatetime"].startswith("2026-06-19")


def test_medtimer_export_endpoint_returns_backup_json():
    triage = client.post(
        "/triage/intake",
        json={
            "name": "王同学",
            "age": 22,
            "gender": "female",
            "chronic_conditions": [],
            "allergies": [],
            "medications": [],
            "chief_complaint": "感冒咳嗽",
            "symptoms": ["咳嗽"],
            "duration": "3天",
            "severity": "轻",
            "companions": [],
        },
    ).json()
    triage_result = client.get(f"/triage/{triage['triage_id']}/result").json()
    booking = client.post(
        "/booking/appointments",
        json={
            "triage_id": triage["triage_id"],
            "hospital_id": "hosp-001",
            "department": triage_result["recommended_department"],
            "doctor_name": "王医生",
            "slot": "2026-06-12 10:00",
        },
    ).json()
    client.post(
        f"/encounters/{booking['encounter_id']}/doctor-note",
        json={
            "diagnosis_summary": "上呼吸道感染",
            "medications": [
                {
                    "name": "右美沙芬片",
                    "dose": "15mg",
                    "frequency": "每日3次",
                    "duration_days": 5,
                    "instruction": "饭后服用",
                }
            ],
            "doctor_advice": "多喝温水，注意休息。",
            "follow_up_date": "2026-06-16",
        },
    )
    client.post(f"/encounters/{booking['encounter_id']}/patient-advice")

    export_response = client.get(f"/reminders/export/medtimer/{booking['encounter_id']}")

    assert export_response.status_code == 200
    payload = export_response.json()
    assert "medicines" in payload
    assert "events" in payload
    assert payload["medicines"]["list"][0]["medicine"]["name"] == "右美沙芬片"
