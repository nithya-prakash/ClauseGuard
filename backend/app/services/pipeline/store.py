"""Interim in-memory document/result store.

This is a REAL, working store - uploads and analysis results genuinely
persist for the life of the process - but it is explicitly not durable
(lost on restart, not shared across multiple backend replicas). Postgres
persistence (spec section 21) is Milestone 21, not yet built. Documented
here rather than silently pretended away.
"""

from dataclasses import dataclass
from pathlib import Path
from threading import Lock

from app.schemas.pipeline import DocumentAnalysisResult


@dataclass
class DocumentRecord:
    document_id: str
    original_filename: str
    stored_path: Path
    content_type: str


_documents: dict[str, DocumentRecord] = {}
_results: dict[str, DocumentAnalysisResult] = {}
_lock = Lock()


def save_document(record: DocumentRecord) -> None:
    with _lock:
        _documents[record.document_id] = record


def get_document(document_id: str) -> DocumentRecord | None:
    with _lock:
        return _documents.get(document_id)


def save_result(document_id: str, result: DocumentAnalysisResult) -> None:
    with _lock:
        _results[document_id] = result


def get_result(document_id: str) -> DocumentAnalysisResult | None:
    with _lock:
        return _results.get(document_id)
