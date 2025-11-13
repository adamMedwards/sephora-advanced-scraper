import logging
from typing import Any, Dict, List, Optional

from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

def _parse_reviews_from_json(product_json: Dict[str, Any]) -> List[Dict[str, Any]]:
    reviews = []

    review_entries = product_json.get("review") or product_json.get("reviews")
    if isinstance(review_entries, dict):
        review_entries = [review_entries]

    if isinstance(review_entries, list):
        for r in review_entries:
            if not isinstance(r, dict):
                continue
            rating = r.get("reviewRating", {}).get("ratingValue") if isinstance(
                r.get("reviewRating"), dict
            ) else r.get("reviewRating")
            author = r.get("author")
            if isinstance(author, dict):
                nickname = author.get("name")
            else:
                nickname = author
            reviews.append(
                {
                    "rating": _safe_float(rating),
                    "review_text": r.get("reviewBody"),
                    "review_title": r.get("name") or r.get("headline"),
                    "submitted_at": r.get("datePublished"),
                    "reviewer_info": {
                        "nickname": nickname,
                    },
                }
            )
    return reviews

def _safe_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None

def _parse_reviews_from_dom(soup: BeautifulSoup) -> List[Dict[str, Any]]:
    reviews: List[Dict[str, Any]] = []

    # Heuristic DOM parsing for reviews section
    review_containers = soup.find_all(
        lambda tag: tag.name in ("div", "li")
        and tag.get("data-at") in ("review", "ugc_review")
    )

    for container in review_containers:
        rating = None
        title = None
        text = None
        nickname = None
        submitted_at = None

        rating_el = container.find(attrs={"data-at": "review_rating"})
        if rating_el:
            rating = _safe_float(rating_el.get_text(strip=True))

        title_el = container.find(attrs={"data-at": "review_title"})
        if title_el:
            title = title_el.get_text(strip=True)

        text_el = container.find(attrs={"data-at": "review_text"})
        if text_el:
            text = text_el.get_text(" ", strip=True)

        nickname_el = container.find(attrs={"data-at": "review_author_name"})
        if nickname_el:
            nickname = nickname_el.get_text(strip=True)

        date_el = container.find(attrs={"data-at": "review_date"})
        if date_el:
            submitted_at = date_el.get_text(strip=True)

        if text or title:
            reviews.append(
                {
                    "rating": rating,
                    "review_text": text,
                    "review_title": title,
                    "submitted_at": submitted_at,
                    "reviewer_info": {
                        "nickname": nickname,
                    },
                }
            )

    return reviews

def extract_reviews(
    soup: BeautifulSoup, product_json: Optional[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """
    Extracts a list of review records from either structured JSON-LD or
    the rendered DOM, using resilient heuristics.
    """
    reviews: List[Dict[str, Any]] = []

    if product_json:
        try:
            reviews.extend(_parse_reviews_from_json(product_json))
        except Exception as e:
            logger.error("Failed to parse reviews from JSON-LD: %s", e)

    # Fall back to scraping rendered HTML
    if not reviews:
        try:
            reviews.extend(_parse_reviews_from_dom(soup))
        except Exception as e:
            logger.error("Failed to parse reviews from DOM: %s", e)

    return reviews