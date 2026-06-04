"""Tests for file_loader.py dispatch + the PDF inline-vs-extract boundary.

Covers the network-free logic flagged by the v2.8.2 Tester audit (H-A3#7):
extension → type mapping, MIME mapping, the `load_file_for_gemini` shape
for each type, and the 20 MB PDF threshold that decides inline_data vs
text-extraction. No Gemini calls.
"""
from __future__ import annotations

from file_loader import (
    get_file_type,
    is_supported,
    get_mime_type,
    load_file_for_gemini,
    build_gemini_parts,
)


class TestGetFileType:
    def test_image_exts(self):
        for ext in ("png", "jpg", "jpeg", "webp", "gif"):
            assert get_file_type(f"pic.{ext}") == "image"

    def test_pdf(self):
        assert get_file_type("doc.pdf") == "pdf"

    def test_word(self):
        assert get_file_type("report.docx") == "word"

    def test_excel(self):
        assert get_file_type("sheet.xlsx") == "excel"
        assert get_file_type("legacy.xls") == "excel"

    def test_csv(self):
        assert get_file_type("data.csv") == "csv"

    def test_text(self):
        assert get_file_type("notes.txt") == "text"
        assert get_file_type("README.md") == "text"

    def test_unknown(self):
        assert get_file_type("archive.zip") == "unknown"
        assert get_file_type("noext") == "unknown"

    def test_case_insensitive(self):
        assert get_file_type("PHOTO.PNG") == "image"

    def test_full_path(self):
        assert get_file_type(r"C:\Users\Nick\mockup.PNG") == "image"


class TestIsSupported:
    def test_supported(self):
        assert is_supported("a.png") is True
        assert is_supported("a.pdf") is True

    def test_unsupported(self):
        assert is_supported("a.exe") is False
        assert is_supported("a.zip") is False


class TestGetMimeType:
    def test_known(self):
        assert get_mime_type("a.png") == "image/png"
        assert get_mime_type("a.jpg") == "image/jpeg"
        assert get_mime_type("a.pdf") == "application/pdf"

    def test_unknown_defaults_octet_stream(self):
        assert get_mime_type("a.bin") == "application/octet-stream"


class TestLoadFileForGemini:
    def test_image_is_inline(self):
        out = load_file_for_gemini("logo.png", b"\x89PNG\r\n")
        assert out["type"] == "image"
        assert out["send_as"] == "inline_data"
        assert out["mime_type"] == "image/png"
        assert out["data"] == b"\x89PNG\r\n"

    def test_small_pdf_is_inline(self):
        out = load_file_for_gemini("small.pdf", b"%PDF-1.4 tiny")
        assert out["type"] == "pdf"
        assert out["send_as"] == "inline_data"
        assert out["mime_type"] == "application/pdf"

    def test_large_pdf_falls_back_to_text(self):
        # > 20 MB → must switch to text extraction (send_as="text"),
        # never inline a huge blob into the request.
        big = b"%PDF-1.4\n" + b"0" * (20 * 1024 * 1024 + 10)
        out = load_file_for_gemini("huge.pdf", big)
        assert out["type"] == "pdf"
        assert out["send_as"] == "text"
        assert "extracted as text" in out["preview"]

    def test_text_file(self):
        out = load_file_for_gemini("notes.txt", "สวัสดี hello".encode("utf-8"))
        assert out["type"] == "text"
        assert out["send_as"] == "text"
        assert "hello" in out["data"]

    def test_unknown_type(self):
        out = load_file_for_gemini("weird.bin", b"\x00\x01")
        assert out["type"] == "unknown"
        assert out["send_as"] == "text"
        assert "Unsupported" in out["data"]


class TestBuildGeminiParts:
    def test_text_only_parts(self):
        files = [load_file_for_gemini("a.txt", b"hello")]
        parts = build_gemini_parts("PROMPT", files)
        assert parts[0] == "PROMPT"
        assert len(parts) == 2
        assert "hello" in parts[1]

    def test_image_part_appended(self):
        files = [load_file_for_gemini("a.png", b"\x89PNG")]
        parts = build_gemini_parts("PROMPT", files)
        # prompt + one inline image Part (a non-str genai Part object)
        assert parts[0] == "PROMPT"
        assert len(parts) == 2
        assert not isinstance(parts[1], str)

    def test_no_files(self):
        parts = build_gemini_parts("PROMPT", [])
        assert parts == ["PROMPT"]
