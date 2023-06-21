import os
import requests


def get_no_scanned_rpm_testdata():
    package_name = os.getenv('TEST_PACAGE_NAME')
    params = {
             "name": package_name,
             "missing_scan_url": True,
             "type": "RPM",
             "namespace": "REDHAT",
             "arch": "src"
        }
    url = os.getenv("CORGI_API_STAGE") + "components"
    try:
        response = requests.get(f"{url}", params=params, timeout=5)
        if response.status_code == 200:
            result = response.json()['results'][0]
            return result["nvr"], result["nevra"], result['purl']
    except Exception as error:
        print(f"An exception occurred for getting test_data {package_name}:",
              error)


def get_the_openlcs_scan_url(test_data_src=None):
    params = {
            "nevra": test_data_src,
            "type": "RPM",
            "namespace": "REDHAT",
            "arch": "src"
        }
    url = os.getenv("CORGI_API_STAGE") + "components"
    try:
        response = requests.get(f"{url}", params=params, timeout=5)
        if response.status_code == 200:
            result = response.json()['results'][0]
            return result["openlcs_scan_url"]
    except Exception as error:
        print(f"An exception occurred for getting openlcs_scan_url for"
              f"{test_data_src}:", error)
