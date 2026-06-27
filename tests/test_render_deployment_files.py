from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_render_deployment_files_are_present_and_safe() -> None:
    dockerfile_path = ROOT / "Dockerfile"
    dockerignore_path = ROOT / ".dockerignore"
    render_yaml_path = ROOT / "render.yaml"

    assert dockerfile_path.exists()
    assert dockerignore_path.exists()
    assert render_yaml_path.exists()

    dockerfile = dockerfile_path.read_text(encoding="utf-8")
    dockerignore = dockerignore_path.read_text(encoding="utf-8")
    render_yaml = render_yaml_path.read_text(encoding="utf-8")

    assert "npm run build" in dockerfile
    assert "uvicorn app.main:app" in dockerfile
    assert "backend/.env" in dockerignore
    assert ".streamlit/secrets.toml" in dockerignore
    assert "frontend/node_modules/" in dockerignore
    assert "runtime: docker" in render_yaml
    assert "AI_TRIAGE_API_KEY" in render_yaml
    assert "AI_TRIAGE_SECONDARY_API_KEY" in render_yaml
    assert "sync: false" in render_yaml
