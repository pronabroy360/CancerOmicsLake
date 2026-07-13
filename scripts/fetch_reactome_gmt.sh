#!/usr/bin/env bash
# Fetch a pinned Reactome GMT release into the bronze reference layer.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

REACTOME_RELEASE="${REACTOME_RELEASE:-97}"
REACTOME_BASE_URL="${REACTOME_BASE_URL:-https://reactome.org/download}"
URL="${REACTOME_GMT_URL:-${REACTOME_BASE_URL%/}/${REACTOME_RELEASE}/ReactomePathways.gmt.zip}"
MIN_PATHWAYS="${REACTOME_MIN_PATHWAYS:-1000}"
PYTHON_BIN="${PYTHON_BIN:-python3}"

OUT_DIR="${REACTOME_OUT_DIR:-${REPO_ROOT}/data/bronze/reference/pathways}"
OUT_FILE="${OUT_DIR}/reactome_pathways.gmt"
PROVENANCE_FILE="${OUT_DIR}/reactome_pathways.provenance.json"
REPORT_FILE="${REACTOME_REPORT_FILE:-${REPO_ROOT}/outputs/reports/reactome_gmt_acquisition_report.json}"
TMP_DIR=""

cleanup() {
  if [[ -n "${TMP_DIR}" && -d "${TMP_DIR}" ]]; then
    rm -rf "${TMP_DIR}"
  fi
}
trap cleanup EXIT

if [[ "${SKIP_GMT_FETCH:-0}" == "1" ]]; then
  echo "[fetch_reactome_gmt] SKIP_GMT_FETCH=1; skipping acquisition."
  exit 0
fi

mkdir -p "${OUT_DIR}" "$(dirname "${REPORT_FILE}")"
TMP_DIR="$(mktemp -d "${OUT_DIR}/.reactome-fetch.XXXXXX")"
TMP_ZIP="${TMP_DIR}/ReactomePathways.gmt.zip"
TMP_GMT="${TMP_DIR}/ReactomePathways.gmt"

sha256_file() {
  "${PYTHON_BIN}" -c 'import hashlib, pathlib, sys; print(hashlib.sha256(pathlib.Path(sys.argv[1]).read_bytes()).hexdigest())' "$1"
}

validate_gmt() {
  local file="$1"
  [[ -s "${file}" ]] || return 1
  awk -F '\t' -v minimum="${MIN_PATHWAYS}" '
    {
      has_gene = 0
      for (i = 3; i <= NF; i++) {
        if ($i != "") {
          has_gene = 1
          break
        }
      }
      if (NF < 3 || $1 == "" || $2 !~ /^R-HSA-[0-9]+$/ || !has_gene || seen[$2]++) {
        invalid = 1
      }
    }
    END { exit(invalid || NR < minimum ? 1 : 0) }
  ' "${file}"
}

cached_gmt_is_valid() {
  [[ -f "${OUT_FILE}" && -f "${PROVENANCE_FILE}" ]] || return 1
  validate_gmt "${OUT_FILE}" || return 1
  local actual_sha256
  actual_sha256="$(sha256_file "${OUT_FILE}")"
  "${PYTHON_BIN}" - "${PROVENANCE_FILE}" "${REACTOME_RELEASE}" "${actual_sha256}" <<'PY'
import json
from pathlib import Path
import sys

try:
    payload = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
except (OSError, json.JSONDecodeError):
    raise SystemExit(1)

release_matches = str(payload.get("source_version", "")) == sys.argv[2]
checksum_matches = str(payload.get("gmt_sha256", "")) == sys.argv[3]
raise SystemExit(0 if release_matches and checksum_matches else 1)
PY
}

write_provenance() {
  local status="$1"
  local archive_sha256="${2:-}"
  local detail="${3:-}"
  local gmt_sha256
  local pathway_count
  local file_size
  local display_path

  gmt_sha256="$(sha256_file "${OUT_FILE}")"
  pathway_count="$(awk 'END {print NR}' "${OUT_FILE}")"
  file_size="$(wc -c < "${OUT_FILE}" | tr -d ' ')"
  display_path="${OUT_FILE#"${REPO_ROOT}/"}"

  "${PYTHON_BIN}" - \
    "${status}" "${REACTOME_RELEASE}" "${URL}" "${display_path}" \
    "${gmt_sha256}" "${archive_sha256}" "${pathway_count}" "${file_size}" \
    "${detail}" "${PROVENANCE_FILE}" "${REPORT_FILE}" <<'PY'
from datetime import UTC, datetime
import json
import os
from pathlib import Path
import sys

(
    status,
    release,
    source_url,
    output_path,
    gmt_sha256,
    archive_sha256,
    pathway_count,
    file_size,
    detail,
    provenance_path,
    report_path,
) = sys.argv[1:]

existing = {}
provenance = Path(provenance_path)
if provenance.exists():
    try:
        existing = json.loads(provenance.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        existing = {}

now = datetime.now(UTC).isoformat()
payload = {
    "status": status,
    "source": "Reactome",
    "source_version": release,
    "source_url": source_url,
    "license": "CC0-1.0",
    "output_path": output_path,
    "pathway_count": int(pathway_count),
    "file_size_bytes": int(file_size),
    "gmt_sha256": gmt_sha256,
    "archive_sha256": archive_sha256 or existing.get("archive_sha256"),
    "retrieved_at": now if status == "downloaded" else existing.get("retrieved_at"),
    "checked_at": now,
    "detail": detail or None,
}

for destination in (provenance, Path(report_path)):
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(destination.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    os.replace(temporary, destination)
PY
}

use_cached_or_fail() {
  local detail="$1"
  if cached_gmt_is_valid; then
    write_provenance "cached_fallback" "" "${detail}"
    echo "[fetch_reactome_gmt] WARNING: ${detail}; retained validated cached release ${REACTOME_RELEASE}." >&2
    return 0
  fi
  echo "[fetch_reactome_gmt] ERROR: ${detail}; no validated cached GMT is available." >&2
  return 1
}

if [[ "${REFRESH_GMT:-0}" != "1" ]] && cached_gmt_is_valid; then
  write_provenance "cached"
  echo "[fetch_reactome_gmt] validated cached release ${REACTOME_RELEASE} -> ${OUT_FILE}"
  exit 0
fi

echo "[fetch_reactome_gmt] downloading pinned Reactome release ${REACTOME_RELEASE} from ${URL}"
if ! curl -fsSL --retry 3 --retry-delay 2 "${URL}" -o "${TMP_ZIP}"; then
  use_cached_or_fail "download failed"
  exit $?
fi

if ! unzip -tqq "${TMP_ZIP}" >/dev/null; then
  use_cached_or_fail "archive integrity validation failed"
  exit $?
fi

if ! unzip -p "${TMP_ZIP}" "ReactomePathways.gmt" > "${TMP_GMT}"; then
  use_cached_or_fail "ReactomePathways.gmt was not extractable"
  exit $?
fi

if ! validate_gmt "${TMP_GMT}"; then
  use_cached_or_fail "downloaded GMT failed structural validation"
  exit $?
fi

ARCHIVE_SHA256="$(sha256_file "${TMP_ZIP}")"
mv -f "${TMP_GMT}" "${OUT_FILE}"
write_provenance "downloaded" "${ARCHIVE_SHA256}"
echo "[fetch_reactome_gmt] acquired validated release ${REACTOME_RELEASE} -> ${OUT_FILE}"
