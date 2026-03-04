"""Reddit OSINT feed fetcher — scrapes conflict/geopolitics subreddits for geolocated intelligence.

Uses Reddit's public JSON API (no OAuth required). Geocodes post titles
against conflict zones and country names to place them on the map.
"""

from __future__ import annotations

import logging
import re
from typing import List, Tuple, Optional

import httpx

from ..utils import COUNTRY_COORDS
from .base import BaseFetcher
from .conflict_zones import CONFLICT_ZONES as _CONFLICT_ZONES

logger = logging.getLogger("agus.fetchers")

# Subreddits to scrape, ordered by OSINT relevance
# (subreddit, category, posts_per_sub)
_SUBREDDITS = [
    # Tier 1: High-volume global intelligence
    ("worldnews", "breaking", 100),
    ("CombatFootage", "conflict", 50),
    ("UkraineWarVideoReport", "conflict", 50),
    ("geopolitics", "geopolitics", 50),
    ("CredibleDefense", "military", 30),
    # Tier 2: Regional conflict coverage
    ("syriancivilwar", "conflict", 30),
    ("IsraelPalestine", "conflict", 30),
    ("UkrainianConflict", "conflict", 30),
    ("yemen", "conflict", 25),
    ("africa", "conflict", 25),
    # Tier 3: Military & defense
    ("Military", "military", 20),
    ("LessCredibleDefence", "military", 20),
    ("WarCollege", "military", 20),
    ("Intelligence", "intelligence", 20),
    ("NationalSecurity", "geopolitics", 20),
    # Tier 4: Cyber & OSINT
    ("netsec", "cyber", 15),
    ("cybersecurity", "cyber", 15),
    ("OSINT", "intelligence", 15),
]

# Build sorted country list for title geocoding (longest name first)
_REGION_KEYWORDS = sorted(
    ((k, v) for k, v in COUNTRY_COORDS.items() if len(k) > 2),
    key=lambda x: -len(x[0]),
)


def _geocode_headline(title: str) -> Optional[Tuple[float, float, str]]:
    """Try to extract coordinates from a headline by matching location names.

    Args:
        title: Post title text to geocode.

    Returns:
        Tuple of (lat, lon, location_name) or None if no match.
    """
    title_lower = title.lower()

    # Check conflict zone keywords first (more specific)
    for zone, (lat, lon) in sorted(_CONFLICT_ZONES.items(), key=lambda x: -len(x[0])):
        if zone in title_lower:
            return lat, lon, zone.title()

    # Check country names
    for name, coords in _REGION_KEYWORDS:
        if name.lower() in title_lower:
            return coords[0], coords[1], name

    return None


def _clean_html(text: str) -> str:
    """Strip HTML tags and decode entities from Reddit text."""
    text = re.sub(r'<[^>]+>', '', text)
    text = text.replace('&amp;', '&').replace('&lt;', '<').replace('&gt;', '>')
    text = text.replace('&quot;', '"').replace('&#39;', "'")
    return text.strip()


class RedditOSINTFetcher(BaseFetcher):
    """Fetches and geolocates OSINT from Reddit conflict/geopolitics subreddits.

    Uses Reddit's public JSON API (no authentication). Posts are geocoded
    by matching titles against conflict zones and country names.
    """

    async def fetch(self, client: httpx.AsyncClient) -> List[dict]:
        """Fetch posts from OSINT subreddits and geocode them.

        Args:
            client: Shared httpx client (not used — we create a dedicated one).

        Returns:
            List of geolocated Reddit OSINT items.
        """
        results: List[dict] = []
        seen_titles: set = set()

        async with httpx.AsyncClient(
            timeout=httpx.Timeout(connect=10.0, read=20.0, write=5.0, pool=10.0),
            follow_redirects=True,
            headers={
                "User-Agent": "AgusOSINT/2.0 (OSINT intelligence platform; contact@agus.dev)",
                "Accept": "application/json",
            },
        ) as reddit_client:
            for subreddit, category, limit in _SUBREDDITS:
                try:
                    resp = await reddit_client.get(
                        f"https://www.reddit.com/r/{subreddit}/hot.json",
                        params={"limit": str(limit), "raw_json": "1"},
                    )
                    if resp.status_code == 429:
                        logger.debug("Reddit rate limited on r/%s", subreddit)
                        continue
                    if resp.status_code != 200:
                        continue

                    data = resp.json()
                    children = data.get("data", {}).get("children", [])

                    for child in children:
                        post = child.get("data", {})
                        title = (post.get("title") or "").strip()
                        if not title:
                            continue

                        # Dedup by normalized title
                        title_key = re.sub(r'\s+', ' ', title.lower())[:80]
                        if title_key in seen_titles:
                            continue
                        seen_titles.add(title_key)

                        # Geocode: try title first, then selftext
                        selftext = _clean_html(post.get("selftext") or "")
                        geo = _geocode_headline(title)
                        if not geo and selftext:
                            geo = _geocode_headline(selftext[:500])
                        if not geo:
                            continue

                        lat, lon, location = geo
                        score = post.get("score", 0)
                        num_comments = post.get("num_comments", 0)

                        # Severity based on score + comment engagement
                        if score > 5000 or num_comments > 500:
                            severity = "critical"
                        elif score > 1000 or num_comments > 100:
                            severity = "high"
                        elif score > 200 or num_comments > 30:
                            severity = "medium"
                        else:
                            severity = "low"

                        # Build permalink
                        permalink = post.get("permalink", "")
                        url = f"https://www.reddit.com{permalink}" if permalink else ""

                        # Capture the post's linked content URL (YouTube, Twitter, etc.)
                        content_url = post.get("url", "")
                        # Check for media (video/image)
                        has_media = bool(
                            post.get("is_video")
                            or post.get("media")
                            or content_url.endswith(('.jpg', '.png', '.gif', '.mp4'))
                            or any(d in content_url for d in [
                                "youtube.com", "youtu.be", "v.redd.it",
                                "streamable.com", "twitter.com", "x.com",
                            ])
                        )

                        results.append({
                            "title": _clean_html(title)[:200],
                            "latitude": lat,
                            "longitude": lon,
                            "location": location,
                            "channel": f"r/{subreddit}",
                            "category": category,
                            "severity": severity,
                            "date": "",
                            "url": url,
                            "media_url": content_url if content_url != url else "",
                            "source": f"Reddit r/{subreddit}",
                            "type": "reddit_osint",
                            "score": score,
                            "comments": num_comments,
                            "has_media": has_media,
                            "flair": post.get("link_flair_text", ""),
                        })
                except Exception as exc:
                    logger.debug("Reddit r/%s: %s", subreddit, exc)
                    continue

                # Rate limit: Reddit allows ~1 req/sec for unauthenticated
                import asyncio
                await asyncio.sleep(2.0)

        logger.info("Reddit OSINT: %d geolocated posts from %d subreddits",
                     len(results), len(_SUBREDDITS))
        return results
