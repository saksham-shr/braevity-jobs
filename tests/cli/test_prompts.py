from unittest.mock import patch


@patch("braevity.cli.prompts.pt_prompt", return_value="Software Engineer")
def test_prompt_role_returns_input(mock_prompt):
    from braevity.cli.prompts import prompt_role
    result = prompt_role()
    assert result == "Software Engineer"
    mock_prompt.assert_called_once()


@patch("braevity.cli.prompts.pt_prompt", return_value="6")
def test_prompt_experience_returns_value(mock_prompt):
    from braevity.cli.prompts import prompt_experience
    result = prompt_experience()
    assert result == "senior"


@patch("braevity.cli.prompts.pt_prompt", return_value="99")
def test_prompt_experience_invalid_then_valid(mock_prompt):
    call_count = [0]
    def side_effect(*args, **kwargs):
        call_count[0] += 1
        if call_count[0] == 1:
            return "99"
        return "1"
    mock_prompt.side_effect = side_effect
    from braevity.cli.prompts import prompt_experience
    result = prompt_experience()
    assert result == "any"


@patch("braevity.cli.prompts.pt_prompt", return_value="New York, San Francisco")
def test_prompt_cities_comma_separated(mock_prompt):
    from braevity.cli.prompts import prompt_cities
    result = prompt_cities()
    assert result == ["New York", "San Francisco"]


@patch("braevity.cli.prompts.pt_prompt", return_value="")
def test_prompt_cities_empty_returns_empty_list(mock_prompt):
    from braevity.cli.prompts import prompt_cities
    result = prompt_cities()
    assert result == []
