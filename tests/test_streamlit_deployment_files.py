from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_streamlit_deployment_files_are_present_and_safe() -> None:
    app_path = ROOT / "streamlit_app.py"
    requirements_path = ROOT / "requirements.txt"
    config_path = ROOT / ".streamlit" / "config.toml"
    gitignore = (ROOT / ".gitignore").read_text(encoding="utf-8")

    assert app_path.exists()
    assert requirements_path.exists()
    assert config_path.exists()
    assert "backend/.env" in gitignore
    assert ".streamlit/secrets.toml" in gitignore

    requirements = requirements_path.read_text(encoding="utf-8")
    assert "streamlit" in requirements
    assert "httpx" in requirements

    app_source = app_path.read_text(encoding="utf-8")
    assert "st.secrets" in app_source
    assert "generate_triage_result" in app_source
    assert "create_patient_advice" in app_source
