def test_sources(pelc_client):
    """
    Test for retrieving sources
    """
    url = '/sources/'
    response = pelc_client.api_call(url, 'GET')
    expected = [{'id': 1, 'license_detections': [], 'copyright_detections': [],
                 'checksum': '45f5aacb70f6eddac629375bd4739471ece1a2747123338349df069919e909ac',
                 'name': 'ansible-2.4.2.0-2.el7.src.rpm',
                 'url': 'http://download.eng.bos.redhat.com/brewroot//vol/rhel-7/packages/ansible/2.4.2.0/2.el7/src/ansible-2.4.2.0-2.el7.src.rpm',
                 'state': 0, 'archive_type': 'rpm'}]
    assert response.get("results") == expected
