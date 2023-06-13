import time

from datetime import datetime, timedelta
from rest_framework import status

def test_subscription(client):
    # List the current all subscriptions
    response = client.api_call(
        '/subscriptions/',
        method="GET",
        expected_code=status.HTTP_200_OK
    )
    # Deactivate the active subscriptions
    for result in response['results']:
        if result['active']:
            subscription_id = result['id']
            response = client.api_call(
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

    # Create new subscription
    subscription_name = "test_subscription"
    query_params = '{"nevra": "virt-who-0.11-5.ael7b.src"}'
    response = client.api_call(
        "/subscriptions/",
        method="POST",
        data={
            "name": subscription_name,
            "query_params": query_params,
            "active": True,
        },
        expected_code=status.HTTP_201_CREATED
    )
    subscription_id = response['id']
    assert response['name'] == subscription_name
    assert response['active'] is True

    # Create crontab schedule
    now = datetime.now()
    future_time = now + timedelta(seconds=65)
    crontab_resp = client.api_call(
        "/crontabschedule/",
        method="POST",
        data={
            "minute": future_time.minute,
            "hour": future_time.hour,
        },
        expected_code=status.HTTP_201_CREATED
    )
    crontab_id = crontab_resp['id']

    # Filter the periodic task run_corgi_sync
    url = "/periodictask/?name=run_corgi_sync"
    run_corgi_sync_resp = client.api_call(
        url,
        method="GET",
        expected_code=status.HTTP_200_OK
    )
    periodic_id = run_corgi_sync_resp['results'][0]['id']

    # Update run_corgi_sync schedule
    url = "/periodictask/{}/".format(periodic_id)
    response = client.api_call(
        url,
        method="PATCH",
        data={
            "crontab": crontab_id,
            "one_off": False,
            "enabled": True,
        },
        expected_code=status.HTTP_200_OK
    )
    assert response['name'] == "run_corgi_sync"
    assert response['crontab'] == crontab_id

    # Check the component_urls after auto sync from corgi
    time.sleep(80)
    response = client.api_call(
        '/subscriptions/{}/'.format(subscription_id),
        method="GET",
        expected_code=status.HTTP_200_OK
    )
    assert response['component_purls'] == \
        ["pkg:rpm/redhat/virt-who@0.11-5.ael7b?arch=src"]
