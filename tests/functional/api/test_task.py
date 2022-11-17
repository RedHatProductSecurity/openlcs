from django.conf import settings


def test_list_tasks(openlcs_client):
    """
    Test for list tasks
    """
    url = '/tasks/?meta_id=&params=&owner__username=&status=SUCCESS&date_done=&traceback=&parent_task_id='
    get_success_response = openlcs_client.api_call(url, 'GET')
    success_expected = [
        {
            'id': 2,
            'meta_id': 'e88aaa64-eeb6-4e8a-84fa-a4087c0cba1c',
            'owner': 'admin',
            'params': '{"package_nvr": "fio-3.1-2.el7", "license_scan": true, "copyright_scan": true, "product_release": "satellite-6.9.0"}',
            'status': 'SUCCESS',
            'date_done': '2022-11-11T04:28:59.961000',
            'traceback': None,
            'object_url': 'http://{}/rest/v1/sources/1/'.format(settings.HOSTNAME),
            'parent_task_id': ''
        },
        {
            'id': 1,
            'meta_id': '723b6b43-d10e-4f6e-bd01-ddc1f1928b27',
            'owner': 'admin',
            'params': '{"package_nvr": "ansible-2.4.2.0-2.el7", "license_scan": true, "copyright_scan": true, "product_release": "satellite-6.9.0"}',
            'status': 'SUCCESS',
            'date_done': '2022-11-11T05:18:34.601000',
            'traceback': None,
            'object_url': 'http://{}/rest/v1/sources/2/'.format(settings.HOSTNAME),
            'parent_task_id': ''
        }
    ]

    assert get_success_response.get("results") == success_expected

    url = '/tasks/?meta_id=ce369f13-b9ec-4a10-9670-0a3647e2770b&' \
          'params=ansible&owner__username=admin&status=STARTED&date_done=&traceback=&parent_task_id='
    combine_query_response = openlcs_client.api_call(url, 'GET')
    combine_query_expected = []

    assert combine_query_response.get("results") == combine_query_expected

    url = '/tasks/'
    list_response = openlcs_client.api_call(url, 'GET')
    list_expected = [
        {
            'id': 1,
            'meta_id': '723b6b43-d10e-4f6e-bd01-ddc1f1928b27',
            'owner': 'admin',
            'params': '{"package_nvr": "ansible-2.4.2.0-2.el7", "license_scan": true, "copyright_scan": true, "product_release": "satellite-6.9.0"}',
            'status': 'SUCCESS',
            'date_done': '2022-11-11T05:18:34.601000',
            'traceback': None,
            'object_url': 'http://{}/rest/v1/sources/2/'.format(settings.HOSTNAME),
            'parent_task_id': ''
        },
        {
            'id': 2,
            'meta_id': 'e88aaa64-eeb6-4e8a-84fa-a4087c0cba1c',
            'owner': 'admin',
            'params': '{"package_nvr": "fio-3.1-2.el7", "license_scan": true, "copyright_scan": true, "product_release": "satellite-6.9.0"}',
            'status': 'SUCCESS',
            'date_done': '2022-11-11T04:28:59.961000',
            'traceback': None,
            'object_url': 'http://{}/rest/v1/sources/1/'.format(settings.HOSTNAME),
            'parent_task_id': ''
        }
    ]

    assert list_response.get("results") == list_expected
