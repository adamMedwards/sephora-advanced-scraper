import csv
import json
import logging
from pathlib import Path
from typing import Any, Dict, Iterable, List

logger = logging.getLogger(__name__)

def _ensure_parent_dir(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)

def _serialize_cell(value: Any) -> str:
    if isinstance(value, (str, int, float, bool)) or value is None:
        return "" if value is None else str(value)
    return json.dumps(value, ensure_ascii=False)

def export_json(dataset: List[Dict[str, Any]], path: Path) -> None:
    _ensure_parent_dir(path)
    with path.open("w", encoding="utf-8") as f:
        json.dump(dataset, f, ensure_ascii=False, indent=2)
    logger.info("Exported JSON dataset to %s", path)

def export_csv(dataset: List[Dict[str, Any]], path: Path) -> None:
    """
    Export a flattened view of the dataset to CSV.

    Nested structures (variants, reviews, questions) are serialized as JSON.
    """
    _ensure_parent_dir(path)
    if not dataset:
        with path.open("w", encoding="utf-8", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["info.id", "info.name", "info.brand"])
        logger.info("Exported empty CSV dataset to %s", path)
        return

    keys = ["info.id", "info.name", "info.brand", "info.price", "statistics.average_rating", "statistics.review_count"]

    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(keys)
        for item in dataset:
            info = item.get("info", {})
            stats = item.get("statistics", {})
            row = [
                _serialize_cell(info.get("id")),
                _serialize_cell(info.get("name")),
                _serialize_cell(info.get("brand")),
                _serialize_cell(info.get("price")),
                _serialize_cell(stats.get("average_rating")),
                _serialize_cell(stats.get("review_count")),
            ]
            writer.writerow(row)

    logger.info("Exported CSV dataset to %s", path)

def export_html(dataset: List[Dict[str, Any]], path: Path) -> None:
    """
    Export a simple HTML table with high-level product information.
    """
    _ensure_parent_dir(path)

    rows_html: List[str] = []
    for item in dataset:
        info = item.get("info", {})
        stats = item.get("statistics", {})
        rows_html.append(
            "<tr>"
            f"<td>{_serialize_cell(info.get('id'))}</td>"
            f"<td>{_serialize_cell(info.get('name'))}</td>"
            f"<td>{_serialize_cell(info.get('brand'))}</td>"
            f"<td>{_serialize_cell(info.get('price'))}</td>"
            f"<td>{_serialize_cell(stats.get('average_rating'))}</td>"
            f"<td>{_serialize_cell(stats.get('review_count'))}</td>"
            "</tr>"
        )

    html = (
        "<!DOCTYPE html><html><head><meta charset='utf-8'>"
        "<title>Sephora Advanced Scraper Output</title>"
        "<style>table{border-collapse:collapse;width:100%;}"
        "th,td{border:1px solid #ddd;padding:8px;font-family:Arial, sans-serif;font-size:14px;}"
        "th{background-color:#f4f4f4;text-align:left;}</style>"
        "</head><body>"
        "<h1>Sephora Advanced Scraper Output</h1>"
        "<table>"
        "<thead><tr>"
        "<th>ID</th><th>Name</th><th>Brand</th><th>Price</th><th>Average Rating</th><th>Review Count</th>"
        "</tr></thead>"
        "<tbody>"
        + "".join(rows_html)
        + "</tbody></table></body></html>"
    )

    with path.open("w", encoding="utf-8") as f:
        f.write(html)

    logger.info("Exported HTML dataset to %s", path)

def export_dataset(dataset: List[Dict[str, Any]], output_path: Path, formats: Iterable[str]) -> None:
    """
    Export dataset in one or more formats based on the formats iterable.

    output_path is treated as the base path; the extension will be adjusted per format.
    """
    formats_clean = [f.lower().strip() for f in formats]
    base = output_path
    if base.suffix:
        base = base.with_suffix("")

    for fmt in formats_clean:
        if fmt == "json":
            export_json(dataset, base.with_suffix(".json"))
        elif fmt == "csv":
            export_csv(dataset, base.with_suffix(".csv"))
        elif fmt in {"html", "htm"}:
            export_html(dataset, base.with_suffix(".html"))
        else:
            logger.warning("Unsupported export format: %s", fmt)