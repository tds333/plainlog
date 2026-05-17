# Plainlog

[![PyPI - Version](https://img.shields.io/pypi/v/plainlog.svg)](https://pypi.org/project/plainlog)
[![PyPI - Python Version](https://img.shields.io/pypi/pyversions/plainlog.svg)](https://pypi.org/project/plainlog)
[![Documentation](https://img.shields.io/badge/docs-github--pages-blue)](https://tds333.github.io/plainlog/)

-----

## Installation

```console
pip install plainlog
```

or add it to your project with

```console
uv add plainlog
uv sync
```

## Quickstart

```python
from plainlog import logger

logger.info("hello world")
logger.warning("look out!")
logger.error("something broke")
```

Or use a profile for more structured output:

```python
from plainlog import logger
from plainlog.configure import apply_log_profile

apply_log_profile("develop", level="DEBUG")
logger.info("ready to go")
```

## Idea

Main goal is to be a plain easy to use logging library.
Simple, small, and fast.

If you are too lazy for long configuration settings simply use the provided log profiles.
Advanced configuration can be done with environment variables or in the code.

No dependencies to other libraries. Pure Python working in different Python implementations.


## Status

In development beta, internal interfaces can change.

## License

`plainlog` is distributed under the terms of any of the following licenses:

- [Apache-2.0](https://spdx.org/licenses/Apache-2.0.html)
- [MIT](https://spdx.org/licenses/MIT.html)
