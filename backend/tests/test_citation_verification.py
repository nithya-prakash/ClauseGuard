from app.schemas.reasoning import Finding
from app.schemas.retrieval import RetrievedPassage
from app.services.verification.citation import verify_citation
from app.services.verification.citation_parser import parse_citation

REAL_276_TEXT = (
    "(1) Der Schuldner hat Vorsatz und Fahrlässigkeit zu vertreten, wenn eine "
    "strengere oder mildere Haftung weder bestimmt noch aus dem sonstigen "
    "Inhalt des Schuldverhältnisses, insbesondere aus der Übernahme einer "
    "Garantie oder eines Beschaffungsrisikos, zu entnehmen ist. Die "
    "Vorschriften der §§ 827 und 828 finden entsprechende Anwendung.\n\n"
    "(2) Fahrlässig handelt, wer die im Verkehr erforderliche Sorgfalt "
    "außer Acht lässt.\n\n"
    "(3) Die Haftung wegen Vorsatzes kann dem Schuldner nicht im Voraus "
    "erlassen werden."
)


def _bgb_276_passage() -> RetrievedPassage:
    return RetrievedPassage(
        source="BGB",
        section="§ 276",
        title="Verantwortlichkeit des Schuldners",
        text=REAL_276_TEXT,
        source_url="https://www.gesetze-im-internet.de/bgb/__276.html",
        score=0.9,
        method="hybrid_rrf_reranked",
    )


def test_parse_citation_bgb_variants():
    assert parse_citation("§ 307 BGB") == ("BGB", "§ 307")
    assert parse_citation("BGB § 276") == ("BGB", "§ 276")
    assert parse_citation("§307") == ("BGB", "§ 307")


def test_parse_citation_dsgvo_variants():
    assert parse_citation("Art. 28 DSGVO") == ("DSGVO", "Art. 28")
    assert parse_citation("Artikel 32 DSGVO") == ("DSGVO", "Art. 32")


def test_parse_citation_unparseable_returns_none():
    assert parse_citation("some vague legal reference") is None


def test_verify_citation_valid_quote_is_verified():
    finding = Finding(
        claim="Der Schuldner haftet grundsätzlich für Vorsatz und Fahrlässigkeit.",
        legal_basis="§ 276 BGB regelt die Verantwortlichkeit des Schuldners.",
        citation="§ 276 BGB",
        evidence="Der Schuldner hat Vorsatz und Fahrlässigkeit zu vertreten",
    )
    result = verify_citation(finding, [_bgb_276_passage()])
    assert result.status == "VERIFIED"
    assert result.reason is None


def test_verify_citation_fabricated_section_is_unverified():
    finding = Finding(
        claim="irrelevant",
        legal_basis="irrelevant",
        citation="§ 999 BGB",
        evidence="irrelevant",
    )
    result = verify_citation(finding, [_bgb_276_passage()])
    assert result.status == "CITATION_UNVERIFIED"
    assert "not a known passage" in result.reason


def test_verify_citation_real_section_but_not_retrieved_is_unverified():
    # § 307 exists in the corpus, but only § 276 was retrieved for this clause.
    finding = Finding(
        claim="irrelevant",
        legal_basis="irrelevant",
        citation="§ 307 BGB",
        evidence="irrelevant",
    )
    result = verify_citation(finding, [_bgb_276_passage()])
    assert result.status == "CITATION_UNVERIFIED"
    assert "not among the evidence" in result.reason


def test_verify_citation_hallucinated_evidence_text_is_unverified():
    finding = Finding(
        claim="Der Vermieter muss die Miete jährlich um 10% erhöhen.",
        legal_basis="§ 276 BGB",
        citation="§ 276 BGB",
        evidence="Der Vermieter muss die Miete jährlich um 10 Prozent erhöhen.",
    )
    result = verify_citation(finding, [_bgb_276_passage()])
    assert result.status == "CITATION_UNVERIFIED"
    assert "does not sufficiently match" in result.reason


def test_verify_citation_inconsistent_legal_basis_is_unverified():
    """The finding's own legal_basis references a different section than
    its citation field - a real internal inconsistency (Milestone 16
    finding: the original 4th check here compared the matched passage's
    source against itself, which is unreachable - see citation.py's
    docstring for why this replaced it)."""
    finding = Finding(
        claim="Der Auftragnehmer verarbeitet Daten weisungsgebunden.",
        legal_basis="Art. 28 DSGVO regelt die Pflichten des Auftragsverarbeiters.",
        citation="§ 276 BGB",
        evidence="Der Schuldner hat Vorsatz und Fahrlässigkeit zu vertreten",
    )
    result = verify_citation(finding, [_bgb_276_passage()])
    assert result.status == "CITATION_UNVERIFIED"
    assert "does not match its own citation field" in result.reason


def test_verify_citation_malformed_citation_is_unverified():
    finding = Finding(
        claim="irrelevant",
        legal_basis="irrelevant",
        citation="some vague legal principle",
        evidence="irrelevant",
    )
    result = verify_citation(finding, [_bgb_276_passage()])
    assert result.status == "CITATION_UNVERIFIED"
    assert "Could not parse" in result.reason
