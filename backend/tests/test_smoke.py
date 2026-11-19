def test_dependencies_import():
    import fastapi, pydantic, sqlalchemy, anthropic  # noqa: F401
    from google import genai  # noqa: F401


def test_service_modules_exist():
    from app.services import (  # noqa: F401
        evidence_assembler,
        prompt_sanitizer,
        llm_adapter,
        rules_engine,
        evaluation_runner,
    )