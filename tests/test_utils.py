import pytest

from plainlog._utils import eval_list, eval_dict, eval_lambda_list, eval_lambda_dict, eval_format


def test_eval_list_empty():
    empty_list = []
    result = eval_list(empty_list)

    assert not result


def test_eval_list_lambda():
    l = [lambda: str(1.0)]
    result = eval_list(l)

    assert result == ["1.0"]


def test_eval_list():
    def myfunc():
        return "result"

    l = [myfunc]
    result = eval_list(l)

    assert result == ["result"]


def test_eval_dict():
    def myfunc():
        return "result"

    d = {"data": myfunc}

    eval_dict(d)

    assert d["data"] == "result"


def test_eval_lambda_list_empty():
    empty_list = []
    result = eval_lambda_list(empty_list)

    assert not result


def test_eval_lambda_list_lambda():
    l = [lambda: str(1.0)]
    result = eval_lambda_list(l)

    assert result == ["1.0"]


def test_eval_lambda_list():
    def myfunc():
        return "result"

    l = [myfunc]
    result = eval_lambda_list(l)

    assert result == [myfunc]


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
    msg = "{0} {val}"
    args = [lambda: "one"]
    kwargs = {"val": lambda: "data"}

    result = eval_format(msg, args, kwargs)

    assert result == "one data"