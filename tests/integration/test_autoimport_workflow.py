import json
import os
import time

from datetime import datetime, timedelta
from rest_framework import status


def test_autoimport_workflow(client):
    """
    This test module aims to test a rpm autoimport workflow.
    The steps as the follows:
    * Get one no scanned test data from corgi dynamically
    * Create new active subscription
    * Update the periodic task schedule to tirgger the autoimport
    * Check the component_urls after auto sync from corgi
    * Check the forked task
    * Check if the scan result was synced to corgi
    """
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
    test_data_nevra = "389-admin-console-1.1.10-1.el7dsrv.src"
    response = client.api_call(
        "/subscriptions/",
        method="POST",
        data={
            "name": subscription_name,
            "query_params": json.dumps({"nevra": test_data_nevra}),
            "active": True,
        },
        expected_code=status.HTTP_201_CREATED
    )
    assert response['name'] == subscription_name
    assert response['active'] is True
    # Create crontab schedule
    now = datetime.now()
    future_time = now + timedelta(minutes=5)
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
    # Check the task status to determine if scan process succeed
    time.sleep(120)
    i = 0
    while i <= 5:
        response = client.api_call(
            f"/tasks/?params={test_data_nevra}",
            method="GET"
        )
        if response['count'] > 1:
            raise AssertionError(f"Have multiple scan task for {test_data_nevra}: {response['results']}")
        task_objs = response['results']
        if task_objs and task_objs[0]['status'] == "SUCCESS":
            print('scan workflow run successfully')
            break
        i += 1
        time.sleep(60)
    else:
        raise AssertionError('scan workflow failed, please login to OCP environment to check')

