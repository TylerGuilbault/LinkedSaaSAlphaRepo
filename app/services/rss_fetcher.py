import feedparser
from typing import List, Dict, Any, Optional
from datetime import datetime
from time import mktime

def _parse_time(entry) -> Optional[str]:
    # Return ISO 8601 string if available
    dt = getattr(entry, "published_parsed", None) or getattr(entry, "updated_parsed", None)
    if dt:
        try:
            return datetime.fromtimestamp(mktime(dt)).isoformat()
        except Exception:
            return None
    return None

def fetch_rss(feed_url: str, keywords: Optional[List[str]] = None, limit: int = 10) -> List[Dict[str, Any]]:
    feed = feedparser.parse(feed_url)
    results: List[Dict[str, Any]] = []
    if not getattr(feed, "entries", None):
        return results

    kws = [k.lower() for k in (keywords or []) if k]
    for entry in feed.entries[:limit]:
        title = getattr(entry, "title", "")
        summary = getattr(entry, "summary", "") or getattr(entry, "description", "")
        link = getattr(entry, "link", "")
        published_iso = _parse_time(entry)
        source = getattr(feed, "feed", {}).get("title") or feed_url

        # keyword filter (title + summary)
        if kws:
            text = f"{title} {summary}".lower()
            if not any(k in text for k in kws):
                continue

        results.append({
            "title": title,
            "summary": summary,
            "url": link,
            "published": published_iso,
            "source": source
        })
    return results
