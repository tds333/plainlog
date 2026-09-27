from __future__ import annotations

import pickle
from typing import Any

from plainlog._base import RecordException


def test_record_exception_creation() -> None:
    try:
        raise ValueError("test error")
    except ValueError:
        typ, val, tb = __import__("sys").exc_info()
        re = RecordException(typ, val, tb)
    assert re.type is ValueError
    assert isinstance(re.value, ValueError)
    assert re.traceback is not None


def test_record_exception_repr() -> None:
    try:
        raise RuntimeError("boom")
    except RuntimeError:
        typ, val, tb = __import__("sys").exc_info()
        re = RecordException(typ, val, tb)
        r = repr(re)
        assert "RuntimeError" in r
        assert "boom" in r


def test_record_exception_none_fields() -> None:
    re = RecordException(None, None, None)
    assert re.type is None
    assert re.value is None
    assert re.traceback is None


def test_record_exception_pickle_roundtrip() -> None:
    try:
        raise ValueError("pickle me")
    except ValueError:
        typ, val, tb = __import__("sys").exc_info()
        re = RecordException(typ, val, tb)
    data = pickle.dumps(re)
    loaded = pickle.loads(data)
    assert loaded.type is ValueError
    assert isinstance(loaded.value, ValueError)
    assert str(loaded.value) == "pickle me"
    assert loaded.traceback is None


def test_record_exception_reduce_error() -> None:
    class UnpicklableExc(Exception):
        def __reduce_ex__(self, protocol: Any) -> Any:
            raise pickle.PickleError("cannot pickle")

    try:
        raise UnpicklableExc("oops")
    except UnpicklableExc:
        typ, val, tb = __import__("sys").exc_info()
        re = RecordException(typ, val, tb)
    result = re.__reduce__()
    assert result[0] is RecordException
    assert result[1][0] is UnpicklableExc
    assert result[1][1] is None
    assert result[1][2] is None


def test_record_exception_reduce_no_traceback() -> None:
    re = RecordException(ValueError, ValueError("simple"), None)
    result = re.__reduce__()
    assert result[0] is RecordException
    assert result[1][0] is ValueError
    assert isinstance(result[1][1], ValueError)
    assert result[1][2] is None


def test_record_exception_reduce_with_traceback() -> None:
    try:
        raise TypeError("bad")
    except TypeError:
        typ, val, tb = __import__("sys").exc_info()
        re = RecordException(typ, val, tb)
    result = re.__reduce__()
    assert result[0] is RecordException
    assert result[1][0] is TypeError
    assert isinstance(result[1][1], TypeError)
    assert result[1][2] is None
