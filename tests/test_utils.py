import pytest

from plainlog._utils import eval_dict, eval_lambda_dict, eval_format


def test_eval_dict():
    def myfunc():
        return "result"

    d = {"data": myfunc}

    eval_dict(d)

    assert d["data"] == "result"


def test_eval_lambda_dict_func():
    def myfunc():
        return "result"

    d = {"data": myfunc}

    eval_lambda_dict(d)

    assert d["data"] == myfunc


def test_eval_lambda_dict_lambda():
    d = {"data": lambda: "result"}

    eval_lambda_dict(d)

    assert d["data"] == "result"


def test_eval_format():
    msg = "{val}"
    kwargs = {"val": lambda: "data"}

    result = eval_format(msg, kwargs)

    assert result == "data"
