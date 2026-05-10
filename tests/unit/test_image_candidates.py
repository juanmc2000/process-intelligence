"""Unit tests for the image candidate detection module.

All tests are purely rule-based — no OCR, no vision model, no network calls.
"""


class TestDetectFromFilename:
    def test_diagram_keyword_in_filename(self):
        """Files named with diagram keywords are detected as candidates."""
        from services.workers.parser.image_candidates import detect_from_filename

        result = detect_from_filename("process_flow_diagram.png")
        assert result is not None
        assert result["location_hint"] == "filename"
        assert any(
            "flow" in r or "process" in r or "diagram" in r for r in result["reasons"]
        )
        assert result["confidence"] in ("low", "medium", "high")

    def test_swimlane_keyword(self):
        """'swimlane' in filename triggers detection."""
        from services.workers.parser.image_candidates import detect_from_filename

        result = detect_from_filename("swimlane_view.png")
        assert result is not None
        assert any("swimlane" in r for r in result["reasons"])

    def test_workflow_keyword(self):
        """'workflow' in filename triggers detection."""
        from services.workers.parser.image_candidates import detect_from_filename

        result = detect_from_filename("workflow.jpg")
        assert result is not None

    def test_bpmn_keyword(self):
        """'bpmn' in filename triggers detection."""
        from services.workers.parser.image_candidates import detect_from_filename

        result = detect_from_filename("purchase_bpmn.png")
        assert result is not None

    def test_neutral_filename_not_detected(self):
        """Unrelated filenames return None."""
        from services.workers.parser.image_candidates import detect_from_filename

        assert detect_from_filename("photo.jpg") is None
        assert detect_from_filename("report.pdf") is None
        assert detect_from_filename("invoice_2024.pdf") is None

    def test_page_is_none_for_filename_candidate(self):
        """Filename-based candidates have no specific page number."""
        from services.workers.parser.image_candidates import detect_from_filename

        result = detect_from_filename("process_map.png")
        assert result is not None
        assert result["page"] is None


class TestScoreCandidates:
    def test_filename_candidate_included(self):
        """score_candidates includes filename-based candidates."""
        from services.workers.parser.image_candidates import score_candidates

        results = score_candidates("process_flow.pdf", {"format": "pdf"})
        assert len(results) >= 1
        assert any(c["location_hint"] == "filename" for c in results)

    def test_neutral_filename_no_candidates(self):
        """Documents with neutral filenames and no reader produce no candidates."""
        from services.workers.parser.image_candidates import score_candidates

        results = score_candidates("report.pdf", {"format": "pdf"}, reader=None)
        assert results == []

    def test_returns_list(self):
        """score_candidates always returns a list."""
        from services.workers.parser.image_candidates import score_candidates

        results = score_candidates("unknown.txt", {"format": "generic"})
        assert isinstance(results, list)


class TestPdfParserIncludesImageCandidates:
    def test_parse_pdf_returns_image_candidates_field(self):
        """parse_pdf result includes image_candidates list."""

        from services.workers.parser.pdf import parse_pdf

        # Minimal syntactically valid PDF with one blank page.
        raw = (
            b"%PDF-1.4\n"
            b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n"
            b"2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n"
            b"3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] >>\nendobj\n"
            b"xref\n0 4\n"
            b"0000000000 65535 f \n"
            b"0000000009 00000 n \n"
            b"0000000058 00000 n \n"
            b"0000000115 00000 n \n"
            b"trailer\n<< /Size 4 /Root 1 0 R >>\n"
            b"startxref\n190\n%%EOF\n"
        )
        result = parse_pdf(raw, "report.pdf")
        assert "image_candidates" in result
        assert isinstance(result["image_candidates"], list)

    def test_diagram_filename_detected_in_pdf_parse(self):
        """parse_pdf detects filename-based image candidates."""
        from services.workers.parser.pdf import parse_pdf

        raw = (
            b"%PDF-1.4\n"
            b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n"
            b"2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n"
            b"3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] >>\nendobj\n"
            b"xref\n0 4\n"
            b"0000000000 65535 f \n"
            b"0000000009 00000 n \n"
            b"0000000058 00000 n \n"
            b"0000000115 00000 n \n"
            b"trailer\n<< /Size 4 /Root 1 0 R >>\n"
            b"startxref\n190\n%%EOF\n"
        )
        result = parse_pdf(raw, "workflow_diagram.pdf")
        candidates = result["image_candidates"]
        assert len(candidates) >= 1
        assert any(c["location_hint"] == "filename" for c in candidates)

    def test_candidate_has_required_fields(self):
        """Image candidate dicts contain required metadata fields."""
        from services.workers.parser.image_candidates import detect_from_filename

        result = detect_from_filename("process_map.png")
        assert result is not None
        assert "page" in result
        assert "location_hint" in result
        assert "reasons" in result
        assert "confidence" in result
        assert isinstance(result["reasons"], list)
        assert result["confidence"] in ("low", "medium", "high")
