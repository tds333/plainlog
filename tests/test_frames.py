import sys

from plainlog._frames import (
    _format_exception,
    add_caller_info,
    get_frame,
    get_frame_fallback,
    load_get_frame_function,
)


def test_load_get_frame_returns_sys_getframe():
    func = load_get_frame_function()
    assert func is sys._getframe


def test_load_get_frame_fallback_when_no_sys_getframe():
    orig = sys._getframe
    del sys._getframe
    try:
        func = load_get_frame_function()
        assert func is get_frame_fallback
        frame = func(0)
        assert frame is not None
    finally:
        sys._getframe = orig


def test_get_frame_returns_frame():
    frame = get_frame(0)
    assert frame is not None
    assert frame.f_code.co_name == "test_get_frame_returns_frame"


def test_get_frame_with_depth():
    def inner():
        return get_frame(1)

    frame = inner()
    assert frame.f_code.co_name == "test_get_frame_with_depth"


def test_get_frame_is_sys_getframe():
    assert get_frame is sys._getframe


def test_get_frame_fallback_returns_frame():
    frame = get_frame_fallback(0)
    assert frame is not None
    assert hasattr(frame, "f_code")


def test_get_frame_fallback_walks_back_correct_depth():
    def level2():
        return level1()

    def level1():
        return get_frame_fallback(2)

    frame = level2()
    assert frame.f_code.co_name == "test_get_frame_fallback_walks_back_correct_depth"


def test_format_exception():
    try:
        raise ValueError("test error")
    except ValueError:
        result = _format_exception(sys.exc_info())
    assert "ValueError" in result
    assert "test error" in result
    assert result[-1] != "\n"


def test_format_exception_with_traceback():
    try:
        raise RuntimeError("nested")
    except RuntimeError:
        result = _format_exception(sys.exc_info())
    assert "RuntimeError" in result
    assert "nested" in result


def test_format_exception_strips_trailing_newline():
    try:
        raise Exception("msg")
    except Exception:
        result = _format_exception(sys.exc_info())
    assert not result.endswith("\n")


def test_add_caller_info_function_name():
    record = {}
    add_caller_info(record, level=1)
    assert record["function"] == "test_add_caller_info_function_name"


def test_add_caller_info_line_number():
    record = {}
    add_caller_info(record, level=1)
    assert isinstance(record["line"], int)
    assert record["line"] > 0


def test_add_caller_info_file_info():
    record = {}
    add_caller_info(record, level=1)
    assert "file_name" in record
    assert "file_path" in record
    assert "path" in record
    assert "module" in record


def test_add_caller_info_process_info():
    record = {}
    add_caller_info(record, level=1)
    assert "process_id" in record
    assert "process_name" in record


def test_add_caller_info_thread_info():
    record = {}
    add_caller_info(record, level=1)
    assert "thread_id" in record
    assert "thread_name" in record


def test_add_caller_info_level_walks_correct_depth():
    def inner():
        record = {}
        add_caller_info(record, level=2)
        return record

    result = inner()
    assert result["function"] == "test_add_caller_info_level_walks_correct_depth"
