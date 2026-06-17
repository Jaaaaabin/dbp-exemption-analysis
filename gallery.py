"""
Build a manifest of generated figures for gallery.html.

Scans res/figures/ for PNG files and writes a JSON manifest grouped by
subfolder, so the gallery stays in sync with the analysis scripts'
output without manual edits.

Run:
    uv run python gallery.py            # just (re)build the manifest
    uv run python gallery.py --serve    # build, serve over HTTP, open browser

The gallery uses fetch() for manifest.json, which browsers block on the
file:// protocol, so --serve is needed to actually view it.
"""
import argparse
import http.server
import json
import socketserver
import threading
import webbrowser
from datetime import datetime, timezone
from pathlib import Path

FIGURES_DIR = Path("res/figures")
MANIFEST_FILE = FIGURES_DIR / "manifest.json"

SECTION_TITLES = {
    "": "Overview (plot.py)",
    "scope": "Scope & Statistics (analyze_scope.py)",
    "exemption": "Exemption (analyze_exemption.py)",
    "decision_basis": "Decision Basis (analyze_decision_basis.py)",
    "both": "Both — Combined (analyze_both.py)",
    "items": "Items (plot.py)",
    "patterns": "Patterns (analyze_patterns.py)",
}
SECTION_ORDER = ["", "scope", "exemption", "decision_basis", "both", "items", "patterns"]

# Folders to leave out of the gallery manifest (figures still generated on disk).
SKIP_FOLDERS = {"items"}


def section_title(folder: str) -> str:
    if folder in SECTION_TITLES:
        return SECTION_TITLES[folder]
    return folder.replace("_", " ").title()


def build_manifest(verbose: bool = True) -> int:
    groups: dict[str, list[Path]] = {}
    for path in FIGURES_DIR.rglob("*.png"):
        folder = path.parent.relative_to(FIGURES_DIR).as_posix()
        if folder == ".":
            folder = ""
        if folder in SKIP_FOLDERS:
            continue
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
    if verbose:
        print(f"Saved {total} figures across {len(sections)} sections -> {MANIFEST_FILE}")
    return total


def serve(port: int, open_browser: bool):
    """Serve the project dir over HTTP so gallery.html can fetch the manifest."""
    manifest_rel = MANIFEST_FILE.as_posix()

    class GalleryHandler(http.server.SimpleHTTPRequestHandler):
        # Rebuild the manifest each time the browser requests it, so figures
        # added / removed / renamed while the server runs appear on the next
        # auto-refresh without re-running gallery.py.
        def do_GET(self):
            if self.path.split("?", 1)[0].lstrip("/") == manifest_rel:
                try:
                    build_manifest(verbose=False)
                except Exception as exc:  # never take the server down over this
                    self.log_error("manifest rebuild failed: %s", exc)
            return super().do_GET()

    handler = GalleryHandler

    class ReuseTCPServer(socketserver.TCPServer):
        allow_reuse_address = True

    with ReuseTCPServer(("127.0.0.1", port), handler) as httpd:
        url = f"http://127.0.0.1:{port}/gallery.html"
        print(f"Serving gallery at {url}  (Ctrl+C to stop)")
        if open_browser:
            threading.Timer(0.5, lambda: webbrowser.open(url)).start()
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nStopped.")


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--serve", action="store_true",
                        help="serve the gallery over HTTP after building the manifest")
    parser.add_argument("--port", type=int, default=8000,
                        help="port for --serve (default: 8000)")
    parser.add_argument("--no-open", action="store_true",
                        help="with --serve, do not open a browser automatically")
    args = parser.parse_args()

    build_manifest()
    if args.serve:
        serve(args.port, open_browser=not args.no_open)


if __name__ == "__main__":
    main()
