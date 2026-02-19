from __future__ import annotations

from collections import defaultdict


class MetricsRegistry:
    def __init__(self) -> None:
        self.requests_total: dict[tuple[str, str, int], int] = defaultdict(int)
        self.request_latency_sum: dict[tuple[str, str], float] = defaultdict(float)
        self.request_latency_count: dict[tuple[str, str], int] = defaultdict(int)
        self.upstream_retries_total: dict[str, int] = defaultdict(int)
        self.upstream_latency_sum: dict[str, float] = defaultdict(float)
        self.upstream_latency_count: dict[str, int] = defaultdict(int)
        self.upstream_errors_total: dict[str, int] = defaultdict(int)
        self.rate_limited_total: int = 0

    def record_request(self, route: str, method: str, status: int, latency_s: float) -> None:
        self.requests_total[(route, method, status)] += 1
        self.request_latency_sum[(route, method)] += latency_s
        self.request_latency_count[(route, method)] += 1

    def record_upstream_retry(self, route: str) -> None:
        self.upstream_retries_total[route] += 1

    def record_upstream_latency(self, route: str, latency_s: float) -> None:
        self.upstream_latency_sum[route] += latency_s
        self.upstream_latency_count[route] += 1

    def record_upstream_error(self, route: str) -> None:
        self.upstream_errors_total[route] += 1

    def record_rate_limited(self) -> None:
        self.rate_limited_total += 1

    def render_prometheus(self) -> str:
        lines: list[str] = []

        lines.append("# HELP proxy_requests_total Total requests handled by the proxy")
        lines.append("# TYPE proxy_requests_total counter")
        for (route, method, status), value in sorted(self.requests_total.items()):
            lines.append(
                f'proxy_requests_total{{route="{route}",method="{method}",status="{status}"}} {value}'
            )

        lines.append("# HELP proxy_request_latency_seconds_sum Sum of request latency in seconds")
        lines.append("# TYPE proxy_request_latency_seconds_sum counter")
        for (route, method), value in sorted(self.request_latency_sum.items()):
            lines.append(
                f'proxy_request_latency_seconds_sum{{route="{route}",method="{method}"}} {value:.6f}'
            )

        lines.append("# HELP proxy_request_latency_seconds_count Count of request latency measurements")
        lines.append("# TYPE proxy_request_latency_seconds_count counter")
        for (route, method), value in sorted(self.request_latency_count.items()):
            lines.append(
                f'proxy_request_latency_seconds_count{{route="{route}",method="{method}"}} {value}'
            )

        lines.append("# HELP proxy_upstream_retries_total Total upstream retries")
        lines.append("# TYPE proxy_upstream_retries_total counter")
        for route, value in sorted(self.upstream_retries_total.items()):
            lines.append(f'proxy_upstream_retries_total{{route="{route}"}} {value}')

        lines.append("# HELP proxy_upstream_latency_seconds_sum Sum of upstream latency in seconds")
        lines.append("# TYPE proxy_upstream_latency_seconds_sum counter")
        for route, value in sorted(self.upstream_latency_sum.items()):
            lines.append(f'proxy_upstream_latency_seconds_sum{{route="{route}"}} {value:.6f}')

        lines.append("# HELP proxy_upstream_latency_seconds_count Count of upstream latency measurements")
        lines.append("# TYPE proxy_upstream_latency_seconds_count counter")
        for route, value in sorted(self.upstream_latency_count.items()):
            lines.append(f'proxy_upstream_latency_seconds_count{{route="{route}"}} {value}')

        lines.append("# HELP proxy_upstream_errors_total Total upstream errors")
        lines.append("# TYPE proxy_upstream_errors_total counter")
        for route, value in sorted(self.upstream_errors_total.items()):
            lines.append(f'proxy_upstream_errors_total{{route="{route}"}} {value}')

        lines.append("# HELP proxy_rate_limited_total Total requests rejected by rate limit")
        lines.append("# TYPE proxy_rate_limited_total counter")
        lines.append(f"proxy_rate_limited_total {self.rate_limited_total}")

        return "\n".join(lines) + "\n"
