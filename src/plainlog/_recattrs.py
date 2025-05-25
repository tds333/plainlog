# SPDX-FileCopyrightText: 2023 Wolfgang Langner <tds333@mailbox.org>
#
# SPDX-License-Identifier: Apache-2.0 OR MIT
import pickle
from types import TracebackType
from typing import NamedTuple, Callable, Any, Tuple, Dict, Optional


class Level(NamedTuple):
    no: int
    name: str

    def __repr__(self) -> str:
        return "(no=%r, name=%r)" % (self.no, self.name)

    def __format__(self, spec):
        return self.name.__format__(spec)


class HandlerRecord(NamedTuple):
    name: str
    level: Level
    print_errors: bool
    handler: Callable


class Options(NamedTuple):
    name: str
    preprocessors: Tuple[Callable, ...]
    processors: Tuple[Callable, ...]
    extra: Dict[str, Any]


class RecordException(NamedTuple):
    type: Optional[type[BaseException]]
    value: Optional[BaseException]
    traceback: Optional[TracebackType]

    def __repr__(self):
        return "(type=%r, value=%r, traceback=%r)" % (self.type, self.value, self.traceback)

    def __reduce__(self):
        # The traceback is not picklable so we need to remove it. Also, some custom exception
        # values aren't picklable either. For user convenience, we try first to serialize it and
        # we remove the value in case or error. As an optimization, we could have re-used the
        # dumped value during unpickling, but this requires using "pickle.loads()" which is
        # flagged as insecure by some security tools.
        try:
            pickle.dumps(self.value)
        except pickle.PickleError:
            return (RecordException, (self.type, None, None))
        else:
            return (RecordException, (self.type, self.value, None))
