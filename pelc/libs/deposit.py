import os
import requests
import re
import subprocess
import time
import json
import xml.dom.minidom


class UploadToDeposit:
    """
    Interact with deposit function
    """

    def __init__(self, settings):
        self.settings = settings
        self._upload_url = settings.get('DEPOSIT_URL')
        self._upload_username = settings.get('DEPOSIT_USER')
        self._upload_password = settings.get('DEPOSIT_PASSWORD')

    @staticmethod
    def get_deposit_id(ret_output):
        """
        @requires: `ret_output`, swh return string
        like xxx{"deposit_id": "2", "deposit_status": "deposited",
        "deposit_status_detail": null,
        "deposit_date": "Dec. 31, 2021, 4:45 a.m."}xxx
        @feeds: `deposit_id` return value of deposit_id
        """
        ret_str_regx = re.search("({.+})", ret_output)
        if not ret_str_regx:
            raise RuntimeError("Deposit return value is invalid")
        ret_str = ret_str_regx.group(0)
        try:
            ret_dict = json.loads(ret_str)
        except Exception as err:
            err_msg = f'Deposit return value is invalid. Reason: {err}'
            raise RuntimeError(err_msg) from None

        deposit_id = ret_dict.get('deposit_id')

        return deposit_id

    def deposit_archive(self, tmp_archive_path, archive_name):
        """
        Library for upload archive to deposit
        """
        # https://docs.softwareheritage.org/devel/swh-deposit/api/user-manual.html
        upload_deposit_cmd = 'swh deposit upload --username {username} ' \
                             '--password {password} ' \
                             '--url {url} ' \
                             '--archive {archive} ' \
                             '--name {name} ' \
                             '--author pelc-dev ' \
                             '--format json '.format(
                                username=self._upload_username,
                                password=self._upload_password,
                                url=self._upload_url,
                                archive=tmp_archive_path,
                                name=archive_name)
        proc = subprocess.Popen(upload_deposit_cmd,
                                shell=True,
                                stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE)
        ret_output, error = proc.communicate()
        err_msg = error.decode('utf-8')
        ret_output = ret_output.decode('utf-8')
        # Ignore this warning message
        ignore_msg = 'WARNING:swh.deposit.cli.client:The metadata ' \
                     ' file provided should contain ' \
                     '"<swh:create_origin>" or "<swh:add_to_origin>" tag'
        if err_msg.strip() != ignore_msg:
            raise RuntimeError("Upload archive to deposit failed")
        return ret_output

    def check_deposit_archive_status(self, deposit_id):
        """
        Library for function check upload result
        """
        # Retrieve deposit archive status
        end_time = time.time() + 60 * 30  # waiting for 30 minutes timeout
        check_deposit_interval_time = 20

        while True:
            # Check status period is 20s
            time.sleep(check_deposit_interval_time)
            if time.time() > end_time:
                raise TimeoutError("Upload timeout")

            # https://docs.softwareheritage.org/devel/swh-deposit/endpoints/status.html
            retrieve_url = os.path.join(self._upload_url,
                                        self._upload_username,
                                        deposit_id,
                                        'status')
            res = requests.get(retrieve_url, auth=(self._upload_username,
                                                   self._upload_password))
            # Deposit return example:
            # https://docs.softwareheritage.org/devel/swh-deposit/endpoints/status.html
            DOMTree = xml.dom.minidom.parseString(res.text)
            collection = DOMTree.documentElement
            deposit_status = collection.\
                getElementsByTagName("sd:deposit_status")[0].\
                childNodes[0].data
            if deposit_status == "done":
                return deposit_status

    def save_data_to_pelc(self):
        """
        After upload archive to deposit success,
        should save data to pelc database
        """
        raise NotImplementedError
