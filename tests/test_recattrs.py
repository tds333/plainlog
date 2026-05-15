import pickle

from plainlog._recattrs import Level, RecordException


def test_level_creation():
    level = Level(10, "DEBUG")
    assert level.no == 10
    assert level.name == "DEBUG"


def test_level_repr():
    level = Level(20, "INFO")
    assert repr(level) == "(no=20, name='INFO')"


def test_level_format():
    level = Level(30, "WARNING")
    assert f"{level}" == "WARNING"
    assert f"{level:>10}" == "   WARNING"


def test_level_equality():
    assert Level(10, "DEBUG") == Level(10, "DEBUG")
    assert Level(10, "DEBUG") != Level(20, "INFO")


def test_level_hash():
    s = {Level(10, "DEBUG")}
    assert Level(10, "DEBUG") in s


def test_record_exception_creation():
    try:
        raise ValueError("test error")
    except ValueError:
        typ, val, tb = __import__("sys").exc_info()
        re = RecordException(typ, val, tb)
    assert re.type is ValueError
    assert isinstance(re.value, ValueError)
    assert re.traceback is not None


def test_record_exception_repr():
    try:
        raise RuntimeError("boom")
    except RuntimeError:
        typ, val, tb = __import__("sys").exc_info()
        re = RecordException(typ, val, tb)
        r = repr(re)
        assert "RuntimeError" in r
        assert "boom" in r


def test_record_exception_none_fields():
    re = RecordException(None, None, None)
    assert re.type is None
    assert re.value is None
    assert re.traceback is None


def test_record_exception_pickle_roundtrip():
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


def test_record_exception_reduce_error():
    class UnpicklableExc(Exception):
        def __reduce_ex__(self, protocol):
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


def test_record_exception_reduce_no_traceback():
    re = RecordException(ValueError, ValueError("simple"), None)
    result = re.__reduce__()
    assert result[0] is RecordException
    assert result[1][0] is ValueError
    assert isinstance(result[1][1], ValueError)
    assert result[1][2] is None


def test_record_exception_reduce_with_traceback():
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
