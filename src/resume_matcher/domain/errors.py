class ResumeMatcherError(Exception):
    code = "internal_error"


class RubricConfigurationError(ResumeMatcherError):
    code = "invalid_rubric"


class UnsupportedPdfError(ResumeMatcherError):
    code = "unsupported_pdf"


class PdfTooLargeError(ResumeMatcherError):
    code = "pdf_too_large"


class InvalidPdfError(ResumeMatcherError):
    code = "invalid_pdf"


class PdfTextUnavailableError(ResumeMatcherError):
    code = "pdf_text_unavailable"


class AssessmentValidationError(ResumeMatcherError):
    code = "invalid_assessment"


class MissingApiKeyError(ResumeMatcherError):
    code = "missing_api_key"


class ProviderAuthenticationError(ResumeMatcherError):
    code = "provider_authentication_failed"


class ProviderTransientError(ResumeMatcherError):
    code = "provider_temporarily_unavailable"


class ProviderOutputError(ResumeMatcherError):
    code = "provider_invalid_output"


class ProviderTimeoutError(ResumeMatcherError):
    code = "provider_timeout"
