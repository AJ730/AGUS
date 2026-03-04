"""Agus OSINT fetchers package -- one class per data source."""

from .base import BaseFetcher, FetcherRegistry
from .flights import FlightFetcher
from .conflicts import ConflictFetcher
from .events import EventFetcher
from .fires import FireFetcher
from .vessels import VesselFetcher
from .cctv import CCTVFetcher
from .news import NewsFetcher
from .satellites import SatelliteFetcher
from .earthquakes import EarthquakeFetcher
from .nuclear import NuclearFetcher
from .weather import WeatherAlertFetcher
from .terrorism import TerrorismFetcher
from .refugees import RefugeeFetcher
from .piracy import PiracyFetcher
from .airspace import AirspaceFetcher
from .sanctions import SanctionsFetcher
from .cyber import CyberFetcher
from .military import MilitaryBaseFetcher
from .airports import AirportFetcher
from .notams import NOTAMFetcher
from .submarines import SubmarineFetcher
from .carriers import CarrierFetcher
from .threat_intel import ThreatIntelFetcher
from .signals import SignalsFetcher
from .missile_tests import MissileTestFetcher
from .telegram_osint import TelegramOSINTFetcher
from .rocket_alerts import RocketAlertFetcher
from .geo_confirmed import GeoConfirmedFetcher
from .infrastructure import UnderseaCableFetcher
from .live_streams import LiveStreamFetcher
from .reddit_osint import RedditOSINTFetcher
from .equipment_losses import EquipmentLossFetcher
from .internet_outages import InternetOutageFetcher
from .gps_jamming import GPSJammingFetcher
from .eonet import EONETFetcher
from .space_weather import SpaceWeatherFetcher
from .air_quality import AirQualityFetcher
from .cyclones import CycloneFetcher
from .volcanoes import VolcanoFetcher
from .asteroids import AsteroidFetcher
from .radiosondes import RadiosondeFetcher
from .disease_outbreaks import DiseaseOutbreakFetcher
from .border_crossings import BorderWaitFetcher
from .mastodon_osint import MastodonOSINTFetcher
from .space_launches import SpaceLaunchFetcher
from .protests import ProtestFetcher
from .critical_infrastructure import CriticalInfrastructureFetcher
from .deforestation import DeforestationFetcher
from .n2yo_satellites import N2YOSatelliteFetcher

__all__ = [
    "BaseFetcher", "FetcherRegistry",
    "FlightFetcher", "ConflictFetcher", "EventFetcher", "FireFetcher",
    "VesselFetcher", "CCTVFetcher", "NewsFetcher", "SatelliteFetcher",
    "EarthquakeFetcher", "NuclearFetcher", "WeatherAlertFetcher",
    "TerrorismFetcher", "RefugeeFetcher", "PiracyFetcher", "AirspaceFetcher",
    "SanctionsFetcher", "CyberFetcher", "MilitaryBaseFetcher",
    "AirportFetcher", "NOTAMFetcher", "SubmarineFetcher", "CarrierFetcher",
    "ThreatIntelFetcher", "SignalsFetcher", "MissileTestFetcher",
    "TelegramOSINTFetcher", "RocketAlertFetcher",
    "GeoConfirmedFetcher", "UnderseaCableFetcher", "LiveStreamFetcher",
    "RedditOSINTFetcher", "EquipmentLossFetcher", "InternetOutageFetcher",
    "GPSJammingFetcher", "EONETFetcher",
    "SpaceWeatherFetcher", "AirQualityFetcher", "CycloneFetcher",
    "VolcanoFetcher", "AsteroidFetcher", "RadiosondeFetcher",
    "DiseaseOutbreakFetcher", "BorderWaitFetcher", "MastodonOSINTFetcher",
    "SpaceLaunchFetcher", "ProtestFetcher", "CriticalInfrastructureFetcher",
    "DeforestationFetcher", "N2YOSatelliteFetcher",
]
