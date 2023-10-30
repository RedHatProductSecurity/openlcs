from rest_framework import status

from packages.models import ComponentSubscription


def test_report_metrics(openlcs_client):
    """
    Test for report metrics
    """
    # Create a subscription with component_urls and source_purls
    subscription_name = "report_subscription"
    openlcs_client.api_call(
        "/subscriptions/",
        method="POST",
        data={
            "name": subscription_name,
            "query_params": '{"nevra": "389-ds-base-1.2.11.15-22.el6_4.i686"}',
            "component_purls": "pkg:rpm/redhat/389-ds-base@1.2.11.15-22.el6_4?arch=i686",
            "source_purls": "pkg:rpm/redhat/389-ds-base@1.2.11.15-22.el6_4?arch=src"
        },
        expected_code=status.HTTP_201_CREATED
    )

    # Get report metrics
    url = '/reportmetrics/'
    response = openlcs_client.api_call(url, 'GET')
    expected = [
        {
            'name': 'ansible_automation_platform:2.2',
            'active': True,
            'query_params': {'ofuri': 'o:redhat:ansible_automation_platform:2.2'},
            'total_scans': 0
        },
        {
            'name': 'redhat:3amp:2 src components',
            'active': True,
            'query_params': {'arch': 'src', 'ofuri': 'redhat:3amp:2'},
            'total_scans': 0
        },
        {
            'name': 'report_subscription',
            'active': False,
            'query_params': {'nevra': '389-ds-base-1.2.11.15-22.el6_4.i686'},
            'total_scans': 1
        }
    ]
    assert response.get("results") == expected
