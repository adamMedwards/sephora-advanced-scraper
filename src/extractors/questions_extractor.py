import logging
from typing import Any, Dict, List, Optional

from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

def _parse_questions_from_json(product_json: Dict[str, Any]) -> List[Dict[str, Any]]:
    questions: List[Dict[str, Any]] = []

    q_and_a = product_json.get("questions") or product_json.get("qa")
    if isinstance(q_and_a, list):
        for q in q_and_a:
            if not isinstance(q, dict):
                continue

            product_id = q.get("product_id") or q.get("productID")
            question_text = q.get("question") or q.get("text")
            asked_at = q.get("dateCreated") or q.get("createdAt")
            answers_raw = q.get("answers") or []

            answers: List[Dict[str, Any]] = []
            if isinstance(answers_raw, list):
                for a in answers_raw:
                    if not isinstance(a, dict):
                        continue
                    answers.append(
                        {
                            "answer": a.get("answer") or a.get("text"),
                            "answered_at": a.get("createdAt") or a.get("dateCreated"),
                            "author": a.get("author"),
                        }
                    )

            questions.append(
                {
                    "product_id": product_id,
                    "question": question_text,
                    "asked_at": asked_at,
                    "answers": answers,
                }
            )
    return questions

def _parse_questions_from_dom(soup: BeautifulSoup) -> List[Dict[str, Any]]:
    questions: List[Dict[str, Any]] = []

    qa_sections = soup.find_all(
        lambda tag: tag.name in ("section", "div")
        and "question" in tag.get_text(" ", strip=True).lower()
        and tag.find(attrs={"data-at": "qa_question"})
    )

    for section in qa_sections:
        for q_el in section.find_all(attrs={"data-at": "qa_question"}):
            question_text = q_el.get_text(" ", strip=True)
            question_container = q_el.parent

            asked_at_el = question_container.find(attrs={"data-at": "qa_question_date"})
            asked_at = asked_at_el.get_text(strip=True) if asked_at_el else None

            answers: List[Dict[str, Any]] = []
            for a_el in question_container.find_all(attrs={"data-at": "qa_answer"}):
                answer_text = a_el.get_text(" ", strip=True)
                answer_date_el = a_el.find(attrs={"data-at": "qa_answer_date"})
                answer_date = (
                    answer_date_el.get_text(strip=True) if answer_date_el else None
                )
                author_el = a_el.find(attrs={"data-at": "qa_answer_author"})
                author = author_el.get_text(strip=True) if author_el else None

                answers.append(
                    {
                        "answer": answer_text,
                        "answered_at": answer_date,
                        "author": author,
                    }
                )

            questions.append(
                {
                    "product_id": None,
                    "question": question_text,
                    "asked_at": asked_at,
                    "answers": answers,
                }
            )

    return questions

def extract_questions(
    soup: BeautifulSoup, product_json: Optional[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """
    Extracts Q&A data for a product. When structured data is unavailable,
    falls back to DOM scraping heuristics and may return a best-effort
    approximation.
    """
    questions: List[Dict[str, Any]] = []

    if product_json:
        try:
            questions.extend(_parse_questions_from_json(product_json))
        except Exception as e:
            logger.error("Failed to parse Q&A from JSON-LD: %s", e)

    if not questions:
        try:
            questions.extend(_parse_questions_from_dom(soup))
        except Exception as e:
            logger.error("Failed to parse Q&A from DOM: %s", e)

    return questions