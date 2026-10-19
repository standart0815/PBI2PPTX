import pytest

from tests.fixtures.samples import make_pages, make_template


@pytest.fixture(scope="session")
def sample_template(tmp_path_factory):
    return make_template(tmp_path_factory.mktemp("template") / "sample-header-footer.potx")


@pytest.fixture(scope="session")
def sample_pages(tmp_path_factory):
    return make_pages(tmp_path_factory.mktemp("pages"))
