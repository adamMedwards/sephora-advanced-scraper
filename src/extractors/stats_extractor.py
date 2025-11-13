from typing import Any, Dict, List, Optional

def build_statistics_from_reviews(reviews: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Builds simple aggregate statistics from a list of review records.
    This does not rely on Sephora-specific markup and can be used as a
    robust fallback even if the website structure changes.
    """
    review_count = len(reviews)
    if review_count == 0:
        return {
            "average_rating": None,
            "helpful_vote_count": None,
            "not_helpful_vote_count": None,
            "recommended_review_count": None,
            "review_count": 0,
        }

    ratings: List[float] = []
    for r in reviews:
        rating = r.get("rating")
        if isinstance(rating, (int, float)):
            ratings.append(float(rating))

    average_rating: Optional[float] = (
        sum(ratings) / len(ratings) if ratings else None
    )

    # Placeholders for votes and recommendations. These can be enhanced with
    # real fields if/when they become available in the parsed data.
    helpful_vote_count: Optional[int] = None
    not_helpful_vote_count: Optional[int] = None
    recommended_review_count: Optional[int] = None

    return {
        "average_rating": average_rating,
        "helpful_vote_count": helpful_vote_count,
        "not_helpful_vote_count": not_helpful_vote_count,
        "recommended_review_count": recommended_review_count,
        "review_count": review_count,
    }