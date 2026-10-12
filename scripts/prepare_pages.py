"""Stage only the generated aggregate dashboard for Pages. No repository copy.

    python scripts/prepare_pages.py

The fixed output directory must contain only the two allowed regular files.
Unexpected entries and symlinks fail rather than being uploaded or deleted.
"""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import build_dashboard as dashboard  # noqa: E402

PUBLIC_FILES = frozenset({"index.html", ".nojekyll"})


def prepare(root: Path = ROOT) -> Path:
    html = dashboard.build()
    source = root / "docs" / "dashboard.html"
    if source.read_text(encoding="utf-8") != html:
        raise ValueError("Dashboard is stale; run scripts/build_dashboard.py before staging Pages")
    output = root / "build" / "pages"
    for directory in (output.parent, output):
        if directory.is_symlink() or (directory.exists() and not directory.is_dir()):
            raise ValueError("Pages output must use ordinary directories")
    if output.exists():
        if {entry.name for entry in output.iterdir()} - PUBLIC_FILES:
            raise ValueError("Unexpected Pages output entries; refusing to publish or remove them")
        for name in PUBLIC_FILES:
            target = output / name
            if target.is_symlink() or (target.exists() and not target.is_file()):
                raise ValueError("Pages outputs must be regular files")
    output.mkdir(parents=True, exist_ok=True)
    (output / "index.html").write_text(html, encoding="utf-8", newline="\n")
    (output / ".nojekyll").write_text("", encoding="utf-8")
    return output


if __name__ == "__main__":
    print(f"Prepared aggregate-only Pages artifact: {prepare()}")
