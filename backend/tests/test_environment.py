"""Environment and dependency foundation smoke test."""
import sys


def test_python_version() -> None:
    """Verify Python version is 3.10+."""
    assert sys.version_info >= (3, 10), f"Python version too old: {sys.version}"


def test_core_package_imports() -> None:
    """Verify that core backend dependencies can be imported successfully."""
    import fastapi
    import pydantic
    import pint
    import numpy
    import scipy
    import pandas
    import duckdb
    import pyarrow
    import yaml
    import jinja2
    import matplotlib
    import pytest
    import hypothesis

    assert fastapi.__version__ is not None
    assert pydantic.__version__ is not None
    assert pint.__version__ is not None
    assert numpy.__version__ is not None
    assert scipy.__version__ is not None
    assert pandas.__version__ is not None
    assert duckdb.__version__ is not None
    assert pyarrow.__version__ is not None
    assert yaml.__version__ is not None
    assert jinja2.__version__ is not None
    assert matplotlib.__version__ is not None
    assert pytest.__version__ is not None
    assert hypothesis.__version__ is not None


def test_package_structure_importable() -> None:
    """Verify that backend application packages are importable."""
    import app
    import app.core
    import app.models
    import app.engine
    import app.api
    import app.adapters
    import app.reports

    assert app is not None
    assert app.core is not None
    assert app.models is not None
    assert app.engine is not None
    assert app.api is not None
    assert app.adapters is not None
    assert app.reports is not None
