import json
import re
from typing import Any, Dict, List, Optional

from bs4 import BeautifulSoup, Tag

def extract_json_ld_objects(soup: BeautifulSoup) -> List[Dict[str, Any]]:
    """
    Extracts JSON-LD objects from <script type="application/ld+json"> tags
    and returns a list of parsed dictionaries.
    """
    results: List[Dict[str, Any]] = []
    for script in soup.find_all("script", attrs={"type": "application/ld+json"}):
        if not script.string:
            continue
        raw = script.string.strip()
        if not raw:
            continue
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            # Some sites concatenate multiple JSON objects or use invalid JSON;
            # try a best-effort fix by wrapping in a list or splitting on "}{"
            try:
                fixed = f"[{raw}]"
                data = json.loads(fixed)
            except Exception:
                continue
        if isinstance(data, list):
            for item in data:
                if isinstance(item, dict):
                    results.append(item)
        elif isinstance(data, dict):
            results.append(data)
    return results

def extract_meta_tag(
    soup: BeautifulSoup,
    name: Optional[str] = None,
    property: Optional[str] = None,
) -> Optional[str]:
    """
    Returns the content of a <meta> tag with the specified name or property.
    """
    attrs: Dict[str, str] = {}
    if name:
        attrs["name"] = name
    if property:
        attrs["property"] = property

    tag = soup.find("meta", attrs=attrs)
    if tag and tag.get("content"):
        return tag["content"].strip()
    return None

def extract_numeric_from_text(text: Optional[str]) -> Optional[str]:
    if not text:
        return None
    match = re.search(r"[\d,.]+", text)
    if not match:
        return None
    return match.group(0)

def find_first(tag: Tag, selector: str) -> Optional[Tag]:
    """
    Convenience wrapper over BeautifulSoup's select_one().
    """
    return tag.select_one(selector)