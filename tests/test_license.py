"""LICENSE stays the standard MIT text so GitHub detects it; the data note lives beside it."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_license_is_plain_mit_text():
    text = (ROOT / "LICENSE").read_text(encoding="utf-8")
    assert text.startswith("MIT License\n\nCopyright (c) 2026 Wenjie Luo\n")
    # Anything after the MIT text makes GitHub report the licence as NOASSERTION.
    assert text.rstrip("\n").endswith("OTHER DEALINGS IN THE\nSOFTWARE.")


def test_third_party_notice_kept_and_linked():
    notice = (ROOT / "THIRD_PARTY_NOTICES.md").read_text(encoding="utf-8")
    assert "App Store review texts belong to their authors" in notice
    assert "not redistributed here beyond short excerpts" in notice
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "(THIRD_PARTY_NOTICES.md)" in readme
    assert "(LICENSE)" in readme
