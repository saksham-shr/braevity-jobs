from braevity.cli.suggestions import ROLES, CITIES, COUNTRIES, EXPERIENCE_LEVELS


def test_roles_non_empty():
    assert len(ROLES) >= 20


def test_roles_no_duplicates():
    assert len(ROLES) == len(set(ROLES))


def test_cities_include_remote():
    assert "Remote" in CITIES


def test_cities_include_bangalore():
    assert "Bangalore" in CITIES


def test_countries_include_india():
    assert "India" in COUNTRIES


def test_countries_include_worldwide():
    assert "Worldwide" in COUNTRIES


def test_experience_levels_has_any():
    values = [v for v, _ in EXPERIENCE_LEVELS]
    assert "any" in values


def test_experience_levels_has_intern():
    values = [v for v, _ in EXPERIENCE_LEVELS]
    assert "intern" in values


def test_experience_levels_has_director():
    values = [v for v, _ in EXPERIENCE_LEVELS]
    assert "director" in values


def test_experience_levels_no_duplicates():
    values = [v for v, _ in EXPERIENCE_LEVELS]
    assert len(values) == len(set(values))
