import logging
import re
from typing import Any, Optional

logger = logging.getLogger(__name__)

NUMBER_WITH_SUFFIX_RE = re.compile(r"^\s*([\d.,]+)\s*([kKmM]?)\s*$")
PRODUCT_ID_RE = re.compile(r"(P\d+)")

def clean_text(text: Optional[str]) -> str:
    if not text:
        return ""
    return " ".join(text.split())

def parse_float(value: Any, default: float = 0.0) -> float:
    if value is None:
        return default
    if isinstance(value, (int, float)):
        return float(value)
    try:
        text = str(value).strip().replace(",", "")
        return float(text)
    except (TypeError, ValueError):
        logger.debug("Unable to parse float from %r", value)
        return default

def parse_int(value: Any, default: int = 0) -> int:
    if value is None:
        return default
    if isinstance(value, int):
        return value
    try:
        text = str(value).strip().replace(",", "")
        return int(float(text))
    except (TypeError, ValueError):
        logger.debug("Unable to parse int from %r", value)
        return default

def parse_number_with_suffix(text: Optional[str], default: int = 0) -> int:
    if not text:
        return default
    match = NUMBER_WITH_SUFFIX_RE.match(text)
    if not match:
        return default
    number_str, suffix = match.groups()
    try:
        value = float(number_str.replace(",", ""))
    except ValueError:
        return default
    suffix = suffix.lower()
    if suffix == "k":
        value *= 1_000
    elif suffix == "m":
        value *= 1_000_000
    return int(round(value))

def infer_product_id_from_url(url: str) -> Optional[str]:
    match = PRODUCT_ID_RE.search(url)
    if match:
        return match.group(1)
    return None