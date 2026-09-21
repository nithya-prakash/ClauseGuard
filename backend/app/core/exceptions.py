class ClauseGuardError(Exception):
    """Base class for all application-raised errors.

    Every subclass carries an explicit, user-safe `detail` message — internal
    details (stack traces, raw exceptions from third-party clients) must
    never be forwarded to API responses.
    """

    status_code: int = 500

    def __init__(self, detail: str):
        self.detail = detail
        super().__init__(detail)


class ValidationFailedError(ClauseGuardError):
    status_code = 422


class UnsupportedFileTypeError(ClauseGuardError):
    status_code = 415


class FileTooLargeError(ClauseGuardError):
    status_code = 413


class NotFoundError(ClauseGuardError):
    status_code = 404


class LLMNotConfiguredError(ClauseGuardError):
    status_code = 503


class ClassifierNotTrainedError(ClauseGuardError):
    """Raised when clause classification is requested but no trained model
    artifact exists yet. Never falls back to a guessed/default label."""

    status_code = 503


class OCRNotImplementedError(ClauseGuardError):
    """Raised when a PDF is detected as likely-scanned (low text density).

    OCR is architecturally planned (see services/ingestion/ocr.py) but not
    implemented. We refuse to silently return near-empty extracted text.
    """

    status_code = 501


class PipelineStageError(ClauseGuardError):
    """A pipeline stage (segmentation, retrieval, reasoning, ...) failed."""

    status_code = 500

    def __init__(self, stage: str, detail: str):
        self.stage = stage
        super().__init__(f"Pipeline stage '{stage}' failed: {detail}")
