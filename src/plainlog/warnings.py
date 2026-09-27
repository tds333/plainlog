import warnings
from typing import Callable, Optional, TextIO, Type, Union

from . import logger

_warnings_showwarning: Optional[Callable[..., None]] = None
_warnings_logger = logger.new("py.warnings")

# mostly copies from Python logging


def _showwarning(
    message: Union[Warning, str],
    category: Type[Warning],
    filename: str,
    lineno: int,
    file: Optional[TextIO] = None,
    line: Optional[str] = None,
) -> None:
    """
    Implementation of showwarnings which redirects to logging, which will first
    check to see if the file parameter is None. If a file is specified, it will
    delegate to the original warnings implementation of showwarning. Otherwise,
    it will call warnings.formatwarning and will log the resulting string to a
    warnings logger named "py.warnings" with level logging.WARNING.
    """
    if file is not None:
        if _warnings_showwarning is not None:
            _warnings_showwarning(message, category, filename, lineno, file, line)
    else:
        s = warnings.formatwarning(message, category, filename, lineno, line)
        _warnings_logger.warning(str(s))


def capture_warnings(capture: bool) -> None:
    """
    If capture is true, redirect all warnings to the logging package.
    If capture is False, ensure that warnings are not redirected to logging
    but to their original destinations.
    """
    global _warnings_showwarning
    if capture:
        if _warnings_showwarning is None:
            _warnings_showwarning = warnings.showwarning
            warnings.showwarning = _showwarning  # type: ignore
    else:
        if _warnings_showwarning is not None:
            warnings.showwarning = _warnings_showwarning  # type: ignore
            _warnings_showwarning = None
