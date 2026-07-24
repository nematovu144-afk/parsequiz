"""Unit tests for the delimiter detection engine."""

from app.parsers.base import RichParagraph, RichRun
from app.parsers.delimiter import split_into_questions


def _plain(text: str) -> RichParagraph:
    """Helper: paragraph with a single unstyled run."""
    return RichParagraph(runs=[RichRun(text=text)])


def _bold(text: str) -> RichParagraph:
    """Helper: paragraph with a single bold run."""
    return RichParagraph(runs=[RichRun(text=text, bold=True)])


class TestPlusPrefixDelimiter:
    def test_basic_plus_marker(self):
        paras = [
            _plain("1. What is 2+2?"),
            _plain("A) 3"),
            _plain("+ B) 4"),
            _plain("C) 5"),
        ]
        qs = split_into_questions(paras, mode="auto")
        assert len(qs) == 1
        assert qs[0].options[1].is_correct is True
        assert qs[0].options[0].is_correct is False
        assert "4" in qs[0].options[1].text

    def test_star_marker(self):
        paras = [
            _plain("1. Capital of France?"),
            _plain("A) London"),
            _plain("* B) Paris"),
            _plain("C) Berlin"),
        ]
        qs = split_into_questions(paras, mode="auto")
        assert qs[0].options[1].is_correct is True

    def test_checkbox_marker(self):
        paras = [
            _plain("1. Largest planet?"),
            _plain("A) Mars"),
            _plain("[x] B) Jupiter"),
            _plain("C) Venus"),
        ]
        qs = split_into_questions(paras, mode="auto")
        assert qs[0].options[1].is_correct is True


class TestBoldDelimiter:
    def test_bold_option_detected(self):
        paras = [
            _plain("1. What color is the sky?"),
            _plain("A) Red"),
            _bold("B) Blue"),
            _plain("C) Green"),
        ]
        qs = split_into_questions(paras, mode="bold")
        assert len(qs) == 1
        assert qs[0].options[1].is_correct is True

    def test_bold_mode_ignores_plus(self):
        paras = [
            _plain("1. Test?"),
            _plain("+ A) Wrong"),
            _plain("B) Right"),
        ]
        qs = split_into_questions(paras, mode="bold")
        # In bold mode, '+' is NOT treated as a correct marker
        assert qs[0].options[0].is_correct is False


class TestMultipleQuestions:
    def test_two_questions(self):
        paras = [
            _plain("1. First question?"),
            _plain("A) Yes"),
            _plain("+ B) No"),
            _plain("2. Second question?"),
            _plain("+ A) True"),
            _plain("B) False"),
        ]
        qs = split_into_questions(paras, mode="auto")
        assert len(qs) == 2
        assert qs[0].options[1].is_correct is True
        assert qs[1].options[0].is_correct is True


class TestQuestionMarkDetection:
    def test_question_ending_with_mark(self):
        paras = [
            _plain("Which element has the symbol 'O'?"),
            _plain("A) Gold"),
            _plain("+ B) Oxygen"),
            _plain("C) Silver"),
        ]
        qs = split_into_questions(paras, mode="auto")
        assert len(qs) == 1
        assert "Oxygen" in qs[0].options[1].text
