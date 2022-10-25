

def test_tasks(openlcs_client):
    """
    Test for retrieving tasks
    """
    url = '/tasks/?meta_id=&params=&owner__username=&status=SUCCESS&date_done=&traceback='
    get_success_response = openlcs_client.api_call(url, 'GET')
    success_expected = [
        {
            "id": 4,
            "meta_id": "8d43f692-e3c6-4924-8b3c-2cb362a4fe01",
            "owner": "admin",
            "params": "{\"package_nvr\": \"fio-3.1-2.el7\", \"license_scan\": true, \"copyright_scan\": true, \"product_release\": \"satellite-6.9.0\"}",
            "status": "SUCCESS",
            "date_done": "2022-11-01T08:04:39.502104Z",
            "traceback": None
        },
        {
            "id": 3,
            "meta_id": "8f01a79b-4cfd-47e8-a15f-acc7e8288b7d",
            "owner": "admin",
            "params": "{\"package_nvr\": \"ansible-2.4.2.0-2.el7\", \"license_scan\": true, \"copyright_scan\": true, \"product_release\": \"satellite-6.9.0\"}",
            "status": "SUCCESS",
            "date_done": "2022-11-01T08:35:25.695500Z",
            "traceback": None
        }
    ]

    assert get_success_response.get("results") == success_expected

    url = '/tasks/?meta_id=8d43f692-e3c6-4924-8b3c-2cb362a4fe01&params=&owner__username=&status=SUCCESS&date_done=&traceback='
    get_target_task_id_response = openlcs_client.api_call(url, 'GET')
    target_task_id_expected = [
        {
            "id": 4,
            "meta_id": "8d43f692-e3c6-4924-8b3c-2cb362a4fe01",
            "owner": "admin",
            "params": "{\"package_nvr\": \"fio-3.1-2.el7\", \"license_scan\": true, \"copyright_scan\": true, \"product_release\": \"satellite-6.9.0\"}",
            "status": "SUCCESS",
            "date_done": "2022-11-01T08:04:39.502104Z",
            "traceback": None
        }
    ]

    assert get_target_task_id_response.get("results") == target_task_id_expected
