from bot.post_parser import extract_word


def test_extracts_simple_hashtag():
    text = "Today's word:\n\n#word_leverage\n\nMake sentences!"
    assert extract_word(text) == "leverage"


def test_case_insensitive():
    assert extract_word("#Word_Despite") == "despite"
    assert extract_word("#WORD_ACHIEVE") == "achieve"


def test_returns_none_when_no_hashtag():
    assert extract_word("Just a normal post with no marker.") is None
    assert extract_word("") is None
    assert extract_word(None) is None


def test_single_simple_hashtag_is_target_word():
    assert extract_word("#Leverage\n\nUshbu so'zga gap tuzing") == "leverage"
    assert extract_word("#despite") == "despite"


def test_multiple_simple_hashtags_ambiguous():
    # 2+ hashtags without #word_ prefix -> can't tell which is target
    assert extract_word("#english #learning #vocabulary") is None


def test_strict_wins_over_simple():
    assert extract_word("#word_first some text #random") == "first"


def test_first_hashtag_wins_when_strict():
    text = "#word_first some text #word_second"
    assert extract_word(text) == "first"


def test_only_latin_letters():
    assert extract_word("#word_leverage123") == "leverage"
    assert extract_word("#word_") is None
