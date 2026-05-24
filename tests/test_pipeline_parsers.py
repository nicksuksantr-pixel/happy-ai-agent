"""Tests for pipeline output parsers — judge score, judge full, tester.

These parsers run on every quality-gate iteration. Off-by-one or
regex mistakes silently mis-score the pipeline (Judge says PASS when
it should be FAIL, or the score doesn't match the threshold).
v2.4.6 had a "Judge errored but DevOps still ran" bug class —
defensive parser tests prevent that family of regression.
"""
import pytest

from pipeline import parse_judge, parse_judge_score, parse_tester_decision


# ─── parse_judge_score ─────────────────────────────────────────────────

class TestParseJudgeScore:
    def test_basic_score(self):
        assert parse_judge_score("SCORE: 95/100") == 95

    def test_score_without_fraction(self):
        assert parse_judge_score("SCORE: 87") == 87

    def test_case_insensitive(self):
        assert parse_judge_score("score: 50/100") == 50

    def test_bold_markdown_stripped(self):
        assert parse_judge_score("**SCORE: 90/100**") == 90

    def test_zero_score(self):
        assert parse_judge_score("SCORE: 0/100") == 0

    def test_max_score(self):
        assert parse_judge_score("SCORE: 100/100") == 100

    def test_missing_score_returns_minus_one(self):
        """-1 sentinel signals "no score parseable" → treat as fail."""
        assert parse_judge_score("nothing here") == -1

    def test_empty_input_returns_minus_one(self):
        assert parse_judge_score("") == -1

    def test_multiline_picks_first(self):
        text = "SCORE: 80\n\nSCORE: 95"
        # Implementation uses re.search → first match wins
        assert parse_judge_score(text) == 80


# ─── parse_judge ───────────────────────────────────────────────────────

class TestParseJudge:
    def test_returns_score_and_instructions(self):
        text = (
            "DECISION: PASS\n"
            "SCORE: 87/100\n"
            "INSTRUCTIONS_FOR_CODER:\n"
            "- add docstrings\n"
        )
        score, instr = parse_judge(text)
        assert score == 87
        assert "add docstrings" in instr

    def test_issues_found_marker_also_works(self):
        text = "SCORE: 75/100\nISSUES FOUND:\n- bug in foo()"
        _, instr = parse_judge(text)
        assert "bug in foo" in instr

    def test_no_instructions_block_returns_empty(self):
        score, instr = parse_judge("SCORE: 90/100")
        assert score == 90
        assert instr == ""

    def test_no_score_returns_minus_one(self):
        score, _ = parse_judge("DECISION: FAIL")
        assert score == -1


# ─── parse_tester_decision ─────────────────────────────────────────────

class TestParseTesterDecision:
    def test_playable_returns_true(self):
        playable, _ = parse_tester_decision("DECISION: PLAYABLE")
        assert playable is True

    def test_broken_returns_false(self):
        playable, _ = parse_tester_decision("DECISION: BROKEN")
        assert playable is False

    def test_unknown_decision_returns_false(self):
        """Defensive default — anything not PLAYABLE → treat as broken."""
        playable, _ = parse_tester_decision("DECISION: WHATEVER")
        assert playable is False

    def test_missing_decision_returns_false(self):
        playable, _ = parse_tester_decision("no decision here")
        assert playable is False

    def test_case_insensitive(self):
        playable, _ = parse_tester_decision("decision: playable")
        assert playable is True

    def test_bold_markdown_stripped(self):
        playable, _ = parse_tester_decision("**DECISION: PLAYABLE**")
        assert playable is True

    def test_instructions_extracted_on_broken(self):
        text = (
            "DECISION: BROKEN\n"
            "INSTRUCTIONS_FOR_CODER:\n"
            "- fix the import\n"
        )
        playable, instr = parse_tester_decision(text)
        assert playable is False
        assert "fix the import" in instr

    def test_issues_underscore_marker_works(self):
        text = "DECISION: BROKEN\nISSUES_FOUND:\n- missing main()"
        _, instr = parse_tester_decision(text)
        assert "missing main" in instr
