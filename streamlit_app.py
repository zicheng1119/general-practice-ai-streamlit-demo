from __future__ import annotations

import os
import sys
from pathlib import Path

import streamlit as st


ROOT = Path(__file__).resolve().parent
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))


def _seed_runtime_env() -> None:
    defaults = {
        "AI_TRIAGE_MODE": "deepseek",
        "AI_TRIAGE_PROVIDER": "deepseek",
        "AI_TRIAGE_MODEL": "deepseek-v4-pro",
        "AI_TRIAGE_BASE_URL": "https://api.deepseek.com",
        "AI_TRIAGE_REASONING_EFFORT": "high",
        "AI_TRIAGE_THINKING_MODE": "disabled",
        "AI_TRIAGE_SECONDARY_PROVIDER": "kimi",
        "AI_TRIAGE_SECONDARY_MODEL": "moonshot-v1-auto",
        "AI_TRIAGE_SECONDARY_BASE_URL": "https://api.moonshot.cn/v1",
        "AI_TRIAGE_SECONDARY_REASONING_EFFORT": "high",
        "AI_TRIAGE_SECONDARY_THINKING_MODE": "disabled",
        "BOOKING_PROVIDER": "mock",
        "CLINICAL_PROVIDER": "memory",
        "REMINDER_PROVIDER": "medtimer",
    }
    try:
        secrets = dict(st.secrets)
    except Exception:
        secrets = {}

    for key, value in defaults.items():
        os.environ.setdefault(key, value)
    for key in (
        "AI_TRIAGE_API_KEY",
        "AI_TRIAGE_SECONDARY_API_KEY",
        "BOOKING_PROVIDER",
        "BOOKING_BASE_URL",
        "BOOKING_API_KEY",
        "BOOKING_USERNAME",
        "BOOKING_PASSWORD",
        "CLINICAL_PROVIDER",
        "CLINICAL_BASE_URL",
        "CLINICAL_USERNAME",
        "CLINICAL_PASSWORD",
        "REMINDER_PROVIDER",
    ):
        if secrets.get(key):
            os.environ[key] = str(secrets[key])


_seed_runtime_env()

from app.adapters import get_booking_provider, get_integration_status, get_reminder_provider  # noqa: E402
from app.models import BookingCreateRequest, DoctorNoteRequest, MedicationInput  # noqa: E402
from app.services import (  # noqa: E402
    DISCLAIMER,
    create_patient_advice,
    enrich_booking_recommendations,
    generate_follow_up_question,
    generate_triage_result,
    serialize_doctor_note,
)
from app.store import store  # noqa: E402


st.set_page_config(
    page_title="全科智能就医闭环工作台",
    page_icon="🩺",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
    <style>
    .main .block-container { max-width: 1180px; padding-top: 2rem; }
    .metric-card {
        border: 1px solid #d6dee8;
        border-radius: 8px;
        padding: 14px 16px;
        background: #fbfcfd;
        min-height: 112px;
    }
    .metric-card span { color: #5a6b7c; font-size: 0.86rem; }
    .metric-card strong { display: block; margin-top: 4px; font-size: 1.02rem; color: #17212b; }
    .result-box {
        border-left: 4px solid #1e6f5c;
        background: #f4faf7;
        padding: 14px 16px;
        border-radius: 6px;
    }
    .warning-box {
        border-left: 4px solid #a13f2d;
        background: #fff7f4;
        padding: 14px 16px;
        border-radius: 6px;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


def _split_list(value: str) -> list[str]:
    return [item.strip() for item in value.replace("，", ",").split(",") if item.strip()]


def _ensure_state() -> None:
    defaults = {
        "triage_id": None,
        "triage_session": None,
        "triage_result": None,
        "recommendations": [],
        "booking": None,
        "doctor_note_saved": False,
        "patient_advice": None,
        "reminders": [],
        "feedback": None,
    }
    for key, value in defaults.items():
        st.session_state.setdefault(key, value)


def _render_status_cards() -> None:
    status = get_integration_status()
    cols = st.columns(4)
    for col, key, title in zip(
        cols,
        ("triage", "booking", "clinical", "reminder"),
        ("AI 分诊", "智能挂号", "临床记录", "提醒桥接"),
        strict=True,
    ):
        item = status[key]
        with col:
            st.markdown(
                f"""
                <div class="metric-card">
                    <span>{title}</span>
                    <strong>{item["label"]}</strong>
                    <span>{item["mode"]} · {"已配置" if item["configured"] else "待配置"}</span>
                </div>
                """,
                unsafe_allow_html=True,
            )


def _create_triage_session(payload: dict) -> None:
    triage_id = store.next_id("triage")
    payload["triage_id"] = triage_id
    payload["answers"] = []
    store.triage_sessions[triage_id] = payload
    result = generate_triage_result(payload)
    st.session_state.triage_id = triage_id
    st.session_state.triage_session = payload
    st.session_state.triage_result = result
    st.session_state.recommendations = []
    st.session_state.booking = None
    st.session_state.patient_advice = None
    st.session_state.reminders = []


def _render_triage_result() -> None:
    result = st.session_state.triage_result
    if not result:
        st.info("提交患者信息后，这里会展示 DeepSeek 主分诊与 Kimi 二路复核。")
        return

    box_class = "warning-box" if result.emergency else "result-box"
    st.markdown(
        f"""
        <div class="{box_class}">
            <strong>{result.recommended_department}</strong><br>
            {result.urgency} · 置信度 {result.confidence:.2f}<br>
            {result.explanation}
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.caption(result.consensus_summary or DISCLAIMER)

    validation_items = result.validation_results or []
    if validation_items:
        st.subheader("双路分诊复核")
        cols = st.columns(len(validation_items))
        for col, item in zip(cols, validation_items, strict=False):
            with col:
                status_icon = "✅" if item.status == "available" else "⚠️"
                st.markdown(f"**{status_icon} {item.label}**")
                st.caption(item.note or "")
                if item.result:
                    st.write(item.result.explanation)
                    st.caption(f"{item.result.recommended_department} · {item.result.urgency}")


def _render_recommendations() -> None:
    result = st.session_state.triage_result
    triage_id = st.session_state.triage_id
    if not result or not triage_id:
        st.info("完成分诊后会生成挂号推荐。")
        return

    if st.button("生成智能挂号推荐", use_container_width=True):
        items = get_booking_provider().list_recommendations(result.recommended_department)
        st.session_state.recommendations = [
            item.model_dump() for item in enrich_booking_recommendations(st.session_state.triage_session, items)
        ]

    recommendations = st.session_state.recommendations
    if not recommendations:
        return

    for index, item in enumerate(recommendations[:4]):
        with st.container(border=True):
            left, right = st.columns([3, 1])
            with left:
                st.markdown(f"**{item['hospital_name']} · {item['department']}**")
                st.write(f"{item['doctor_name']}｜{item['slot']}｜{item['distance_km']} km")
                st.caption(item.get("ai_reason") or item.get("label", ""))
            with right:
                if st.button("确认预约", key=f"book-{index}", use_container_width=True):
                    appointment_id = store.next_id("appt")
                    encounter_id = store.next_id("enc")
                    request = BookingCreateRequest(
                        triage_id=triage_id,
                        hospital_id=item["hospital_id"],
                        department=item["department"],
                        doctor_name=item["doctor_name"],
                        slot=item["slot"],
                    )
                    booking = get_booking_provider().create_booking(
                        request,
                        triage_id=triage_id,
                        appointment_id=appointment_id,
                        encounter_id=encounter_id,
                        triage_session=st.session_state.triage_session,
                    )
                    store.appointments[appointment_id] = booking
                    store.encounters[encounter_id] = {
                        "encounter_id": encounter_id,
                        "triage_id": triage_id,
                        "patient_name": st.session_state.triage_session["name"],
                    }
                    st.session_state.booking = booking
                    st.success("预约已确认")


def _render_doctor_note() -> None:
    booking = st.session_state.booking
    if not booking:
        st.info("确认预约后，医生端录入区域会激活。")
        return

    st.write(f"当前预约：{booking['hospital_name']} · {booking['department']} · {booking['doctor_name']}")
    with st.form("doctor-note-form"):
        diagnosis_summary = st.text_area("诊断摘要", "上呼吸道感染可能，建议对症治疗并观察体温变化。")
        medication_name = st.text_input("药物名称", "氨溴索片")
        medication_dose = st.text_input("剂量", "30mg")
        medication_frequency = st.text_input("频次", "每日3次")
        medication_days = st.number_input("用药天数", min_value=1, max_value=30, value=5)
        medication_instruction = st.text_input("用药说明", "饭后服用，多饮水")
        doctor_advice = st.text_area("医生医嘱", "清淡饮食，注意休息，如持续高热请及时复诊。")
        follow_up_date = st.date_input("复诊日期")
        submitted = st.form_submit_button("保存医嘱并生成患者提醒", use_container_width=True)

    if submitted:
        note = DoctorNoteRequest(
            diagnosis_summary=diagnosis_summary,
            medications=[
                MedicationInput(
                    name=medication_name,
                    dose=medication_dose,
                    frequency=medication_frequency,
                    duration_days=int(medication_days),
                    instruction=medication_instruction,
                )
            ],
            doctor_advice=doctor_advice,
            follow_up_date=follow_up_date.strftime("%Y-%m-%d"),
        )
        encounter_id = booking["encounter_id"]
        encounter = store.encounters[encounter_id] | serialize_doctor_note(note)
        store.encounters[encounter_id] = encounter
        advice = create_patient_advice(encounter_id, encounter)
        for reminder in advice.reminders:
            store.reminders[reminder.id] = reminder.model_dump()
        st.session_state.patient_advice = advice
        st.session_state.reminders = [reminder.model_dump() for reminder in advice.reminders]
        st.session_state.doctor_note_saved = True
        st.success("患者白话医嘱和提醒已生成")


def _render_patient_advice() -> None:
    advice = st.session_state.patient_advice
    if not advice:
        st.info("医生保存医嘱后，这里会生成患者可读版本和提醒。")
        return

    st.markdown("**白话医嘱**")
    st.write(advice.plain_language_advice)
    st.markdown("**生活建议**")
    for tip in advice.lifestyle_tips:
        st.write(f"- {tip}")

    st.markdown("**提醒任务**")
    reminders = st.session_state.reminders
    for reminder in reminders:
        st.checkbox(
            f"{reminder['title']}｜{reminder['due_at']}",
            value=reminder["status"] == "done",
            key=f"reminder-{reminder['id']}",
        )

    if st.session_state.booking:
        encounter_id = st.session_state.booking["encounter_id"]
        export_payload = get_reminder_provider().export_backup(
            store.encounters[encounter_id],
            reminders,
            store.feedback.get(encounter_id, []),
        )
        st.download_button(
            "下载 MedTimer 备份 JSON",
            data=str(export_payload).replace("'", '"'),
            file_name=f"MedTimer_Backup_{encounter_id}.json",
            mime="application/json",
            use_container_width=True,
        )


def main() -> None:
    _ensure_state()

    st.title("全科智能就医闭环工作台")
    st.caption("Streamlit Cloud 部署版：DeepSeek 主分诊 + Kimi 云端复核 + 本地演示挂号/医嘱/提醒闭环")
    _render_status_cards()

    with st.sidebar:
        st.header("演示控制")
        st.write("部署到 Streamlit Cloud 后，请在 Secrets 中配置 DeepSeek 和 Kimi API Key。")
        if st.button("清空当前演示", use_container_width=True):
            for key in list(st.session_state.keys()):
                del st.session_state[key]
            st.rerun()

    tab_patient, tab_booking, tab_doctor, tab_advice = st.tabs(
        ["1 患者录入与分诊", "2 智能挂号", "3 医生诊后录入", "4 患者提醒"]
    )

    with tab_patient:
        left, right = st.columns([1, 1])
        with left:
            with st.form("triage-form"):
                name = st.text_input("患者姓名", "李同学")
                age = st.number_input("年龄", min_value=0, max_value=120, value=28)
                gender_label = st.selectbox("性别", ["女", "男", "其他"])
                chief_complaint = st.text_area("主诉", "发热咳嗽两天")
                symptoms = st.text_input("症状标签", "发热,咳嗽")
                duration = st.text_input("病程", "2天")
                severity = st.selectbox("严重程度", ["轻", "中等", "严重"], index=1)
                companions = st.text_input("伴随症状", "咽痛")
                chronic_conditions = st.text_input("慢病史", "")
                allergies = st.text_input("过敏史", "")
                medications = st.text_input("正在用药", "")
                submitted = st.form_submit_button("提交并生成双路分诊", use_container_width=True)

            if submitted:
                gender_map = {"女": "female", "男": "male", "其他": "other"}
                _create_triage_session(
                    {
                        "name": name,
                        "age": int(age),
                        "gender": gender_map[gender_label],
                        "chronic_conditions": _split_list(chronic_conditions),
                        "allergies": _split_list(allergies),
                        "medications": _split_list(medications),
                        "chief_complaint": chief_complaint,
                        "symptoms": _split_list(symptoms),
                        "duration": duration,
                        "severity": severity,
                        "companions": _split_list(companions),
                    }
                )
                question = generate_follow_up_question(st.session_state.triage_session)
                st.success(f"已生成分诊。补充问题：{question}")

        with right:
            _render_triage_result()

    with tab_booking:
        _render_recommendations()

    with tab_doctor:
        _render_doctor_note()

    with tab_advice:
        _render_patient_advice()


if __name__ == "__main__":
    main()
