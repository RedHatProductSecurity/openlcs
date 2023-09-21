from django.conf import settings
from rest_framework import status


def test_list_missingcomponents(openlcs_client):
    """
    Test for listing missing components.
    """
    url = '/missingcomponents/?subscription_id=1'
    response = openlcs_client.api_call(url, 'GET')
    expected = [
        {
            "id": 1,
            "purl": "pkg:golang/github.com/moby/sys/signal@v0.6.0",
            "subscriptions": [
                1
            ]
        }
    ]
    assert response.get("results") == expected

    url = '/missingcomponents/?subscription_id=2'
    response = openlcs_client.api_call(url, 'GET')
    expected = []
    assert response.get("results") == expected


def test_retrieve_missingcomponent(openlcs_client):
    """
    Test for retrieving a missing component.
    """
    url = '/missingcomponents/1/'
    response = openlcs_client.api_call(url, 'GET')
    expected = {
        "id": 1,
        "purl": "pkg:golang/github.com/moby/sys/signal@v0.6.0",
        "subscriptions": [
            1
        ]
    }
    assert response == expected


def test_create_missingcomponents(openlcs_client):
    """
    Test for creating missing components.
    """
    url = '/missingcomponents/'
    data = {
        "missing_purls": ["pkg:rpm/389-admin@1.1.42"],
        "subscription_id": 2
    }
    response = openlcs_client.api_call(
        url,
        method="POST",
        data=data,
        expected_code=status.HTTP_200_OK
    )
    url = '/missingcomponents/?subscription_id=2'
    response = openlcs_client.api_call(url, 'GET')
    expected = [
        {
            "id": 2,
            "purl": "pkg:rpm/389-admin@1.1.42",
            "subscriptions": [
                2
            ]
        }
    ]
    assert response.get("results") == expected


def test_delete_missingcomponents(openlcs_client):
    """
    Test for creating missing components.
    """
    url = '/delete_success_component_from_missing/'
    data = {
        "purl": "pkg:golang/github.com/moby/sys/signal@v0.6.0",
    }
    openlcs_client.api_call(
        url,
        method="POST",
        data=data,
        expected_code=status.HTTP_200_OK
    )
    url = '/missingcomponents/?subscription_id=1'
    response = openlcs_client.api_call(url, 'GET')
    expected = []
    assert response.get("results") == expected
