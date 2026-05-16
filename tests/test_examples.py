import pytest
from pytest_examples import CodeExample, EvalExample, find_examples


@pytest.mark.parametrize(
    "example",
    find_examples("README.md", "docs"),
    ids=str,
)
def test_examples(example: CodeExample, eval_example: EvalExample) -> None:
    eval_example.run(example)
