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


class TestLineDelimitedFormat:
    """The '====' (option separator) / '++++' (question separator) /
    '#' (correct marker) format exported by Hemis and similar systems."""

    def _paras(self, text: str) -> list[RichParagraph]:
        return [_plain(line.strip()) for line in text.strip("\n").splitlines() if line.strip()]

    def test_basic_two_questions(self):
        raw = """
            TCP/IP protokollari steki nechta sathdan iborat?
            ====
            #4
            ====
            3
            ====
            5
            ====
            7
            ++++

            Capital of France?
            ====
            London
            ====
            #Paris
            ====
            Berlin
            ++++
        """
        qs = split_into_questions(self._paras(raw), mode="auto")
        assert len(qs) == 2

        q1 = qs[0]
        assert q1.question_text == "TCP/IP protokollari steki nechta sathdan iborat?"
        assert [o.text for o in q1.options] == ["4", "3", "5", "7"]
        assert [o.is_correct for o in q1.options] == [True, False, False, False]

        q2 = qs[1]
        assert [o.text for o in q2.options] == ["London", "Paris", "Berlin"]
        assert q2.options[1].is_correct is True

    def test_separator_line_does_not_leak_into_question_text(self):
        raw = """
            What is 2+2?
            ====
            #4
            ====
            5
            ++++
        """
        qs = split_into_questions(self._paras(raw), mode="auto")
        assert qs[0].question_text == "What is 2+2?"
        assert "====" not in qs[0].question_text

    def test_question_separator_is_not_mistaken_for_plus_marker(self):
        # A bare "++++" line must never itself become a bogus option --
        # the naive single-char '+' marker regex would otherwise eat one
        # '+' and leave a "+++" option behind.
        raw = """
            First question?
            ====
            #A
            ====
            B
            ++++

            Second question?
            ====
            #C
            ====
            D
            ++++
        """
        qs = split_into_questions(self._paras(raw), mode="auto")
        assert len(qs) == 2
        assert [o.text for o in qs[0].options] == ["A", "B"]
        assert not any("+" in o.text for o in qs[0].options)

    def test_no_correct_marker_leaves_all_unmarked(self):
        raw = """
            Unmarked question?
            ====
            Alpha
            ====
            Beta
            ++++

            Another one?
            ====
            #X
            ====
            Y
            ++++
        """
        qs = split_into_questions(self._paras(raw), mode="auto")
        assert all(not o.is_correct for o in qs[0].options)


class TestUzbekOptionLetters:
    """Hemis-style Uzbek quiz banks often letter options A) V) S) D)
    instead of A) B) C) D)."""

    def test_v_and_s_prefixes_recognized_as_options(self):
        paras = [
            _plain("1. Shovqinlar qayerlarda ko'p uchraydi?"),
            _plain("*A) Shaharlarda."),
            _plain("V) Tog'larda."),
            _plain("S) Qishloqlarda."),
            _plain("D) O'rmonlarda."),
        ]
        qs = split_into_questions(paras, mode="auto")
        assert len(qs) == 1
        assert [o.text for o in qs[0].options] == [
            "Shaharlarda.",
            "Tog'larda.",
            "Qishloqlarda.",
            "O'rmonlarda.",
        ]
        assert qs[0].options[0].is_correct is True


class TestLeadingTitleIsNotAQuestion:
    """A bold/underlined document title before the first real question
    must not surface as a bogus empty question or a fake 'option'."""

    def test_bold_title_before_first_question_is_discarded(self):
        paras = [
            RichParagraph(runs=[RichRun(text="TEST SAVOLLARI", bold=True, underline=True)]),
            _plain("1. What color is the sky?"),
            _plain("*A) Blue"),
            _plain("B) Green"),
        ]
        qs = split_into_questions(paras, mode="auto")
        assert len(qs) == 1
        assert qs[0].question_text == "What color is the sky?"
        assert [o.text for o in qs[0].options] == ["Blue", "Green"]


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
