"""
Agus OSINT Backend -- Utilities
====================================
Shared helper functions and lookup tables used across multiple modules.
"""

from __future__ import annotations

from typing import Dict, Optional

# ---------------------------------------------------------------------------
# Country centroid lookup for ReliefWeb entries that lack explicit coordinates
# ---------------------------------------------------------------------------
COUNTRY_COORDS: Dict[str, tuple] = {
    "Afghanistan": (33.93, 67.71), "Albania": (41.15, 20.17),
    "Algeria": (28.03, 1.66), "Angola": (-11.20, 17.87),
    "Argentina": (-38.42, -63.62), "Armenia": (40.07, 45.04),
    "Australia": (-25.27, 133.78), "Azerbaijan": (40.14, 47.58),
    "Bangladesh": (23.68, 90.36), "Belarus": (53.71, 27.95),
    "Belgium": (50.50, 4.47), "Benin": (9.31, 2.32),
    "Bolivia": (-16.29, -63.59), "Bosnia and Herzegovina": (43.92, 17.68),
    "Brazil": (-14.24, -51.93), "Burkina Faso": (12.24, -1.56),
    "Burundi": (-3.37, 29.92), "Cambodia": (12.57, 104.99),
    "Cameroon": (7.37, 12.35), "Canada": (56.13, -106.35),
    "Central African Republic": (6.61, 20.94),
    "Chad": (15.45, 18.73), "Chile": (-35.68, -71.54),
    "China": (35.86, 104.20), "Colombia": (4.57, -74.30),
    "Democratic Republic of the Congo": (-4.04, 21.76),
    "Republic of the Congo": (-0.23, 15.83),
    "Costa Rica": (9.75, -83.75), "Croatia": (45.10, 15.20),
    "Cuba": (21.52, -77.78), "Cyprus": (35.13, 33.43),
    "Czech Republic": (49.82, 15.47),
    "Denmark": (56.26, 9.50), "Djibouti": (11.83, 42.59),
    "Ecuador": (-1.83, -78.18), "Egypt": (26.82, 30.80),
    "El Salvador": (13.79, -88.90), "Eritrea": (15.18, 39.78),
    "Estonia": (58.60, 25.01), "Ethiopia": (9.15, 40.49),
    "Finland": (61.92, 25.75), "France": (46.23, 2.21),
    "Gabon": (-0.80, 11.61), "Gambia": (13.44, -15.31),
    "Georgia": (42.32, 43.36), "Germany": (51.17, 10.45),
    "Ghana": (7.95, -1.02), "Greece": (39.07, 21.82),
    "Guatemala": (15.78, -90.23), "Guinea": (9.95, -9.70),
    "Guinea-Bissau": (11.80, -15.18), "Haiti": (18.97, -72.29),
    "Honduras": (15.20, -86.24), "Hungary": (47.16, 19.50),
    "India": (20.59, 78.96), "Indonesia": (-0.79, 113.92),
    "Iran": (32.43, 53.69), "Iraq": (33.22, 43.68),
    "Ireland": (53.14, -7.69), "Israel": (31.05, 34.85),
    "Italy": (41.87, 12.57), "Ivory Coast": (7.54, -5.55),
    "Jamaica": (18.11, -77.30), "Japan": (36.20, 138.25),
    "Jordan": (30.59, 36.24), "Kazakhstan": (48.02, 66.92),
    "Kenya": (-0.02, 37.91), "Kosovo": (42.60, 20.90),
    "Kuwait": (29.31, 47.48), "Kyrgyzstan": (41.20, 74.77),
    "Laos": (19.86, 102.50), "Latvia": (56.88, 24.60),
    "Lebanon": (33.85, 35.86), "Lesotho": (-29.61, 28.23),
    "Liberia": (6.43, -9.43), "Libya": (26.34, 17.23),
    "Lithuania": (55.17, 23.88), "Madagascar": (-18.77, 46.87),
    "Malawi": (-13.25, 34.30), "Malaysia": (4.21, 101.98),
    "Mali": (17.57, -4.00), "Mauritania": (21.01, -10.94),
    "Mexico": (23.63, -102.55), "Moldova": (47.41, 28.37),
    "Mongolia": (46.86, 103.85), "Montenegro": (42.71, 19.37),
    "Morocco": (31.79, -7.09), "Mozambique": (-18.67, 35.53),
    "Myanmar": (21.91, 95.96), "Namibia": (-22.96, 18.49),
    "Nepal": (28.39, 84.12), "Netherlands": (52.13, 5.29),
    "New Zealand": (-40.90, 174.89), "Nicaragua": (12.87, -85.21),
    "Niger": (17.61, 8.08), "Nigeria": (9.08, 8.68),
    "North Korea": (40.34, 127.51), "North Macedonia": (41.51, 21.75),
    "Norway": (60.47, 8.47), "Oman": (21.51, 55.92),
    "Pakistan": (30.38, 69.35), "Palestine": (31.95, 35.23),
    "Panama": (8.54, -80.78), "Papua New Guinea": (-6.31, 143.96),
    "Paraguay": (-23.44, -58.44), "Peru": (-9.19, -75.02),
    "Philippines": (12.88, 121.77), "Poland": (51.92, 19.15),
    "Portugal": (39.40, -8.22), "Qatar": (25.35, 51.18),
    "Romania": (45.94, 24.97), "Russia": (61.52, 105.32),
    "Rwanda": (-1.94, 29.87), "Saudi Arabia": (23.89, 45.08),
    "Senegal": (14.50, -14.45), "Serbia": (44.02, 21.01),
    "Sierra Leone": (8.46, -11.78), "Slovakia": (48.67, 19.70),
    "Slovenia": (46.15, 14.99), "Somalia": (5.15, 46.20),
    "South Africa": (-30.56, 22.94), "South Korea": (35.91, 127.77),
    "South Sudan": (6.88, 31.31), "Spain": (40.46, -3.75),
    "Sri Lanka": (7.87, 80.77), "Sudan": (12.86, 30.22),
    "Sweden": (60.13, 18.64), "Switzerland": (46.82, 8.23),
    "Syria": (34.80, 38.00), "Taiwan": (23.70, 120.96),
    "Tajikistan": (38.86, 71.28), "Tanzania": (-6.37, 34.89),
    "Thailand": (15.87, 100.99), "Togo": (8.62, 1.21),
    "Trinidad and Tobago": (10.69, -61.22),
    "Tunisia": (33.89, 9.54), "Turkey": (38.96, 35.24),
    "Turkmenistan": (38.97, 59.56), "Uganda": (1.37, 32.29),
    "Ukraine": (48.38, 31.17), "United Arab Emirates": (23.42, 53.85),
    "United Kingdom": (55.38, -3.44), "United States": (37.09, -95.71),
    "Uruguay": (-32.52, -55.77), "Uzbekistan": (41.38, 64.59),
    "Venezuela": (6.42, -66.59), "Vietnam": (14.06, 108.28),
    "Yemen": (15.55, 48.52), "Zambia": (-13.13, 27.85),
    "Zimbabwe": (-19.02, 29.15),
    # Aliases / common alternate names
    "Dem. Rep. Congo": (-4.04, 21.76),
    "DRC": (-4.04, 21.76),
    "Cote d'Ivoire": (7.54, -5.55),
    "Turkiye": (38.96, 35.24),
    "occupied Palestinian territory": (31.95, 35.23),
    "State of Palestine": (31.95, 35.23),
    # ISO 3166-1 alpha-2 codes (used by OpenSanctions, UNHCR, etc.)
    "af": (33.93, 67.71), "al": (41.15, 20.17), "dz": (28.03, 1.66),
    "ao": (-11.20, 17.87), "ar": (-38.42, -63.62), "am": (40.07, 45.04),
    "au": (-25.27, 133.78), "az": (40.14, 47.58), "bd": (23.68, 90.36),
    "by": (53.71, 27.95), "be": (50.50, 4.47), "bj": (9.31, 2.32),
    "bo": (-16.29, -63.59), "ba": (43.92, 17.68), "br": (-14.24, -51.93),
    "bf": (12.24, -1.56), "bi": (-3.37, 29.92), "kh": (12.57, 104.99),
    "cm": (7.37, 12.35), "ca": (56.13, -106.35), "cf": (6.61, 20.94),
    "td": (15.45, 18.73), "cl": (-35.68, -71.54), "cn": (35.86, 104.20),
    "co": (4.57, -74.30), "cd": (-4.04, 21.76), "cg": (-0.23, 15.83),
    "cr": (9.75, -83.75), "hr": (45.10, 15.20), "cu": (21.52, -77.78),
    "cy": (35.13, 33.43), "cz": (49.82, 15.47), "dk": (56.26, 9.50),
    "dj": (11.83, 42.59), "ec": (-1.83, -78.18), "eg": (26.82, 30.80),
    "sv": (13.79, -88.90), "er": (15.18, 39.78), "ee": (58.60, 25.01),
    "et": (9.15, 40.49), "fi": (61.92, 25.75), "fr": (46.23, 2.21),
    "ga": (-0.80, 11.61), "gm": (13.44, -15.31), "ge": (42.32, 43.36),
    "de": (51.17, 10.45), "gh": (7.95, -1.02), "gr": (39.07, 21.82),
    "gt": (15.78, -90.23), "gn": (9.95, -9.70), "gw": (11.80, -15.18),
    "ht": (18.97, -72.29), "hn": (15.20, -86.24), "hu": (47.16, 19.50),
    "in": (20.59, 78.96), "id": (-0.79, 113.92), "ir": (32.43, 53.69),
    "iq": (33.22, 43.68), "ie": (53.14, -7.69), "il": (31.05, 34.85),
    "it": (41.87, 12.57), "ci": (7.54, -5.55), "jm": (18.11, -77.30),
    "jp": (36.20, 138.25), "jo": (30.59, 36.24), "kz": (48.02, 66.92),
    "ke": (-0.02, 37.91), "xk": (42.60, 20.90), "kw": (29.31, 47.48),
    "kg": (41.20, 74.77), "la": (19.86, 102.50), "lv": (56.88, 24.60),
    "lb": (33.85, 35.86), "ls": (-29.61, 28.23), "lr": (6.43, -9.43),
    "ly": (26.34, 17.23), "lt": (55.17, 23.88), "mg": (-18.77, 46.87),
    "mw": (-13.25, 34.30), "my": (4.21, 101.98), "ml": (17.57, -4.00),
    "mr": (21.01, -10.94), "mx": (23.63, -102.55), "md": (47.41, 28.37),
    "mn": (46.86, 103.85), "me": (42.71, 19.37), "ma": (31.79, -7.09),
    "mz": (-18.67, 35.53), "mm": (21.91, 95.96), "na": (-22.96, 18.49),
    "np": (28.39, 84.12), "nl": (52.13, 5.29), "nz": (-40.90, 174.89),
    "ni": (12.87, -85.21), "ne": (17.61, 8.08), "ng": (9.08, 8.68),
    "kp": (40.34, 127.51), "mk": (41.51, 21.75), "no": (60.47, 8.47),
    "om": (21.51, 55.92), "pk": (30.38, 69.35), "ps": (31.95, 35.23),
    "pa": (8.54, -80.78), "pg": (-6.31, 143.96), "py": (-23.44, -58.44),
    "pe": (-9.19, -75.02), "ph": (12.88, 121.77), "pl": (51.92, 19.15),
    "pt": (39.40, -8.22), "qa": (25.35, 51.18), "ro": (45.94, 24.97),
    "ru": (61.52, 105.32), "rw": (-1.94, 29.87), "sa": (23.89, 45.08),
    "sn": (14.50, -14.45), "rs": (44.02, 21.01), "sl": (8.46, -11.78),
    "sk": (48.67, 19.70), "si": (46.15, 14.99), "so": (5.15, 46.20),
    "za": (-30.56, 22.94), "kr": (35.91, 127.77), "ss": (6.88, 31.31),
    "es": (40.46, -3.75), "lk": (7.87, 80.77), "sd": (12.86, 30.22),
    "se": (60.13, 18.64), "ch": (46.82, 8.23), "sy": (34.80, 38.00),
    "tw": (23.70, 120.96), "tj": (38.86, 71.28), "tz": (-6.37, 34.89),
    "th": (15.87, 100.99), "tg": (8.62, 1.21), "tt": (10.69, -61.22),
    "tn": (33.89, 9.54), "tr": (38.96, 35.24), "tm": (38.97, 59.56),
    "ug": (1.37, 32.29), "ua": (48.38, 31.17), "ae": (23.42, 53.85),
    "gb": (55.38, -3.44), "us": (37.09, -95.71), "uy": (-32.52, -55.77),
    "uz": (41.38, 64.59), "ve": (6.42, -66.59), "vn": (14.06, 108.28),
    "ye": (15.55, 48.52), "zm": (-13.13, 27.85), "zw": (-19.02, 29.15),
}


def deep_get(d: dict, path: str, default=None):
    """Get a nested key from a dict using dot-separated path."""
    keys = path.split(".")
    val = d
    for k in keys:
        if isinstance(val, dict):
            val = val.get(k, default)
        else:
            return default
    return val


def resolve_country_coords(
    item: dict, country_field: str = "country"
) -> tuple:
    """Return (lat, lon) from a ReliefWeb-style item, using country centroid as fallback."""
    for lat_key, lon_key in [
        ("latitude", "longitude"),
        ("lat", "lon"),
        ("fields.primary_country.location.lat", "fields.primary_country.location.lon"),
    ]:
        lat = deep_get(item, lat_key)
        lon = deep_get(item, lon_key)
        if lat is not None and lon is not None:
            try:
                return float(lat), float(lon)
            except (ValueError, TypeError):
                pass

    country_name = ""
    country_data = deep_get(item, "fields.primary_country")
    if isinstance(country_data, dict):
        country_name = country_data.get("name", "")
    elif isinstance(country_data, str):
        country_name = country_data
    else:
        countries = deep_get(item, "fields.country")
        if isinstance(countries, list) and countries:
            first = countries[0]
            country_name = first.get("name", "") if isinstance(first, dict) else str(first)

    if country_name and country_name in COUNTRY_COORDS:
        return COUNTRY_COORDS[country_name]
    return (0.0, 0.0)
