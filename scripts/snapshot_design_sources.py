"""Archive short checked excerpts and response hashes, not copyrighted full articles."""

import hashlib
import html
import json
import re
from datetime import UTC, datetime
from pathlib import Path
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
SOURCES = [
    (
        "nng-principles",
        "https://www.nngroup.com/articles/principles-visual-design/",
        [
            "Using relative size to signal importance",
            "equally distributed (but not necessarily symmetrical)",
            "reducing text contrast also reduces legibility",
        ],
    ),
    (
        "nng-hierarchy",
        "https://www.nngroup.com/articles/visual-hierarchy-ux-definition/",
        ["If everything is contrasted, then nothing stands out", "Let it breathe"],
    ),
    (
        "w3c-local-contrast",
        "https://www.w3.org/WAI/WCAG22/Techniques/general/G18",
        ["background pixels immediately next to the letter"],
    ),
    (
        "w3c-thin-fonts",
        "https://www.w3.org/WAI/WCAG22/Understanding/contrast-minimum.html",
        ["particularly thin or unusual fonts may be rendered"],
    ),
    (
        "w3c-text-spacing",
        "https://www.w3.org/WAI/WCAG22/Understanding/text-spacing.html",
        ["Content is not required to use these text spacing values", "Images of text"],
    ),
]


def capture():
    records = []
    for key, url, excerpts in SOURCES:
        request = Request(url, headers={"User-Agent": "PosterPilot-SourceReview/1.0"})
        with urlopen(request, timeout=30) as response:
            raw = response.read()
            resolved_url = response.url
        markup = raw.decode("utf-8")
        clean = re.sub(r"<(script|style)\b.*?</\1>", "", markup, flags=re.S)
        clean = re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", clean)))
        for excerpt in excerpts:
            if excerpt.lower() not in clean.lower():
                raise ValueError(
                    f"Source changed or excerpt not found: {key}: {excerpt}"
                )
        title = html.unescape(re.search(r"<title>(.*?)</title>", markup, flags=re.S)[1])
        records.append(
            {
                "id": key,
                "url": url,
                "resolved_url": resolved_url,
                "title": title,
                "checked_at": datetime.now(UTC).isoformat(),
                "response_sha256": hashlib.sha256(raw).hexdigest(),
                "checked_excerpts": excerpts,
                "review": "已读取上下文；知识卡为中文概括和项目应用建议，不是整篇转载。",
            }
        )
    target = ROOT / "data/knowledge/web-source-review-2026-09-20.json"
    target.write_text(
        json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"Verified {len(records)} source pages; saved short evidence to {target}")


if __name__ == "__main__":
    capture()
