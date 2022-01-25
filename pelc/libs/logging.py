import os
import logging

import sys


class ClosingFileHandler(logging.Handler):
    def __init__(self, path):
        super().__init__()
        self.path = path

    def emit(self, record):
        msg = self.format(record) + '\n'
        self.acquire()
        try:
            with open(self.path, 'a', encoding='utf8') as f:
                f.write(msg)
        finally:
            self.release()


def get_task_logger(directory, task_id):
    # Create a new logger each time to prevent mixing handlers
    task_logger = logging.Logger('pelc.task_logger.{}'.format(task_id))
    log_file = os.path.join(directory, '{}.log'.format(task_id))
    file_handler = ClosingFileHandler(log_file)
    formatter = logging.Formatter(
        '[%(asctime)s] [%(levelname)s] %(message)s',
    )
    file_handler.setFormatter(formatter)
    stderr_handler = logging.StreamHandler(sys.stderr)
    stderr_handler.setFormatter(formatter)
    task_logger.addHandler(file_handler)
    task_logger.addHandler(stderr_handler)
    task_logger.setLevel(logging.INFO)
    return task_logger
