"""
Build a manifest of generated figures for gallery.html.

Scans res/figures/ for PNG files and writes a JSON manifest grouped by
subfolder, so the gallery stays in sync with the analysis scripts'
output without manual edits.

Run:
    uv run python gallery.py
"""
import json
from datetime import datetime, timezone
from pathlib import Path

FIGURES_DIR = Path("res/figures")
MANIFEST_FILE = FIGURES_DIR / "manifest.json"

SECTION_TITLES = {
    "": "Overview (plot.py)",
    "exemption": "Exemption (analyze_exemption.py)",
    "decision_basis": "Decision Basis (analyze_decision_basis.py)",
    "both": "Both — Combined (analyze_both.py)",
    "items": "Items (plot.py)",
    "patterns": "Patterns (analyze_patterns.py)",
}
SECTION_ORDER = ["", "exemption", "decision_basis", "both", "items", "patterns"]


def section_title(folder: str) -> str:
    if folder in SECTION_TITLES:
        return SECTION_TITLES[folder]
    return folder.replace("_", " ").title()


def main():
    groups: dict[str, list[Path]] = {}
    for path in FIGURES_DIR.rglob("*.png"):
        folder = path.parent.relative_to(FIGURES_DIR).as_posix()
        if folder == ".":
            folder = ""
        groups.setdefault(folder, []).append(path)

    known = [folder for folder in SECTION_ORDER if folder in groups]
    extra = sorted(folder for folder in groups if folder not in SECTION_ORDER)

    sections = []
    for folder in known + extra:
        files = sorted(groups[folder], key=lambda p: p.name)
        sections.append({
            "title": section_title(folder),
            "files": [path.as_posix() for path in files],
        })

    manifest = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "sections": sections,
    }

    with open(MANIFEST_FILE, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)

    total = sum(len(section["files"]) for section in sections)
    print(f"Saved {total} figures across {len(sections)} sections -> {MANIFEST_FILE}")


if __name__ == "__main__":
    main()
