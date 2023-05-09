from rest_framework import status

from packages.models import ComponentSubscription


def test_list_subscription(openlcs_client):
    response = openlcs_client.api_call(
        "/subscriptions/",
        method="GET",
        expected_code=status.HTTP_200_OK
    )
    assert response["count"] == 2
    assert response["results"][0]["name"] == 'ansible_automation_platform:2.2'


def test_create_subscription(openlcs_client):
    subscription_name = "mock_subscription"
    response = openlcs_client.api_call(
        "/subscriptions/",
        method="POST",
        data={
            "name": subscription_name,
            "query_params": '{"arch": "src"}'
        },
        expected_code=status.HTTP_201_CREATED
    )
    instance = ComponentSubscription.objects.get(pk=response["id"])
    assert instance.name == subscription_name
    assert instance.query_params == {"arch": "src"}


def test_patch_subscription(openlcs_client):
    data = dict()
    data['name'] = 'test_subscription_updated'
    data['active'] = False
    openlcs_client.api_call(
        "/subscriptions/2/",
        method="PATCH",
        data=data,
        expected_code=status.HTTP_200_OK
    )
    instance = ComponentSubscription.objects.get(pk=2)
    assert instance.name == 'test_subscription_updated'
    assert instance.active is False
