from __future__ import annotations

from typing import Any

from plainlog._utils import eval_lambda_dict


def test_eval_lambda_dict_func() -> None:
    def myfunc() -> Any:
        return "result"

    d = {"data": myfunc}

    res = eval_lambda_dict(d)

    assert res["data"] == myfunc


def test_eval_lambda_dict_lambda() -> None:
    d = {"data": lambda: "result"}

    res = eval_lambda_dict(d)

    assert res["data"] == "result"
