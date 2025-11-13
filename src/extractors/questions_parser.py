import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from bs4 import BeautifulSoup, Tag

from .utils_format import clean_text

logger = logging.getLogger(__name__)

def _normalize_question_date(text: str) -> Optional[str]:
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

def _parse_answer(answer_tag: Tag) -> Dict[str, Any]:
    body_tag = answer_tag.find(attrs={"data-at": "answer_body"}) or answer_tag
    answer_text = clean_text(body_tag.get_text(separator=" ", strip=True))
    date_tag = answer_tag.find(attrs={"data-at": "answer_date"})
    submitted_at = None
    if date_tag:
        submitted_at = _normalize_question_date(clean_text(date_tag.get_text(strip=True)))
    return {
        "answer": answer_text,
        "submitted_at": submitted_at,
    }

def _parse_question_block(block: Tag, product_id: Optional[str]) -> Dict[str, Any]:
    question_tag = block.find(attrs={"data-at": "question_body"}) or block.find("p")
    question_text = clean_text(question_tag.get_text(separator=" ", strip=True)) if question_tag else ""
    date_tag = block.find(attrs={"data-at": "question_date"})
    submitted_at = None
    if date_tag:
        submitted_at = _normalize_question_date(clean_text(date_tag.get_text(strip=True)))

    answers: List[Dict[str, Any]] = []
    for ans_container in block.find_all(attrs={"data-comp": "Answers"}):
        for ans in ans_container.find_all(attrs={"data-at": "answer_body"}):
            answers.append(_parse_answer(ans.parent or ans))

    if not answers:
        for ans in block.find_all(attrs={"data-at": "answer_body"}):
            answers.append(_parse_answer(ans.parent or ans))

    helpful_tag = block.find(attrs={"data-at": "question_helpful_count"})
    not_helpful_tag = block.find(attrs={"data-at": "question_not_helpful_count"})
    helpful_vote_count = 0
    not_helpful_vote_count = 0
    if helpful_tag:
        from .utils_format import parse_int

        helpful_vote_count = parse_int(helpful_tag.get_text(strip=True), default=0)
    if not_helpful_tag:
        from .utils_format import parse_int

        not_helpful_vote_count = parse_int(not_helpful_tag.get_text(strip=True), default=0)

    question_payload: Dict[str, Any] = {
        "product_id": product_id or "",
        "question": question_text,
        "submitted_at": submitted_at,
        "answers": answers,
        "helpful_vote_count": helpful_vote_count,
        "not_helpful_vote_count": not_helpful_vote_count,
    }
    return question_payload

def parse_questions(
    soup: BeautifulSoup,
    product_id: Optional[str] = None,
    max_questions: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """
    Parse Sephora product Q&A section into a structured list.

    If no Q&A is present on the page, returns an empty list.
    """
    logger.debug("Parsing questions")
    questions: List[Dict[str, Any]] = []

    question_blocks = soup.select('[data-comp*="Question"]:not(script)')
    if not question_blocks:
        question_blocks = soup.find_all("section")

    for block in question_blocks:
        if not isinstance(block, Tag):
            continue
        if not block.find(attrs={"data-at": "question_body"}) and "question" not in block.get_text(
            separator=" ", strip=True
        ).lower():
            continue

        q = _parse_question_block(block, product_id)
        if q["question"]:
            questions.append(q)

        if max_questions is not None and len(questions) >= max_questions:
            break

    logger.info("Parsed %d questions", len(questions))
    return questions