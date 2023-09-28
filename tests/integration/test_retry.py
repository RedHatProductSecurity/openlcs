import time
import json
from datetime import datetime, timedelta

from rest_framework import status


def test_retry_workflow(client):
    # create subscription
    response = client.api_call(
        "/subscriptions/",
        method="POST",
        data={
            "name": "test_retry",
            "query_params":
                json.dumps({"nevra": "ariga.io/atlas-v0.3.7-0.20220303204946-787354f533c3.noarch"}),
            "active": False,
        },
        expected_code=status.HTTP_201_CREATED
    )
    subscription_id = response['id']
    # create missing data
    client.api_call(
        "/missingcomponents/",
        method="POST",
        data={
            "subscription_id": subscription_id,
            "missing_purls": ['pkg:golang/ariga.io/atlas@v0.3.7-0.20220303204946-787354f533c3']
        },
    )

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
    # Filter retry periodic task
    url = "/periodictask/?name=retry"
    resp = client.api_call(
        url,
        method="GET",
    )
    retry_task_id = resp['results'][0]['id']
    # Update retry task schedule
    url = "/periodictask/{}/".format(retry_task_id)
    response = client.api_call(
        url,
        method="PATCH",
        data={
            "interval": "",
            "crontab": crontab_id,
            "one_off": False,
            "enabled": True,
        },
    )
    assert response['name'] == "retry"
    assert response['crontab'] == crontab_id
    # Check if the missing table is empty, empty means the retry task
    # run successfully
    time.sleep(120)
    i = 0
    while i <= 5:
        response = client.api_call(
            "/missingcomponents/",
            method="GET"
        )
        if response['count'] == 0:
            print('retry workflow run successfully')
            break
        i += 1
        time.sleep(60)
    else:
        raise AssertionError('retry workflow failed, please login to OCP environment to check')
