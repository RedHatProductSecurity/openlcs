import time
import pytest
from rest_framework import status
from datetime import datetime, timedelta
import django
import os
os.environ.setdefault(
                'DJANGO_SETTINGS_MODULE', 'openlcs.settings')
django.setup()
from django_celery_beat import models
from django_celery_beat.models import (
    CrontabSchedule,
    PeriodicTask,
)

@pytest.mark.django_db(transaction=True)
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
            response = client.api_call(
            '/subscriptions/{}/'.format(subscription_id),
            method="PATCH",
            data={
                "active": "false",
            },
            expected_code=status.HTTP_200_OK
        )
    # Check the if there any active subscriptions
    response = client.api_call(
        '/subscriptions/?active=true',
        method="GET",
        expected_code=status.HTTP_200_OK
    )
    assert response['count'] == 0
    # Create an active subscription
    subscription_name = "test_subscription"
    query_params = '{"nevra": "virt-who-0.11-5.ael7b.src"}'
    response = client.api_call(
        "/subscriptions/",
        method="POST",
        data={
            "name": subscription_name,
            "query_params": query_params,
            "active": "true",
        },
        expected_code=status.HTTP_201_CREATED
    )
    assert response['name'] == subscription_name
    subscription_id = response['id']
    specific_subscription = '/subscriptions/{}'.format(subscription_id)
    response1 = client.api_call(
        specific_subscription,
        method="GET",
        expected_code=status.HTTP_200_OK
    )
    assert response1['name'] == subscription_name

    # Trigger the periodic task
    # os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'openlcs.openlcs.settings')
    now = datetime.now()
    print("current time is:")
    print(now)
    future_time = now + timedelta(seconds=60)
    print("future time is:")
    print(future_time)
    print("future_time.minute is:")
    print(future_time.minute)
    schedule, _ = CrontabSchedule.objects.get_or_create(
        minute=future_time.minute,
        hour=future_time.hour,
            day_of_week='*',
            day_of_month='*',
            month_of_year='*',
            )
    schedule.save()
    periodic_task = PeriodicTask.objects.create(
            crontab=schedule,
            name='test_run_corgi_sync',
            task='openlcsd.flow.periodic_tasks.run_corgi_sync',
            )
    periodic_task.save()
    print(PeriodicTask.objects.all())
    #run_corgi_sync = PeriodicTask.objects.get(name='run_corgi_sync')
    #run_corgi_sync.crontab = schedule
    #run_corgi_sync.save()
    #client.update_crontab_schedule()
    # Waiting for the periodic task to trigger the collection components from
    # Corgi
    time.sleep(80)
    response1 = client.api_call(
        specific_subscription,
        method="GET",
        expected_code=status.HTTP_200_OK
    )
    assert response1['component_purls'] == \
            ["pkg:rpm/redhat/virt-who@0.11-5.ael7b?arch=src"]

