"""Exact-string checks for the bilingual helpers in app/domain/text.py."""

from app.domain.text import month, month_span, num, pct


def test_month_names_follow_costa_rican_spanish():
    assert month(9).en == "September"
    assert month(9).es == "setiembre"


def test_month_span_in_year():
    t = month_span((9, 10, 11))
    assert (t.en, t.es) == ("Sep–Nov", "set–nov")


def test_month_span_wrapping_the_year_keeps_order():
    t = month_span((11, 12, 1, 2))
    assert (t.en, t.es) == ("Nov–Feb", "nov–feb")


def test_month_span_single_month():
    t = month_span((4,))
    assert (t.en, t.es) == ("Apr–Apr", "abr–abr")


def test_numbers_use_a_decimal_comma_in_spanish():
    t = num(1234.5, 1)
    assert (t.en, t.es) == ("1234.5", "1234,5")
    assert num(7).es == "7"


def test_percent_has_a_space_in_spanish():
    t = pct(0.94)
    assert (t.en, t.es) == ("94%", "94 %")
