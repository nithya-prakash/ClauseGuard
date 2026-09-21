"""Fetch real DSGVO (GDPR, Regulation (EU) 2016/679) article text from the
official source, EUR-Lex (the EU's official law publication portal,
CELEX:32016R0679, German-language consolidated text).

Scope is deliberately constrained to the articles directly relevant to the
data-processing clauses ClauseGuard classifies: principles (Art. 5),
lawfulness of processing (Art. 6), processors (Art. 28), and security of
processing (Art. 32) - not the full 99-article regulation.

The whole regulation is one large HTML page; EUR-Lex marks each article with
a predictable `id="art_<n>"` div (ELI markup), so individual articles are
extracted from one fetch rather than requiring per-article requests.

Usage:
    python legal_corpus/ingestion/fetch_dsgvo.py
"""

import sys
from datetime import UTC, datetime
from pathlib import Path

import httpx
from lxml import html

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "backend"))

from app.schemas.legal_passage import LegalPassage  # noqa: E402

URL = "https://eur-lex.europa.eu/legal-content/DE/TXT/HTML/?uri=CELEX:32016R0679"
USER_AGENT = "ClauseGuard-research-project/0.1 (contract compliance analysis, educational use)"

ARTICLES = ["5", "6", "28", "32"]

# GDPR's real, publicly-known date of application - not fabricated (Art. 99(2)).
EFFECTIVE_DATE = "2018-05-25"

RAW_PATH = Path(__file__).resolve().parent.parent / "sources" / "dsgvo" / "full_text.html"


def fetch_raw() -> bytes:
    response = httpx.get(URL, headers={"User-Agent": USER_AGENT}, timeout=60, follow_redirects=True)
    response.raise_for_status()
    # Returned as bytes (not .text): the page has an XML encoding
    # declaration, which lxml only accepts on bytes input, not str.
    return response.content


def parse_article(tree: html.HtmlElement, article_number: str) -> LegalPassage:
    matches = tree.xpath(f"//div[@id='art_{article_number}']")
    if not matches:
        raise ValueError(f"Could not find Art. {article_number} DSGVO - page structure changed?")
    article_div = matches[0]

    title_els = article_div.xpath(".//p[@class='oj-sti-art']")
    title = title_els[0].text_content().strip() if title_els else ""

    body_paragraphs = [
        p.text_content().strip()
        for p in article_div.xpath(".//p[@class='oj-normal']")
    ]
    text = "\n\n".join(p for p in body_paragraphs if p)
    if not text:
        raise ValueError(f"No body text parsed for Art. {article_number} DSGVO - page changed?")

    return LegalPassage(
        source="DSGVO",
        section=f"Art. {article_number}",
        title=title,
        text=text,
        jurisdiction="European Union",
        domain="data_protection",
        source_url=f"{URL}#art_{article_number}",
        effective_date=EFFECTIVE_DATE,
        retrieved_at=datetime.now(UTC).isoformat(),
    )


def fetch_all() -> list[LegalPassage]:
    RAW_PATH.parent.mkdir(parents=True, exist_ok=True)
    raw = fetch_raw()
    RAW_PATH.write_bytes(raw)

    tree = html.fromstring(raw)
    return [parse_article(tree, article) for article in ARTICLES]


if __name__ == "__main__":
    import json

    result = fetch_all()
    print(json.dumps([p.model_dump() for p in result], indent=2, ensure_ascii=False))
