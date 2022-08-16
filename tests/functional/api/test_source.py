import os


def test_sources(openlcs_client):
    """
    Test for retrieving sources
    """
    url = '/sources/'
    response = openlcs_client.api_call(url, 'GET')
    expected = [{
                    'id': 1,
                    'license_detections': [],
                    'copyright_detections': [],
                    'component_set': [],
                    'checksum': '45f5aacb70f6eddac629375bd4739471ece1a2747123338349df069919e909ac',
                    'name': 'ansible-2.4.2.0-2.el7.src.rpm',
                    'url': f'{os.getenv("KOJI_DOWNLOAD")}//vol/rhel-7/packages/ansible/2.4.2.0/2.el7/src/ansible-2.4.2.0-2.el7.src.rpm',
                    'state': 0,
                    'archive_type': 'rpm',
                    'scan_flag': 'license(scancode-toolkit 30.1.0),copyright(scancode-toolkit 30.1.0)'
                }]

    assert response.get("results") == expected
