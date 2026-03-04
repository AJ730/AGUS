"""Fetcher registry builder — registers every OSINT data source."""

from __future__ import annotations

from .fetchers import (
    AirportFetcher,
    AirspaceFetcher,
    AsteroidFetcher,
    AirQualityFetcher,
    BorderWaitFetcher,
    CarrierFetcher,
    CCTVFetcher,
    ConflictFetcher,
    CriticalInfrastructureFetcher,
    CycloneFetcher,
    CyberFetcher,
    DeforestationFetcher,
    DiseaseOutbreakFetcher,
    EarthquakeFetcher,
    EONETFetcher,
    EquipmentLossFetcher,
    EventFetcher,
    FetcherRegistry,
    FireFetcher,
    FlightFetcher,
    GeoConfirmedFetcher,
    GPSJammingFetcher,
    InternetOutageFetcher,
    LiveStreamFetcher,
    MastodonOSINTFetcher,
    MilitaryBaseFetcher,
    MissileTestFetcher,
    N2YOSatelliteFetcher,
    NewsFetcher,
    NOTAMFetcher,
    NuclearFetcher,
    PiracyFetcher,
    ProtestFetcher,
    RadiosondeFetcher,
    RedditOSINTFetcher,
    RefugeeFetcher,
    RocketAlertFetcher,
    SanctionsFetcher,
    SatelliteFetcher,
    SignalsFetcher,
    SpaceLaunchFetcher,
    SpaceWeatherFetcher,
    SubmarineFetcher,
    TelegramOSINTFetcher,
    TerrorismFetcher,
    ThreatIntelFetcher,
    UnderseaCableFetcher,
    VesselFetcher,
    VolcanoFetcher,
    WeatherAlertFetcher,
)
from .flight_intel import FlightIntelligence


def build_registry(intel: FlightIntelligence) -> FetcherRegistry:
    """Create a FetcherRegistry with all OSINT data sources registered.

    Args:
        intel: FlightIntelligence instance for flight-related enrichment.

    Returns:
        Fully populated FetcherRegistry.
    """
    registry = FetcherRegistry()
    registry.register("flights", FlightFetcher(intel))
    registry.register("conflicts", ConflictFetcher())
    registry.register("events", EventFetcher())
    registry.register("fires", FireFetcher())
    registry.register("vessels", VesselFetcher())
    registry.register("cctv", CCTVFetcher())
    registry.register("satellites", SatelliteFetcher())
    registry.register("earthquakes", EarthquakeFetcher())
    registry.register("nuclear", NuclearFetcher())
    registry.register("weather_alerts", WeatherAlertFetcher())
    registry.register("terrorism", TerrorismFetcher())
    registry.register("refugees", RefugeeFetcher())
    registry.register("piracy", PiracyFetcher())
    registry.register("airspace", AirspaceFetcher())
    registry.register("sanctions", SanctionsFetcher())
    registry.register("cyber", CyberFetcher())
    registry.register("military_bases", MilitaryBaseFetcher())
    registry.register("airports", AirportFetcher())
    registry.register("notams", NOTAMFetcher())
    registry.register("submarines", SubmarineFetcher())
    registry.register("carriers", CarrierFetcher())
    registry.register("news", NewsFetcher())
    registry.register("threat_intel", ThreatIntelFetcher())
    registry.register("signals", SignalsFetcher())
    registry.register("missile_tests", MissileTestFetcher())
    registry.register("telegram_osint", TelegramOSINTFetcher())
    registry.register("rocket_alerts", RocketAlertFetcher())
    registry.register("geo_confirmed", GeoConfirmedFetcher())
    registry.register("undersea_cables", UnderseaCableFetcher())
    registry.register("live_streams", LiveStreamFetcher())
    registry.register("reddit_osint", RedditOSINTFetcher())
    registry.register("equipment_losses", EquipmentLossFetcher())
    registry.register("internet_outages", InternetOutageFetcher())
    registry.register("gps_jamming", GPSJammingFetcher())
    registry.register("natural_events", EONETFetcher())
    registry.register("space_weather", SpaceWeatherFetcher())
    registry.register("air_quality", AirQualityFetcher())
    registry.register("cyclones", CycloneFetcher())
    registry.register("volcanoes", VolcanoFetcher())
    registry.register("asteroids", AsteroidFetcher())
    registry.register("radiosondes", RadiosondeFetcher())
    registry.register("disease_outbreaks", DiseaseOutbreakFetcher())
    registry.register("border_crossings", BorderWaitFetcher())
    registry.register("mastodon_osint", MastodonOSINTFetcher())
    registry.register("space_launches", SpaceLaunchFetcher())
    registry.register("protests", ProtestFetcher())
    registry.register("critical_infrastructure", CriticalInfrastructureFetcher())
    registry.register("deforestation", DeforestationFetcher())
    registry.register("n2yo_satellites", N2YOSatelliteFetcher())
    return registry
