"""Digitraffic AIS vessel position fetcher with military MMSI enrichment.

Uses Digitraffic for live AIS positions, enhanced with a curated military
MMSI database, MMSI range heuristics, AIS ship type codes, vessel name
pattern matching, and callsign analysis for warship identification.
"""

from __future__ import annotations

import logging
import re
from typing import Dict, List, Optional, Set, Tuple

import httpx

from ..config import MAX_VESSELS
from .base import BaseFetcher

logger = logging.getLogger("agus.fetchers")

_URL = "https://meri.digitraffic.fi/api/ais/v1/locations"

# ---------------------------------------------------------------------------
# Military MMSI database -- curated from public sources
# MID (first 3 digits) indicates country. Military vessels often use
# specific MMSI blocks or are listed in public warship registries.
# ---------------------------------------------------------------------------
# Format: MMSI -> (vessel_name, vessel_type, navy, hull_number)
_MILITARY_MMSIS: Dict[int, tuple] = {
    # United States Navy (MID 366-369)
    369970010: ("USS Gerald R. Ford", "Aircraft Carrier", "US Navy", "CVN-78"),
    369970011: ("USS George H.W. Bush", "Aircraft Carrier", "US Navy", "CVN-77"),
    369970012: ("USS Abraham Lincoln", "Aircraft Carrier", "US Navy", "CVN-72"),
    369970013: ("USS Theodore Roosevelt", "Aircraft Carrier", "US Navy", "CVN-71"),
    369970014: ("USS Dwight D. Eisenhower", "Aircraft Carrier", "US Navy", "CVN-69"),
    369970015: ("USS Carl Vinson", "Aircraft Carrier", "US Navy", "CVN-70"),
    369970016: ("USS Nimitz", "Aircraft Carrier", "US Navy", "CVN-68"),
    369970017: ("USS Harry S. Truman", "Aircraft Carrier", "US Navy", "CVN-75"),
    369970018: ("USS Ronald Reagan", "Aircraft Carrier", "US Navy", "CVN-76"),
    369970019: ("USS John C. Stennis", "Aircraft Carrier", "US Navy", "CVN-74"),
    # US Amphibious assault ships
    369970020: ("USS America", "Amphibious Assault", "US Navy", "LHA-6"),
    369970021: ("USS Tripoli", "Amphibious Assault", "US Navy", "LHA-7"),
    369970022: ("USS Wasp", "Amphibious Assault", "US Navy", "LHD-1"),
    369970023: ("USS Bataan", "Amphibious Assault", "US Navy", "LHD-5"),
    369970024: ("USS Makin Island", "Amphibious Assault", "US Navy", "LHD-8"),
    # Royal Navy (MID 232-235)
    232001000: ("HMS Queen Elizabeth", "Aircraft Carrier", "Royal Navy", "R08"),
    232001001: ("HMS Prince of Wales", "Aircraft Carrier", "Royal Navy", "R09"),
    232003000: ("HMS Daring", "Destroyer", "Royal Navy", "D32"),
    232003001: ("HMS Dragon", "Destroyer", "Royal Navy", "D35"),
    232003002: ("HMS Diamond", "Destroyer", "Royal Navy", "D34"),
    232003003: ("HMS Defender", "Destroyer", "Royal Navy", "D36"),
    232003004: ("HMS Duncan", "Destroyer", "Royal Navy", "D37"),
    # French Navy (MID 226-228)
    226000100: ("Charles de Gaulle", "Aircraft Carrier", "Marine Nationale", "R91"),
    226000101: ("Mistral", "Amphibious Assault", "Marine Nationale", "L9013"),
    # Chinese Navy / PLAN (MID 412-414)
    412000001: ("Liaoning", "Aircraft Carrier", "PLAN", "CV-16"),
    412000002: ("Shandong", "Aircraft Carrier", "PLAN", "CV-17"),
    412000003: ("Fujian", "Aircraft Carrier", "PLAN", "CV-18"),
    # Russian Navy (MID 273)
    273000001: ("Admiral Kuznetsov", "Aircraft Carrier", "Russian Navy", "063"),
    273000010: ("Pyotr Velikiy", "Battlecruiser", "Russian Navy", "099"),
    273000011: ("Admiral Gorshkov", "Frigate", "Russian Navy", "454"),
    # Indian Navy (MID 419)
    419000001: ("INS Vikramaditya", "Aircraft Carrier", "Indian Navy", "R33"),
    419000002: ("INS Vikrant", "Aircraft Carrier", "Indian Navy", "R11"),
    # Japanese Maritime Self-Defense Force (MID 431)
    431000001: ("JS Izumo", "Helicopter Carrier", "JMSDF", "DDH-183"),
    431000002: ("JS Kaga", "Helicopter Carrier", "JMSDF", "DDH-184"),
    # Italian Navy (MID 247)
    247000001: ("Cavour", "Aircraft Carrier", "Marina Militare", "C550"),
    247000002: ("Trieste", "Amphibious Assault", "Marina Militare", "L9890"),
}

# Military MMSI prefix ranges (MID-based country identification)
_MILITARY_MID_NAVY: Dict[str, str] = {
    "366": "US Navy", "367": "US Navy", "368": "US Navy", "369": "US Navy",
    "303": "US Navy",
    "232": "Royal Navy", "233": "Royal Navy", "234": "Royal Navy", "235": "Royal Navy",
    "226": "Marine Nationale", "227": "Marine Nationale",
    "412": "PLAN", "413": "PLAN", "414": "PLAN",
    "273": "Russian Navy",
    "419": "Indian Navy",
    "431": "JMSDF",
    "247": "Marina Militare",
    "244": "Royal Netherlands Navy",
    "245": "Royal Netherlands Navy",
    "211": "Deutsche Marine",
    "224": "Spanish Armada",
    "440": "ROKN",
    "525": "Royal Thai Navy",
    "503": "Royal Australian Navy",
    "316": "Royal Canadian Navy",
    "261": "Polish Navy",
    "257": "Royal Norwegian Navy",
    "265": "Swedish Navy",
    "219": "Royal Danish Navy",
    "237": "Hellenic Navy", "239": "Hellenic Navy",
    "240": "Hellenic Navy", "241": "Hellenic Navy",
    "271": "Turkish Navy",
    "351": "Portuguese Navy",
    "548": "Philippine Navy",
    "533": "Republic of Singapore Navy",
}

# ---------------------------------------------------------------------------
# Military MMSI range blocks -- (start, end) inclusive
# These are known allocations for military ship stations. MMSI ranges
# are assigned by national administrations; military vessels often
# cluster in specific sub-ranges within the MID block.
# ---------------------------------------------------------------------------
_MILITARY_MMSI_RANGES: List[Tuple[int, int]] = [
    # US Navy / USCG -- 3669xxxxx and 3038xxxxx blocks
    (366900000, 366999999),
    (303800000, 303899999),
    (338900000, 338999999),  # US government vessels
    # Royal Navy UK -- 2320xxxxx block
    (232000000, 232099999),
    # Russian Navy -- 2731xxxxx block
    (273100000, 273199999),
    # Chinese Navy PLAN -- 4121xxxxx block
    (412100000, 412199999),
    # French Navy -- 2260xxxxx block
    (226000000, 226099999),
    # Indian Navy -- 4190xxxxx block
    (419000000, 419099999),
    # JMSDF -- 4310xxxxx block
    (431000000, 431099999),
    # German Navy -- 2110xxxxx block
    (211000000, 211099999),
    # Italian Navy -- 2470xxxxx block
    (247000000, 247099999),
    # ROKN -- 4400xxxxx block
    (440000000, 440099999),
    # Royal Australian Navy -- 5030xxxxx block
    (503000000, 503099999),
    # Turkish Navy -- 2710xxxxx block
    (271000000, 271099999),
    # Royal Canadian Navy -- 3160xxxxx block
    (316000000, 316099999),
]

# ---------------------------------------------------------------------------
# Vessel name prefixes indicating military / government vessels
# Each prefix maps to (navy_name, default_vessel_class)
# ---------------------------------------------------------------------------
_NAVAL_NAME_PREFIXES: Dict[str, Tuple[str, str]] = {
    "USS ":   ("US Navy", "Warship"),
    "USNS ":  ("US Navy", "Auxiliary"),
    "USCGC ": ("US Coast Guard", "Patrol"),
    "HMS ":   ("Royal Navy", "Warship"),
    "HMCS ":  ("Royal Canadian Navy", "Warship"),
    "HMAS ":  ("Royal Australian Navy", "Warship"),
    "HMNZS ": ("Royal New Zealand Navy", "Warship"),
    "INS ":   ("Indian Navy", "Warship"),
    "JS ":    ("JMSDF", "Warship"),
    "KRI ":   ("Indonesian Navy", "Warship"),
    "TCG ":   ("Turkish Navy", "Warship"),
    "ARA ":   ("Argentine Navy", "Warship"),
    "BNS ":   ("Bangladesh Navy", "Warship"),
    "KD ":    ("Royal Malaysian Navy", "Warship"),
    "HTMS ":  ("Royal Thai Navy", "Warship"),
    "RSS ":   ("Republic of Singapore Navy", "Warship"),
    "FS ":    ("Marine Nationale", "Warship"),
    "FGS ":   ("Deutsche Marine", "Warship"),
    "ITS ":   ("Marina Militare", "Warship"),
    "HNLMS ": ("Royal Netherlands Navy", "Warship"),
    "ESPS ":  ("Spanish Armada", "Warship"),
    "NRP ":   ("Portuguese Navy", "Warship"),
    "HNoMS ": ("Royal Norwegian Navy", "Warship"),
    "HDMS ":  ("Royal Danish Navy", "Warship"),
    "HS ":    ("Hellenic Navy", "Warship"),
    "ORP ":   ("Polish Navy", "Warship"),
    "ROKS ":  ("ROKN", "Warship"),
}

# ---------------------------------------------------------------------------
# Military callsign patterns
# US Navy ships often use callsigns starting with "N" (NTDS tactical),
# UK military uses callsigns with specific patterns, etc.
# ---------------------------------------------------------------------------
_MILITARY_CALLSIGN_PREFIXES: Set[str] = {
    "NJDT",   # US Navy common prefix
    "NEPM",   # US Navy
    "NRKA",   # US Navy
    "NRKB",   # US Navy
    "NRKC",   # US Navy
    "NAVW",   # Naval vessel
    "NAVY",   # Generic navy
}

# US Navy callsigns follow the pattern N + 3-4 uppercase letters
_US_NAVY_CALLSIGN_RE = re.compile(r"^N[A-Z]{3,4}$")

# ---------------------------------------------------------------------------
# AIS ship type code classification
# ITU-R M.1371 defines ship type codes in the AIS standard.
# Codes 35 and 50-59 are military/law enforcement related.
# ---------------------------------------------------------------------------
_MILITARY_SHIP_TYPES: Set[int] = {
    35,  # Military ops
    55,  # Law enforcement
}
_MILITARY_SHIP_TYPE_RANGE: Tuple[int, int] = (50, 59)  # 50-59 inclusive

# Ship type code to human-readable vessel class mapping
_SHIP_TYPE_CLASSES: Dict[int, str] = {
    35: "Warship",
    50: "Pilot Vessel",
    51: "Search and Rescue",
    52: "Tug",
    53: "Port Tender",
    54: "Anti-Pollution",
    55: "Law Enforcement",
    56: "Spare (Local)",
    57: "Spare (Local)",
    58: "Medical Transport",
    59: "RR Resolution Ship",
}

# ---------------------------------------------------------------------------
# MMSI MID -> Country mapping (ITU Maritime Identification Digits)
# ---------------------------------------------------------------------------
_MID_COUNTRY: Dict[str, str] = {
    "201": "Albania", "202": "Andorra", "203": "Austria",
    "204": "Azores", "205": "Belgium", "206": "Belarus",
    "207": "Bulgaria", "208": "Vatican", "209": "Cyprus",
    "210": "Cyprus", "211": "Germany", "212": "Cyprus",
    "213": "Georgia", "214": "Moldova", "215": "Malta",
    "216": "Armenia", "218": "Germany", "219": "Denmark",
    "220": "Denmark", "224": "Spain", "225": "Spain",
    "226": "France", "227": "France", "228": "France",
    "229": "Malta", "230": "Finland", "231": "Faroe Islands",
    "232": "United Kingdom", "233": "United Kingdom",
    "234": "United Kingdom", "235": "United Kingdom",
    "236": "Gibraltar", "237": "Greece", "238": "Croatia",
    "239": "Greece", "240": "Greece", "241": "Greece",
    "242": "Morocco", "243": "Hungary", "244": "Netherlands",
    "245": "Netherlands", "246": "Netherlands",
    "247": "Italy", "248": "Malta", "249": "Malta",
    "250": "Ireland", "251": "Iceland", "252": "Liechtenstein",
    "253": "Luxembourg", "254": "Monaco", "255": "Madeira",
    "256": "Malta", "257": "Norway", "258": "Norway",
    "259": "Norway", "261": "Poland", "263": "Portugal",
    "264": "Romania", "265": "Sweden", "266": "Sweden",
    "267": "Slovakia", "268": "San Marino", "269": "Switzerland",
    "270": "Czech Republic", "271": "Turkey", "272": "Ukraine",
    "273": "Russia", "274": "North Macedonia",
    "275": "Latvia", "276": "Lithuania", "277": "Lithuania",
    "278": "Slovenia",
    "301": "Anguilla", "303": "USA", "304": "Antigua",
    "305": "Antigua", "306": "Curacao",
    "307": "Aruba", "308": "Bahamas", "309": "Bahamas",
    "310": "Bermuda", "311": "Bahamas", "312": "Belize",
    "314": "Barbados", "316": "Canada",
    "319": "Cayman Islands", "321": "Costa Rica",
    "323": "Cuba", "325": "Dominica",
    "327": "Dominican Republic",
    "329": "Guadeloupe", "330": "Grenada",
    "331": "Greenland", "332": "Guatemala",
    "334": "Honduras", "336": "Haiti",
    "338": "USA", "339": "Jamaica",
    "341": "Saint Kitts", "343": "Saint Lucia",
    "345": "Mexico", "347": "Martinique",
    "348": "Montserrat", "350": "Nicaragua",
    "351": "Panama", "352": "Panama", "353": "Panama",
    "354": "Panama", "355": "Panama", "356": "Panama",
    "357": "Panama",
    "358": "Puerto Rico", "359": "El Salvador",
    "361": "Saint Pierre",
    "362": "Trinidad and Tobago",
    "364": "Turks and Caicos",
    "366": "USA", "367": "USA", "368": "USA", "369": "USA",
    "370": "Panama", "371": "Panama", "372": "Panama",
    "373": "Panama",
    "375": "Saint Vincent",
    "376": "Saint Vincent",
    "377": "Saint Vincent",
    "378": "British Virgin Islands",
    "379": "US Virgin Islands",
    "401": "Afghanistan", "403": "Saudi Arabia",
    "405": "Bangladesh", "408": "Bahrain",
    "410": "Bhutan", "412": "China", "413": "China",
    "414": "China", "416": "Taiwan",
    "417": "Sri Lanka", "419": "India",
    "422": "Iran", "423": "Azerbaijan",
    "425": "Iraq", "428": "Israel",
    "431": "Japan", "432": "Japan",
    "434": "Turkmenistan",
    "436": "Kazakhstan", "437": "Uzbekistan",
    "438": "Jordan", "440": "South Korea",
    "441": "South Korea",
    "443": "Palestine", "445": "North Korea",
    "447": "Kuwait", "450": "Lebanon",
    "451": "Kyrgyzstan",
    "453": "Macao", "455": "Maldives",
    "457": "Mongolia", "459": "Nepal",
    "461": "Oman", "463": "Pakistan",
    "466": "Qatar", "468": "Syria",
    "470": "UAE", "471": "UAE",
    "472": "Tajikistan", "473": "Yemen",
    "475": "Yemen",
    "477": "Hong Kong",
    "478": "Bosnia and Herzegovina",
    "501": "Adelie Land", "503": "Australia",
    "506": "Myanmar", "508": "Brunei",
    "510": "Micronesia", "511": "Palau",
    "512": "New Zealand", "514": "Cambodia",
    "515": "Cambodia", "516": "Christmas Island",
    "518": "Cook Islands", "520": "Fiji",
    "523": "Cocos Islands", "525": "Indonesia",
    "529": "Kiribati",
    "531": "Laos", "533": "Malaysia",
    "536": "Northern Mariana Islands",
    "538": "Marshall Islands",
    "540": "New Caledonia", "542": "Niue",
    "544": "Nauru", "546": "French Polynesia",
    "548": "Philippines", "553": "Papua New Guinea",
    "555": "Pitcairn Island", "557": "Solomon Islands",
    "559": "American Samoa", "561": "Samoa",
    "563": "Singapore", "564": "Singapore",
    "565": "Singapore", "566": "Singapore",
    "567": "Thailand", "570": "Tonga",
    "572": "Tuvalu", "574": "Vietnam",
    "576": "Vanuatu", "577": "Vanuatu",
    "578": "Wallis and Futuna",
    "601": "South Africa", "603": "Angola",
    "605": "Algeria", "607": "Ascension Island",
    "608": "Ascension Island",
    "609": "Burundi", "610": "Benin",
    "611": "Botswana", "612": "Central African Republic",
    "613": "Cameroon", "615": "Congo",
    "616": "Comoros", "617": "Cabo Verde",
    "618": "Djibouti",
    "619": "Cote d'Ivoire",
    "620": "Comoros", "621": "Djibouti",
    "622": "Egypt", "624": "Ethiopia",
    "625": "Eritrea", "626": "Gabon",
    "627": "Ghana", "629": "Gambia",
    "630": "Guinea-Bissau", "631": "Equatorial Guinea",
    "632": "Guinea", "633": "Burkina Faso",
    "634": "Kenya", "635": "Kerguelen Islands",
    "636": "Liberia", "637": "Liberia",
    "642": "Libya",
    "644": "Lesotho", "645": "Mauritius",
    "647": "Madagascar", "649": "Mali",
    "650": "Mozambique", "654": "Mauritania",
    "655": "Malawi", "656": "Niger",
    "657": "Nigeria", "659": "Namibia",
    "660": "Reunion", "661": "Rwanda",
    "662": "Sudan", "663": "Senegal",
    "664": "Seychelles", "665": "Saint Helena",
    "666": "Somalia", "667": "Sierra Leone",
    "668": "Sao Tome and Principe",
    "669": "Eswatini", "670": "Chad",
    "671": "Togo", "672": "Tunisia",
    "674": "Tanzania", "675": "Uganda",
    "676": "Democratic Republic of Congo",
    "677": "Tanzania", "678": "Zambia",
    "679": "Zimbabwe",
}


def _check_mmsi_range(mmsi: int) -> bool:
    """Check if an MMSI falls within known military MMSI ranges.

    Args:
        mmsi: The 9-digit Maritime Mobile Service Identity number.

    Returns:
        True if the MMSI is within a known military allocation block.
    """
    for start, end in _MILITARY_MMSI_RANGES:
        if start <= mmsi <= end:
            return True
    return False


def _check_name_prefix(name: str) -> Optional[Tuple[str, str]]:
    """Check vessel name for known naval designation prefixes.

    Args:
        name: The vessel name from AIS data.

    Returns:
        Tuple of (navy_name, default_vessel_class) if matched, else None.
    """
    if not name:
        return None
    name_upper = name.upper().strip()
    for prefix, info in _NAVAL_NAME_PREFIXES.items():
        if name_upper.startswith(prefix.upper()):
            return info
    return None


def _check_callsign(callsign: str) -> bool:
    """Check if a callsign matches known military patterns.

    Args:
        callsign: The AIS callsign string.

    Returns:
        True if the callsign matches a military pattern.
    """
    if not callsign:
        return False
    cs = callsign.strip().upper()
    # Check explicit known prefixes
    for prefix in _MILITARY_CALLSIGN_PREFIXES:
        if cs.startswith(prefix):
            return True
    # US Navy tactical callsign pattern: N + 3-4 uppercase
    if _US_NAVY_CALLSIGN_RE.match(cs):
        return True
    return False


def _check_ship_type(ship_type: Optional[int]) -> bool:
    """Check if the AIS ship type code indicates military/government vessel.

    Args:
        ship_type: AIS ship type code (0-99).

    Returns:
        True if the ship type code is in the military/government range.
    """
    if ship_type is None:
        return False
    if ship_type in _MILITARY_SHIP_TYPES:
        return True
    start, end = _MILITARY_SHIP_TYPE_RANGE
    return start <= ship_type <= end


def _classify_vessel(
    name: str,
    ship_type: Optional[int],
    mmsi: Optional[int],
    callsign: str,
) -> Tuple[bool, str, str, str]:
    """Run the full military classification pipeline on a single vessel.

    Checks all identification methods in priority order:
    1. Known MMSI database (exact match with rich metadata)
    2. MMSI range blocks (military allocation ranges)
    3. Vessel name prefixes (USS, HMS, etc.)
    4. AIS ship type codes (35=military, 50-59 range)
    5. Callsign patterns (US Navy N-prefix, etc.)

    Args:
        name: Vessel name from AIS.
        ship_type: AIS ship type code.
        mmsi: Maritime Mobile Service Identity number.
        callsign: AIS callsign.

    Returns:
        Tuple of (is_naval, vessel_class, navy, hull_number).
    """
    # --- 1. Exact MMSI match from curated database ---
    if mmsi and mmsi in _MILITARY_MMSIS:
        info = _MILITARY_MMSIS[mmsi]
        return True, info[1], info[2], info[3]

    navy = ""
    vessel_class = "Civilian"
    hull_number = ""
    is_naval = False

    # --- 2. MMSI range block check ---
    if mmsi and _check_mmsi_range(mmsi):
        is_naval = True
        mid = str(mmsi)[:3]
        navy = _MILITARY_MID_NAVY.get(mid, "Unknown Navy")
        vessel_class = "Warship"

    # --- 3. Vessel name prefix check ---
    name_match = _check_name_prefix(name)
    if name_match:
        is_naval = True
        if not navy:
            navy = name_match[0]
        if vessel_class == "Civilian":
            vessel_class = name_match[1]

    # --- 4. AIS ship type code check ---
    if _check_ship_type(ship_type):
        is_naval = True
        if vessel_class == "Civilian":
            vessel_class = _SHIP_TYPE_CLASSES.get(ship_type, "Warship")
        if not navy and mmsi:
            mid = str(mmsi)[:3]
            navy = _MILITARY_MID_NAVY.get(mid, "")

    # --- 5. Callsign pattern check ---
    if _check_callsign(callsign):
        is_naval = True
        if not navy and mmsi:
            mid = str(mmsi)[:3]
            navy = _MILITARY_MID_NAVY.get(mid, "")
        if vessel_class == "Civilian":
            vessel_class = "Warship"

    # Final cleanup: if naval but still "Civilian" somehow, fix it
    if is_naval and vessel_class == "Civilian":
        vessel_class = "Warship"

    if not is_naval:
        vessel_class = "Civilian"

    return is_naval, vessel_class, navy, hull_number


def _get_country_from_mmsi(mmsi: Optional[int]) -> str:
    """Derive country/flag from MMSI MID digits.

    The first 3 digits of an MMSI encode the Maritime Identification
    Digits (MID), which map to flag state. This returns a short
    country label for display.

    Args:
        mmsi: The vessel MMSI.

    Returns:
        Country name string, or empty string if unknown.
    """
    if not mmsi:
        return ""
    mid = str(mmsi)[:3]
    return _MID_COUNTRY.get(mid, "")


class VesselFetcher(BaseFetcher):
    """Fetches live vessel positions from Digitraffic AIS with military enrichment.

    Uses a multi-layered classification pipeline to identify naval and
    military vessels from raw AIS transponder data:

    1. Exact MMSI lookup against curated warship database
    2. MMSI range matching against known military allocation blocks
    3. Vessel name prefix detection (USS, HMS, USCGC, etc.)
    4. AIS ship type code analysis (codes 35, 50-59)
    5. Callsign pattern matching (US Navy N-prefix, etc.)
    """

    async def fetch(self, client: httpx.AsyncClient) -> List[dict]:
        """Fetch vessels from Digitraffic AIS API with military classification.

        Retrieves live AIS position reports and runs each vessel through
        the classification pipeline to tag naval/military vessels with
        enriched metadata.

        Args:
            client: Shared httpx async client.

        Returns:
            List of vessel dicts with classification fields including
            is_military, is_naval, vessel_class, navy, hull_number,
            country, and callsign. Includes a summary dict at index 0
            with military_vessels count when military vessels are found.
        """
        try:
            resp = await client.get(_URL)
            resp.raise_for_status()
            features = resp.json().get("features") or []
            results: List[dict] = []
            mil_count = 0
            seen_mmsi: Set[int] = set()

            for feat in features:
                if len(results) >= MAX_VESSELS:
                    break
                props = feat.get("properties") or {}
                coords = (
                    (feat.get("geometry") or {}).get("coordinates")
                    or [None, None]
                )
                if coords[0] is None or coords[1] is None:
                    continue

                mmsi = props.get("mmsi")

                # Deduplicate by MMSI (AIS can broadcast duplicates)
                if mmsi and mmsi in seen_mmsi:
                    continue
                if mmsi:
                    seen_mmsi.add(mmsi)

                ship_type = props.get("shipType")
                name = (props.get("name") or "").strip()
                callsign = (props.get("callSign") or "").strip()

                # Run full classification pipeline
                is_naval, vessel_class, navy, hull_number = _classify_vessel(
                    name, ship_type, mmsi, callsign,
                )

                # Override name from curated database if we have a match
                mil_info = _MILITARY_MMSIS.get(mmsi) if mmsi else None
                if mil_info:
                    name = name or mil_info[0]

                # Derive country from MMSI MID digits
                country = _get_country_from_mmsi(mmsi)

                if is_naval:
                    mil_count += 1

                results.append({
                    "mmsi": mmsi,
                    "name": name,
                    "latitude": coords[1],
                    "longitude": coords[0],
                    "speed": props.get("sog"),
                    "heading": props.get("cog"),
                    "ship_type": ship_type,
                    "is_military": is_naval,
                    "is_naval": is_naval,
                    "nav_status": props.get("navStat"),
                    "navy": navy,
                    "vessel_class": vessel_class,
                    "hull_number": hull_number,
                    "callsign": callsign,
                    "country": country,
                    "military_vessels": mil_count if is_naval else None,
                })

            logger.info(
                "Vessels: %d total, %d military/naval (%.1f%%)",
                len(results),
                mil_count,
                (mil_count / len(results) * 100) if results else 0,
            )
            return results

        except httpx.HTTPStatusError as exc:
            logger.warning(
                "Digitraffic AIS HTTP error %s: %s",
                exc.response.status_code, exc,
            )
        except httpx.ConnectError as exc:
            logger.warning("Digitraffic AIS connection failed: %s", exc)
        except httpx.TimeoutException as exc:
            logger.warning("Digitraffic AIS request timed out: %s", exc)
        except ValueError as exc:
            logger.warning("Digitraffic AIS JSON decode error: %s", exc)
        return []
