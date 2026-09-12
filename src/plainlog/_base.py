# SPDX-FileCopyrightText: 2023 Wolfgang Langner <tds333@mailbox.org>
#
# SPDX-License-Identifier: Apache-2.0 OR MIT
import pickle
from types import TracebackType
from typing import Any, Dict, NamedTuple, Optional, Protocol, Union

# Msg = str
Msg = Any
"""Type alias for log message content. Accepts any type."""
Record = Dict[str, Any]
"""Type alias for a log record — a plain dictionary."""


class RecordException(NamedTuple):
    """Pickle-safe exception info attached to log records.

    Attributes:
        type: The exception class, or ``None``.
        value: The exception instance, or ``None``.
        traceback: The traceback object, or ``None``.
            Stripped during pickling.
    """

    type: Optional[type[BaseException]]
    value: Optional[BaseException]
    traceback: Optional[TracebackType]

    def __repr__(self):
        return "(type=%r, value=%r, traceback=%r)" % (
            self.type,
            self.value,
            self.traceback,
        )

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


class ProcessorProtocol(Protocol):
    def __call__(self, record: Record) -> Record: ...


class ProcessorCloseProtocol(ProcessorProtocol, Protocol):
    def close(self) -> None: ...
    def __call__(self, record: Record) -> Record: ...


UniversalProcessorProtocol = Union[ProcessorProtocol, ProcessorCloseProtocol]
