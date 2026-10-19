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


# --- Date cards and date slicers ----------------------------------------------------------------

from datetime import date  # noqa: E402

from pbi2pptx.page_url import DateFilter  # noqa: E402


def date_slicer(available, selected, language="de"):
    """A date slicer's aria-labels, as Power BI wrote them on 2026-10-19."""
    if language == "de":
        labels = (
            "Date",
            f"Startdatum. Verfügbarer Eingabebereich {available[0]} für {available[1]}",
            f"Startdatum, Kalenderschaltfläche, ausgewählt: {selected[0]}, Datum auswählen",
            f"Enddatum. Verfügbarer Eingabebereich {available[0]} für {available[1]}",
            f"Enddatum, Kalenderschaltfläche, ausgewählt: {selected[1]}, Datum auswählen",
        )
    else:
        labels = (
            "Date",
            f"Start date. Available input range {available[0]} to {available[1]}",
            f"Start date, calendar button, selected: {selected[0]}, choose date",
            f"End date. Available input range {available[0]} to {available[1]}",
            f"End date, calendar button, selected: {selected[1]}, choose date",
        )
    return Slicer("Date", "range", labels=labels)


SECOND_HALF_2013 = DateFilter("Calendar", "Date", date(2013, 6, 1), date(2013, 12, 31))


def test_date_cards_become_one_date_filter():
    german = [DATE_ALL, FilterCard('"Calendar"[Date]', "ist am oder nach 01.06.2013"), FilterCard('"Calendar"[Date]', "ist vor 01.01.2014")]
    english = [FilterCard("'Calendar'[Date]", "is on or after 6/1/2013"), FilterCard("'Calendar'[Date]", "is before 1/1/2014")]
    assert take_over(german, []).filters == [SECOND_HALF_2013]
    assert take_over(english, []).filters == [SECOND_HALF_2013]


def test_after_and_on_or_before_count_the_day_right():
    cards = [FilterCard('"Calendar"[Date]', "ist nach 31.05.2013"), FilterCard('"Calendar"[Date]', "ist am oder vor 31.12.2013")]
    assert take_over(cards, []).filters == [SECOND_HALF_2013]


def test_a_date_slicer_gives_its_narrowed_ends():
    whole = ("01.01.2013", "31.12.2014")
    only_end = date_slicer(whole, ("01.01.2013", "30.06.2014"))
    both = date_slicer(("1/1/2013", "12/31/2014"), ("6/1/2013", "12/31/2013"), "en")
    assert take_over([DATE_ALL], [only_end]).filters == [DateFilter("Calendar", "Date", end=date(2014, 6, 30))]
    assert take_over([DATE_ALL], [both]).filters == [SECOND_HALF_2013]


def test_a_date_slicer_over_its_whole_range_is_no_filter():
    # Also the case when date cards narrowed the slicer's range: it then only mirrors them.
    cards = [FilterCard('"Calendar"[Date]', "ist am oder nach 01.06.2013"), FilterCard('"Calendar"[Date]', "ist vor 01.01.2014")]
    mirror = date_slicer(("01.06.2013", "31.12.2013"), ("01.06.2013", "31.12.2013"))
    result = take_over([DATE_ALL, *cards], [mirror])
    assert result.filters == [SECOND_HALF_2013] and result.left_out == []


def test_a_date_slicer_narrower_than_the_cards_narrows_their_date_filter():
    cards = [FilterCard('"Calendar"[Date]', "ist am oder nach 01.06.2013")]
    narrower = date_slicer(("01.06.2013", "31.12.2014"), ("01.06.2013", "31.12.2013"))
    assert take_over(cards, [narrower]).filters == [SECOND_HALF_2013]


def test_date_settings_that_cant_be_taken_over():
    slicers = [
        date_slicer(("01.01.2013", "31.12.2014"), ("01.06.2013", "31.12.2013")),  # no card names its table
        Slicer("Units", "range", labels=("Units", "Minimum 0", "Maximum 100")),  # a number range
        Slicer("Order date", "other"),  # e.g. a relative date slicer, markup not yet seen
    ]
    cards = [FilterCard('"Orders"[Order Date]', "ist in den letzten 3 Monaten")]
    reasons = {lo.what: lo.reason for lo in take_over(cards, slicers).left_out}
    assert reasons == {
        "Order Date ist in den letzten 3 Monaten": "relative dates aren't supported",
        "Slicer Date = 01.06.2013 – 31.12.2013": "table unknown: add this Filter by hand",
        "Slicer Units": "only date ranges are supported",
        "Slicer Order date": "this kind of slicer isn't supported (such as relative dates)",
    }
