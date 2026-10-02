import pytest
from pytest_examples import CodeExample, EvalExample, find_examples


def _examples() -> list[CodeExample]:
    return [
        example
        for example in find_examples("README.md", "docs")
        if "superpowers" not in str(example)
    ]


@pytest.mark.parametrize(
    "example",
    _examples(),
    ids=str,
)
def test_examples(example: CodeExample, eval_example: EvalExample) -> None:
    eval_example.run(example)
