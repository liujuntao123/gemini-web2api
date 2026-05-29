from gemini_web2api.models import resolve_model


def test_missing_model_falls_back_to_default():
    model_name, model_id, think_mode, err, extra = resolve_model(None)

    assert err is None
    assert model_name == "gemini-3.5-flash"
    assert model_id == 1
    assert think_mode == 4
    assert extra is None


def test_rejects_out_of_range_think_level():
    _, _, _, err, _ = resolve_model("gemini-3.5-flash@think=9")

    assert err == "Invalid think level: 9"
