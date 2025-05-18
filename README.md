# Plainlog

[![PyPI - Version](https://img.shields.io/pypi/v/plainlog.svg)](https://pypi.org/project/plainlog)
[![PyPI - Python Version](https://img.shields.io/pypi/pyversions/plainlog.svg)](https://pypi.org/project/plainlog)

-----

**Table of Contents**

- [Installation](#installation)
- [License](#license)

## Installation

```console
pip install plainlog
```

or add it to your project with

```console
uv add plainlog
uv sync
```

## Installation for development

You need `uv` as package and environment manager, see [uv installation](https://docs.astral.sh/uv/getting-started/installation/).
Than `make install`. Now you can use the make commands, see `make help`.

## Idea

Main goal is to be a plain easy to use logging library.
Simple, small, and fast.

If you are to lazy for long configuration settings simply use the provided log profiles.
Advanced configuration can be done with environment variables or in the code.

No dependencies to other libraries. Pure Python working in different Python implementations.

### What is the difference to other logging libraries?

Plainlog wants to be simple and fast. It should work the same way in async and sync code.
Because of this there is a clean separation between a logger and the core. This separation is done with a thread safe queue.
This guaranties nothing is blocking your code, so you simply can use the logger in an async context.

You don't have to care about performance, the hot path of the logger is minimal and fast.
It creates a dict and puts it into a queue. The core handles the rest in an extra thread, not blocking anything.

The concept of preprocessors and processors is special. A preprocessor runs in the context of the logger (application Thread), a processor in the context of the core (logger core Thread).
So you can enrich log record information in the context of the call or later in the context of processing.

For easy usage and configuration a list of profiles is availabel.
They add documented (pre)-processors and handlers and everything is ready to be used.


### What is from other libraries?

From structlog the idea of processors are taken. But simplyfied and separated. In plainlog it is a simple list of preprocessors and processors
and they are executed in order. No wraping and complicated parameter handling.
Also the formating for development log output is inspired from structlog. The logger has the feature to `bind` and `unbind` extra variables.

From loguru the concept of a logger and core is taken. But with cleaner separation.
The separation in plainlog is also seen with configuration, it is done on the core and not mixed up with the logger.
Also the separation in handling log records is done with a queue and extra thread in the core.
The logger has the feature to add something to the `context` or use the `contextualize` context manager.

From logbook the idea of the fingerscrossed handler was taken.

From twisted logging, the idea a record is simply a dictionary. Nothing more, nothing special.

From the Python standard library the log levels (numbers and names) are taken. Even if you add your own there, plainlog
takes them and adds them internally. But plainlog does not invent own log levels or add some more. (as loguru does)

The concept of handlers and formatters is also there. But everything simplified. 
A handler can have a formatter but this is up to the user.

In contrast to all other libraries, the interface is plain and simple. Not to much methods to remember. Simple and easy configuration.
But powerfull enough to handle everyones logging needs.

### In short

- Logging is done at the logger level, also preprocessing. 
- Configuration with handlers and processors on the core level.
- Clean separation, the logger is fast and pushes to a queue where the core handles the records in an extra thread. It does not block.
- Same interface for sync and async code.
- There is no hierarchy as in standard logging. Therer are loggers and they share one core.
- Everything is fully configurable and can be as minimal as possible. The amount of preprocessors, processors and handlers are under your control.
- It is really fast. 
- Handlers, preprocessors, processors all use a simple call interface. They must be callable and get the log record dictionary.
- Profiles are there for simple configuration.
- Working with the library should be fun and increase productivity.

### Why I created it?

After I have seen and used a lot of diffent log libraries I cam to loguru. Powerfull and easy to use, but with some hard corners.
I use a lot of async frameworks and code. But most of them don't really care to handle logging in a right way. Standard logging asumes
you hopefully add not a blocking handler. But even stdout or stderr is blocking. So there is the way to write a logging library that have
async methods. But than you have to provide async and sync stuff with different names. Dual interfaces are not nice.
Finally for logging it is enough if you guaranty that a sync call is not blocking. 
Hence execute blocking stuff in an extra thread.

There was no library out there with this feature. So I decided to write my own, learning from others, stealing good features from them.
Implement everything as simple as possible.

It is fast from the beginning by simply doing only the minimal stuff in the hot path of your code where you execute `logger.debug(...)` or another
logger method. It is much faster than standard library logger and also faster in the sense of not blocking your code than all other Python logging
libraries.

## Status

In development alpha, internal interfaces can change.

## License

`plainlog` is distributed under the terms of any of the following licenses:

- [Apache-2.0](https://spdx.org/licenses/Apache-2.0.html)
- [MIT](https://spdx.org/licenses/MIT.html)
