

def test_sources(openlcs_client):
    """
    Test for retrieving sources
    """
    url = '/sources/'
    response = openlcs_client.api_call(url, 'GET')
    expected = [
        {
            'id': 1,
            'name': 'fio-3.1-2.el7.src.rpm',
            'url': 'http://git.kernel.dk/?p=fio.git;a=summary',
            'checksum': '65ddad4b0831a46d9064d96e80283618c04bd10906be6eed14ae6c13460f0a01',
            'state': 0,
            'archive_type': 'rpm',
            'scan_flag': 'copyright(scancode-toolkit 30.1.0)',
            'component_set': [],
            'license_detections': {},
            'copyright_detections': {}
        },
        {
            'id': 2,
            'name': 'ansible-2.4.2.0-2.el7.src.rpm',
            'url': 'http://ansible.com',
            'checksum': '45f5aacb70f6eddac629375bd4739471ece1a2747123338349df069919e909ac',
            'state': 0,
            'archive_type': 'rpm',
            'scan_flag': 'copyright(scancode-toolkit 30.1.0)',
            'component_set': [],
            'license_detections': {},
            'copyright_detections': {}
        }
    ]

    assert response.get("results") == expected
