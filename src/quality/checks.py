from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import UTC, datetime


@dataclass
class CheckResult:
    check_name: str
    status: str
    failed_rows: int = 0
    metric_name: str = ""
    metric_value: float | None = None
    threshold: float | None = None

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def check_non_negative_expression(rows: list[dict[str, str]]) -> CheckResult:
    failed = sum(1 for row in rows if float(row["expression_value"]) < 0)
    return CheckResult(
        check_name="expression_values_non_negative",
        status="passed" if failed == 0 else "failed",
        failed_rows=failed,
    )


def check_gene_mapping_rate(mapped_rows: list[dict[str, str]], threshold: float = 0.98) -> CheckResult:
    if not mapped_rows:
        rate = 0.0
    else:
        ok = sum(1 for row in mapped_rows if bool(row.get("gene_id_normalized")))
        rate = ok / len(mapped_rows)
    status = "passed" if rate >= threshold else "warning"
    return CheckResult(
        check_name="gene_mapping_rate",
        status=status,
        metric_name="mapping_rate",
        metric_value=rate,
        threshold=threshold,
    )


def build_quality_payload(run_id: str, results: list[CheckResult]) -> dict[str, object]:
    statuses = {result.status for result in results}
    status = "passed"
    if "failed" in statuses:
        status = "failed"
    elif "warning" in statuses:
        status = "passed_with_warnings"
    return {
        "pipeline_run_id": run_id,
        "generated_at": datetime.now(UTC).isoformat(),
        "status": status,
        "checks": [result.to_dict() for result in results],
    }
