from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]


def test_all_deployment_entrypoints_disable_uvicorn_access_log():
    paths = (
        REPOSITORY_ROOT / "backend" / "Dockerfile",
        REPOSITORY_ROOT / "docker-compose.yml",
        REPOSITORY_ROOT / "render.yaml",
    )

    for path in paths:
        contents = path.read_text(encoding="utf-8")
        assert "uvicorn" in contents
        assert "--no-access-log" in contents


def test_nginx_safe_access_log_is_inherited_by_every_server_block():
    contents = (REPOSITORY_ROOT / "deploy" / "nginx-template.conf").read_text(
        encoding="utf-8"
    )

    first_server = contents.index("server {")
    safe_access_log = contents.index(
        "access_log /var/log/nginx/access.log timesheet_safe;"
    )
    assert "$timesheet_access_uri" in contents
    assert safe_access_log < first_server
