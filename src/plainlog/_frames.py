import sys
import traceback
from collections.abc import Callable
from io import StringIO
from os.path import basename, splitext
from pathlib import Path
from threading import current_thread
from types import FrameType

from ._base import Record


def get_frame_fallback(n: int) -> FrameType:
    try:
        raise Exception
    except Exception:
        frame = sys.exc_info()[2].tb_frame.f_back  # type: ignore
        for _ in range(n):
            frame = frame.f_back  # type: ignore
        return frame  # type: ignore


def load_get_frame_function() -> Callable[[int], FrameType]:
    if hasattr(sys, "_getframe"):
        get_frame = sys._getframe
    else:
        get_frame = get_frame_fallback
    return get_frame


get_frame = load_get_frame_function()


def _format_exception(exc_info: tuple) -> str:
    """
    Prettyprint an `exc_info` tuple.

    Shamelessly stolen from stdlib's logging module.
    """
    sio = StringIO()

    traceback.print_exception(exc_info[0], exc_info[1], exc_info[2], None, sio)
    s = sio.getvalue()
    sio.close()
    if s[-1:] == "\n":  # pragma: no cover
        s = s[:-1]

    return s


def add_caller_info(record: Record, call_level: int = 3) -> None:
    frame = get_frame(call_level)
    # name = frame.f_globals["__name__"]
    code = frame.f_code
    file_path = code.co_filename
    file_name = basename(file_path)
    thread = current_thread()
    record["function"] = code.co_name
    record["line"] = frame.f_lineno
    record["path"] = Path(file_path)
    record["module"] = splitext(file_name)[0]
    record["file_name"] = file_name
    record["file_path"] = file_path
    record["thread_id"] = thread.ident
    record["thread_name"] = thread.name
