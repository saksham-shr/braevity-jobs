from braevity.sources.base import load_catalog


def test_catalog_loads_all_ats():
    catalog = load_catalog()
    assert "greenhouse" in catalog
    assert "lever" in catalog
    assert "workday" in catalog
    assert "ashby" in catalog
    assert len(catalog["greenhouse"]) >= 15


def test_catalog_entries_have_required_keys():
    catalog = load_catalog()
    for company in catalog["greenhouse"]:
        assert "name" in company
        assert "board_token" in company
    for company in catalog["lever"]:
        assert "name" in company
        assert "org" in company
    for company in catalog["workday"]:
        assert "name" in company
        assert "url" in company
    for company in catalog["ashby"]:
        assert "name" in company
        assert "org" in company
