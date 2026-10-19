import pytest

from pbi2pptx.page_url import Filter
from pbi2pptx.set_filters import FilterCard, Slicer, looks_like_number_or_date, split_field, take_over

# As seen in Power BI on 2026-10-19.
COUNTRY = FilterCard('"financials"[Country]', "ist Germany oder France")
PRODUCT_ALL = FilterCard('"financials"[Product]', "ist (alle)")
BAND_ALL = FilterCard('"financials"[Discount Band]', "ist (alle)")
DATE_ALL = FilterCard('"Calendar"[Date]', "ist (alle)")


def test_reads_table_and_column_from_the_field_label():
    assert split_field('"financials"[Country]') == ("financials", "Country")
    assert split_field("'Sales Table'[Net Amount]") == ("Sales Table", "Net Amount")
    assert split_field("Country") is None


@pytest.mark.parametrize("value, expected", [("2013", True), ("01.09.2013", True), ("1.234,5", True), ("Germany", False), ("Qtr 1", False), ("B2B", False)])
def test_spots_numbers_and_dates(value, expected):
    assert looks_like_number_or_date(value) is expected


def test_takes_over_filter_pane_cards_with_exact_names():
    result = take_over([PRODUCT_ALL, COUNTRY, DATE_ALL], [])
    assert result.filters == [Filter("financials", "Country", ("Germany", "France"))]
    assert result.left_out == []


def test_slicers_take_their_table_from_a_matching_card():
    # Ticking "High" off in a select-all slicer leaves Low, Medium and None ticked ("mixed").
    band = Slicer("Discount Band", "list", ticked=("Low", "Medium", "None"), select_all="mixed")
    result = take_over([BAND_ALL], [band])
    assert result.filters == [Filter("financials", "Discount Band", ("Low", "Medium", "None"))]


def test_all_and_nothing_chosen_are_not_filters():
    slicers = [
        Slicer("Discount Band", "list", ticked=("Low",), select_all="true"),
        Slicer("Discount Band", "list", ticked=(), select_all="false"),
        Slicer("Product", "dropdown", dropdown_text="Alle"),
    ]
    result = take_over([BAND_ALL, PRODUCT_ALL], slicers)
    assert result.filters == [] and result.left_out == []


def test_left_out_with_reasons():
    cards = [
        FilterCard('"financials"[Segment]', "ist nicht Government"),
        FilterCard('"financials"[Product]', "enthält Car"),
        FilterCard('"financials"[Units]', "ist 2013"),
        FilterCard('"financials"[Country]', "ist Germany, France und 3 weitere"),
    ]
    slicers = [
        Slicer("Date", "range"),
        Slicer("Region", "list", ticked=("EMEA",), select_all="mixed"),  # no card: table unknown
        Slicer("Product", "dropdown", dropdown_text="Mehrere Auswahlen"),
        Slicer("Segment", "list", ticked=("Government",), select_all="mixed", scrollable=True),
    ]
    result = take_over(cards, slicers)
    assert result.filters == []
    reasons = {lo.what: lo.reason for lo in result.left_out}
    assert reasons == {
        "Segment ist nicht Government": '"is not" isn\'t supported',
        "Product enthält Car": 'only "is one of" is supported',
        "Units ist 2013": "numbers and dates aren't taken over",
        "Country ist Germany, France und 3 weitere": "the list of values couldn't be read completely",
        "Slicer Date": "ranges aren't supported",
        "Slicer Region = EMEA": "table unknown: add this Filter by hand",
        "Slicer Product": "the list of values couldn't be read completely",
        "Slicer Segment": "the list is too long to read completely",
    }


def test_a_shortened_list_is_taken_over_from_the_ticked_values():
    card = FilterCard('"financials"[Country]', "ist Germany, France und 1 weitere", ticked=("Germany", "France", "Mexico"))
    assert take_over([card], []).filters == [Filter("financials", "Country", ("Germany", "France", "Mexico"))]


def test_the_same_filter_is_taken_over_once():
    slicer = Slicer("Country", "list", ticked=("Germany", "France"), select_all="mixed")
    assert take_over([COUNTRY], [slicer]).filters == [Filter("financials", "Country", ("Germany", "France"))]
