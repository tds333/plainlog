import json
from tests.helpers import make_record
from plainlog.formatters import format_message, SimpleFormatter, DefaultFormatter, JsonFormatter


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
        serializable = {
            "message": "my message",
            "name": record["name"],
            "datetime": record["datetime"].isoformat(),
            "timestamp": record["datetime"].timestamp(),
            "level_name": record["level"].name,
            "level_no": record["level"].no,
            "extra": record["extra"],
            "process_id": record["process_id"],
            "process_name": record["process_name"],
        }

        assert json_result == serializable
