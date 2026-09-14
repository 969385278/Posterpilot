"""Download unmodified OFL fonts from a pinned Google Fonts revision."""
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps/api"))
from app.poster.font_catalog import FONTS, FONT_ROOT, bundled_font_name
from PIL import ImageFont


def fetch(url):
    with urlopen(Request(url, headers={"User-Agent": "PosterPilot-font-preparation"}), timeout=90) as response:
        return response.read()


def main():
    manifest_path = FONT_ROOT / "manifest.json"
    previous = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else None
    revision = previous["revision"] if previous else json.loads(fetch("https://api.github.com/repos/google/fonts/commits/main"))["sha"]
    entries = []
    for font_id, (filename, label, description) in FONTS.items():
        base = f"https://raw.githubusercontent.com/google/fonts/{revision}/ofl/{font_id}"
        directory = FONT_ROOT / font_id
        directory.mkdir(parents=True, exist_ok=True)
        records = []
        for name in ("OFL.txt", "METADATA.pb", filename):
            path = directory / name
            data = path.read_bytes() if path.exists() else fetch(f"{base}/{name}")
            if name == "OFL.txt" and b"SIL OPEN FONT LICENSE Version 1.1" not in data:
                raise ValueError(f"Unexpected license: {font_id}")
            old = next((entry for entry in previous["fonts"] if entry["id"] == font_id), None) if previous else None
            old_file = next((record for record in old["files"] if record["name"] == name), None) if old else None
            digest = hashlib.sha256(data).hexdigest()
            if old_file and old_file["sha256"] != digest:
                raise ValueError(f"Existing font file differs from manifest: {path}")
            if not path.exists():
                path.write_bytes(data)
            records.append({"name": name, "source": f"{base}/{name}", "sha256": digest, "bytes": len(data)})
        ImageFont.truetype(str(directory / filename), 40)
        actual_name = bundled_font_name(directory / filename)
        entries.append({"id": font_id, "label": label, "description": description, "actual_name": actual_name,
                        "license": "OFL-1.1", "source": f"https://github.com/google/fonts/tree/{revision}/ofl/{font_id}", "files": records})
        print(f"Verified {font_id}: {actual_name}", flush=True)
    retrieved_at = previous["retrieved_at"] if previous else datetime.now(timezone.utc).isoformat()
    manifest_path.write_text(json.dumps({"revision": revision, "retrieved_at": retrieved_at, "fonts": entries}, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
