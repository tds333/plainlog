import json

from plainlog.formatters import (
    DefaultFormatter,
    JsonFormatter,
    SimpleFormatter,
    format_message,
)
from tests.helpers import make_record


class TestFormatMessage:
    def test_format_message_simple(self):
        message = "my message"
        log_record = make_record(message)
        result = format_message(log_record)
        assert result == message

    def test_format_message_percent_dict(self):
        message = "my message {name}"
        log_record = make_record(message, kwargs={"name": "one"})
        result = format_message(log_record)
        assert result == "my message one"


class TestDefaultFormatter:
    def test_call(self):
        df = DefaultFormatter()
        log_record = make_record("default message")
        result = df(log_record)
        # Check that the output contains expected log parts
        assert "DEBUG" in result
        assert "[root]" in result
        assert "default message" in result


class TestSimpleFormatter:
    def test_call(self):
        sf = SimpleFormatter()
        log_record = make_record("my message")
        result = sf(log_record)
        assert "DEBUG    [root] my message" in result


class TestJsonFormatter:
    def test_call(self):
        f = JsonFormatter()
        record = make_record("my message")
        result = f(record)
        json_result = json.loads(result)
        import time
        created = record["created"]
        sec = int(created)
        ts_str = time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(sec))
        serializable = {
            "message": "my message",
            "name": record["name"],
            "datetime": f"{ts_str}.{int((created - sec) * 1_000_000):06d}Z",
            "timestamp": record["created"],
            "level_name": record["level"].name,
            "level_no": record["level"].no,
            "extra": record["extra"],
            "process_id": record["process_id"],
            "process_name": record["process_name"],
        }

        assert json_result == serializable

    def test_custom_converter(self):
        f = JsonFormatter(converter=lambda x: "CUSTOM")
        record = make_record("test")
        record["extra"] = {"obj": object()}
        result = json.loads(f(record))
        assert result["extra"]["obj"] == "CUSTOM"

    def test_custom_additional_keys(self):
        f = JsonFormatter(additional_keys=("custom_key",))
        record = make_record("test")
        record["custom_key"] = "val"
        result = json.loads(f(record))
        assert result["custom_key"] == "val"
