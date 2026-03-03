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

__all__ = [
    "BaseFetcher", "FetcherRegistry",
    "FlightFetcher", "ConflictFetcher", "EventFetcher", "FireFetcher",
    "VesselFetcher", "CCTVFetcher", "NewsFetcher", "SatelliteFetcher",
    "EarthquakeFetcher", "NuclearFetcher", "WeatherAlertFetcher",
    "TerrorismFetcher", "RefugeeFetcher", "PiracyFetcher", "AirspaceFetcher",
    "SanctionsFetcher", "CyberFetcher", "MilitaryBaseFetcher",
    "AirportFetcher", "NOTAMFetcher", "SubmarineFetcher", "CarrierFetcher",
    "ThreatIntelFetcher", "SignalsFetcher", "MissileTestFetcher",
]
