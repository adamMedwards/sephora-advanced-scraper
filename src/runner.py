import argparse
import json
import logging
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests
from bs4 import BeautifulSoup

from extractors.product_parser import (
    parse_product_info,
    parse_product_variants,
    parse_statistics,
)
from extractors.reviews_parser import parse_reviews
from extractors.questions_parser import parse_questions
from outputs.data_exporter import export_dataset

BASE_DIR = Path(__file__).resolve().parents[1]
DEFAULT_INPUTS_PATH = BASE_DIR / "data" / "inputs.sample.json"
DEFAULT_SETTINGS_PATH = BASE_DIR / "src" / "config" / "settings.example.json"

def configure_logging(verbosity: int) -> None:
    level = logging.WARNING
    if verbosity == 1:
        level = logging.INFO
    elif verbosity >= 2:
        level = logging.DEBUG

    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
    )

def load_json_file(path: Path) -> Any:
    if not path.exists():
        raise FileNotFoundError(f"Expected JSON file at {path}")
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)

def load_settings(path: Path) -> Dict[str, Any]:
    try:
        settings = load_json_file(path)
        logging.info("Loaded settings from %s", path)
        return settings
    except FileNotFoundError:
        logging.warning("Settings file %s not found, using defaults", path)
        return {
            "user_agent": "Mozilla/5.0 (compatible; SephoraScraper/1.0; +https://bitbash.dev)",
            "timeout": 15,
            "concurrent_requests": 4,
            "export": {
                "formats": ["json"],
                "output_path": str(BASE_DIR / "data" / "sample_output.json"),
            },
        }

def build_session(settings: Dict[str, Any]) -> requests.Session:
    session = requests.Session()
    user_agent = settings.get(
        "user_agent",
        "Mozilla/5.0 (compatible; SephoraScraper/1.0; +https://bitbash.dev)",
    )
    session.headers.update({"User-Agent": user_agent})
    return session

def fetch_html(session: requests.Session, url: str, timeout: int) -> Optional[str]:
    logger = logging.getLogger("fetch_html")
    logger.info("Fetching %s", url)
    try:
        resp = session.get(url, timeout=timeout)
        resp.raise_for_status()
        return resp.text
    except requests.RequestException as exc:
        logger.error("Failed to fetch %s: %s", url, exc)
        return None

def normalize_url(url: str) -> str:
    return url.strip()

def discover_product_urls_from_category(
    session: requests.Session,
    category_url: str,
    timeout: int,
    max_products: int = 100,
) -> List[str]:
    """
    Best-effort discovery for product URLs from a Sephora category page.
    If parsing fails, falls back to returning the category URL itself.
    """
    logger = logging.getLogger("category_discovery")
    category_url = normalize_url(category_url)
    html = fetch_html(session, category_url, timeout)
    if not html:
        return [category_url]

    soup = BeautifulSoup(html, "html.parser")
    urls: List[str] = []

    for a in soup.find_all("a", href=True):
        href = a["href"]
        if "/product/" in href:
            if href.startswith("/"):
                href = "https://www.sephora.com" + href
            urls.append(href)

        if len(urls) >= max_products:
            break

    deduped: List[str] = []
    seen = set()
    for u in urls:
        u_norm = normalize_url(u)
        if u_norm not in seen:
            seen.add(u_norm)
            deduped.append(u_norm)

    if not deduped:
        logger.warning(
            "No product URLs discovered on category page %s, falling back to category URL as product",
            category_url,
        )
        deduped = [category_url]

    logger.info("Discovered %d product URLs from category %s", len(deduped), category_url)
    return deduped

def process_product(
    session: requests.Session,
    url: str,
    timeout: int,
    max_reviews: Optional[int],
    max_questions: Optional[int],
) -> Optional[Dict[str, Any]]:
    logger = logging.getLogger("process_product")
    url = normalize_url(url)
    html = fetch_html(session, url, timeout)
    if not html:
        logger.error("Skipping %s due to fetch failure", url)
        return None

    soup = BeautifulSoup(html, "html.parser")

    info = parse_product_info(soup, url)
    variants = parse_product_variants(soup)
    reviews = parse_reviews(soup, max_reviews=max_reviews)
    questions = parse_questions(soup, product_id=info.get("id"), max_questions=max_questions)
    statistics = parse_statistics(soup, reviews)

    product_payload: Dict[str, Any] = {
        "info": info,
        "product_variants": variants,
        "statistics": statistics,
        "reviews": reviews,
        "questions": questions,
    }
    logger.debug("Processed product %s", url)
    return product_payload

def load_inputs(path: Path) -> Dict[str, Any]:
    raw = load_json_file(path)
    if not isinstance(raw, dict):
        raise ValueError("Input file must contain a JSON object at the root")

    product_urls = raw.get("product_urls") or raw.get("products") or []
    category_urls = raw.get("category_urls") or raw.get("categories") or []

    if not isinstance(product_urls, list) or not isinstance(category_urls, list):
        raise ValueError("product_urls and category_urls must be lists")

    return {
        "product_urls": [str(u) for u in product_urls],
        "category_urls": [str(u) for u in category_urls],
        "include_similar_products": bool(raw.get("include_similar_products", False)),
        "max_reviews": raw.get("max_reviews"),
        "max_questions": raw.get("max_questions"),
    }

def resolve_output_path(settings: Dict[str, Any]) -> Path:
    export_cfg = settings.get("export", {})
    output_path_str = export_cfg.get("output_path") or str(BASE_DIR / "data" / "sample_output.json")
    output_path = Path(output_path_str)
    if not output_path.is_absolute():
        output_path = BASE_DIR / output_path
    output_path.parent.mkdir(parents=True, exist_ok=True)
    return output_path

def main(argv: Optional[List[str]] = None) -> None:
    parser = argparse.ArgumentParser(
        description="Sephora Advanced Scraper - demo runner",
    )
    parser.add_argument(
        "--inputs",
        type=str,
        default=str(DEFAULT_INPUTS_PATH),
        help="Path to JSON file with product_urls and category_urls (default: data/inputs.sample.json)",
    )
    parser.add_argument(
        "--settings",
        type=str,
        default=str(DEFAULT_SETTINGS_PATH),
        help="Path to settings JSON file (default: src/config/settings.example.json)",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="count",
        default=0,
        help="Increase verbosity (-v for INFO, -vv for DEBUG)",
    )
    args = parser.parse_args(argv)

    configure_logging(args.verbose)
    logger = logging.getLogger("runner")

    settings = load_settings(Path(args.settings))
    inputs = load_inputs(Path(args.inputs))

    session = build_session(settings)
    timeout = int(settings.get("timeout", 15))

    product_urls: List[str] = list(inputs["product_urls"])
    category_urls: List[str] = list(inputs["category_urls"])

    for category_url in category_urls:
        discovered = discover_product_urls_from_category(
            session=session,
            category_url=category_url,
            timeout=timeout,
        )
        product_urls.extend(discovered)

    # Deduplicate product URLs
    unique_product_urls: List[str] = []
    seen_urls = set()
    for url in product_urls:
        norm = normalize_url(url)
        if norm and norm not in seen_urls:
            seen_urls.add(norm)
            unique_product_urls.append(norm)

    logger.info("Preparing to scrape %d unique product URLs", len(unique_product_urls))

    dataset: List[Dict[str, Any]] = []
    for url in unique_product_urls:
        product_data = process_product(
            session=session,
            url=url,
            timeout=timeout,
            max_reviews=inputs.get("max_reviews"),
            max_questions=inputs.get("max_questions"),
        )
        if product_data:
            dataset.append(product_data)

    if not dataset:
        logger.warning("No data scraped; nothing to export")
        return

    export_cfg = settings.get("export", {})
    formats = export_cfg.get("formats") or ["json"]
    output_path = resolve_output_path(settings)

    export_dataset(dataset, output_path, formats=formats)
    logger.info("Export complete. Wrote %d records.", len(dataset))

if __name__ == "__main__":
    main(sys.argv[1:])