from rest_framework import status


def test_subscription(client):
    # List the current all subscriptions
    subscription_endpoint = '/subscriptions/'
    response = client.api_call(
        subscription_endpoint,
        method="GET",
        expected_code=status.HTTP_200_OK
    )
    # Deactivate the active subscriptions
    for result in response['results']:
        if result['active']:
            subscription_id = result['id']
            client.api_call(
                '/subscriptions/{}/'.format(subscription_id),
                method="PATCH",
                data={
                    "active": "false",
                },
                expected_code=status.HTTP_200_OK
            )
    # Check the if there exists any active subscriptions
    response = client.api_call(
        '/subscriptions/?active=true',
        method="GET",
        expected_code=status.HTTP_200_OK
    )
    assert response['count'] == 0
