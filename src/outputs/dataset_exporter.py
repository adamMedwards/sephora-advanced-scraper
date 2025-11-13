import csv
import json
from pathlib import Path
from typing import Any, Dict, Iterable, List

class DatasetExporter:
    """
    Handles exporting structured product data into JSON and CSV formats.
    """

    def export_to_json(self, products: List[Dict[str, Any]], path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as f:
            json.dump(products, f, ensure_ascii=False, indent=2)

    def export_to_csv(self, products: List[Dict[str, Any]], path: Path) -> None:
        """
        Flattens nested product records into a simple row-per-product CSV.
        Only top-level info and basic statistics are included to keep the
        table readable. Full data is still available in JSON.
        """
        path.parent.mkdir(parents=True, exist_ok=True)

        rows: List[Dict[str, Any]] = []
        for product in products:
            info = product.get("info", {}) or {}
            stats = product.get("statistics", {}) or {}

            row: Dict[str, Any] = {
                "id": info.get("id"),
                "name": info.get("name"),
                "brand": info.get("brand"),
                "price": info.get("price"),
                "is_available": info.get("is_available"),
                "love_count": info.get("love_count"),
                "image": info.get("image"),
                "average_rating": stats.get("average_rating"),
                "review_count": stats.get("review_count"),
                "helpful_vote_count": stats.get("helpful_vote_count"),
                "not_helpful_vote_count": stats.get("not_helpful_vote_count"),
                "recommended_review_count": stats.get("recommended_review_count"),
                "source_url": (product.get("_source") or {}).get("url"),
            }
            rows.append(row)

        fieldnames = list(rows[0].keys()) if rows else []

        with path.open("w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for row in rows:
                writer.writerow(row)