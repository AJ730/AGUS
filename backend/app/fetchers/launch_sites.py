"""Launch site database for missile arc origin inference."""

from __future__ import annotations

# Actor/country → known launch sites: (lat, lon, name)
# Used to infer missile origins when ACLED only provides impact coordinates.

LAUNCH_SITES: dict[str, list[tuple[float, float, str]]] = {
    # Iran (priority)
    "iran": [
        (35.24, 51.42, "Parchin Military Complex"),
        (35.23, 53.92, "Semnan Space Center"),
        (32.65, 51.68, "Isfahan/Natanz"),
        (38.08, 46.30, "Tabriz Missile Base"),
        (29.62, 52.53, "Shiraz Air Base"),
        (27.18, 56.28, "Bandar Abbas Naval"),
        (34.31, 47.07, "Kermanshah Missile Base"),
        (33.49, 48.36, "Khorramabad"),
        (36.27, 59.61, "Mashhad Air Base"),
        (33.69, 51.68, "Shahrud Missile Test"),
    ],
    "irgc": [
        (35.24, 51.42, "Parchin/IRGC HQ"),
        (35.23, 53.92, "Semnan Launch"),
        (27.18, 56.28, "Bandar Abbas IRGC Naval"),
        (34.31, 47.07, "Kermanshah IRGC"),
    ],
    "hezbollah": [
        (33.86, 35.51, "Beirut/Dahieh"),
        (34.0, 36.2, "Baalbek"),
        (33.27, 35.2, "Southern Lebanon/Tyre"),
    ],
    "houthi": [
        (15.35, 44.21, "Sanaa"),
        (14.80, 42.95, "Hodeidah"),
        (15.50, 43.50, "Saada"),
    ],
    # Russia
    "russia": [
        (48.57, 45.62, "Kapustin Yar"),
        (62.93, 40.57, "Plesetsk Cosmodrome"),
        (45.92, 63.34, "Baikonur"),
        (51.77, 128.33, "Vostochny"),
        (64.58, 39.77, "Severodvinsk Naval"),
        (55.75, 37.62, "Moscow Region"),
        (44.95, 34.12, "Crimea"),
        (48.70, 44.52, "Volgograd"),
    ],
    # China
    "china": [
        (40.96, 100.29, "Jiuquan"),
        (28.25, 102.03, "Xichang"),
        (19.61, 110.95, "Wenchang"),
        (38.85, 111.61, "Taiyuan"),
        (40.00, 116.40, "Beijing Region"),
    ],
    # North Korea
    "north korea": [
        (39.66, 124.71, "Tongchang-ri/Sohae"),
        (40.85, 129.66, "Musudan-ri/Tonghae"),
        (39.02, 125.75, "Pyongyang"),
        (39.19, 127.07, "Wonsan"),
    ],
    "dprk": [
        (39.66, 124.71, "Tongchang-ri/Sohae"),
        (40.85, 129.66, "Musudan-ri/Tonghae"),
    ],
    # United States
    "united states": [
        (28.57, -80.65, "Cape Canaveral"),
        (34.73, -120.57, "Vandenberg SFB"),
        (32.38, -106.47, "White Sands"),
        (48.46, -97.86, "Grand Forks AFB"),
    ],
    "us": [
        (28.57, -80.65, "Cape Canaveral"),
        (34.73, -120.57, "Vandenberg SFB"),
    ],
    # Israel
    "israel": [
        (31.88, 34.68, "Palmachim Air Base"),
        (30.97, 34.67, "Negev/Sdot Micha"),
        (31.29, 34.27, "Hatzerim Air Base"),
    ],
    "idf": [
        (31.88, 34.68, "Palmachim"),
        (30.97, 34.67, "Sdot Micha"),
    ],
    # India
    "india": [
        (13.73, 80.23, "Sriharikota/Satish Dhawan"),
        (20.75, 86.92, "Abdul Kalam Island/Wheeler"),
        (17.26, 78.44, "Hyderabad DRDO"),
    ],
    # Pakistan
    "pakistan": [
        (28.30, 66.53, "Sonmiani"),
        (26.97, 68.35, "Tilla Test Range"),
        (33.60, 73.05, "Islamabad Region"),
    ],
    # France
    "france": [
        (5.24, -52.77, "Guiana Space Centre/Kourou"),
        (47.40, -4.28, "Ile Longue SSBN Base"),
    ],
    # UK
    "united kingdom": [
        (58.62, -4.95, "Cape Wrath Range"),
        (56.07, -5.73, "RNAD Coulport"),
    ],
    # Turkey
    "turkey": [
        (37.76, 30.00, "Aksehir Missile Base"),
        (39.93, 32.86, "Ankara Region"),
        (36.56, 32.00, "Sinop Test Range"),
    ],
    # Ukraine
    "ukraine": [
        (50.45, 30.52, "Kyiv Region"),
        (48.50, 35.00, "Dnipro/Pivdenne"),
        (46.62, 32.60, "Kherson Region"),
    ],
    # Saudi Arabia
    "saudi arabia": [
        (24.70, 46.68, "Riyadh/Al-Watah"),
        (21.43, 39.83, "Jeddah Region"),
        (28.38, 36.57, "Tabuk Air Base"),
    ],
    # Yemen (non-Houthi)
    "yemen": [
        (15.35, 44.21, "Sanaa"),
        (12.83, 45.01, "Aden"),
    ],
    # Syria
    "syria": [
        (33.51, 36.31, "Damascus"),
        (36.18, 37.22, "Aleppo"),
        (34.73, 36.72, "Homs"),
        (35.47, 35.95, "Latakia/Khmeimim"),
    ],
    # Hamas
    "hamas": [
        (31.52, 34.47, "Gaza City"),
        (31.35, 34.30, "Khan Younis"),
        (31.54, 34.48, "Jabalia"),
    ],
    # Islamic State / ISIS
    "islamic state": [
        (35.47, 44.39, "Mosul Region"),
        (35.33, 40.14, "Raqqa"),
        (34.45, 40.92, "Deir ez-Zor"),
    ],
    "isis": [
        (35.47, 44.39, "Mosul Region"),
        (35.33, 40.14, "Raqqa"),
    ],
    # Myanmar military
    "myanmar": [
        (19.76, 96.07, "Naypyidaw"),
        (16.87, 96.20, "Yangon"),
    ],
    # Ethiopia
    "ethiopia": [
        (9.02, 38.75, "Addis Ababa Region"),
        (13.50, 39.47, "Tigray/Mekelle"),
    ],
    # Sudan
    "sudan": [
        (15.60, 32.53, "Khartoum"),
        (19.17, 30.22, "Dongola Air Base"),
    ],
    "rsf": [
        (13.45, 22.44, "Darfur/El Geneina"),
        (13.63, 25.35, "Nyala"),
    ],
}

# Country centroid fallbacks (used when actor doesn't match above)
COUNTRY_CENTROIDS: dict[str, tuple[float, float]] = {
    "iran": (32.43, 53.69),
    "russia": (55.75, 37.62),
    "china": (39.90, 116.40),
    "north korea": (39.02, 125.75),
    "united states": (38.90, -77.04),
    "israel": (31.77, 35.22),
    "india": (28.61, 77.21),
    "pakistan": (33.69, 73.04),
    "france": (48.86, 2.35),
    "united kingdom": (51.51, -0.13),
    "turkey": (39.93, 32.86),
    "ukraine": (50.45, 30.52),
    "saudi arabia": (24.71, 46.68),
    "syria": (33.51, 36.31),
    "yemen": (15.35, 44.21),
    "iraq": (33.31, 44.37),
    "lebanon": (33.89, 35.50),
    "afghanistan": (34.53, 69.17),
    "libya": (32.90, 13.18),
    "somalia": (2.05, 45.34),
    "sudan": (15.60, 32.53),
    "ethiopia": (9.02, 38.75),
    "myanmar": (19.76, 96.07),
    "nigeria": (9.08, 7.49),
    "mali": (12.64, -8.00),
    "niger": (13.51, 2.11),
    "burkina faso": (12.37, -1.52),
    "chad": (12.13, 15.06),
    "congo": (-4.32, 15.32),
    "drc": (-4.32, 15.32),
    "cameroon": (3.87, 11.52),
    "mozambique": (-25.97, 32.58),
    "palestine": (31.90, 35.20),
    "gaza": (31.52, 34.47),
    "west bank": (31.95, 35.25),
}


def infer_origin(actor: str, country: str) -> tuple[float, float, str, str] | None:
    """Infer launch origin from actor name and country.

    Returns (lat, lon, site_name, confidence) or None.
    Confidence: 'confirmed' (exact actor match), 'inferred' (country match), None.
    """
    actor_lower = (actor or "").lower().strip()
    country_lower = (country or "").lower().strip()

    # Try exact actor match first
    for key, sites in LAUNCH_SITES.items():
        if key in actor_lower or actor_lower in key:
            site = sites[0]  # Use primary launch site
            return site[0], site[1], site[2], "confirmed"

    # Try country match
    for key, sites in LAUNCH_SITES.items():
        if key == country_lower:
            site = sites[0]
            return site[0], site[1], site[2], "inferred"

    # Fallback to country centroid
    centroid = COUNTRY_CENTROIDS.get(country_lower)
    if centroid:
        return centroid[0], centroid[1], f"{country} (approx)", "inferred"

    return None
