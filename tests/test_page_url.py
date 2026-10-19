import pytest

from pbi2pptx.page_url import Filter, ReachedThrough, filter_expression, is_app_link, parse_page_url

WS = "https://app.powerbi.com/groups/1b2c3d4e-0000-0000-0000-000000000001/reports/9f8e7d6c-0000-0000-0000-000000000002/ReportSection0e71dafbc949c0853608?experience=power-bi"
APP = "https://app.powerbi.com/groups/me/apps/a1a1a1a1-0000-0000-0000-000000000003/reports/9f8e7d6c-0000-0000-0000-000000000002/90c2e07d8e84e7d5c026?ctid=t-1&experience=power-bi"
MINE = "https://app.powerbi.com/groups/me/reports/0e0e0e0e-0000-0000-0000-000000000004/cacea11bd78861e6a8a2"
APP_LINK = "https://app.powerbi.com/Redirect?action=OpenApp&appId=a1a1a1a1-0000-0000-0000-000000000005&ctid=t-1&experience=power-bi"


def test_workspace_page():
    ref = parse_page_url(WS)
    assert (ref.reached_through, ref.page, ref.app) == (ReachedThrough.WORKSPACE, "ReportSection0e71dafbc949c0853608", None)
    assert ref.url == WS.split("?")[0]


def test_app_page_with_hex_page_name_keeps_tenant():
    ref = parse_page_url(APP)
    assert ref.reached_through is ReachedThrough.POWER_BI_APP
    assert (ref.app, ref.page, ref.ctid) == ("a1a1a1a1-0000-0000-0000-000000000003", "90c2e07d8e84e7d5c026", "t-1")
    assert ref.url.endswith("/90c2e07d8e84e7d5c026?ctid=t-1")


def test_my_workspace_page():
    assert parse_page_url(MINE).reached_through is ReachedThrough.MY_WORKSPACE


@pytest.mark.parametrize("url", ["https://app.powerbi.com/groups/me/list", APP_LINK, "https://example.com/reports/x"])
def test_rejects_anything_that_is_not_a_page_url(url):
    with pytest.raises(ValueError):
        parse_page_url(url)


def test_recognises_shared_app_links():
    assert is_app_link(APP_LINK)
    assert not is_app_link(APP)
    assert not is_app_link("https://app.powerbi.com/Redirect?action=OpenReport&reportObjectId=x")


def test_filter_expression_escapes_names_and_quotes_values():
    filters = [Filter.parse("Store Region/Name=EMEA,O'Brien"), Filter.parse("Date/Year=2026")]
    assert filter_expression(filters) == "Store_x0020_Region/Name in ('EMEA','O''Brien') and Date/Year eq 2026"


def test_filters_are_added_to_the_page_url_with_percent_encoding():
    url = parse_page_url(APP).with_filters([Filter.parse("financials/Country=Germany")])
    assert "ctid=t-1" in url
    assert "filter=financials%2FCountry%20eq%20%27Germany%27" in url


def test_no_filters_leaves_the_url_alone():
    ref = parse_page_url(WS)
    assert ref.with_filters([]) == ref.url


@pytest.mark.parametrize("text", ["Region=EMEA", "Geo/Region=", "/Region=EMEA"])
def test_rejects_malformed_filters(text):
    with pytest.raises(ValueError):
        Filter.parse(text)


# --- Date Filters -------------------------------------------------------------------------------

from datetime import date  # noqa: E402

from pbi2pptx.page_url import DateFilter  # noqa: E402


def test_date_filter_sends_the_end_day_as_before_the_next_day():
    between = DateFilter("Calendar", "Date", date(2026, 1, 1), date(2026, 10, 19))
    assert filter_expression([between]) == "Calendar/Date ge 2026-01-01 and Calendar/Date lt 2026-10-20"
    assert filter_expression([DateFilter("Calendar", "Date", start=date(2026, 1, 1))]) == "Calendar/Date ge 2026-01-01"
    assert filter_expression([DateFilter("Calendar", "Date", end=date(2026, 12, 31))]) == "Calendar/Date lt 2027-01-01"


from pbi2pptx.dates import DateRule  # noqa: E402


def test_date_rules_are_worked_out_on_the_day_of_the_export():
    year_to_date = DateFilter("Calendar", "Date", DateRule.START_OF_THIS_YEAR, DateRule.TODAY)
    assert year_to_date.on(date(2026, 10, 19)) == DateFilter("Calendar", "Date", date(2026, 1, 1), date(2026, 10, 19))


@pytest.mark.parametrize(
    "rule, on_1_march, on_15_january",
    [
        (DateRule.TODAY, date(2026, 3, 1), date(2026, 1, 15)),
        (DateRule.YESTERDAY, date(2026, 2, 28), date(2026, 1, 14)),
        (DateRule.START_OF_THIS_MONTH, date(2026, 3, 1), date(2026, 1, 1)),
        (DateRule.START_OF_LAST_MONTH, date(2026, 2, 1), date(2025, 12, 1)),
        (DateRule.END_OF_LAST_MONTH, date(2026, 2, 28), date(2025, 12, 31)),
        (DateRule.START_OF_THIS_YEAR, date(2026, 1, 1), date(2026, 1, 1)),
        (DateRule.START_OF_LAST_YEAR, date(2025, 1, 1), date(2025, 1, 1)),
        (DateRule.END_OF_LAST_YEAR, date(2025, 12, 31), date(2025, 12, 31)),
    ],
)
def test_each_date_rule(rule, on_1_march, on_15_january):
    assert DateFilter("Calendar", "Date", end=rule).on(date(2026, 3, 1)).end == on_1_march
    assert DateFilter("Calendar", "Date", start=rule).on(date(2026, 1, 15)).start == on_15_january


def test_fixed_dates_stay_as_they_are():
    fixed = DateFilter("Calendar", "Date", date(2025, 6, 1))
    assert fixed.on(date(2026, 10, 19)) == fixed
    country = Filter.parse("financials/Country=Germany")
    assert country.on(date(2026, 10, 19)) == country
