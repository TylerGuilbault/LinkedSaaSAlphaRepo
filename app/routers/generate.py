from fastapi import APIRouter, Query
from typing import List, Optional, Dict, Any
from app.services.rss_fetcher import fetch_rss

router = APIRouter(prefix="/rss", tags=["rss"])

@router.get("/test")
def rss_test(
    url: str = Query(..., description="RSS feed URL, e.g. https://techcrunch.com/feed/"),
    keywords: Optional[List[str]] = Query(None, description="Optional keyword filters"),
    limit: int = Query(10, ge=1, le=50)
) -> Dict[str, Any]:
    items = fetch_rss(url, keywords=keywords, limit=limit)
    return {"count": len(items), "items": items}

@router.post("/fetch")
def rss_fetch(
    urls: List[str],
    keywords: Optional[List[str]] = None,
    limit: int = 10
) -> Dict[str, Any]:
    all_items: List[Dict[str, Any]] = []
    for u in urls:
        all_items.extend(fetch_rss(u, keywords=keywords, limit=limit))
    # sort newest first if published available
    all_items.sort(key=lambda x: x.get("published") or "", reverse=True)
    return {"count": len(all_items), "items": all_items}
