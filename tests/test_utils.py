from plainlog._utils import eval_dict, eval_format, eval_lambda_dict


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


def test_eval_dict_with_non_callable():
    d = {"a": lambda: "result", "b": 42}
    eval_dict(d)
    assert d["a"] == "result"
    assert d["b"] == 42
