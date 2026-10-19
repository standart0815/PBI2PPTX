import pytest

from pbi_window import Filter, filter_expression, page_url_with_filters, parse_page_url

WS = "https://app.powerbi.com/groups/1b2c3d4e-0000-0000-0000-000000000001/reports/9f8e7d6c-0000-0000-0000-000000000002/ReportSection0e71dafbc949c0853608?experience=power-bi"
APP = "https://app.powerbi.com/groups/me/apps/a1a1a1a1-0000-0000-0000-000000000003/reports/9f8e7d6c-0000-0000-0000-000000000002/90c2e07d8e84e7d5c026?ctid=t-1&experience=power-bi"


def test_parses_workspace_page():
    ref = parse_page_url(WS)
    assert (ref.via, ref.page, ref.app) == ("Workspace", "ReportSection0e71dafbc949c0853608", None)
    assert ref.url == WS.split("?")[0]


def test_parses_app_page_with_hex_page_name_and_keeps_tenant():
    ref = parse_page_url(APP)
    assert (ref.via, ref.app, ref.page, ref.ctid) == ("Power BI App", "a1a1a1a1-0000-0000-0000-000000000003", "90c2e07d8e84e7d5c026", "t-1")
    assert ref.url.endswith("/90c2e07d8e84e7d5c026?ctid=t-1")


def test_rejects_non_page_urls():
    with pytest.raises(ValueError):
        parse_page_url("https://app.powerbi.com/groups/me/list")


def test_filter_expression_escapes_names_and_quotes_values():
    filters = [Filter.parse("Store Region/Name=EMEA,O'Brien"), Filter.parse("Date/Year=2026")]
    assert filter_expression(filters) == "Store_x0020_Region/Name in ('EMEA','O''Brien') and Date/Year eq 2026"


def test_filters_are_added_to_the_page_url():
    url = page_url_with_filters(parse_page_url(APP), [Filter.parse("Geo/Region=EMEA")])
    assert "ctid=t-1" in url and "filter=Geo%2FRegion%20eq%20%27EMEA%27" in url
