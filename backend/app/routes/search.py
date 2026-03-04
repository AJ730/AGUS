"""YouTube / video search endpoint (GDELT DOC + cached OSINT mining)."""

from __future__ import annotations

import logging
import re

import httpx
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from ._helpers import _cache, _client, get_cached_items

logger = logging.getLogger("agus.routes")

router = APIRouter()


def _extract_youtube_id(url: str) -> str:
    """Extract YouTube video ID from URL."""
    patterns = [
        r'youtube\.com/watch\?v=([a-zA-Z0-9_-]{11})',
        r'youtu\.be/([a-zA-Z0-9_-]{11})',
        r'youtube\.com/embed/([a-zA-Z0-9_-]{11})',
    ]
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    return ""


@router.get("/youtube_search")
async def youtube_search(request: Request, q: str = ""):
    """Dynamic video search — crawls cached OSINT data for video URLs.

    Zero hardcoded channels. Acts like a worm:
    1. Mine video URLs from cached Reddit OSINT (posts link to YouTube, v.redd.it, etc.)
    2. Mine video URLs from cached Telegram OSINT article links
    3. Crawl GDELT DOC API dynamically for YouTube links matching the query
    4. Scan cached news/conflicts for related article URLs
    5. Try Piped/Invidious API as final fallback search
    """
    if not q.strip():
        return JSONResponse(content={"videos": [], "articles": []})

    client = _client(request)
    cache = _cache(request)
    videos: list = []
    articles: list = []
    seen_ids: set = set()
    seen_urls: set = set()
    query_lower = q.lower()
    q_words = [w for w in query_lower.split() if len(w) > 2]

    def _relevance_score(title: str) -> int:
        t = title.lower()
        return sum(1 for w in q_words if w in t)

    def _try_extract_video(url: str, title: str, source: str, date: str = "") -> bool:
        if not url:
            return False
        video_id = _extract_youtube_id(url)
        if video_id and video_id not in seen_ids:
            seen_ids.add(video_id)
            videos.append({
                "title": title[:200],
                "video_id": video_id,
                "url": f"https://www.youtube.com/watch?v={video_id}",
                "source": source,
                "date": date,
                "relevance": _relevance_score(title),
            })
            return True
        if any(d in url for d in ["v.redd.it", "streamable.com", "clips.twitch.tv"]):
            if url not in seen_urls:
                seen_urls.add(url)
                videos.append({
                    "title": title[:200],
                    "video_id": "",
                    "url": url,
                    "source": source,
                    "date": date,
                    "relevance": _relevance_score(title),
                })
                return True
        return False

    # Source 1: Mine Reddit OSINT cache
    reddit_items = get_cached_items(cache, "reddit_osint")
    for item in reddit_items:
        title = item.get("title", "")
        permalink = item.get("url", "")
        media_url = item.get("media_url", "")
        has_media = item.get("has_media", False)
        score = _relevance_score(title)

        if score >= 1 or (has_media and any(w in title.lower() for w in q_words)):
            if media_url:
                _try_extract_video(media_url, title, item.get("source", "Reddit"), item.get("date", ""))
            _try_extract_video(permalink, title, item.get("source", "Reddit"), item.get("date", ""))
            if permalink and permalink not in seen_urls and score >= 1:
                seen_urls.add(permalink)
                articles.append({
                    "title": title[:200],
                    "url": permalink,
                    "source": item.get("source", "Reddit"),
                    "date": item.get("date", ""),
                    "relevance": score,
                })

    # Source 2: Mine Telegram OSINT cache
    telegram_items = get_cached_items(cache, "telegram_osint")
    for item in telegram_items:
        title = item.get("title", "")
        url = item.get("url", "")
        score = _relevance_score(title)
        if score >= 1:
            _try_extract_video(url, title, item.get("source", "OSINT Feed"), item.get("date", ""))
            if url and "youtube" not in url and "youtu.be" not in url and url not in seen_urls:
                seen_urls.add(url)
                articles.append({
                    "title": title[:200],
                    "url": url,
                    "source": item.get("source", ""),
                    "date": item.get("date", ""),
                    "relevance": score,
                })

    # Source 3: Mine conflicts/news/missile_tests
    for layer in ["conflicts", "news", "missile_tests", "piracy"]:
        layer_items = get_cached_items(cache, layer)
        for item in layer_items[:100]:
            title = item.get("title") or item.get("event_type") or item.get("name", "")
            url = item.get("url") or item.get("source_url", "")
            score = _relevance_score(title)
            if score >= 1 and url:
                _try_extract_video(url, title, item.get("source", layer), item.get("date", ""))

    # Source 4: GDELT DOC API
    try:
        resp = await client.get(
            "http://api.gdeltproject.org/api/v2/doc/doc",
            params={
                "query": f"{q} sourcelang:english",
                "mode": "ArtList",
                "maxrecords": "75",
                "format": "json",
                "TIMESPAN": "14D",
            },
            timeout=20.0,
        )
        if resp.status_code == 200:
            data = resp.json()
            for art in (data.get("articles") or []):
                url = art.get("url", "")
                title = art.get("title", "")
                source = art.get("domain", "")
                date = art.get("seendate", "")
                _try_extract_video(url, title, source, date)
                if url not in seen_urls and "youtube" not in url:
                    seen_urls.add(url)
                    articles.append({
                        "title": title[:200],
                        "url": url,
                        "source": source,
                        "date": date,
                        "relevance": _relevance_score(title),
                    })
    except (httpx.HTTPError, httpx.TimeoutException, ValueError, KeyError) as exc:
        logger.debug("GDELT video search: %s", exc)

    # Source 5: GDELT TV API
    try:
        resp = await client.get(
            "http://api.gdeltproject.org/api/v2/tv/tv",
            params={
                "query": q,
                "mode": "clipgallery",
                "maxrecords": "20",
                "format": "json",
                "LAST24H": "YES",
            },
            timeout=15.0,
        )
        if resp.status_code == 200:
            data = resp.json()
            for clip in (data.get("clips") or []):
                preview_url = clip.get("preview_url", "")
                show = clip.get("show", "")
                station = clip.get("station", "")
                snippet = clip.get("snippet", "")[:200]

                if preview_url and preview_url not in seen_urls:
                    seen_urls.add(preview_url)
                    videos.append({
                        "title": f"{station}: {show}" if show else snippet,
                        "video_id": "",
                        "url": preview_url,
                        "source": station or "TV Broadcast",
                        "date": clip.get("date", ""),
                        "relevance": _relevance_score(snippet),
                    })
    except (httpx.HTTPError, httpx.TimeoutException, ValueError, KeyError) as exc:
        logger.debug("GDELT TV search: %s", exc)

    # Source 6: Piped/Invidious fallback
    if len(videos) < 5:
        piped_instances = [
            "https://pipedapi.kavin.rocks",
            "https://pipedapi.adminforge.de",
        ]
        for piped_url in piped_instances:
            if len(videos) >= 10:
                break
            try:
                resp = await client.get(
                    f"{piped_url}/search",
                    params={"q": q, "filter": "videos"},
                    timeout=8.0,
                )
                if resp.status_code == 200:
                    data = resp.json()
                    for item in (data.get("items") or []):
                        if item.get("type") != "stream":
                            continue
                        vid_url = item.get("url", "")
                        video_id = _extract_youtube_id(
                            f"https://youtube.com{vid_url}" if vid_url.startswith("/") else vid_url
                        )
                        if video_id and video_id not in seen_ids:
                            seen_ids.add(video_id)
                            videos.append({
                                "title": item.get("title", ""),
                                "video_id": video_id,
                                "url": f"https://www.youtube.com/watch?v={video_id}",
                                "source": item.get("uploaderName", "YouTube"),
                                "date": "",
                                "relevance": _relevance_score(item.get("title", "")),
                            })
                        if len(videos) >= 10:
                            break
            except (httpx.HTTPError, httpx.TimeoutException, ValueError, KeyError) as exc:
                logger.debug("Piped search %s: %s", piped_url, exc)

    # Sort by relevance
    videos.sort(key=lambda v: v.get("relevance", 0), reverse=True)
    articles.sort(key=lambda a: a.get("relevance", 0), reverse=True)

    for v in videos:
        v.pop("relevance", None)
    for a in articles:
        a.pop("relevance", None)

    logger.info("Video search '%s': %d videos, %d articles (from cached OSINT + GDELT)",
                q, len(videos), len(articles))

    return JSONResponse(content={
        "videos": videos[:20],
        "articles": articles[:15],
        "query": q,
        "sources_scanned": {
            "reddit_osint": len(reddit_items),
            "telegram_osint": len(telegram_items),
            "gdelt": True,
            "gdelt_tv": True,
        },
    })
