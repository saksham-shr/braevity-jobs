from braevity.cli.suggestions import ROLES, CITIES, COUNTRIES, EXPERIENCE_LEVELS, EXPERIENCE_MAP


def test_roles_non_empty():
    assert len(ROLES) >= 20


def test_roles_no_duplicates():
    assert len(ROLES) == len(set(ROLES))


def test_cities_include_remote():
    assert "Remote" in CITIES


def test_cities_include_bengaluru():
    assert "Bengaluru" in CITIES


def test_countries_include_india():
    assert "India" in COUNTRIES


def test_experience_levels_has_any():
    values = [v for v, _ in EXPERIENCE_LEVELS]
    assert "1" in values


def test_experience_levels_has_intern():
    labels = [label for _, label in EXPERIENCE_LEVELS]
    assert "Intern" in labels


def test_experience_levels_has_director():
    labels = [label for _, label in EXPERIENCE_LEVELS]
    assert "Director+" in labels


def test_experience_levels_no_duplicates():
    values = [v for v, _ in EXPERIENCE_LEVELS]
    assert len(values) == len(set(values))


def test_experience_map():
    assert EXPERIENCE_MAP["1"] == "any"
    assert EXPERIENCE_MAP["6"] == "senior"
    assert EXPERIENCE_MAP["10"] == "director"
