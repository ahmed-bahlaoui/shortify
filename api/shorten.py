"""
URL Shortening API Endpoint

This FastAPI serverless function handles URL shortening requests.
It uses Upstash Redis for storage and Base62 encoding for slug generation.
"""

import os
import re

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, HttpUrl
from upstash_redis import Redis

# Initialize FastAPI app
app = FastAPI(
    title="Shortify API", description="URL Shortening Service", version="1.0.0"
)

# CORS configuration for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize Upstash Redis client
redis = Redis(
    url=os.environ.get("UPSTASH_REDIS_REST_URL", ""),
    token=os.environ.get("UPSTASH_REDIS_REST_TOKEN", ""),
)

# Base62 character set for slug generation
BASE62_CHARS = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"


# ─────────────────────────────────────────────────────────────────────────────
# Request/Response Models
# ─────────────────────────────────────────────────────────────────────────────


class ShortenRequest(BaseModel):
    """Request body for URL shortening"""

    url: HttpUrl


class ShortenResponse(BaseModel):
    """Response body with shortened URL details"""

    short_url: str
    slug: str
    original_url: str


# ─────────────────────────────────────────────────────────────────────────────
# Helper Functions
# ─────────────────────────────────────────────────────────────────────────────


def encode_base62(num: int) -> str:
    """
    Encode an integer to a Base62 string.

    Base62 uses 0-9, A-Z, a-z (62 characters total).
    This produces short, URL-safe slugs.

    Examples:
        0 -> "0"
        61 -> "z"
        62 -> "10"
        1000 -> "g8"
    """
    if num == 0:
        return BASE62_CHARS[0]

    result = []
    while num > 0:
        result.append(BASE62_CHARS[num % 62])
        num //= 62

    return "".join(reversed(result))


def get_next_counter() -> int:
    """
    Get the next counter value from Redis.

    Uses Redis INCR for atomic increment, ensuring
    unique slugs even under concurrent requests.
    """
    counter = redis.incr("shortify:counter")
    return counter


def is_valid_url(url: str) -> bool:
    """Basic URL validation"""
    url_pattern = re.compile(
        r"^https?://"  # http:// or https://
        r"(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,6}\.?|"  # domain
        r"localhost|"  # localhost
        r"\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})"  # or IP
        r"(?::\d+)?"  # optional port
        r"(?:/?|[/?]\S+)$",
        re.IGNORECASE,
    )
    return url_pattern.match(url) is not None


# ─────────────────────────────────────────────────────────────────────────────
# API Endpoints
# ─────────────────────────────────────────────────────────────────────────────


@app.post("/api/shorten", response_model=ShortenResponse)
async def shorten_url(request: ShortenRequest):
    """
    Create a shortened URL.

    Flow:
    1. Validate the input URL
    2. Get next counter value (atomic increment)
    3. Encode counter to Base62 slug
    4. Store slug -> original URL mapping in Redis
    5. Return the shortened URL
    """
    original_url = str(request.url)

    # Check if URL was already shortened (optional deduplication)
    existing_slug = redis.get(f"shortify:url:{original_url}")
    if existing_slug:
        return ShortenResponse(
            short_url=f"/{existing_slug}", slug=existing_slug, original_url=original_url
        )

    # Generate new slug
    counter = get_next_counter()
    slug = encode_base62(counter)

    # Store mappings in Redis
    # Primary: slug -> URL (for redirects)
    redis.set(f"shortify:slug:{slug}", original_url)
    # Secondary: URL -> slug (for deduplication)
    redis.set(f"shortify:url:{original_url}", slug)

    return ShortenResponse(short_url=f"/{slug}", slug=slug, original_url=original_url)


@app.get("/api/health")
async def health_check():
    """Health check endpoint for monitoring"""
    return {"status": "healthy", "service": "shortify"}
