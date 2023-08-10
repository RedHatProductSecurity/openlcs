import json
import os
import time

from datetime import datetime, timedelta
from rest_framework import status
from .get_test_data import (
    get_no_scanned_rpm_testdata,
    get_the_openlcs_scan_url
    )


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
    # Get one no scanned test data dynamically
    test_data_nvr, test_data_src, test_data_purl = \
        get_no_scanned_rpm_testdata()
    # Create new subscription
    subscription_name = "test_subscription"
    params = {"nvr": test_data_nvr}
    query_params = json.dumps(params)
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
    future_time = now + timedelta(seconds=600)
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
    sleep_time = os.getenv('SLEEP_TIME')
    response['component_purls'] = []
    i = 0
    try:
        while response['component_purls'] == [] and i < 10:
            i = i + 1
            time.sleep(int(sleep_time))  # waiting for query components
            response = client.api_call(
                '/subscriptions/{}/'.format(subscription_id),
                method="GET",
                expected_code=status.HTTP_200_OK
            )
    except Exception as error:
        print("Couldn't get the component_purls in 20 mins.", error)
    assert response['component_purls'] == \
        [f"{test_data_purl}"]
    # Check the forked task
    response = client.api_call(
        '/tasks/?params={}'.format(test_data_nvr),
        method="GET",
        expected_code=status.HTTP_200_OK
    )
    i = 0
    try:
        waiting_status = ['PENDING', 'STARTED']
        while response['status'] in waiting_status and i < 10:
            i = i + 1
            time.sleep(int(sleep_time))  # waiting for scanning
            response = client.api_call(
                '/tasks/?params={}'.format(test_data_nvr),
                method="GET",
                expected_code=status.HTTP_200_OK
            )
        if response['status'] != "SUCCESS":
            print(f"Task for {test_data_nvr} wasn't SUCCESS in 20 mins.")
        else:
            # Check if the scan result was synced to corgi
            time.sleep(10)  # waiting for syncing result to corgi
            openlcs_scan_url = get_the_openlcs_scan_url(test_data_src)
            assert os.getenv('OPENLCS_TEST_URL') in openlcs_scan_url
    except Exception as error:
        print(error)
