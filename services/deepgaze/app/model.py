from typing import Protocol

import numpy as np


class SaliencyModel(Protocol):
    model_name: str
    device: str
    config_id: str

    def predict(self, image: np.ndarray) -> np.ndarray: ...


class ModelUnavailableError(RuntimeError):
    pass


class DeepGazeModel:
    """Lazy DeepGaze III wrapper so health checks do not download model weights."""

    model_name = "DeepGaze III"
    config_id = "deepgaze-iii-c87b106-rgb255-v2"

    def __init__(self) -> None:
        self._model = None
        self._torch = None
        self.device = "uninitialized"

    def predict(self, image: np.ndarray) -> np.ndarray:
        self._load()
        assert self._model is not None and self._torch is not None
        torch = self._torch
        tensor = torch.from_numpy(image.copy()).permute(2, 0, 1).unsqueeze(0).to(self.device)
        # Upstream deepgaze_pytorch.features.normalizer.Normalizer already
        # divides RGB values by 255. Passing [0, 1] here normalizes twice.
        tensor = tensor.float()
        centerbias = torch.zeros((1, image.shape[0], image.shape[1]), device=self.device)
        # DeepGaze III conditions on the four latest fixations. Its upstream scanpath
        # encoder requires one seed, so the neutral center is used before sampling.
        x_history = torch.full((1, 4), float("nan"), device=self.device)
        y_history = torch.full((1, 4), float("nan"), device=self.device)
        x_history[0, 0] = image.shape[1] / 2
        y_history[0, 0] = image.shape[0] / 2
        with torch.inference_mode():
            prediction = self._model(tensor, centerbias, x_hist=x_history, y_hist=y_history)
        values = prediction.squeeze().detach().float().cpu().numpy()
        return np.exp(values - np.max(values))

    def _load(self) -> None:
        if self._model is not None:
            return
        try:
            import torch
            from deepgaze_pytorch import DeepGazeIII
        except ImportError as error:
            raise ModelUnavailableError(
                "DeepGaze is not installed. Install the verified DeepGaze model dependencies first."
            ) from error
        self._torch = torch
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        try:
            self._model = DeepGazeIII(pretrained=True).to(self.device).eval()
        except Exception as error:  # Model weights are fetched by the upstream implementation.
            raise ModelUnavailableError(f"DeepGaze model could not be loaded: {error}") from error
