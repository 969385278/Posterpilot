from app.cache import PredictionCache, cache_key


def test_cache_key_changes_when_steps_change() -> None:
    image = b"poster-bytes"

    assert cache_key(image, steps=3, model_config="deepgaze-iii") != cache_key(
        image, steps=4, model_config="deepgaze-iii"
    )


def test_memory_cache_returns_a_saved_prediction() -> None:
    cache = PredictionCache()
    key = cache_key(b"poster-bytes", steps=3, model_config="deepgaze-iii")
    cache.set(key, {"model": "fake", "fixations": []})

    assert cache.get(key) == {"model": "fake", "fixations": []}
