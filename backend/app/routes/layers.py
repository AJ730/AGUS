"""Passthrough data-layer endpoints — one GET per OSINT source.

Instead of 47 hand-written two-line functions we register them in a loop.
"""

from __future__ import annotations

from fastapi import APIRouter, Request

from ._helpers import layer_response

router = APIRouter()

# Every layer whose endpoint is just ``return await layer_response(request, name)``
_PASSTHROUGH_LAYERS = [
    "flights",
    "conflicts",
    "events",
    "fires",
    "vessels",
    "cctv",
    "satellites",
    "earthquakes",
    "nuclear",
    "weather_alerts",
    "terrorism",
    "refugees",
    "piracy",
    "airspace",
    "sanctions",
    "cyber",
    "military_bases",
    "airports",
    "notams",
    "submarines",
    "carriers",
    "news",
    "threat_intel",
    "signals",
    "telegram_osint",
    "rocket_alerts",
    "geo_confirmed",
    "undersea_cables",
    "live_streams",
    "reddit_osint",
    "equipment_losses",
    "internet_outages",
    "gps_jamming",
    "natural_events",
    "space_weather",
    "air_quality",
    "cyclones",
    "volcanoes",
    "asteroids",
    "radiosondes",
    "disease_outbreaks",
    "border_crossings",
    "mastodon_osint",
    "space_launches",
    "protests",
    "critical_infrastructure",
    "deforestation",
    "n2yo_satellites",
]

for _name in _PASSTHROUGH_LAYERS:
    def _make(name: str):
        async def _endpoint(request: Request):
            return await layer_response(request, name)
        _endpoint.__name__ = name
        return _endpoint
    router.add_api_route(f"/{_name}", _make(_name), methods=["GET"])
