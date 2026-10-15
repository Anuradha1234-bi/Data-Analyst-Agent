def test_fastapi_app_imports_and_instantiates():
    """Test that FastAPI app imports and instantiates properly."""
    from app.main import app, create_application

    assert app is not None
    assert app.title == "AI Data Analyst Agent"

    # Test application factory
    fresh_app = create_application()
    assert fresh_app is not None
    assert fresh_app.title == "AI Data Analyst Agent"


def test_cors_middleware_is_configured():
    """Verify CORS middleware is properly registered."""
    from app.main import app

    middleware_classes = [m.cls.__name__ for m in app.user_middleware]
    assert "CORSMiddleware" in middleware_classes


def test_routes_registered():
    """Verify essential routes and documentation paths are mounted."""
    from app.main import app

    openapi_spec = app.openapi()
    paths = list(openapi_spec["paths"].keys())
    assert "/api/health" in paths
    assert app.docs_url == "/docs"
    assert app.openapi_url == "/openapi.json"

