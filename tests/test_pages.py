"""The public artifact is isolated even when the checkout has private files."""
import importlib.util
import json
from pathlib import Path
import re

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("prepare_pages", ROOT / "scripts" / "prepare_pages.py")
pages = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pages)


@pytest.fixture
def checkout(tmp_path):
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "dashboard.html").write_text(pages.dashboard.build(), encoding="utf-8")
    for relative in ("data/raw/reviews.json", "data/work/private.log", ".venv/token", ".env"):
        target = tmp_path / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("PRIVATE_SENTINEL_DO_NOT_PUBLISH", encoding="utf-8")
    return tmp_path


def test_only_aggregate_dashboard_and_empty_marker_are_staged(checkout):
    output = pages.prepare(checkout)
    assert {entry.name for entry in output.iterdir()} == {"index.html", ".nojekyll"}
    html = (output / "index.html").read_text(encoding="utf-8")
    assert html == pages.dashboard.build()
    assert "PRIVATE_SENTINEL_DO_NOT_PUBLISH" not in html
    assert (output / ".nojekyll").read_bytes() == b""
    assert pages.prepare(checkout) == output  # repeated preparation is idempotent
    data = json.loads(re.search(r"const DATA = (.*);\n", html).group(1))
    forbidden = {"review_key", "review_id", "text_sha256", "text", "prompt", "response", "messages", "token"}
    def visit(value):
        if isinstance(value, dict):
            assert not forbidden.intersection(value)
            for child in value.values():
                visit(child)
        elif isinstance(value, list):
            for child in value:
                visit(child)
    visit(data)


def test_stale_dashboard_does_not_replace_existing_artifact(checkout):
    output = pages.prepare(checkout)
    before = (output / "index.html").read_bytes()
    (checkout / "docs" / "dashboard.html").write_text("stale", encoding="utf-8")
    with pytest.raises(ValueError, match="stale"):
        pages.prepare(checkout)
    assert (output / "index.html").read_bytes() == before


def test_unexpected_file_is_preserved_and_refuses_upload_preparation(checkout):
    output = pages.prepare(checkout)
    private = output / "private.log"
    private.write_text("PRIVATE_SENTINEL_DO_NOT_PUBLISH", encoding="utf-8")
    with pytest.raises(ValueError, match="Unexpected"):
        pages.prepare(checkout)
    assert private.read_text() == "PRIVATE_SENTINEL_DO_NOT_PUBLISH"


def test_allowed_filename_cannot_be_a_directory(checkout):
    output = checkout / "build" / "pages"
    (output / "index.html").mkdir(parents=True)
    with pytest.raises(ValueError, match="regular files"):
        pages.prepare(checkout)


@pytest.mark.parametrize("location", ["build", "build/pages", "build/pages/index.html"])
def test_symlinked_output_cannot_write_outside_artifact(checkout, tmp_path, location):
    target = tmp_path / "external"
    target.mkdir()
    link = checkout / location
    link.parent.mkdir(parents=True, exist_ok=True)
    try:
        link.symlink_to(target, target_is_directory=True)
    except OSError as error:
        pytest.skip(f"symlink creation is unavailable: {error}")
    with pytest.raises(ValueError, match="ordinary directories|regular files"):
        pages.prepare(checkout)
    assert list(target.iterdir()) == []


def test_dashboard_navigation_is_absolute_and_requests_no_external_assets():
    html = pages.dashboard.build()
    assert 'aria-label="Project evidence"' in html
    links = re.findall(r'<a href="([^"]+)"', html)
    assert len(links) == 3
    assert all(link.startswith("https://github.com/LUOaini1213/keeta-review-voc") for link in links)
    assert not re.search(r'<(?:script|link|img)[^>]+(?:src|href)=', html)


def test_workflow_cannot_publish_from_a_pr_or_upload_the_checkout():
    workflow = yaml.safe_load((ROOT / ".github" / "workflows" / "pages.yml").read_text())
    assert workflow["permissions"] == {"contents": "read"}
    build, deploy = (workflow["jobs"][key] for key in ("build", "deploy"))
    assert "permissions" not in build
    uploads = [step for step in build["steps"] if "upload-pages-artifact" in step.get("uses", "")]
    assert len(uploads) == 1 and uploads[0]["with"]["path"] == "build/pages"
    assert deploy["needs"] == "build"
    assert deploy["permissions"] == {"pages": "write", "id-token": "write"}
    condition = deploy["if"]
    assert condition.startswith("${{ ") and condition.endswith(" }}")
    assert set(condition[4:-3].split(" && ")) == {
        "github.event_name == 'workflow_dispatch'", "github.ref == 'refs/heads/main'",
        "inputs.publish", "vars.KEETA_PAGES_ENABLED == 'true'",
    }
    triggers = yaml.load((ROOT / ".github" / "workflows" / "pages.yml").read_text(), Loader=yaml.BaseLoader)["on"]
    assert triggers["workflow_dispatch"]["inputs"]["publish"]["default"] == "false"
    configure = next(step for step in deploy["steps"] if "configure-pages" in step.get("uses", ""))
    assert configure["with"]["enablement"] is False
