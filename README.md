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

## Idea

Main goal is to be a plain easy to use logging library.
Simple, small, easy to use, easy to understand, fast.

Because of this there is a clean separation between the logger and the core.
Everything related about the logger is for normal developer using logging and simply want to emit log messages.
To the logger core the handlers are attached and the configuration of the logging system.
If you are to lazy for long configuration settings simply use the provided log profiles.
Configuration can be done with some environment variables or in the code.

### What is the difference to other logging libraries?

Plainlog wants to be simple and fast. It should work the same way in async and sync code.
Because of this there is a clean separation between a logger and the core. This separation is done with a thread safe queue.
This guaranties also that everything is not blocking your code, so you simply can use the logger in an async context,
without having the methods to be async.
With this concept you normally also have not to care about performance. In the hot path of the logger everything is fast
and minimal. Then put the log record (a simple dict) into the queue and the core handles the rest in an extra thread, not blocking anything.
You can log lot of messages in debug level and the performance of your code is not affected.

Also the concept of preprocessors and processors is special. A preprocessor runs in the context of the logger, a processor in the context of the core.
So you can enrich log record information in the context of the call or later in the context of processing.

For easy usage and configuration a list of profiles is provided that can simply be selected and used.
This ads documented (pre)-processors and handlers and everything is ready to be used.

For every class, method or function I care what it does. Normally I think twice about it and implement it in three different ways to come to a final
"plain" solution.


### What is from other libraries?

From structlog the idea of processors are taken. But simplyfied and separated. In plainlog it is a simple list of preprocessors and processors
and they are executed in order. No wraping and complicated parameter handling.
Also the formating for development log output is inspired from structlog. The logger has the feature to `bind` and `unbind` extra variables.

From logure the concept of a logger and core is taken. But with cleaner separation.
The separation is seen with configuration, in plainlog it is done on the core and not mixed up with the logger.
Also the separation in handling log records is done with a queue and extra thread in the core.
The logger has the feature to add something to the `context` or use the `contextualize` context manager.

From logbook the idea for the fingerscrossed handler was taken.

From twisted logging, the idea a record is simply a dictionary. Nothing more, nothing special.

From the Python standard library the log levels (numbers and names) are taken. Even if you add your own there, plainlog
takes them and adds them internally. But plainlog does not invent own log levels or add some more. (as loguru does)

The concept of handlers and formatters is also there. But everything simplified. A handler can have a formatter but this is
up to the user of the library.

In contrast to all other libraries, the interface is plain and simple. Not to much methods to remember. Simple and easy configuration.
But powerfull enough to handle everyones logging needs.

### In short

- Logging is done at the logger level, also preprocessing. Configuration with handlers and processors on the core level.
- Clean separation, the logger is fast and pushes to a queue where the core handles the records in an extra thread. It does not block.
- You can use the same interface for sync and async code. Simply call the log function.
- There is no hierarchy as in standard logging. Therer are loggers and they share one core.
- Everything is fully configurable and can be as minimal as possible. The amount of preprocessors, processors and handlers are under control
  of the developer.
- There is only one global minimal log level and it is tied to the minimal log level needed for the handlers. You don't have to care or set it.
- It is really fast. Only the minimal stuff is done in the hot path of the code. Everything else is done in the core in an extra thread.
- Handlers, formatters, preprocessors, processors all use a simple call interface. They must be callable and get the log record dictionary.
- Profiles are there for simple configuration. For developer, cloud json logging, or records in a file.
- Working with the library should be fun and increase productivity.

### Why I created it?

After I have seen and used a lot of diffent log libraries I cam to loguru. Powerfull and easy to use, but with some hard corners.
I use a lot of async frameworks and code. But most of them don't really care to handle logging in a right way. Standard logging asumes
you hopefully add not a blocking handler. But even stdout or stderr is blocking. So there is the way to write a logging library that have
async methods. But than you have to provide async and sync stuff with different names. Dual interfaces are not nice.
Finally for logging is is enough if you guaranty that a sync call is not blocking. This can be done with doing the blocking stuff in an extra thread.
There was no library out there with this feature. So I decided to write my own, learning from others, stealing good features from them.
Than implement everything as simple as possible. Finally also not saying it is the fastest library out there and after a few lines writing this will
only be the case if I have rewritten something in C for performance reasons. (read in lot of docu)
It is fast from the beginning on by simply doing only the minimal stuff in the hot path of your code where you execute `logger.debug(...)` or another
logger method. It is much faster than standard library logger and also faster in the sense of not blocking your code than all other Python logging
libraries.


## License

`plainlog` is distributed under the terms of any of the following licenses:

- [Apache-2.0](https://spdx.org/licenses/Apache-2.0.html)
- [MIT](https://spdx.org/licenses/MIT.html)
