"""Legal corpus ingestion tests.

Parser-logic tests use small embedded HTML fixtures (structurally accurate
excerpts of the real page structure, not full downloads) so they run fast
and offline. The actual live fetch against the official sources is a
separate @pytest.mark.integration test, skipped by default CI.
"""

import sys
from pathlib import Path

import pytest
from lxml import html

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "backend"))

from legal_corpus.ingestion.fetch_bgb import fetch_all as fetch_bgb_all  # noqa: E402
from legal_corpus.ingestion.fetch_bgb import fetch_raw as fetch_bgb_raw  # noqa: E402
from legal_corpus.ingestion.fetch_bgb import parse_passage as parse_bgb_passage  # noqa: E402
from legal_corpus.ingestion.fetch_dsgvo import fetch_all as fetch_dsgvo_all  # noqa: E402
from legal_corpus.ingestion.fetch_dsgvo import fetch_raw as fetch_dsgvo_raw  # noqa: E402
from legal_corpus.ingestion.fetch_dsgvo import parse_article as parse_dsgvo_article  # noqa: E402

BGB_FIXTURE_HTML = """
<html><body>
<div class="jnheader"><h1>B&#252;rgerliches Gesetzbuch (BGB)<br />
<span class="jnenbez">&#167; 307</span>&#160;
<span class="jnentitel">Inhaltskontrolle</span></h1></div>
<div class="jurAbsatz">(1) Bestimmungen in Allgemeinen Gesch&#228;ftsbedingungen
sind unwirksam, wenn sie den Vertragspartner des Verwenders entgegen den
Geboten von Treu und Glauben unangemessen benachteiligen.</div>
<div class="jurAbsatz">(2) Eine unangemessene Benachteiligung ist im Zweifel
anzunehmen.</div>
</body></html>
"""

DSGVO_FIXTURE_HTML = """
<html><body>
<div class="eli-subdivision" id="art_28">
  <p class="oj-ti-art">Artikel 28</p>
  <div class="eli-title"><p class="oj-sti-art">Auftragsverarbeiter</p></div>
  <div><p class="oj-normal">(1) Erfolgt eine Verarbeitung im Auftrag eines
  Verantwortlichen...</p></div>
  <div><p class="oj-normal">(2) Der Auftragsverarbeiter nimmt keinen
  weiteren Auftragsverarbeiter...</p></div>
</div>
</body></html>
"""


def test_parse_bgb_passage_from_fixture():
    passage = parse_bgb_passage("307", BGB_FIXTURE_HTML)
    assert passage.source == "BGB"
    assert passage.section == "§ 307"
    assert passage.title == "Inhaltskontrolle"
    assert "Treu und Glauben" in passage.text
    assert passage.jurisdiction == "Germany"
    assert passage.domain == "contract_law"
    assert passage.retrieved_at  # non-empty ISO timestamp


def test_parse_bgb_passage_raises_on_unexpected_structure():
    with pytest.raises(ValueError, match="page changed"):
        parse_bgb_passage("999", "<html><body>no matching structure here</body></html>")


def test_parse_dsgvo_article_from_fixture():
    tree = html.fromstring(DSGVO_FIXTURE_HTML)
    passage = parse_dsgvo_article(tree, "28")
    assert passage.source == "DSGVO"
    assert passage.section == "Art. 28"
    assert passage.title == "Auftragsverarbeiter"
    assert "Auftragsverarbeiter" in passage.text
    assert passage.jurisdiction == "European Union"
    assert passage.domain == "data_protection"
    assert passage.effective_date == "2018-05-25"


def test_parse_dsgvo_article_raises_when_missing():
    tree = html.fromstring(DSGVO_FIXTURE_HTML)
    with pytest.raises(ValueError, match="Could not find"):
        parse_dsgvo_article(tree, "999")


@pytest.mark.integration
def test_live_fetch_bgb_section():
    raw = fetch_bgb_raw("307")
    passage = parse_bgb_passage("307", raw)
    assert passage.section == "§ 307"
    assert len(passage.text) > 100


@pytest.mark.integration
@pytest.mark.external_flaky
def test_live_fetch_dsgvo_article():
    # EUR-Lex has been observed (Milestone 8) intermittently returning HTTP
    # 202 with an empty body under repeated automated requests - marked
    # separately so CI can exclude it without excluding all integration
    # tests (see clauseguard_build_conventions memory).
    raw = fetch_dsgvo_raw()
    tree = html.fromstring(raw)
    passage = parse_dsgvo_article(tree, "28")
    assert passage.section == "Art. 28"
    assert len(passage.text) > 100


@pytest.mark.integration
@pytest.mark.external_flaky
def test_full_corpus_build_produces_expected_passage_count():
    passages = fetch_bgb_all() + fetch_dsgvo_all()
    assert len(passages) == 15
    assert {p.source for p in passages} == {"BGB", "DSGVO"}
