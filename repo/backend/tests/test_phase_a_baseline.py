import os
import shutil
import subprocess

import pytest
from fastapi.testclient import TestClient

if os.path.exists("./test_phase_a.db"):
    os.remove("./test_phase_a.db")

os.environ["DATABASE_URL"] = "sqlite:///./test_phase_a.db"
os.environ["JWT_SECRET"] = "test-secret"
os.environ["WHITELIST_ENCRYPTION_KEY"] = "MDEyMzQ1Njc4OUFCQ0RFRjAxMjM0NTY3ODlBQkNERUY="
os.environ["FEATURE_DUPLICATE_CHECK"] = "false"

from main import app  # noqa: E402
import auth  # noqa: E402
import models  # noqa: E402
from database import engine, SessionLocal  # noqa: E402

models.Base.metadata.create_all(bind=engine)
client = TestClient(app)


def _seed_system_admin():
    db = SessionLocal()
    try:
        if db.query(models.User).filter(models.User.username == "admin@test.com").first():
            return
        db.add(
            models.User(
                username="admin@test.com",
                password_hash=auth.get_password_hash("admin123"),
                role=models.RoleEnum.SystemAdmin,
            )
        )
        db.commit()
    finally:
        db.close()


def _admin_auth_headers():
    _seed_system_admin()
    login = client.post(
        "/login",
        data={"username": "admin@test.com", "password": "admin123"},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert login.status_code == 200
    return {"Authorization": f"Bearer {login.json()['access_token']}"}


def test_register_login_and_duplicate_interface_disabled():
    reg = client.post(
        "/register",
        json={"username": "applicant@test.com", "password": "secret123", "role": "Applicant"},
    )
    assert reg.status_code == 200

    login = client.post(
        "/login",
        data={"username": "applicant@test.com", "password": "secret123"},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert login.status_code == 200
    token = login.json()["access_token"]

    dup = client.post(
        "/materials/duplicate-check",
        json={"file_hash": "abc123"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert dup.status_code == 200
    assert dup.json()["enabled"] is False


def test_register_ignores_privileged_role():
    reg = client.post(
        "/register",
        json={"username": "escalate@test.com", "password": "secret123", "role": "SystemAdmin"},
    )
    assert reg.status_code == 200
    assert reg.json()["role"] == "Applicant"


def test_system_admin_user_management_block_unblock():
    _seed_system_admin()

    reg_user = client.post(
        "/register",
        json={"username": "reviewer@test.com", "password": "review123", "role": "Reviewer"},
    )
    assert reg_user.status_code == 200
    assert reg_user.json()["role"] == "Applicant"
    reviewer_id = reg_user.json()["id"]

    login_admin = client.post(
        "/login",
        data={"username": "admin@test.com", "password": "admin123"},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    token = login_admin.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    promote = client.put(
        f"/admin/users/{reviewer_id}",
        headers=headers,
        json={"username": "reviewer@test.com", "role": "Reviewer"},
    )
    assert promote.status_code == 200

    block = client.post(f"/admin/users/{reviewer_id}/block", headers=headers)
    assert block.status_code == 200
    assert block.json()["is_blocked"] == 1

    blocked_login = client.post(
        "/login",
        data={"username": "reviewer@test.com", "password": "review123"},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert blocked_login.status_code == 403

    unblock = client.post(f"/admin/users/{reviewer_id}/unblock", headers=headers)
    assert unblock.status_code == 200
    assert unblock.json()["is_blocked"] == 0


def test_metrics_calculate_alerts_approval_rate_when_below_threshold():
    headers = _admin_auth_headers()
    assert client.post("/admin/metrics/calculate", headers=headers).status_code == 200
    alerts = client.get("/admin/alerts", headers=headers).json()
    assert any(
        a["metric_name"] == "approval_rate" and "below" in a["message"].lower() for a in alerts
    )


def test_recovery_rejects_unsafe_file_name():
    headers = _admin_auth_headers()
    for bad in ("../passwd", "a/b.sql", "/etc/passwd"):
        r = client.post("/admin/recovery", data={"file_name": bad}, headers=headers)
        assert r.status_code == 400, bad


def test_applicant_cannot_access_admin_users():
    reg = client.post(
        "/register",
        json={"username": "plain@test.com", "password": "secret123"},
    )
    assert reg.status_code == 200
    login = client.post(
        "/login",
        data={"username": "plain@test.com", "password": "secret123"},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert login.status_code == 200
    token = login.json()["access_token"]
    r = client.get("/admin/users", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 403


def test_daily_backup_script_requires_database_url():
    if not shutil.which("bash"):
        pytest.skip("bash not available")
    script = os.path.join(os.path.dirname(__file__), "..", "scripts", "daily_backup.sh")
    env = {k: v for k, v in os.environ.items() if k != "DATABASE_URL"}
    result = subprocess.run(
        ["bash", script],
        capture_output=True,
        text=True,
        env=env,
        cwd=os.path.join(os.path.dirname(__file__), ".."),
    )
    combined = (result.stderr or "") + (result.stdout or "")
    if result.returncode != 0 and "DATABASE_URL" not in combined:
        if "execvpe" in combined or "No such file" in combined:
            pytest.skip("bash could not execute the script in this environment")
    assert result.returncode != 0
    assert "DATABASE_URL" in combined
