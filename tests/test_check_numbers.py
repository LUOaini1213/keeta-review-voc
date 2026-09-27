import importlib.util
import shutil
from pathlib import Path

import pytest

from keeta_voc.render import RenderError, literal_numbers, render

ROOT = Path(__file__).resolve().parents[1]


def _load_check():
    spec = importlib.util.spec_from_file_location("check_numbers", ROOT / "scripts" / "check_numbers.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_render_formats_and_lookup():
    ctx = {"a": {"n": 1234, "p": 0.4567, "ci": [0.1, 0.25], "lst": [5, 6]}}
    out = render("{{a.n|int}} {{a.p|pct0}} {{a.p|pct1}} {{a.p|f2}} {{a.ci|ci_pct0}} {{a.lst.1}}", ctx)
    assert out == "1,234 46% 45.7% 0.46 [10–25%] 6"
    assert render("{{ t:x }}".replace("t:", "table:"), {}, {"x": lambda: "|T|"}) == "|T|"
    with pytest.raises(RenderError):
        render("{{a.missing}}", ctx)
    with pytest.raises(RenderError):
        render("{{a.n|nope}}", ctx)


def test_literal_numbers_ignores_placeholders():
    t = "We saw {{m.n|int}} reviews over 12 months\n{{x.y}} and 3.5 stars"
    assert literal_numbers(t) == [(1, "12"), (2, "3.5")]


def test_committed_docs_match_results():
    cn = _load_check()
    assert cn.problems() == []


def _copy_repo_docs(tmp_path):
    for tmpl, doc in _load_check().DOCS:
        (tmp_path / tmpl).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(ROOT / tmpl, tmp_path / tmpl)
        shutil.copy(ROOT / doc, tmp_path / doc)


def test_tampered_number_in_doc_is_caught(tmp_path):
    cn = _load_check()
    _copy_repo_docs(tmp_path)
    assert cn.problems(tmp_path, cn.render_all()) == []
    report = tmp_path / "REPORT.md"
    text = report.read_text(encoding="utf-8")
    import re
    m = re.search(r"\d+%", text)
    assert m, "REPORT.md should contain at least one percentage"
    old = m.group(0)
    new = str(int(old[:-1]) + 1) + "%"
    report.write_text(text.replace(old, new, 1), encoding="utf-8")
    errs = cn.problems(tmp_path, cn.render_all())
    assert errs and "REPORT.md" in errs[0]


def test_hand_typed_number_in_template_is_caught(tmp_path):
    cn = _load_check()
    _copy_repo_docs(tmp_path)
    tmpl = tmp_path / cn.DOCS[0][0]
    tmpl.write_text(tmpl.read_text(encoding="utf-8") + "\nWe reviewed 4321 things.\n", encoding="utf-8")
    errs = cn.problems(tmp_path, cn.render_all())
    assert any("4321" in e for e in errs)
