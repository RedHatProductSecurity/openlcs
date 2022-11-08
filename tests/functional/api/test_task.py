

def test_list_tasks(openlcs_client):
    """
    Test for list tasks
    """
    url = '/tasks/?meta_id=&params=&owner__username=&status=SUCCESS&date_done=&traceback='
    get_success_response = openlcs_client.api_call(url, 'GET')
    success_expected = [
        {
            'id': 4,
            'meta_id': '9f2008cc-78d4-4eaf-97b4-2455d70c4420',
            'owner': 'admin',
            'params': '{"package_nvr": "fio-3.1-2.el7", "license_scan": true, "copyright_scan": true, "product_release": "satellite-6.9.0"}',
            'status': 'SUCCESS',
            'date_done': '2022-11-02T11:42:51.971000',
            'traceback': None
        }
    ]

    assert get_success_response.get("results") == success_expected

    url = '/tasks/?meta_id=ce369f13-b9ec-4a10-9670-0a3647e2770b&' \
          'params=ansible&owner__username=admin&status=STARTED&date_done=&traceback='
    combine_query_response = openlcs_client.api_call(url, 'GET')
    combine_query_expected = [
        {
            'id': 1,
            'meta_id': 'ce369f13-b9ec-4a10-9670-0a3647e2770b',
            'owner': 'admin',
            'params': '{"package_nvr": "ansible-2.4.2.0-2.el7", "license_scan": true, "copyright_scan": true, "product_release": "satellite-6.9.0"}',
            'status': 'STARTED',
            'date_done': None,
            'traceback': None
        }
    ]

    assert combine_query_response.get("results") == combine_query_expected

    url = '/tasks/'
    list_response = openlcs_client.api_call(url, 'GET')
    list_expected = [
        {
            'id': 1,
            'meta_id': 'ce369f13-b9ec-4a10-9670-0a3647e2770b',
            'owner': 'admin',
            'params': '{"package_nvr": "ansible-2.4.2.0-2.el7", "license_scan": true, "copyright_scan": true, "product_release": "satellite-6.9.0"}',
            'status': 'STARTED',
            'date_done': None,
            'traceback': None
        },
        {
            'id': 2,
            'meta_id': 'e647c67c-7941-45a7-8712-97c4ac9d9a01',
            'owner': 'admin',
            'params': '{"package_nvr": "fio-3.1-2.el7", "license_scan": true, "copyright_scan": true, "product_release": "satellite-6.9.0"}',
            'status': 'STARTED',
            'date_done': None,
            'traceback': None
        },
        {
            'id': 3,
            'meta_id': 'b0693b20-9190-4ebc-93ac-3dccd57a7718',
            'owner': 'admin',
            'params': '{"package_nvr": "ansible-2.4.2.0-2.el7", "license_scan": true, "copyright_scan": true, "product_release": "satellite-6.9.0"}',
            'status': 'STARTED',
            'date_done': None,
            'traceback': None
        },
        {
            'id': 4,
            'meta_id': '9f2008cc-78d4-4eaf-97b4-2455d70c4420',
            'owner': 'admin',
            'params': '{"package_nvr": "fio-3.1-2.el7", "license_scan": true, "copyright_scan": true, "product_release": "satellite-6.9.0"}',
            'status': 'SUCCESS',
            'date_done': '2022-11-02T11:42:51.971000',
            'traceback': None
        }
    ]

    assert list_response.get("results") == list_expected
