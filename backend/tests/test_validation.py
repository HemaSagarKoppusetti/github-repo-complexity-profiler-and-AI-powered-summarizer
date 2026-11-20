# backend/tests/test_validation.py
import pytest

from app.schemas.analysis import validate_github_repo_url


def test_valid_github_urls():
    assert validate_github_repo_url("https://github.com/pallets/flask") == "https://github.com/pallets/flask"
    assert validate_github_repo_url("https://github.com/pallets/markupsafe.git") == "https://github.com/pallets/markupsafe"
    assert validate_github_repo_url("https://github.com/psf/requests/") == "https://github.com/psf/requests"
    assert validate_github_repo_url("https://github.com/torvalds/linux") == "https://github.com/torvalds/linux"


def test_invalid_urls():
    # Non-https
    with pytest.raises(ValueError):
        validate_github_repo_url("http://github.com/pallets/flask")

    # Non-github host
    with pytest.raises(ValueError):
        validate_github_repo_url("https://gitlab.com/pallets/flask")

    with pytest.raises(ValueError):
        validate_github_repo_url("https://bitbucket.org/pallets/flask")

    # File or SSH protocols
    with pytest.raises(ValueError):
        validate_github_repo_url("file:///etc/passwd")

    with pytest.raises(ValueError):
        validate_github_repo_url("git@github.com:pallets/flask.git")

    # Shell metacharacters
    with pytest.raises(ValueError):
        validate_github_repo_url("https://github.com/pallets/flask; rm -rf /")

    with pytest.raises(ValueError):
        validate_github_repo_url("https://github.com/pallets/flask && whoami")

    with pytest.raises(ValueError):
        validate_github_repo_url("https://github.com/pallets/flask | echo test")

    # Malformed paths
    with pytest.raises(ValueError):
        validate_github_repo_url("https://github.com/pallets")

    with pytest.raises(ValueError):
        validate_github_repo_url("https://github.com/pallets/flask/tree/main")
