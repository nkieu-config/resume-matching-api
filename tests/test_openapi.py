from resume_matcher.config import Settings
from resume_matcher.main import create_app


def test_openapi_documents_pdf_upload_and_analysis_response() -> None:
    schema = create_app(Settings(_env_file=None)).openapi()
    operation = schema["paths"]["/v1/resume-analyses"]["post"]

    assert operation["requestBody"]["content"]["multipart/form-data"]
    assert operation["responses"]["200"]["content"]["application/json"]
    assert "AnalysisResult" in schema["components"]["schemas"]


def test_openapi_documents_health_endpoint() -> None:
    schema = create_app(Settings(_env_file=None)).openapi()

    assert "/health" in schema["paths"]
