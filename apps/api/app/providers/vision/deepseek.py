"""Image-input chat adapter; endpoint/model capability must be verified at connection time."""

from app.providers.vision.ark import ArkVisionProvider


class DeepSeekVisionProvider(ArkVisionProvider):
    provider_name = "DeepSeek"
