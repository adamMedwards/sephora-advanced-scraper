import argparse
import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Set

from .parser.product_parser import ProductParser
from .parser.category_parser import CategoryParser
from .parser.similar_products import SimilarProductsParser
from .utils.request_helper import RequestHelper
from .outputs.dataset_exporter import DatasetExporter

logger = logging.getLogger(__name__)

def configure_logging(verbose: bool = False) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
    )

def load_settings(project_root: Path) -> Dict[str, Any]:
    config_path = project_root / "src" / "config" / "settings.example.json"
    if not config_path.exists():
        logger.warning("Config file %s not found, using defaults.", config_path)
        return {}

    try:
        with config_path.open("r", encoding="utf-8") as f:
            data = json.load(f)
        logger.debug("Loaded settings from %s", config_path)
        return data
    except Exception as e:
        logger.error("Failed to load settings: %s", e)
        return {}

def load_input_payload(input_path: Path) -> Dict[str, Any]:
    if not input_path.exists():
        raise FileNotFoundError(f"Input file not found: {input_path}")

    with input_path.open("r", encoding="utf-8") as f:
        payload = json.load(f)

    if not isinstance(payload, dict):
        raise ValueError("Input JSON root must be an object.")

    payload.setdefault("product_urls", [])
    payload.setdefault("category_urls", [])
    payload.setdefault("include_similar", False)

    if not isinstance(payload["product_urls"], list) or not isinstance(
        payload["category_urls"], list
    ):
        raise ValueError("product_urls and category_urls must be arrays.")

    return payload

def dedupe_urls(urls: List[str]) -> List[str]:
    seen: Set[str] = set()
    result: List[str] = []
    for u in urls:
        u = u.strip()
        if not u:
            continue
        if u not in seen:
            seen.add(u)
            result.append(u)
    return result

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Sephora Advanced Scraper - Product, Reviews, Q&A, and Category data extractor."
    )
    parser.add_argument(
        "--input",
        "-i",
        type=str,
        default="data/inputs.sample.json",
        help="Path to input JSON file describing product/category URLs.",
    )
    parser.add_argument(
        "--output-dir",
        "-o",
        type=str,
        default="data",
        help="Directory to store exported datasets.",
    )
    parser.add_argument(
        "--export-format",
        "-f",
        type=str,
        default="json",
        choices=["json", "csv", "both"],
        help="Export format for scraped dataset.",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Enable verbose logging.",
    )

    args = parser.parse_args()
    configure_logging(args.verbose)

    project_root = Path(__file__).resolve().parents[2]
    settings = load_settings(project_root)

    input_path = (project_root / args.input).resolve()
    output_dir = (project_root / args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    payload = load_input_payload(input_path)
    product_urls = dedupe_urls(payload.get("product_urls", []))
    category_urls = dedupe_urls(payload.get("category_urls", []))
    include_similar = bool(payload.get("include_similar", False))

    if not product_urls and not category_urls:
        logger.warning("No product_urls or category_urls provided in input. Nothing to do.")
        return

    logger.info("Starting Sephora scraping run.")
    logger.info("Products: %d | Categories: %d | Include similar: %s",
                len(product_urls), len(category_urls), include_similar)

    request_helper = RequestHelper(
        default_headers=settings.get("default_headers") or {},
        timeout=float(settings.get("request_timeout", 20)),
        max_retries=int(settings.get("max_retries", 3)),
        backoff_factor=float(settings.get("backoff_factor", 0.5)),
    )

    product_parser = ProductParser()
    category_parser = CategoryParser()
    similar_parser = SimilarProductsParser()

    all_products: List[Dict[str, Any]] = []
    processed_product_urls: Set[str] = set()

    # Process category URLs -> product URLs
    for category_url in category_urls:
        logger.info("Fetching category page: %s", category_url)
        category_html = request_helper.fetch_html(category_url)
        if not category_html:
            logger.error("Failed to retrieve category URL: %s", category_url)
            continue
        category_products = category_parser.extract_product_links(category_html, base_url=category_url)
        logger.info("Discovered %d product URLs from category %s", len(category_products), category_url)
        product_urls.extend(category_products)

    product_urls = dedupe_urls(product_urls)

    # Process product URLs
    for url in product_urls:
        if url in processed_product_urls:
            logger.debug("Skipping duplicate product URL: %s", url)
            continue

        logger.info("Fetching product page: %s", url)
        html = request_helper.fetch_html(url)
        if not html:
            logger.error("Failed to retrieve product URL: %s", url)
            continue

        try:
            product_record = product_parser.parse_product(html, source_url=url)
            if product_record:
                all_products.append(product_record)
                processed_product_urls.add(url)
                logger.info("Parsed product: %s", product_record.get("info", {}).get("name") or url)
            else:
                logger.warning("Product parser returned empty record for %s", url)
        except Exception as e:
            logger.exception("Error parsing product %s: %s", url, e)
            continue

        if include_similar:
            try:
                similar_links = similar_parser.extract_similar_product_links(html, base_url=url)
                for s_url in similar_links:
                    if s_url not in processed_product_urls:
                        logger.debug("Queued similar product URL: %s", s_url)
                        product_urls.append(s_url)
            except Exception as e:
                logger.error("Failed to extract similar products for %s: %s", url, e)

    if not all_products:
        logger.warning("No products were successfully scraped. Exiting without export.")
        return

    exporter = DatasetExporter()
    base_output_name = "sephora_products"

    if args.export_format in ("json", "both"):
        json_path = output_dir / f"{base_output_name}.json"
        exporter.export_to_json(all_products, json_path)
        logger.info("Exported JSON dataset to %s", json_path)

    if args.export_format in ("csv", "both"):
        csv_path = output_dir / f"{base_output_name}.csv"
        exporter.export_to_csv(all_products, csv_path)
        logger.info("Exported flat CSV dataset to %s", csv_path)

    logger.info("Scraping run completed. Total products: %d", len(all_products))

if __name__ == "__main__":
    main()