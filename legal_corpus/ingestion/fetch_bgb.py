"""Fetch real BGB (Bürgerliches Gesetzbuch) section text from the official
source, gesetze-im-internet.de (published by the German Federal Ministry of
Justice together with juris GmbH - the authoritative online source for
German federal law).

Scope is deliberately constrained (spec section 4), not "all German law":
the core AGB-Recht sections (§§ 305-310) plus a handful of general contract
law sections directly relevant to the clause categories ClauseGuard
classifies (liability, termination).

Each page is plain server-rendered HTML (no JS) at a predictable URL, so
this is a real, reproducible fetch - not a manual copy-paste. Raw HTML
snapshots are saved for audit purposes (gitignored - large/regeneratable);
the parsed, structured output is what gets committed.

Usage:
    python legal_corpus/ingestion/fetch_bgb.py
"""

import sys
import time
from datetime import UTC, datetime
from pathlib import Path

import httpx
from lxml import html
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "backend"))

from app.schemas.legal_passage import LegalPassage  # noqa: E402

BASE_URL = "https://www.gesetze-im-internet.de/bgb/__{}.html"
USER_AGENT = "ClauseGuard-research-project/0.1 (contract compliance analysis, educational use)"

# Deliberately constrained scope, per spec section 4: core AGB sections plus
# a few general contract-law sections relevant to LIABILITY/TERMINATION.
SECTIONS = [
    "305",  # Einbeziehung Allgemeiner Geschäftsbedingungen
    "305b",  # Vorrang der Individualabrede
    "305c",  # Überraschende und mehrdeutige Klauseln
    "306",  # Rechtsfolgen bei Nichteinbeziehung und Unwirksamkeit
    "307",  # Inhaltskontrolle
    "308",  # Klauselverbote mit Wertungsmöglichkeit
    "309",  # Klauselverbote ohne Wertungsmöglichkeit
    "310",  # Anwendungsbereich
    "276",  # Verantwortlichkeit des Schuldners
    "280",  # Schadensersatz wegen Pflichtverletzung
    "314",  # Kündigung von Dauerschuldverhältnissen aus wichtigem Grund
]

RAW_DIR = ROOT / "legal_corpus" / "sources" / "bgb"


@retry(
    # Real failure observed on a GitHub Actions run: httpx.ConnectTimeout
    # after 30s (never even established a TCP connection) - a different
    # failure mode than EUR-Lex's HTTP 202/empty-body pattern (see
    # fetch_dsgvo.py), plausibly transient network conditions or
    # datacenter-IP-specific handling by the source site. Retrying is a
    # genuine mitigation here (unlike a real 404/parse error, which
    # wouldn't be fixed by retrying) - this site had been reliable in all
    # local testing throughout the project, so no evidence yet that a
    # retry alone is insufficient (see backend/tests/test_legal_corpus.py's
    # external_flaky marker on the live test either way).
    retry=retry_if_exception_type((httpx.ConnectTimeout, httpx.ConnectError, httpx.ReadTimeout)),
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=2, min=2, max=20),
    reraise=True,
)
def fetch_raw(section: str) -> str:
    url = BASE_URL.format(section)
    response = httpx.get(url, headers={"User-Agent": USER_AGENT}, timeout=30, follow_redirects=True)
    response.raise_for_status()
    # Page declares iso-8859-1 in its meta tag.
    response.encoding = "iso-8859-1"
    return response.text


def parse_passage(section: str, raw_html: str) -> LegalPassage:
    tree = html.fromstring(raw_html)

    section_label_els = tree.xpath("//span[@class='jnenbez']")
    title_els = tree.xpath("//span[@class='jnentitel']")
    if not section_label_els or not title_els:
        raise ValueError(f"Could not parse section/title for BGB § {section} - page changed?")
    section_label = section_label_els[0].text_content().strip()
    title = title_els[0].text_content().strip()

    paragraphs = [p.text_content().strip() for p in tree.xpath("//div[@class='jurAbsatz']")]
    text = "\n\n".join(p for p in paragraphs if p)
    if not text:
        raise ValueError(f"No body text parsed for BGB § {section} - page structure changed?")

    return LegalPassage(
        source="BGB",
        section=section_label,
        title=title,
        text=text,
        jurisdiction="Germany",
        domain="contract_law",
        source_url=BASE_URL.format(section),
        effective_date=None,
        retrieved_at=datetime.now(UTC).isoformat(),
    )


def fetch_all() -> list[LegalPassage]:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    passages = []
    for section in SECTIONS:
        raw = fetch_raw(section)
        (RAW_DIR / f"{section}.html").write_text(raw, encoding="utf-8")
        passages.append(parse_passage(section, raw))
        time.sleep(0.5)  # polite delay between requests to a public government server
    return passages


if __name__ == "__main__":
    import json

    result = fetch_all()
    print(json.dumps([p.model_dump() for p in result], indent=2, ensure_ascii=False))
