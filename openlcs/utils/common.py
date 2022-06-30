import datetime
import json


class DateEncoder(json.JSONEncoder):
    def default(self, o):    # pylint: disable=E0202
        if isinstance(o, datetime.datetime):
            return o.strftime('%Y-%m-%d %H:%M:%S')
        elif isinstance(o, datetime.date):
            return o.strftime("%Y-%m-%d")
        else:
            return json.JSONEncoder.default(self, o)
