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
