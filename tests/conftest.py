"""Keep test scratch files private to each invocation and execution account."""

from pathlib import Path
from tempfile import TemporaryDirectory

import pytest


def pytest_configure(config: pytest.Config) -> None:
    if config.option.basetemp is None:
        # The default pytest-of-<username> directory can be shared by Windows
        # sandbox and interactive accounts with incompatible directory ACLs.
        # A fresh root avoids reading or deleting another account's test files.
        scratch = TemporaryDirectory(prefix="flow-pytest-")
        config.option.basetemp = str(Path(scratch.name) / "tests")
        config.add_cleanup(scratch.cleanup)
