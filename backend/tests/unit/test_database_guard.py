import pytest
from conftest import validated_test_url


@pytest.mark.parametrize(
    "url",
    [
        "postgresql+psycopg://localhost/devops_hub_test?host=remote.example",
        "postgresql+psycopg://localhost/devops_hub_test?hostaddr=192.0.2.1",
        "postgresql+psycopg://localhost/devops_hub_test?service=production",
        "postgresql+psycopg://localhost/devops_hub_test?dbname=production",
        "postgresql+psycopg://remote.example/devops_hub_test",
        "postgresql+psycopg://localhost/production",
        "postgresql+psycopg://localhost/devops_hub_test?host=localhost&host=remote.example",
        "postgresql+psycopg://localhost/devops_hub_test?options=-csearch_path=public",
    ],
)
def test_reject_unsafe_test_destinations(url):
    with pytest.raises(ValueError):
        validated_test_url(url, {})


@pytest.mark.parametrize("name", ["PGHOSTADDR", "PGSERVICE", "PGSERVICEFILE"])
def test_reject_libpq_environment_overrides(name):
    with pytest.raises(ValueError):
        validated_test_url("postgresql+psycopg://localhost/devops_hub_test", {name: "override"})


@pytest.mark.parametrize(
    "url",
    [
        "postgresql+psycopg://postgres@localhost/devops_hub_test",
        "postgresql+psycopg://postgres@127.0.0.1/devops_hub_test_run1",
        "postgresql+psycopg://postgres@/devops_hub_test?host=/private/tmp/isolated/socket",
    ],
)
def test_allow_explicit_local_test_destinations(url):
    assert validated_test_url(url, {}).database.startswith("devops_hub_test")
