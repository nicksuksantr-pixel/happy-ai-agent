"""Tests for v2.7.0 project-type directives + their injection.

The directives shape EVERY agent's output for the chosen target
(HTML vs desktop installer). Regressions here look like "the user
asked for a desktop app but got a single index.html" — silent UX
disasters. These tests pin the contract.
"""
import pytest

from agents import PROJECT_TYPE_DIRECTIVES, get_project_type_directive


class TestProjectTypeDirectives:
    def test_html_directive_exists(self):
        assert "html" in PROJECT_TYPE_DIRECTIVES
        assert len(PROJECT_TYPE_DIRECTIVES["html"]) > 500

    def test_desktop_installer_directive_exists(self):
        assert "desktop_installer" in PROJECT_TYPE_DIRECTIVES
        assert len(PROJECT_TYPE_DIRECTIVES["desktop_installer"]) > 500

    def test_html_mentions_index_html(self):
        """Without `index.html` as the named entry point, Coder has no
        anchor for the deliverable shape."""
        assert "index.html" in PROJECT_TYPE_DIRECTIVES["html"].lower()

    def test_html_forbids_react_etc(self):
        """The directive must explicitly forbid build-step frameworks
        — otherwise Coder will happily emit React/Vue/Svelte."""
        body = PROJECT_TYPE_DIRECTIVES["html"]
        # Match at least one of the major build-step frameworks
        forbidden_keywords = ["React", "Vue", "Svelte"]
        assert any(kw in body for kw in forbidden_keywords)

    def test_html_forbids_server_side(self):
        body = PROJECT_TYPE_DIRECTIVES["html"].lower()
        assert "no server" in body or "no node" in body

    def test_desktop_installer_mentions_main_py(self):
        body = PROJECT_TYPE_DIRECTIVES["desktop_installer"]
        assert "main.py" in body

    def test_desktop_installer_mentions_pyinstaller(self):
        body = PROJECT_TYPE_DIRECTIVES["desktop_installer"]
        assert "PyInstaller" in body or "pyinstaller" in body

    def test_desktop_installer_requires_dunder_main(self):
        body = PROJECT_TYPE_DIRECTIVES["desktop_installer"]
        # The __main__ guard must be explicitly required — PyInstaller
        # needs it. Match either '__name__ == "__main__"' or just the
        # phrase "__main__".
        assert '__main__' in body

    def test_desktop_installer_recommends_customtkinter(self):
        body = PROJECT_TYPE_DIRECTIVES["desktop_installer"]
        assert "CustomTkinter" in body or "customtkinter" in body

    def test_desktop_installer_forbids_web_frameworks(self):
        body = PROJECT_TYPE_DIRECTIVES["desktop_installer"]
        for fw in ("Flask", "FastAPI", "Django"):
            assert fw in body, f"{fw} should be in the forbidden list"

    def test_each_directive_has_validation_section(self):
        """Every directive must end with a VALIDATION clause Tester can
        check against — without it Tester has no pass/fail criteria."""
        for key, body in PROJECT_TYPE_DIRECTIVES.items():
            assert "VALIDATION" in body, f"{key} missing VALIDATION section"

    def test_each_directive_has_deliverables_section(self):
        for key, body in PROJECT_TYPE_DIRECTIVES.items():
            assert "DELIVERABLES" in body, f"{key} missing DELIVERABLES section"


class TestGetProjectTypeDirective:
    def test_known_keys_return_body(self):
        assert get_project_type_directive("html") == PROJECT_TYPE_DIRECTIVES["html"]
        assert get_project_type_directive("desktop_installer") == (
            PROJECT_TYPE_DIRECTIVES["desktop_installer"]
        )

    def test_unknown_key_returns_empty_string(self):
        """Empty string lets `build_context()` skip the directive block
        cleanly — old runs that predate v2.7.0 (no project_type in meta)
        keep working with no directive injected."""
        assert get_project_type_directive("totally-unknown") == ""

    def test_empty_string_returns_empty(self):
        assert get_project_type_directive("") == ""

    def test_none_returns_empty(self):
        assert get_project_type_directive(None) == ""


class TestBuildContextInjection:
    """Integration: PipelineRunner.build_context() must prepend the
    chosen directive ABOVE the user task so PM/Architect/Coder all see
    it. This is the wiring that turns the directive into actual agent
    behaviour."""

    def _make_runner(self, project_type):
        from pipeline import PipelineRunner
        return PipelineRunner(
            client=None,
            get_model=lambda: "gemini-3.1-flash-lite",
            project_type=project_type,
        )

    def test_html_directive_prepended(self):
        r = self._make_runner("html")
        ctx = r.build_context("pm_kickoff", "make a calculator")
        assert "PROJECT TYPE DIRECTIVE (html)" in ctx
        assert "index.html" in ctx
        # User task still appears after the directive
        assert "make a calculator" in ctx
        assert ctx.index("PROJECT TYPE") < ctx.index("ORIGINAL USER TASK")

    def test_desktop_directive_prepended(self):
        r = self._make_runner("desktop_installer")
        ctx = r.build_context("pm_kickoff", "tic-tac-toe")
        assert "PROJECT TYPE DIRECTIVE (desktop_installer)" in ctx
        assert "main.py" in ctx
        assert "tic-tac-toe" in ctx

    def test_unknown_type_skips_directive(self):
        r = self._make_runner("unknown_type")
        ctx = r.build_context("pm_kickoff", "anything")
        assert "PROJECT TYPE DIRECTIVE" not in ctx
        assert "anything" in ctx

    def test_default_project_type_is_html(self):
        """Backward compat: an old runner built without explicit
        project_type defaults to html (matches DEFAULT_SETTINGS)."""
        from pipeline import PipelineRunner
        r = PipelineRunner(
            client=None,
            get_model=lambda: "gemini-3.1-flash-lite",
        )
        assert r.project_type == "html"
