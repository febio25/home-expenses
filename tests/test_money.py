import pytest

from app.money import AmountError, format_cents, parse_amount


@pytest.mark.parametrize(
    "text, cents",
    [
        ("12,50", 1250),
        ("12.50", 1250),
        ("12,5", 1250),
        ("12", 1200),
        ("12,", 1200),
        (",50", 50),
        ("0,05", 5),
        ("0.01", 1),
        (" 7,90 € ", 790),
        ("€3", 300),
        ("1234,56", 123456),
        ("1.234,56", 123456),
        ("1,234.56", 123456),
        ("12.345,6", 1234560),
        ("007,10", 710),
        ("1000000", 100_000_000),
    ],
)
def test_parse_valid(text, cents):
    assert parse_amount(text) == cents


@pytest.mark.parametrize(
    "text",
    [
        "",
        "   ",
        "abc",
        "12,345",      # three decimals
        "1.234",       # ambiguous: thousands or decimals?
        "12,5,0",
        "1.234.56",    # same separator for thousands and decimals
        "-5",
        "0",
        "0,00",
        ",",
        "1e3",
        "12 50 x",
        "1000000,01",  # above the sanity limit
        "12.345.678,90",
    ],
)
def test_parse_invalid(text):
    with pytest.raises(AmountError):
        parse_amount(text)


def test_ambiguous_thousands_say_how_to_write_them():
    # Typical for salaries: refused as before, with a message that helps.
    with pytest.raises(AmountError, match=r"^Importo ambiguo: scrivi 1850 oppure 1\.850,00\.$"):
        parse_amount("1.850")
    with pytest.raises(AmountError, match="scrivi 12345 oppure 12.345,00"):
        parse_amount("12.345")
    # A comma with three digits is a decimal typo, not thousands.
    with pytest.raises(AmountError, match="due decimali"):
        parse_amount("12,345")


def test_parse_never_uses_float():
    # 0.1 + 0.2 style traps: these must be exact.
    assert parse_amount("0,10") + parse_amount("0,20") == 30
    assert parse_amount("19,99") == 1999
    assert parse_amount("4,35") == 435  # 4.35 * 100 == 434.99999999999994 in float


def test_format_cents():
    assert format_cents(1250) == "12.50"
    assert format_cents(5) == "0.05"
    assert format_cents(123456, ",") == "1234,56"
    assert format_cents(100) == "1.00"
