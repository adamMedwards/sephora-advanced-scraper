import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from bs4 import BeautifulSoup, Tag

from .utils_format import clean_text, parse_float, parse_int

logger = logging.getLogger(__name__)

def _parse_review_container(container: Tag) -> Dict[str, Any]:
    rating = 0.0
    title = ""
    text = ""
    is_recommended: Optional[bool] = None
    submitted_at: Optional[str] = None
    helpful_vote_count = 0
    not_helpful_vote_count = 0

    rating_tag = container.find(attrs={"data-at": "review_rating"})
    if rating_tag:
        rating = parse_float(rating_tag.get_text(strip=True), default=0.0)
    else:
        star_tag = container.find("span", attrs={"aria-label": True})
        if star_tag and "out of 5" in star_tag["aria-label"]:
            rating_text = star_tag["aria-label"].split("out of 5")[0]
            rating = parse_float(rating_text, default=0.0)

    title_tag = container.find(attrs={"data-at": "review_title"})
    if title_tag:
        title = clean_text(title_tag.get_text(strip=True))

    body_tag = container.find(attrs={"data-at": "review_body"})
    if body_tag:
        text = clean_text(body_tag.get_text(separator=" ", strip=True))

    recommended_tag = container.find(attrs={"data-at": "review_recommendation"})
    if recommended_tag:
        rec_text = recommended_tag.get_text(strip=True).lower()
        if "yes" in rec_text or "recommended" in rec_text:
            is_recommended = True
        elif "no" in rec_text or "not recommended" in rec_text:
            is_recommended = False

    date_tag = container.find(attrs={"data-at": "review_date"})
    if date_tag:
        raw_date = clean_text(date_tag.get_text(strip=True))
        submitted_at = _normalize_date(raw_date)

    helpful_tag = container.find(attrs={"data-at": "review_helpful_count"})
    if helpful_tag:
        helpful_vote_count = parse_int(helpful_tag.get_text(strip=True), default=0)

    not_helpful_tag = container.find(attrs={"data-at": "review_not_helpful_count"})
    if not_helpful_tag:
        not_helpful_vote_count = parse_int(not_helpful_tag.get_text(strip=True), default=0)

    review = {
        "rating": rating,
        "review_text": text,
        "review_title": title,
        "is_recommended": is_recommended,
        "submitted_at": submitted_at,
        "helpful_vote_count": helpful_vote_count,
        "not_helpful_vote_count": not_helpful_vote_count,
    }
    return review

def _normalize_date(text: str) -> Optional[str]:
    """
    Attempt to normalize a Sephora-style date into ISO8601.
    """
    formats = [
        "%b %d, %Y",
        "%B %d, %Y",
        "%Y-%m-%d",
    ]
    for fmt in formats:
        try:
            dt = datetime.strptime(text, fmt)
            return dt.isoformat()
        except ValueError:
            continue
    return None

def parse_reviews(soup: BeautifulSoup, max_reviews: Optional[int] = None) -> List[Dict[str, Any]]:
    """
    Parse reviews from Sephora product page HTML.

    Uses data-at attributes commonly used in Sephora markup, with a fallback
    to generic container parsing.
    """
    logger.debug("Parsing reviews")
    reviews: List[Dict[str, Any]] = []

    container_candidates = soup.select('[data-comp*="Review"]:not(script)')
    if not container_candidates:
        container_candidates = soup.find_all("article")
    if not container_candidates:
        container_candidates = soup.find_all("li")

    for container in container_candidates:
        if not isinstance(container, Tag):
            continue
        # Heuristic: skip containers that obviously do not contain a rating
        if not container.find(attrs={"data-at": "review_rating"}) and not container.find(
            "span", attrs={"aria-label": lambda v: v and "out of 5" in v}
        ):
            continue

        review = _parse_review_container(container)
        if review["review_text"] or review["review_title"]:
            reviews.append(review)

        if max_reviews is not None and len(reviews) >= max_reviews:
            break

    logger.info("Parsed %d reviews", len(reviews))
    return reviews