"""
Agus OSINT Backend -- Flight Intelligence
==============================================
Enriches raw flight data with military detection, airline identification,
squawk code alerts, and aircraft registration country estimation.
"""

from __future__ import annotations

import re
from typing import ClassVar, Dict, List, Optional


class FlightIntelligence:
    """Enriches flight data with military detection, airline identification, and squawk alerts."""

    # Military callsign prefixes (ICAO airline designators for armed forces)
    MILITARY_PREFIXES: ClassVar[set] = {
        "RCH", "REACH",   # USAF Air Mobility Command
        "RRR",             # USAF tanker/cargo
        "JAKE",            # US Navy
        "NAVY",            # US Navy
        "TOPCAT",          # US Marine Corps
        "EPIC",            # USAF special ops
        "DUKE",            # USAF
        "EVAC",            # USAF aeromedical
        "CASA",            # USAF
        "KING",            # USAF rescue
        "MOOSE",           # USAF C-17
        "PACK",            # USAF
        "STONE",           # US Army
        "PAT",             # USAF VIP transport
        "SAM",             # Special Air Mission (POTUS/VIP)
        "VENUS",           # USAF
        "SPAR",            # USAF VIP
        "EXEC",            # USAF executive
        "ORDER",           # NATO AWACS
        "NATO",            # NATO
        "MMF",             # French Air Force
        "CTM",             # French Air Force (COTAM)
        "GAF",             # German Air Force
        "IAM",             # Italian Air Force
        "RFR",             # French Air Force
        "BAF",             # Belgian Air Force
        "HVK",             # Royal Netherlands Air Force
        "SHF",             # Swedish Air Force
        "NOH",             # Norwegian Air Force
        "DAF",             # Danish Air Force
        "PLF",             # Polish Air Force
        "HAF",             # Hellenic (Greek) Air Force
        "THF",             # Turkish Air Force
        "TUAF",            # Turkish Air Force
        "RSD",             # Russian Air Force
        "RFF",             # Russian Federation Air Force
        "CFC",             # Chinese Air Force (PLAAF) / Canadian Forces
        "CHN",             # Chinese military
        "IAF",             # Israeli Air Force
        "IFC",             # Israeli Air Force cargo
        "ASCOT",           # RAF (UK)
        "RRF",             # RAF
        "NINJA",           # RAF special ops
        "ASY",             # Royal Australian Air Force
        "RAAF",            # Royal Australian Air Force
        "KAF",             # Kuwait Air Force
        "UAE",             # UAE Air Force
        "RSF",             # Saudi Air Force
        "QAF",             # Qatar Air Force
        "JNS",             # Japan Air Self-Defense Force
        "JASDF",           # Japan Air Self-Defense Force
        "ROKAF",           # Republic of Korea Air Force
    }

    MILITARY_RE: ClassVar[re.Pattern] = re.compile(
        r"^(RCH|REACH|RRR|NAVY|JAKE|TOPCAT|EPIC|DUKE|EVAC|KING|MOOSE|"
        r"PAT|SAM|SPAR|EXEC|ORDER|NATO|ASCOT|NINJA|FORTE|HOMER|CYLON|"
        r"MMF|CTM|GAF|IAM|RFR|BAF|HVK|SHF|NOH|DAF|PLF|HAF|THF|TUAF|"
        r"RSD|RFF|CFC|IAF|IFC|ASY|RAAF|KAF|UAE|RSF|QAF|JNS)\d*",
        re.IGNORECASE,
    )

    # ICAO24 address blocks for military registries (first 2 hex chars)
    MILITARY_ICAO24_PREFIXES: ClassVar[set] = {
        "ae", "af",  # US military
        "3f", "3e",  # German military
        "43",        # UK military
        "3a",        # French military
        "33",        # Italian military
        "50",        # Israeli military
        "70",        # Russian military cluster
        "78",        # Chinese military cluster
    }

    # Airline ICAO 3-letter code -> airline name
    AIRLINE_CODES: ClassVar[Dict[str, str]] = {
        "AAL": "American Airlines", "UAL": "United Airlines", "DAL": "Delta Air Lines",
        "SWA": "Southwest Airlines", "JBU": "JetBlue", "NKS": "Spirit Airlines",
        "FFT": "Frontier Airlines", "ASA": "Alaska Airlines", "HAL": "Hawaiian Airlines",
        "BAW": "British Airways", "DLH": "Lufthansa", "AFR": "Air France",
        "KLM": "KLM Royal Dutch", "SAS": "Scandinavian Airlines", "FIN": "Finnair",
        "IBE": "Iberia", "AZA": "ITA Airways", "TAP": "TAP Portugal",
        "SWR": "Swiss International", "AUA": "Austrian Airlines", "BEL": "Brussels Airlines",
        "RYR": "Ryanair", "EZY": "easyJet", "WZZ": "Wizz Air",
        "VLG": "Vueling", "NWG": "Norwegian", "TOM": "TUI Airways",
        "THY": "Turkish Airlines", "ELY": "El Al", "MEA": "Middle East Airlines",
        "SVA": "Saudia", "ETD": "Etihad Airways", "UAE": "Emirates",
        "QTR": "Qatar Airways", "GFA": "Gulf Air", "OMA": "Oman Air",
        "KAC": "Kuwait Airways", "MSR": "EgyptAir", "RJA": "Royal Jordanian",
        "AFL": "Aeroflot", "SBI": "S7 Airlines", "AIC": "Air India",
        "CES": "China Eastern", "CSN": "China Southern", "CCA": "Air China",
        "CPA": "Cathay Pacific", "SIA": "Singapore Airlines", "MAS": "Malaysia Airlines",
        "THA": "Thai Airways", "GIA": "Garuda Indonesia", "VNM": "Vietnam Airlines",
        "JAL": "Japan Airlines", "ANA": "All Nippon Airways", "KAL": "Korean Air",
        "AAR": "Asiana Airlines", "QFA": "Qantas", "ANZ": "Air New Zealand",
        "RAM": "Royal Air Maroc", "ETH": "Ethiopian Airlines", "SAA": "South African Airways",
        "KQA": "Kenya Airways", "AVA": "Avianca", "LAN": "LATAM Airlines",
        "AZU": "Azul Brazilian", "GLO": "Gol Linhas Aereas", "TAM": "LATAM Brasil",
        "AMX": "Aeromexico", "CMP": "Copa Airlines", "ACA": "Air Canada",
        "WJA": "WestJet", "FDX": "FedEx Express", "UPS": "UPS Airlines",
        "GTI": "Atlas Air", "CLX": "Cargolux", "KZR": "Air Astana",
    }

    # ICAO24 prefix ranges -> approximate aircraft registration country
    ICAO24_RANGES: ClassVar[List[tuple]] = [
        ("a00000", "afffff", "United States", "various"),
        ("c00000", "c3ffff", "Canada", "various"),
        ("400000", "43ffff", "United Kingdom", "various"),
        ("3c0000", "3fffff", "Germany", "various"),
        ("380000", "3bffff", "France", "various"),
        ("300000", "33ffff", "Italy", "various"),
        ("340000", "37ffff", "Spain", "various"),
        ("480000", "4fffff", "Netherlands/Belgium/Luxembourg", "various"),
        ("440000", "47ffff", "Austria/Switzerland", "various"),
        ("500000", "57ffff", "Israel/Palestine", "various"),
        ("700000", "70ffff", "Russia", "various"),
        ("780000", "7bffff", "China", "various"),
        ("7c0000", "7fffff", "Australia", "various"),
        ("800000", "83ffff", "India", "various"),
        ("840000", "87ffff", "Japan", "various"),
        ("680000", "6fffff", "South Korea", "various"),
        ("e00000", "e3ffff", "Brazil/Argentina", "various"),
        ("0c0000", "0fffff", "Middle East (various)", "various"),
    ]

    @staticmethod
    def is_military_dbflags(db_flags: int) -> bool:
        """Check if adsb.lol dbFlags bit 0 indicates military."""
        return bool(db_flags & 1) if isinstance(db_flags, int) else False

    def is_military(self, callsign: str, icao24: str) -> bool:
        """Determine if a flight is likely military based on callsign and ICAO24 address."""
        if callsign and self.MILITARY_RE.match(callsign):
            return True
        if icao24 and len(icao24) >= 2:
            prefix = icao24[:2].lower()
            if prefix in self.MILITARY_ICAO24_PREFIXES:
                return True
        return False

    def estimate_route(self, callsign: str) -> Optional[str]:
        """Estimate airline/route from callsign."""
        if not callsign or len(callsign) < 4:
            return None
        prefix = callsign[:3].upper()
        airline = self.AIRLINE_CODES.get(prefix)
        if airline:
            return f"{airline} flight {callsign[3:].strip()}"
        return None

    def estimate_aircraft_type(self, icao24: str) -> Optional[str]:
        """Estimate aircraft registration country from ICAO24 hex address."""
        if not icao24 or len(icao24) < 2:
            return None
        hex_lower = icao24.lower()
        for start, end, country, _ in self.ICAO24_RANGES:
            if start <= hex_lower <= end:
                return f"{country}-registered"
        return None

    def detect_squawk_alert(self, squawk: str) -> Optional[str]:
        """Detect special squawk codes."""
        if squawk == "7500":
            return "HIJACK"
        elif squawk == "7600":
            return "RADIO_FAILURE"
        elif squawk == "7700":
            return "EMERGENCY"
        return None

    def enrich_flight(self, raw_state: list) -> dict:
        """
        Enrich a raw OpenSky state vector (17-field list) into a full dict
        with intelligence annotations.
        """
        if len(raw_state) < 17:
            return {}

        s = raw_state
        if s[5] is None or s[6] is None:
            return {}

        icao24 = s[0] or ""
        callsign = (s[1] or "").strip()
        squawk = s[14] if len(s) > 14 else None
        spi = s[15] if len(s) > 15 else False
        position_source = s[16] if len(s) > 16 else 0

        position_source_label = {
            0: "ADS-B", 1: "ASTERIX", 2: "MLAT", 3: "FLARM"
        }.get(position_source, "unknown")

        is_mil = self.is_military(callsign, icao24)
        flight_route = self.estimate_route(callsign)
        aircraft_type = self.estimate_aircraft_type(icao24)
        squawk_alert = self.detect_squawk_alert(squawk) if squawk else None

        return {
            "icao24": icao24,
            "callsign": callsign,
            "origin_country": s[2],
            "time_position": s[3],
            "last_contact": s[4],
            "longitude": s[5],
            "latitude": s[6],
            "baro_altitude": s[7],
            "on_ground": s[8],
            "velocity": s[9],
            "heading": s[10],
            "vertical_rate": s[11],
            "geo_altitude": s[13],
            "squawk": squawk,
            "spi": spi,
            "position_source": position_source_label,
            "flight_route": flight_route,
            "aircraft_type": aircraft_type,
            "is_military": is_mil,
            "squawk_alert": squawk_alert,
            "altitude": s[7],
        }
