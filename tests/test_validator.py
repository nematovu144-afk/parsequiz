"""Unit tests for structural question validation/flagging."""

from app.schemas.quiz import Question, ValidationFlag
from app.services.validator import validate_questions


def test_valid_question_gets_no_flags():
    q = Question(question="2+2?", options=["3", "4"], correct_option_index=1)
    validate_questions([q])
    assert q.flags == []


def test_empty_question_text_flagged():
    q = Question(question="   ", options=["3", "4"], correct_option_index=1)
    validate_questions([q])
    assert ValidationFlag.EMPTY_QUESTION in q.flags


def test_too_few_options_flagged():
    q = Question(question="2+2?", options=["4"], correct_option_index=0)
    validate_questions([q])
    assert ValidationFlag.TOO_FEW_OPTIONS in q.flags


def test_missing_correct_answer_flagged():
    q = Question(question="2+2?", options=["3", "4"], correct_option_index=None)
    validate_questions([q])
    assert ValidationFlag.MISSING_CORRECT in q.flags


def test_out_of_range_correct_index_flagged():
    q = Question(question="2+2?", options=["3", "4"], correct_option_index=5)
    validate_questions([q])
    assert ValidationFlag.MISSING_CORRECT in q.flags


def test_duplicate_options_flagged():
    q = Question(question="2+2?", options=["Four", "four"], correct_option_index=0)
    validate_questions([q])
    assert ValidationFlag.DUPLICATE_OPTIONS in q.flags


def test_parse_artifact_flagged():
    q = Question(question="2+2?", options=["4", "+"], correct_option_index=0)
    validate_questions([q])
    assert ValidationFlag.PARSE_ARTIFACT in q.flags


def test_flags_are_reset_on_revalidation():
    """Calling validate_questions twice shouldn't accumulate duplicate flags."""
    q = Question(question="", options=["4"], correct_option_index=None)
    validate_questions([q])
    first_pass = list(q.flags)
    validate_questions([q])
    assert q.flags == first_pass
