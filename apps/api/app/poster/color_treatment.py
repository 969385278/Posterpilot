"""Bounded, deterministic background-only edits; no generated scene replacement."""

from pathlib import Path

from PIL import Image, ImageEnhance

from app.schemas.design_control import BackgroundTreatment


def treat_background(image: Image.Image, treatment: BackgroundTreatment) -> Image.Image:
    validated = BackgroundTreatment.model_validate(treatment.model_dump())
    result = image.convert("RGB")
    if validated.saturation != 1.0:
        result = ImageEnhance.Color(result).enhance(validated.saturation)
    if validated.contrast != 1.0:
        result = ImageEnhance.Contrast(result).enhance(validated.contrast)
    return result


def load_treated_background(path: Path | str, treatment: BackgroundTreatment) -> Image.Image:
    with Image.open(path) as source:
        return treat_background(source, treatment)
