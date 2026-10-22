"""Regression test suite for Analytics Page component integrity and error boundary protection."""

import os
import sys
import re
import unittest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "backend"))

from app.main import app
from app.services.analytics_service import AnalyticsService


class TestAnalyticsPageIntegrity(unittest.TestCase):
    """Test frontend code integrity and backend analytics integration."""

    def setUp(self):
        self.client = TestClient(app)
        self.frontend_path = os.path.join(os.path.dirname(__file__), "frontend")

    def test_01_analytics_page_jsx_syntax_and_imports(self):
        """Verify AnalyticsPage.jsx imports all JSX components including Lightbulb and ErrorBoundary."""
        analytics_file = os.path.join(self.frontend_path, "src", "pages", "AnalyticsPage.jsx")
        self.assertTrue(os.path.exists(analytics_file), "AnalyticsPage.jsx must exist")

        with open(analytics_file, "r", encoding="utf-8") as f:
            content = f.read()

        # Check Lightbulb import
        self.assertIn("Lightbulb", content, "Lightbulb must be imported in AnalyticsPage.jsx")
        self.assertRegex(
            content,
            r"import\s*\{[^}]*Lightbulb[^}]*\}\s*from\s*['\"]lucide-react['\"]",
            "Lightbulb must be explicitly imported from lucide-react",
        )

        # Check ErrorBoundary import
        self.assertIn("ErrorBoundary", content, "ErrorBoundary must be imported in AnalyticsPage.jsx")

        # Scan for any unimported/undeclared JSX tags
        import_matches = re.findall(r"import\s+\{([^}]+)\}\s+from", content)
        imported = set()
        for m in import_matches:
            for item in m.split(","):
                name = item.strip().split(" as ")[-1].strip()
                if name:
                    imported.add(name)

        default_imports = re.findall(r"import\s+([A-Za-z0-9_]+)\s+from", content)
        for d in default_imports:
            imported.add(d.strip())

        local_defs = set(re.findall(r"(?:const|let|var|function|class)\s+([A-Z][a-zA-Z0-9_]*)", content))
        jsx_tags = set(re.findall(r"<([A-Z][a-zA-Z0-9_]*)", content))

        missing = jsx_tags - imported - local_defs - {"React", "Icon"}
        self.assertEqual(len(missing), 0, f"Found missing JSX components in AnalyticsPage.jsx: {missing}")

    def test_02_error_boundary_component_exists_and_exports(self):
        """Verify ErrorBoundary.jsx exists, exports component, and has fallback render logic."""
        eb_file = os.path.join(self.frontend_path, "src", "components", "ErrorBoundary.jsx")
        self.assertTrue(os.path.exists(eb_file), "ErrorBoundary.jsx must exist")

        with open(eb_file, "r", encoding="utf-8") as f:
            content = f.read()

        self.assertIn("class ErrorBoundary extends Component", content)
        self.assertIn("getDerivedStateFromError", content)
        self.assertIn("componentDidCatch", content)
        self.assertIn("export default ErrorBoundary", content)

    def test_03_main_layout_wraps_outlet_in_error_boundary(self):
        """Verify MainLayout.jsx wraps Outlet in ErrorBoundary to prevent blank white screens application-wide."""
        layout_file = os.path.join(self.frontend_path, "src", "layouts", "MainLayout.jsx")
        with open(layout_file, "r", encoding="utf-8") as f:
            content = f.read()

        self.assertIn("ErrorBoundary", content)
        self.assertRegex(content, r"<ErrorBoundary>\s*<Outlet\s*/>\s*</ErrorBoundary>")

    def test_04_backend_analytics_overview_unauthorized_isolation(self):
        """Verify analytics endpoints require valid authentication."""
        res = self.client.get("/api/analytics/status")
        # 401 unauthorized without bearer token
        self.assertEqual(res.status_code, 401)

    def test_05_backend_dataset_not_found_safe_handling(self):
        """Verify analytics endpoints return 401/404 rather than unhandled 500 crashes."""
        res = self.client.get("/api/analytics/overview/9999999")
        self.assertIn(res.status_code, [401, 404])


if __name__ == "__main__":
    unittest.main()
