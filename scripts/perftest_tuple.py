from enum import IntEnum
from time import time
import data
from typing import Final


LEVEL = 0
EXTRA = 7

class rec(IntEnum):
    LEVEL = 0
    MSG = 1
    NAME = 2
    DATETIME = 3
    PROCESS_INDENT = 4
    PROCESS_NAME = 5
    CONTEXT = 6
    EXTRA = 7
    ARGS = 8
    KWARGS = 9

class r:
    LEVEL: Final = 0
    MSG = 1
    NAME = 2
    DATETIME = 3
    PROCESS_INDENT = 4
    PROCESS_NAME = 5
    CONTEXT = 6
    EXTRA: Final = 7
    ARGS = 8
    KWARGS = 9



def usage_t():
    log_record = (
                10,
                "my message",  # raw message as in std logging
                "name",
                0,
                1,
                "pname",
                {},
                {},
                [],
                {},
            )
    log_record2 = (
                10,
                "my message",  # raw message as in std logging
                "name",
                0,
                1,
                "pname",
                {},
                {},
                [],
                {},
            )

    #level = log_record[rec.LEVEL]
    level = log_record[r.LEVEL]
    #level = log_record[data.LEVEL]
    #level = log_record[LEVEL]
    #level = log_record[0]

    #log_record[rec.EXTRA]["sfdf"] = "ola"
    log_record[r.EXTRA]["sfdf"] = "ola"
    #log_record[data.EXTRA]["sfdf"] = "ola"
    #log_record[EXTRA]["sfdf"] = "ola"
    #log_record[7]["sfdf"] = "ola"

def usage_d():
    log_record = {
            "level": 10,
            "msg": "my message",
            "name": "name",
            "datetime": 0,
            "process_id": 1,
            "process_name": "pname",
            "context": {},
            "extra": {},
            "args": [],
            "kwargs": {},
        }
    log_record2 = {
            "level": 10,
            "msg": "my message",
            "name": "name",
            "datetime": 0,
            "process_id": 1,
            "process_name": "pname",
            "context": {},
            "extra": {},
            "args": [],
            "kwargs": {},
        }

    level = log_record["level"]

    log_record["extra"]["sfdf"] = "ola"


def main():
    r = 1000000
    t0 = time()
    for i in range(r):
        usage_d()
    t1 = time()
    duration = t1 - t0
    print(f"duration d: {duration}")
    t0 = time()
    for i in range(r):
        usage_t()
    t1 = time()
    duration = t1 - t0
    print(f"duration t: {duration}")


if __name__ == "__main__":
    main()