"""
Guards on outbound fetches and on text that reaches the language model.

The live data paths hand URLs to GDAL and free text to an LLM. Both inputs originate outside the
process — asset hrefs come from a third-party STAC API, and a location label comes from the query
string — so neither can be trusted by default.

    allowed_url()    a URL must be https and on a known imagery host before GDAL opens it
    safe_label()     free text is flattened and capped before it is put in front of the model
"""

from __future__ import annotations

import re
from urllib.parse import urlparse

# Hosts the imagery archives actually serve from. GDAL's /vsicurl will fetch whatever it is given,
# including redirects and, in some builds, local paths — so the check happens before it is called,
# not inside it.
ALLOWED_HOSTS: tuple[str, ...] = (
    "usgs-wma-sentinel-2-aqr-acolite-dsf.s3.us-west-2.amazonaws.com",
    "sentinel-cogs.s3.us-west-2.amazonaws.com",
    "earth-search.aws.element84.com",
    "waterservices.usgs.gov",
)
# Suffixes covering the same buckets addressed through alternate S3 styles.
ALLOWED_SUFFIXES: tuple[str, ...] = (
    ".s3.us-west-2.amazonaws.com",
    ".s3.amazonaws.com",
)


class BlockedURL(ValueError):
    """Raised when a URL is not on the imagery allowlist."""


def allowed_url(url: str) -> str:
    """Return `url` unchanged if it is safe to fetch, else raise BlockedURL.

    Rejects anything that is not https, that carries credentials, or whose host is not a known
    imagery archive. A compromised or spoofed STAC response therefore cannot steer the process
    into fetching an arbitrary address.
    """
    parsed = urlparse(url)
    if parsed.scheme != "https":
        raise BlockedURL(f"refusing non-https URL ({parsed.scheme or 'no scheme'})")
    if parsed.username or parsed.password or "@" in (parsed.netloc.split("/")[0]):
        raise BlockedURL("refusing URL carrying credentials")
    host = (parsed.hostname or "").lower()
    if not host:
        raise BlockedURL("refusing URL without a host")
    if host in ALLOWED_HOSTS or any(host.endswith(sfx) for sfx in ALLOWED_SUFFIXES):
        return url
    raise BlockedURL(f"refusing URL on unexpected host {host!r}")


# ----------------------------------------------------------------------------- LLM input
_CONTROL = re.compile(r"[\x00-\x1f\x7f]")
MAX_LABEL = 120


def safe_label(text: str | None, fallback: str = "unnamed location", limit: int = MAX_LABEL) -> str:
    """Flatten and cap free text before it is placed in the model's prompt.

    The prompt is line-oriented, so a label containing newlines could otherwise introduce what
    looks like a new instruction ("LOCATION: x\\nIGNORE THE ABOVE..."). Collapsing control
    characters and whitespace removes that shape; the length cap keeps a long payload from
    crowding out the real content.
    """
    if not text:
        return fallback
    flat = _CONTROL.sub(" ", str(text))
    flat = re.sub(r"\s+", " ", flat).strip()
    if not flat:
        return fallback
    return flat[:limit].rstrip() + ("…" if len(flat) > limit else "")
