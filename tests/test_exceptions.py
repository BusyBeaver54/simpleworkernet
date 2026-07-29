"""Тесты иерархии исключений."""

from simpleworkernet.core.exceptions import (
    GraphicsError,
    SVGValidationError,
    WorkerNetAPIError,
    WorkerNetCacheError,
    WorkerNetConfigError,
    WorkerNetConnectionError,
    WorkerNetError,
    WorkerNetRecursionError,
    WorkerNetSmartDataError,
    WorkerNetValidationError,
)


def test_hierarchy():
    assert issubclass(WorkerNetConfigError, WorkerNetError)
    assert issubclass(WorkerNetConnectionError, WorkerNetError)
    assert issubclass(WorkerNetAPIError, WorkerNetError)
    assert issubclass(WorkerNetCacheError, WorkerNetError)
    assert issubclass(WorkerNetValidationError, WorkerNetError)
    assert issubclass(WorkerNetSmartDataError, WorkerNetError)
    assert issubclass(WorkerNetRecursionError, WorkerNetSmartDataError)
    assert issubclass(GraphicsError, WorkerNetError)
    assert issubclass(SVGValidationError, GraphicsError)


def test_connection_error_message():
    e = WorkerNetConnectionError("timeout", url="https://x", timeout=30)
    assert "timeout" in str(e)
    assert "https://x" in str(e)
    assert "30" in str(e)
    assert e.url == "https://x"
    assert e.timeout == 30


def test_api_error_message():
    e = WorkerNetAPIError("fail", status_code=500, response={"error": "oops"})
    assert "fail" in str(e)
    assert "500" in str(e)
    assert e.status_code == 500
