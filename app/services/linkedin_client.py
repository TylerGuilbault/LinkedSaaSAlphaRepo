from typing import Tuple
import datetime as dt

def post_text_to_linkedin(access_token: str | None, text: str) -> Tuple[bool, str]:
    # TODO: replace with real LinkedIn API call after OAuth
    # For now we 'simulate' success.
    return True, f"sim-post-{int(dt.datetime.utcnow().timestamp())}"
