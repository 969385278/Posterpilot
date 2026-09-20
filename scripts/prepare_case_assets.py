"""Fetch public-domain AIC poster assets, retaining source evidence.

This does not curate cases: a separate visual review is required before a
catalog entry can be marked curated. Existing files are validated, not replaced.
"""
import argparse
import hashlib
import io
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.parse import urlencode

from PIL import Image

DEFAULT_IDS = [111986, 16907, 82287, 13598, 13606, 63622, 67166,
               29979, 183283, 218855, 218856, 218854]
COMMONS_IDS = [8886929, 41905046, 107429666, 106991594, 31793744,
               22408276, 24131151, 24204726, 31912550, 32018105,
               3645151, 46015465]
ROOT = Path(__file__).resolve().parents[1] / "data/knowledge/cases"
ALLOWED_LICENSES = {"Public domain", "CC0", "CC BY 4.0", "CC BY-SA 4.0", "CC BY 3.0", "CC BY-SA 3.0"}


def fetch(url: str) -> bytes:
    request = Request(url, headers={"User-Agent": "PosterPilot-Educational-CaseLibrary/1.0"})
    with urlopen(request, timeout=60) as response:
        return response.read()


def prepare(artwork_id: int, root: Path) -> dict:
    source_url = f"https://api.artic.edu/api/v1/artworks/{artwork_id}"
    metadata_path = root / "sources" / f"aic-{artwork_id}.json"
    if metadata_path.exists():
        record = json.loads(metadata_path.read_text(encoding="utf-8"))
    else:
        payload = json.loads(fetch(source_url))
        record = {"retrieved_at": datetime.now(timezone.utc).isoformat(),
                  "api_url": source_url, "response": payload}
    data = record["response"]["data"]
    if data.get("is_public_domain") is not True or not data.get("image_id"):
        raise ValueError(f"{artwork_id}: no confirmed public-domain image")
    image_url = (f"https://www.artic.edu/iiif/2/{data['image_id']}"
                 "/full/843,/0/default.jpg")
    image_path = root / "images" / f"aic-{artwork_id}.jpg"
    image_bytes = image_path.read_bytes() if image_path.exists() else fetch(image_url)
    with Image.open(io.BytesIO(image_bytes)) as image:
        image.verify()
    digest = hashlib.sha256(image_bytes).hexdigest()
    if record.get("image_sha256") not in (None, digest):
        raise ValueError(f"{artwork_id}: cached image hash mismatch")
    record.update(image_url=image_url, image_sha256=digest)
    for folder in (root / "sources", root / "images"):
        folder.mkdir(parents=True, exist_ok=True)
    if not image_path.exists():
        image_path.write_bytes(image_bytes)
    if not metadata_path.exists():
        metadata_path.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"id": artwork_id, "title": data["title"], "creator": data.get("artist_display"),
            "date": data.get("date_display"), "image": str(image_path), "sha256": digest}


def prepare_commons(ids: list[int], root: Path):
    for folder in (root / "sources", root / "images"):
        folder.mkdir(parents=True, exist_ok=True)
    missing = [item for item in ids if not (root / "sources" / f"commons-{item}.json").exists()]
    pages = {}
    if missing:
        url = "https://commons.wikimedia.org/w/api.php?" + urlencode({
            "action": "query", "pageids": "|".join(map(str, missing)),
            "prop": "imageinfo", "iiprop": "url|extmetadata|size",
            "iiurlwidth": 800, "format": "json",
        })
        pages = json.loads(fetch(url))["query"]["pages"]
    for item in ids:
        metadata_path = root / "sources" / f"commons-{item}.json"
        if metadata_path.exists():
            record = json.loads(metadata_path.read_text(encoding="utf-8"))
        else:
            page = pages[str(item)]
            info = page["imageinfo"][0]
            license_name = info["extmetadata"].get("LicenseShortName", {}).get("value")
            if license_name not in ALLOWED_LICENSES:
                raise ValueError(f"{item}: unsupported or unclear reuse license: {license_name}")
            record = {"retrieved_at": datetime.now(timezone.utc).isoformat(),
                      "api_url": url, "response": page,
                      "image_url": info.get("thumburl", info["url"])}
        license_name = record["response"]["imageinfo"][0]["extmetadata"].get("LicenseShortName", {}).get("value")
        if license_name not in ALLOWED_LICENSES:
            raise ValueError(f"{item}: unsupported cached license")
        path = root / "images" / record.get("image_asset", f"commons-{item}.jpg")
        content = path.read_bytes() if path.exists() else fetch(record["image_url"])
        with Image.open(io.BytesIO(content)) as image:
            extension = {"JPEG": "jpg", "PNG": "png"}.get(image.format)
            if extension is None:
                raise ValueError(f"{item}: unsupported image format: {image.format}")
            image.verify()
        asset_name = f"commons-{item}.{extension}"
        if not metadata_path.exists():
            record["image_asset"] = asset_name
            path = root / "images" / asset_name
        digest = hashlib.sha256(content).hexdigest()
        if record.get("image_sha256") not in (None, digest):
            raise ValueError(f"{item}: cached image hash mismatch")
        record["image_sha256"] = digest
        if not path.exists():
            path.write_bytes(content)
        if not metadata_path.exists():
            metadata_path.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps({"id": item, "title": record["response"]["title"], "image": str(path)}, ensure_ascii=False), flush=True)
        time.sleep(1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("ids", type=int, nargs="*", default=DEFAULT_IDS)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--commons", action="store_true", help="Use explicitly licensed Wikimedia Commons candidates; visual review is separate")
    args = parser.parse_args()
    if args.commons:
        prepare_commons(COMMONS_IDS if args.ids == DEFAULT_IDS else args.ids, args.root)
    else:
        for item in args.ids:
            print(json.dumps(prepare(item, args.root), ensure_ascii=False), flush=True)
