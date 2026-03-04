"""
Agus OSINT Backend -- Flight Intelligence
==============================================
Enriches raw flight data with military detection, airline identification,
squawk code alerts, and aircraft registration country estimation.

Military detection strategy (ordered by reliability):
1. adsb.lol dbFlags bit 0 — curated database, most accurate
2. Callsign matching — only unambiguous military callsigns (4+ chars)
3. Short (3-char) callsign prefixes — only if NOT a known civilian airline
4. ICAO24 ranges — DISABLED (too many false positives)
"""

from __future__ import annotations

import re
from typing import ClassVar, Dict, List, Optional


class FlightIntelligence:
    """Enriches flight data with military detection, airline identification, and squawk alerts.

    Military classification is intentionally conservative to avoid false positives.
    The adsb.lol dbFlags field (bit 0) is the primary military indicator.
    Callsign-based detection only uses unambiguous long-form military callsigns.
    """

    # -----------------------------------------------------------------------
    # Unambiguous military callsigns (4+ characters, never used by airlines)
    # These are safe to match without further checks.
    # -----------------------------------------------------------------------
    STRONG_MILITARY_CALLSIGNS: ClassVar[set] = {
        # US Armed Forces
        "REACH",            # USAF Air Mobility Command
        "NAVY",             # US Navy
        "JAKE",             # US Navy carrier ops
        "TOPCAT",           # US Marine Corps
        "MOOSE",            # USAF C-17 Globemaster
        "EVAC",             # USAF aeromedical evacuation
        "SPAR",             # USAF Special Priority Air Resource (VIP)
        "EXEC",             # USAF executive transport
        "FORTE",            # USAF RQ-4 Global Hawk (recon drone)
        "HOMER",            # USAF tanker/ISR
        "CYLON",            # US military exercise
        "STONE",            # US Army aviation
        # NATO / Allied
        "ORDER",            # NATO AWACS E-3 Sentry
        "NATO",             # NATO general
        "ASCOT",            # RAF (UK Royal Air Force)
        "NINJA",            # RAF special operations
        "RAFR",             # RAF Reserves
        # Other distinctive callsigns
        "RAAF",             # Royal Australian Air Force
        "ROKAF",            # Republic of Korea Air Force
        "JASDF",            # Japan Air Self-Defense Force
        "TUAF",             # Turkish Air Force
    }

    # -----------------------------------------------------------------------
    # 3-letter ICAO military designators — ONLY match when NOT a known airline
    # These are real military codes but some overlap with civilian use,
    # so we check against AIRLINE_CODES and CIVILIAN_OVERRIDES first.
    # -----------------------------------------------------------------------
    MILITARY_3CHAR: ClassVar[set] = {
        "RCH",              # USAF Air Mobility Command (C-5, C-17)
        "RRR",              # USAF tanker/cargo
        "MMF",              # French Air Force (Armee de l'Air)
        "CTM",              # French Air Force COTAM
        "RFR",              # French Air Force
        "IAF",              # Israeli Air Force
        "IFC",              # Israeli Air Force cargo
        "RSD",              # Russian Air Force
        "RFF",              # Russian Federation Forces
        "ASY",              # Royal Australian Air Force
        "JNS",              # Japan Self-Defense Forces
    }

    # -----------------------------------------------------------------------
    # Callsigns that LOOK military but are civilian airlines — never flag these
    # -----------------------------------------------------------------------
    CIVILIAN_OVERRIDES: ClassVar[set] = {
        "UAE",              # Emirates airline (NOT UAE Air Force)
        "CHN",              # China Airlines (Taiwanese carrier)
        "CFC",              # Canadian North airline
        "IAM",              # Iaero Airlines (Brazil) — overlaps Italian AF
        "GAF",              # Generic Aviation (some civilian operators use this)
        "SAM",              # Samoa Airways / SAM Colombia
        "BAF",              # Can be Belgian AF but also Brussels Airlines ops
        "PAT",              # Various civilian operators
        "DAF",              # Can be Danish AF but also civilian
        "HAF",              # Can be Hellenic AF but also civilian
        "THF",              # Can overlap with civilian
        "SHF",              # Can overlap with civilian
        "NOH",              # Can overlap with civilian
        "HVK",              # Can overlap with civilian
        "PLF",              # Can overlap with civilian
        "KAF",              # Can overlap with Kuwait Airways ops
        "RSF",              # Can overlap with civilian
        "QAF",              # Can overlap with Qatar Airways ops
        "DUKE",             # Various civilian operators
        "KING",             # Various civilian operators
        "EPIC",             # Epic Aviation (civilian charter)
        "CASA",             # CASA aircraft manufacturer / civilian
        "PACK",             # Various civilian cargo
        "VENUS",            # Various civilian operators
    }

    # -----------------------------------------------------------------------
    # Regex for matching — uses only the reliable callsigns
    # Must be followed by at least 1 digit to reduce false positives
    # -----------------------------------------------------------------------
    MILITARY_RE: ClassVar[re.Pattern] = re.compile(
        r"^(REACH|NAVY|JAKE|TOPCAT|MOOSE|EVAC|SPAR|EXEC|FORTE|HOMER|"
        r"CYLON|STONE|ORDER|NATO|ASCOT|NINJA|RAFR|RAAF|ROKAF|JASDF|TUAF|"
        r"RCH|RRR|MMF|CTM|RFR|IAF|IFC|RSD|RFF|ASY|JNS)\d+$",
        re.IGNORECASE,
    )

    # -----------------------------------------------------------------------
    # Airline ICAO 3-letter codes -> airline name (civilian identification)
    # Used BOTH for route estimation AND to prevent military false positives.
    # -----------------------------------------------------------------------
    AIRLINE_CODES: ClassVar[Dict[str, str]] = {
        # North America
        "AAL": "American Airlines", "UAL": "United Airlines", "DAL": "Delta Air Lines",
        "SWA": "Southwest Airlines", "JBU": "JetBlue", "NKS": "Spirit Airlines",
        "FFT": "Frontier Airlines", "ASA": "Alaska Airlines", "HAL": "Hawaiian Airlines",
        "ACA": "Air Canada", "WJA": "WestJet", "FLE": "Flair Airlines",
        # Europe — majors
        "BAW": "British Airways", "DLH": "Lufthansa", "AFR": "Air France",
        "KLM": "KLM Royal Dutch", "SAS": "Scandinavian Airlines", "FIN": "Finnair",
        "IBE": "Iberia", "AZA": "ITA Airways", "TAP": "TAP Portugal",
        "SWR": "Swiss International", "AUA": "Austrian Airlines", "BEL": "Brussels Airlines",
        "LOT": "LOT Polish Airlines", "CSA": "Czech Airlines", "ROT": "TAROM",
        "THY": "Turkish Airlines", "PGT": "Pegasus Airlines",
        # Europe — low-cost
        "RYR": "Ryanair", "EZY": "easyJet", "EZS": "easyJet Switzerland",
        "WZZ": "Wizz Air", "VLG": "Vueling", "NWG": "Norwegian",
        "TOM": "TUI Airways", "TCX": "Thomas Cook",
        # Middle East
        "ELY": "El Al", "MEA": "Middle East Airlines",
        "SVA": "Saudia", "ETD": "Etihad Airways", "UAE": "Emirates",
        "QTR": "Qatar Airways", "GFA": "Gulf Air", "OMA": "Oman Air",
        "KAC": "Kuwait Airways", "MSR": "EgyptAir", "RJA": "Royal Jordanian",
        "IRA": "Iran Air", "KUK": "Kish Air", "IRC": "Iran Aseman",
        # Asia
        "AFL": "Aeroflot", "SBI": "S7 Airlines", "AIC": "Air India",
        "CES": "China Eastern", "CSN": "China Southern", "CCA": "Air China",
        "CHH": "Hainan Airlines", "CXA": "Xiamen Airlines",
        "CPA": "Cathay Pacific", "SIA": "Singapore Airlines", "MAS": "Malaysia Airlines",
        "THA": "Thai Airways", "GIA": "Garuda Indonesia", "VNM": "Vietnam Airlines",
        "JAL": "Japan Airlines", "ANA": "All Nippon Airways", "KAL": "Korean Air",
        "AAR": "Asiana Airlines", "EVA": "EVA Air", "CAL": "China Airlines",
        # Oceania
        "QFA": "Qantas", "ANZ": "Air New Zealand", "VOZ": "Virgin Australia",
        # Africa
        "RAM": "Royal Air Maroc", "ETH": "Ethiopian Airlines", "SAA": "South African Airways",
        "KQA": "Kenya Airways",
        # Americas
        "AVA": "Avianca", "LAN": "LATAM Airlines",
        "AZU": "Azul Brazilian", "GLO": "Gol Linhas Aereas", "TAM": "LATAM Brasil",
        "AMX": "Aeromexico", "CMP": "Copa Airlines",
        # Cargo
        "FDX": "FedEx Express", "UPS": "UPS Airlines",
        "GTI": "Atlas Air", "CLX": "Cargolux", "ABW": "AirBridgeCargo",
        "GEC": "Lufthansa Cargo", "BOX": "Aerologic",
        # Other
        "KZR": "Air Astana", "AHY": "Azerbaijan Airlines",
        "TCV": "TACV Cabo Verde", "HHI": "Hi Fly",
    }

    # -----------------------------------------------------------------------
    # ICAO24 prefix ranges -> aircraft registration country
    # -----------------------------------------------------------------------
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
        """Check if adsb.lol dbFlags bit 0 indicates military.

        This is the most reliable military indicator — it comes from adsb.lol's
        curated aircraft database which has been manually verified.
        """
        return bool(db_flags & 1) if isinstance(db_flags, int) else False

    def is_civilian_airline(self, callsign: str) -> bool:
        """Check if callsign belongs to a known civilian airline.

        Used to prevent dbFlags from overriding civilian classification.
        For example, UAE46D (Emirates) should never be flagged as military
        even if adsb.lol's database has dbFlags bit 0 set incorrectly.

        Args:
            callsign: The aircraft callsign (e.g., "UAE46D").

        Returns:
            True if the callsign matches a known civilian airline or override.
        """
        if not callsign or len(callsign) < 3:
            return False
        prefix3 = callsign[:3].upper().strip()
        if prefix3 in self.AIRLINE_CODES:
            return True
        if prefix3 in self.CIVILIAN_OVERRIDES or callsign.upper().strip() in self.CIVILIAN_OVERRIDES:
            return True
        return False

    def is_military(self, callsign: str, icao24: str) -> bool:
        """Determine if a flight is military based on callsign analysis.

        Conservative approach to minimize false positives:
        1. If callsign matches a known civilian airline -> NOT military
        2. If callsign matches a known civilian override -> NOT military
        3. If callsign matches strong military pattern (4+ chars + digits) -> military
        4. Otherwise -> NOT military (let dbFlags handle it)

        Note: ICAO24 range checking is intentionally disabled because
        the static hex ranges have too many civilian aircraft mixed in.
        The adsb.lol dbFlags (checked separately) is more reliable.
        """
        if not callsign:
            return False

        cs_upper = callsign.upper().strip()
        if len(cs_upper) < 3:
            return False

        prefix3 = cs_upper[:3]

        # Step 1: Known civilian airline -> definitely not military
        if prefix3 in self.AIRLINE_CODES:
            return False

        # Step 2: Known ambiguous callsigns that are usually civilian
        if prefix3 in self.CIVILIAN_OVERRIDES or cs_upper in self.CIVILIAN_OVERRIDES:
            return False

        # Step 3: Check strong military callsigns (long-form, unambiguous)
        for mil_cs in self.STRONG_MILITARY_CALLSIGNS:
            if cs_upper.startswith(mil_cs) and (
                len(cs_upper) == len(mil_cs) or cs_upper[len(mil_cs):].isdigit()
            ):
                return True

        # Step 4: Check 3-char military codes (must be followed by digits)
        if prefix3 in self.MILITARY_3CHAR and len(cs_upper) > 3 and cs_upper[3:].isdigit():
            return True

        return False

    def estimate_route(self, callsign: str) -> Optional[str]:
        """Estimate airline name and flight number from ICAO callsign.

        Args:
            callsign: The aircraft callsign (e.g., "BAW123" -> "British Airways flight 123")

        Returns:
            Formatted airline flight string, or None if not a known airline.
        """
        if not callsign or len(callsign) < 4:
            return None
        prefix = callsign[:3].upper()
        airline = self.AIRLINE_CODES.get(prefix)
        if airline:
            return f"{airline} flight {callsign[3:].strip()}"
        return None

    def estimate_aircraft_type(self, icao24: str) -> Optional[str]:
        """Estimate aircraft registration country from ICAO24 hex address.

        Args:
            icao24: The 6-character hex ICAO24 address.

        Returns:
            Country registration string (e.g., "United States-registered"), or None.
        """
        if not icao24 or len(icao24) < 2:
            return None
        hex_lower = icao24.lower()
        for start, end, country, _ in self.ICAO24_RANGES:
            if start <= hex_lower <= end:
                return f"{country}-registered"
        return None

    def detect_squawk_alert(self, squawk: str) -> Optional[str]:
        """Detect emergency squawk transponder codes.

        Args:
            squawk: 4-digit squawk code string.

        Returns:
            Alert type string ('HIJACK', 'RADIO_FAILURE', 'EMERGENCY'), or None.
        """
        if squawk == "7500":
            return "HIJACK"
        elif squawk == "7600":
            return "RADIO_FAILURE"
        elif squawk == "7700":
            return "EMERGENCY"
        return None

    def enrich_flight(self, raw_state: list) -> dict:
        """Enrich a raw state vector (17-field list) into a full dict with intel annotations.

        Args:
            raw_state: 17-element list matching OpenSky state vector format:
                [icao24, callsign, origin_country, time_position, last_contact,
                 longitude, latitude, baro_altitude, on_ground, velocity,
                 heading, vertical_rate, sensors, geo_altitude, squawk, spi, position_source]

        Returns:
            Enriched flight dict with military detection, route estimation, etc.
            Empty dict if required fields are missing.
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
        # Only flag squawk alerts for airborne aircraft with callsigns (reduces false positives)
        on_ground = s[8] if len(s) > 8 else False
        squawk_alert = None
        if squawk and callsign and not on_ground:
            squawk_alert = self.detect_squawk_alert(squawk)

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
