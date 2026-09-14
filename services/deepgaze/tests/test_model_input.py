from contextlib import nullcontext
import numpy as np
from app.model import DeepGazeModel


class Tensor:
    def __init__(self, array): self.array = np.asarray(array)
    def permute(self, *axes): return Tensor(self.array.transpose(axes))
    def unsqueeze(self, axis): return Tensor(np.expand_dims(self.array, axis))
    def to(self, device): return self
    def float(self): return Tensor(self.array.astype(np.float32))
    def __setitem__(self, key, value): self.array[key] = value
    def squeeze(self): return Tensor(self.array.squeeze())
    def detach(self): return self
    def cpu(self): return self
    def numpy(self): return self.array


class FakeTorch:
    from_numpy = staticmethod(Tensor)
    zeros = staticmethod(lambda shape, **kwargs: Tensor(np.zeros(shape)))
    full = staticmethod(lambda shape, value, **kwargs: Tensor(np.full(shape, value)))
    inference_mode = staticmethod(nullcontext)


def test_deepgaze_receives_rgb_255_not_twice_normalized_pixels():
    wrapper = DeepGazeModel()
    wrapper._torch = FakeTorch()
    wrapper.device = "fixture"
    def model(image, centerbias, **kwargs):
        assert image.array.dtype == np.float32
        assert image.array.max() == 255
        assert image.array.min() == 64
        assert centerbias.array.shape == (1, 4, 6)
        return Tensor(np.zeros((1, 4, 6)))
    wrapper._model = model
    image = np.full((4, 6, 3), 64, dtype=np.uint8)
    image[0, 0] = 255
    assert wrapper.predict(image).shape == (4, 6)
    assert "rgb255" in wrapper.config_id
