"""Read-only Prometheus correlation (spec: result-investigation)."""

import pytest
from pytest_httpserver import HTTPServer

from shamal.prometheus import PrometheusClient, PrometheusUnavailable


@pytest.fixture
def prom(httpserver: HTTPServer) -> PrometheusClient:
    return PrometheusClient(httpserver.url_for(""))


class TestQueryRange:
    def test_values_returned(self, httpserver: HTTPServer, prom: PrometheusClient) -> None:
        httpserver.expect_request("/api/v1/query_range").respond_with_json(
            {
                "status": "success",
                "data": {
                    "resultType": "matrix",
                    "result": [
                        {
                            "metric": {"__name__": "db_connections", "pool": "main"},
                            "values": [[1751364000, "98"], [1751364015, "100"]],
                        }
                    ],
                },
            }
        )
        series = prom.query_range("db_connections", start=1751364000, end=1751364060, step=15)
        assert series[0]["metric"]["pool"] == "main"
        assert series[0]["values"][-1] == [1751364015, "100"]

    def test_http_error_raises_unavailable(
        self, httpserver: HTTPServer, prom: PrometheusClient
    ) -> None:
        httpserver.expect_request("/api/v1/query_range").respond_with_data(
            "boom", status=500
        )
        with pytest.raises(PrometheusUnavailable):
            prom.query_range("up", start=0, end=60, step=15)

    def test_unreachable_endpoint_raises_unavailable(self) -> None:
        client = PrometheusClient("http://127.0.0.1:1", timeout_s=0.2)
        with pytest.raises(PrometheusUnavailable):
            client.query_range("up", start=0, end=60, step=15)

    def test_error_status_in_body_raises_unavailable(
        self, httpserver: HTTPServer, prom: PrometheusClient
    ) -> None:
        httpserver.expect_request("/api/v1/query_range").respond_with_json(
            {"status": "error", "error": "bad query"}
        )
        with pytest.raises(PrometheusUnavailable, match="bad query"):
            prom.query_range("up{", start=0, end=60, step=15)
