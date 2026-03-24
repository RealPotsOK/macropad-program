from __future__ import annotations

from macropad.qt.pages.setup_page import parse_screen_format_from_sample


def test_parse_screen_format_from_sample_with_separator_and_end_token() -> None:
    prefix, separator, end_token = parse_screen_format_from_sample("display:Abcde|123///")

    assert prefix == "display:"
    assert separator == "|"
    assert end_token == "///"


def test_parse_screen_format_from_sample_without_separator_assumes_single_line() -> None:
    prefix, separator, end_token = parse_screen_format_from_sample("display:Abcde123///")

    assert prefix == "display:"
    assert separator == ""
    assert end_token == "///"
