# -*- coding:utf-8 -*-
import datetime
import time
from random import randint


class ProcedureException(Exception):
    def __init__(self, message):
        Exception.__init__(self, message)


def retry(max_retries=3, max_wait_interval=10,
          max_elapsed=900, multiplier=1, rand=False):
    """
    Decorator function that wraps function, method that would be retried on
    failure capabilities. If the condition is not met, an exception is thrown.

    Arguments:
    max_retries(int): max retry time. Defaults to `3`
    max_wait_interval(int): max wait interval.
        Defaults to `10`, will use the minimal one between retry interval
        with max_wait_interval.
    max_elapsed (int): max elapsed total allowed time in seconds.
        Defaults to `15` minutes == `15 * 60` seconds.
    multiplier (int|float): exponential multiplier. Defaults to 1.
    rand(bool): random retry interval or specified interval.
        Defaults to `False`, so will get a random from (0, 2**retries).
        If set it to `True`, will retry with 2**retries interval.
        `retries` is current number of retries.

    Example:
    @retry(max_retries=3, max_wait_interval=10, max_elapsed=60, rand=True)
    def task(x):
        return x * x

    When retry 3 times, or spead 60 seconds, will raise an
    `ProcedureException` Exception.
    Will use random interval, but the max interval will be 10 seconds.
    """

    def retry_decorator(func):

        def retry_function(*args, **kwargs):
            retries = 0
            error = None
            start_time = datetime.datetime.now()
            delta_time = datetime.timedelta(seconds=max_elapsed)
            end_time = start_time + delta_time

            while retries < max_retries:
                now = datetime.datetime.now()
                if now < end_time:
                    try:
                        return func(*args, **kwargs)
                    except RuntimeError as err:
                        error = err
                        sleep_time = min(
                            2 ** retries * multiplier if not rand
                            else randint(0, 2 ** retries) * multiplier,
                            max_wait_interval)
                        time.sleep(sleep_time)
                        retries += 1
                else:
                    error = ProcedureException("Procedure request time out")
                    break

            if error:
                raise error
            else:
                raise ProcedureException("Unknown error")
        return retry_function
    return retry_decorator
