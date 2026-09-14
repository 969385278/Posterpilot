import re

STANDALONE_PAGE_NUMBER = re.compile(r"^\s*[-–—]?\s*\d{1,4}\s*[-–—]?\s*$")
SENTENCE_BOUNDARY = re.compile(r"(?<=[。！？.!?])")
PARAGRAPH_BREAK = "\x00"


def clean_page_text(text: str) -> str:
    normalized = text.replace("\r\n", "\n").replace("\r", "\n").replace("\u3000", " ")
    normalized = re.sub(r"[^\S\n]+", " ", normalized)
    cleaned_lines: list[str] = []
    for line in normalized.splitlines():
        collapsed = re.sub(r"[ \t]+", " ", line).strip()
        if not collapsed:
            if cleaned_lines and cleaned_lines[-1] != PARAGRAPH_BREAK:
                cleaned_lines.append(PARAGRAPH_BREAK)
            continue
        if STANDALONE_PAGE_NUMBER.fullmatch(collapsed):
            continue
        collapsed = re.sub(
            r"(?<=[\u3400-\u9fff])(?<![章节]) (?=[\u3400-\u9fff])",
            "",
            collapsed,
        )
        cleaned_lines.append(collapsed)
    while cleaned_lines and cleaned_lines[-1] == PARAGRAPH_BREAK:
        cleaned_lines.pop()
    cleaned = "\n".join(cleaned_lines)
    cleaned = re.sub(
        r"(?<=[\u3400-\u9fff])(?<![章节])\n(?=[\u3400-\u9fff])",
        "",
        cleaned,
    )
    return cleaned.replace(f"\n{PARAGRAPH_BREAK}\n", "\n")


def split_page_text(
    text: str,
    *,
    target_chars: int = 800,
    overlap_chars: int = 120,
    min_chars: int = 120,
) -> list[str]:
    if target_chars < 40:
        raise ValueError("target_chars must be at least 40")
    if overlap_chars < 0 or overlap_chars >= target_chars:
        raise ValueError("overlap_chars must be non-negative and smaller than target_chars")
    if min_chars < 1 or min_chars > target_chars:
        raise ValueError("min_chars must be between 1 and target_chars")

    normalized = text.replace("\r\n", "\n").replace("\r", "\n").strip()
    if not normalized:
        return []

    units: list[str] = []
    for paragraph in re.split(r"\n\s*\n", normalized):
        paragraph = re.sub(r"[ \t]+", " ", paragraph.replace("\n", " ")).strip()
        if not paragraph:
            continue
        sentences = [sentence.strip() for sentence in SENTENCE_BOUNDARY.split(paragraph)]
        for sentence in sentences:
            if not sentence:
                continue
            units.extend(_split_long_unit(sentence, target_chars))

    chunks: list[str] = []
    current = ""
    for unit in units:
        separator = "" if not current else " "
        candidate = f"{current}{separator}{unit}"
        if current and len(candidate) > target_chars:
            chunks.append(current.strip())
            prefix = current[-overlap_chars:].strip() if overlap_chars else ""
            current = f"{prefix} {unit}".strip() if prefix else unit
        else:
            current = candidate

    if current.strip():
        chunks.append(current.strip())

    if len(chunks) > 1 and len(chunks[-1]) < min_chars:
        orphan = chunks.pop()
        combined = f"{chunks[-1]} {orphan}".strip()
        maximum_merged_length = target_chars + overlap_chars * 2
        if len(combined) <= maximum_merged_length:
            chunks[-1] = combined
        else:
            left, right = _split_balanced(combined)
            chunks[-1] = left
            chunks.append(right)
    return chunks


def _split_long_unit(unit: str, target_chars: int) -> list[str]:
    if len(unit) <= target_chars:
        return [unit]
    return [unit[index : index + target_chars] for index in range(0, len(unit), target_chars)]


def _split_balanced(text: str) -> tuple[str, str]:
    midpoint = len(text) // 2
    boundary_after = text.find(" ", midpoint)
    boundary_before = text.rfind(" ", 0, midpoint)
    candidates = [boundary for boundary in (boundary_before, boundary_after) if boundary > 0]
    boundary = min(candidates, key=lambda item: abs(item - midpoint)) if candidates else midpoint
    return text[:boundary].strip(), text[boundary:].strip()
