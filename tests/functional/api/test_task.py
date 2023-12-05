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
            'params': '{"component": {"version": "v1.2.0", "nevra": "github.com/stoewer/go-strcase-v1.2.0.noarch", "link": "https://corgi.prodsec.redhat.com/api/v1/components?purl=pkg%3Agolang/github.com/stoewer/go-strcase%40v1.2.0", "software_build": {}, "download_url": "https://github.com/stoewer/go-strcase/archive/v1.2.0.zip", "purl": "pkg:golang/github.com/stoewer/go-strcase@v1.2.0", "nvr": "github.com/stoewer/go-strcase-v1.2.0", "type": "GOLANG", "arch": "noarch", "name": "github.com/stoewer/go-strcase", "license_declared": "", "uuid": "ca7cb0b1-7f3e-4163-a7e9-58ee71f92002", "release": ""}, "license_scan": true, "copyright_scan": true, "priority": "medium", "parent": "450daf6f-e195-495e-a073-51a9c945d514", "provenance": "sync_corgi", "parent_component": {"name": "ose-cluster-samples-operator-container", "version": "v4.14.0", "release": "202311021650.p0.gb5396eb.assembly.stream", "build_id": "2764441", "purl": "pkg:oci/ose-cluster-samples-operator@sha256:498741e91d2414f07ff6a634cf69b68b7803e5f2f3485360d56fb5868c3a8cbf?repository_url=registry.redhat.io/openshift/ose-cluster-samples-operator&tag=v4.14.0-202311021650.p0.gb5396eb.assembly.stream", "arch": "noarch"}}',
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
            'params': '{"component": {"version": "1.2.6", "nevra": "@aashutoshrathi/word-wrap-1.2.6.noarch", "link": "https://corgi.prodsec.redhat.com/api/v1/components?purl=pkg%3Anpm/%2540aashutoshrathi/word-wrap%401.2.6", "software_build": {}, "download_url": "http://registry.npmjs.org/word-wrap/-/word-wrap-1.2.6.tgz", "purl": "pkg:npm/%40aashutoshrathi/word-wrap@1.2.6", "nvr": "@aashutoshrathi/word-wrap-1.2.6", "type": "NPM", "arch": "noarch", "name": "@aashutoshrathi/word-wrap", "license_declared": "", "uuid": "b5e51bdc-58a2-4384-88c5-c54e2989919a", "release": ""}, "license_scan": true, "copyright_scan": true, "priority": "medium", "provenance": "sync_corgi"}',
            'status': 'SUCCESS',
            'date_done': '2022-11-11T05:18:34.601000',
            'traceback': None,
            'object_url': 'http://{}/rest/v1/sources/2/'.format(settings.HOSTNAME),
            'parent_task_id': ''
        },
        {
            "id": 3,
            "meta_id": "e06038ad-4144-4fb5-b812-67df3a8e5dde",
            'owner': 'admin',
            'params': '{"component": {"version": "v4.3.0", "nevra": "sigs.k8s.io/structured-merge-diff/v4-v4.3.0.noarch", "link": "https://corgi.prodsec.redhat.com/api/v1/components?purl=pkg%3Agolang/sigs.k8s.io/structured-merge-diff/v4%40v4.3.0", "software_build": {}, "download_url": "https://proxy.golang.org/sigs.k8s.io/structured-merge-diff/v4/@v/v4.3.0.zip", "purl": "pkg:golang/sigs.k8s.io/structured-merge-diff/v4@v4.3.0", "nvr": "sigs.k8s.io/structured-merge-diff/v4-v4.3.0", "type": "GOLANG", "arch": "noarch", "name": "sigs.k8s.io/structured-merge-diff/v4", "license_declared": "", "uuid": "272c1db2-fd7f-4a9d-afc5-944b24c70b4f", "release": ""}, "license_scan": true, "copyright_scan": true, "priority": "medium", "parent": "450daf6f-e195-495e-a073-51a9c945d514", "provenance": "sync_corgi", "subscription_id": 3, "parent_component": {"name": "ose-cluster-samples-operator-container", "version": "v4.14.0", "release": "202311021650.p0.gb5396eb.assembly.stream", "build_id": "2764441", "purl": "pkg:oci/ose-cluster-samples-operator@sha256:498741e91d2414f07ff6a634cf69b68b7803e5f2f3485360d56fb5868c3a8cbf?repository_url=registry.redhat.io/openshift/ose-cluster-samples-operator&tag=v4.14.0-202311021650.p0.gb5396eb.assembly.stream", "arch": "noarch"}}',
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
            'params': '{"component": {"version": "1.2.6", "nevra": "@aashutoshrathi/word-wrap-1.2.6.noarch", "link": "https://corgi.prodsec.redhat.com/api/v1/components?purl=pkg%3Anpm/%2540aashutoshrathi/word-wrap%401.2.6", "software_build": {}, "download_url": "http://registry.npmjs.org/word-wrap/-/word-wrap-1.2.6.tgz", "purl": "pkg:npm/%40aashutoshrathi/word-wrap@1.2.6", "nvr": "@aashutoshrathi/word-wrap-1.2.6", "type": "NPM", "arch": "noarch", "name": "@aashutoshrathi/word-wrap", "license_declared": "", "uuid": "b5e51bdc-58a2-4384-88c5-c54e2989919a", "release": ""}, "license_scan": true, "copyright_scan": true, "priority": "medium", "provenance": "sync_corgi"}',
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
            'params': '{"component": {"version": "v1.2.0", "nevra": "github.com/stoewer/go-strcase-v1.2.0.noarch", "link": "https://corgi.prodsec.redhat.com/api/v1/components?purl=pkg%3Agolang/github.com/stoewer/go-strcase%40v1.2.0", "software_build": {}, "download_url": "https://github.com/stoewer/go-strcase/archive/v1.2.0.zip", "purl": "pkg:golang/github.com/stoewer/go-strcase@v1.2.0", "nvr": "github.com/stoewer/go-strcase-v1.2.0", "type": "GOLANG", "arch": "noarch", "name": "github.com/stoewer/go-strcase", "license_declared": "", "uuid": "ca7cb0b1-7f3e-4163-a7e9-58ee71f92002", "release": ""}, "license_scan": true, "copyright_scan": true, "priority": "medium", "parent": "450daf6f-e195-495e-a073-51a9c945d514", "provenance": "sync_corgi", "parent_component": {"name": "ose-cluster-samples-operator-container", "version": "v4.14.0", "release": "202311021650.p0.gb5396eb.assembly.stream", "build_id": "2764441", "purl": "pkg:oci/ose-cluster-samples-operator@sha256:498741e91d2414f07ff6a634cf69b68b7803e5f2f3485360d56fb5868c3a8cbf?repository_url=registry.redhat.io/openshift/ose-cluster-samples-operator&tag=v4.14.0-202311021650.p0.gb5396eb.assembly.stream", "arch": "noarch"}}',
            'status': 'SUCCESS',
            'date_done': '2022-11-11T04:28:59.961000',
            'traceback': None,
            'object_url': 'http://{}/rest/v1/sources/1/'.format(settings.HOSTNAME),
            'parent_task_id': ''
        },
        {
            "id": 3,
            "meta_id": "e06038ad-4144-4fb5-b812-67df3a8e5dde",
            'owner': 'admin',
            'params': '{"component": {"version": "v4.3.0", "nevra": "sigs.k8s.io/structured-merge-diff/v4-v4.3.0.noarch", "link": "https://corgi.prodsec.redhat.com/api/v1/components?purl=pkg%3Agolang/sigs.k8s.io/structured-merge-diff/v4%40v4.3.0", "software_build": {}, "download_url": "https://proxy.golang.org/sigs.k8s.io/structured-merge-diff/v4/@v/v4.3.0.zip", "purl": "pkg:golang/sigs.k8s.io/structured-merge-diff/v4@v4.3.0", "nvr": "sigs.k8s.io/structured-merge-diff/v4-v4.3.0", "type": "GOLANG", "arch": "noarch", "name": "sigs.k8s.io/structured-merge-diff/v4", "license_declared": "", "uuid": "272c1db2-fd7f-4a9d-afc5-944b24c70b4f", "release": ""}, "license_scan": true, "copyright_scan": true, "priority": "medium", "parent": "450daf6f-e195-495e-a073-51a9c945d514", "provenance": "sync_corgi", "subscription_id": 3, "parent_component": {"name": "ose-cluster-samples-operator-container", "version": "v4.14.0", "release": "202311021650.p0.gb5396eb.assembly.stream", "build_id": "2764441", "purl": "pkg:oci/ose-cluster-samples-operator@sha256:498741e91d2414f07ff6a634cf69b68b7803e5f2f3485360d56fb5868c3a8cbf?repository_url=registry.redhat.io/openshift/ose-cluster-samples-operator&tag=v4.14.0-202311021650.p0.gb5396eb.assembly.stream", "arch": "noarch"}}',
            'status': 'SUCCESS',
            'date_done': '2022-11-11T05:18:34.601000',
            'traceback': None,
            'object_url': 'http://{}/rest/v1/sources/2/'.format(settings.HOSTNAME),
            'parent_task_id': ''
        }
    ]

    assert list_response.get("results") == list_expected
