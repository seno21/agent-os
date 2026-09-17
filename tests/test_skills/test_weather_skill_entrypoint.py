from __future__ import annotations

import importlib.util
import json
from pathlib import Path

SCRIPT = (
    Path(__file__).resolve().parents[2]
    / "src"
    / "agentos"
    / "skills"
    / "bundled"
    / "weather"
    / "scripts"
    / "weather_fetch.py"
)


def _load_module():
    spec = importlib.util.spec_from_file_location("weather_fetch", SCRIPT)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_weather_entrypoint_extracts_destination_and_compacts_forecast(
    monkeypatch,
    capsys,
) -> None:
    module = _load_module()

    def fake_fetch(location: str, timeout: float):
        assert location == "Tokyo, Japan"
        assert timeout == 8.0
        return {
            "current_condition": [
                {
                    "weatherDesc": [{"value": "Light rain"}],
                    "temp_C": "25",
                    "FeelsLikeC": "28",
                    "humidity": "84",
                    "precipMM": "1.2",
                    "windspeedKmph": "12",
                },
            ],
            "weather": [
                {
                    "date": "2026-06-25",
                    "mintempC": "22",
                    "maxtempC": "28",
                    "hourly": [
                        {"chanceofrain": "40"},
                        {"chanceofrain": "80"},
                    ],
                },
            ],
        }

    monkeypatch.setattr(module, "_fetch_wttr_json", fake_fetch)

    status = module.main(
        [
            "--location",
            "DESTINATION: Tokyo, Japan\nDATES: late June",
            "--days",
            "3",
        ],
    )

    assert status == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["location"] == "Tokyo, Japan"
    assert payload["current"]["condition"] == "Light rain"
    assert payload["forecast"][0]["rain_chance_max_pct"] == "80"
    assert "rainy season" in payload["seasonal_hint"]
    assert payload["errors"] == []


def test_weather_entrypoint_returns_seasonal_hint_on_network_error(
    monkeypatch,
    capsys,
) -> None:
    module = _load_module()

    def fake_fetch(_location: str, _timeout: float):
        raise TimeoutError("slow")

    monkeypatch.setattr(module, "_fetch_wttr_json", fake_fetch)

    status = module.main(["--location", "DESTINATION: Tokyo\nDATES: late June"])

    assert status == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["location"] == "Tokyo"
    assert payload["forecast"] == []
    assert payload["errors"]
    assert "rainy season" in payload["seasonal_hint"]


def test_weather_entrypoint_handles_null_values_and_malformed_items(
    monkeypatch,
    capsys,
) -> None:
    module = _load_module()

    def fake_fetch(_location: str, _timeout: float):
        return {
            "current_condition": [
                {
                    "weatherDesc": [None],
                    "temp_C": None,
                    "FeelsLikeC": None,
                    "humidity": None,
                    "precipMM": None,
                    "windspeedKmph": None,
                },
            ],
            "weather": [
                {
                    "date": None,
                    "mintempC": None,
                    "maxtempC": None,
                    "hourly": [
                        None,
                        "invalid",
                        {"chanceofrain": "50"},
                        {"chanceofrain": None},
                    ],
                },
                None,
                "bad_item",
            ],
        }

    monkeypatch.setattr(module, "_fetch_wttr_json", fake_fetch)

    status = module.main(["--location", "London"])

    assert status == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["location"] == "London"
    assert payload["current"]["condition"] == ""
    assert payload["current"]["temperature_c"] == ""
    assert payload["current"]["feels_like_c"] == ""
    assert payload["forecast"][0]["rain_chance_max_pct"] == "50"
    assert payload["errors"] == []


def test_weather_entrypoint_handles_non_dict_payload(
    monkeypatch,
    capsys,
) -> None:
    module = _load_module()

    def fake_fetch(_location: str, _timeout: float):
        return ["not", "a", "dict"]

    monkeypatch.setattr(module, "_fetch_wttr_json", fake_fetch)

    status = module.main(["--location", "Paris"])

    assert status == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["location"] == "Paris"
    assert payload["current"] == {}
    assert payload["forecast"] == []
    assert payload["errors"] == []
