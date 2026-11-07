#!/usr/bin/env bash
# cv-pronto.sh <anuncio.txt> <cv.pdf> — ATS gate before attaching a per-job CV (prompt_cv.md step 4).
# Prints "ANEXAR <path>" and exits 0 only when check_ats.py approves (exit 0). Exit 1 = rejected,
# exit 2 = not verifiable; neither is ever an approval. Each verdict goes to the ATS log for the audit.
set -u
[ $# -eq 2 ] || { echo "uso: cv-pronto.sh <anuncio.txt> <cv.pdf>" >&2; exit 2; }
# check_ats.py next to the CALLED path: a private install symlinks both into its own dir, and check_ats.py finds
# dados_candidato.json next to the path it was called by (the real bot/ dir has no profile there).
AQUI=$(cd "$(dirname "$0")" && pwd)
[ -e "$AQUI/check_ats.py" ] || AQUI=$(cd "$(dirname "$(readlink -f "$0")")" && pwd)
LOG=${OV_ATS_LOG:-${BOT_ROOT:-$AQUI/..}/logs/ats.log}
hash_file() { python3 -c 'import hashlib,sys; h=hashlib.sha256(); f=open(sys.argv[1],"rb"); [h.update(c) for c in iter(lambda:f.read(131072),b"")]; f.close(); print(h.hexdigest())' "$1" 2>/dev/null; }
if [ "${OV_RESUME_MATCHER_REQUIRED:-0}" = "1" ]; then
  JOB_SHA_BEFORE=$(hash_file "$1")
  PDF_SHA_BEFORE=$(hash_file "$2")
  MANIFEST_DIR=${OV_RESUME_MATCHER_MANIFEST_DIR:-$HOME/.local/share/oportunizavaga/resume-matcher/manifests}
fi
saida=$(python3 "$AQUI/check_ats.py" "$1" "$2"); rc=$?
printf '%s\n' "$saida"
mkdir -p "$(dirname "$LOG")" 2>/dev/null
printf '%s rc=%s cv=%s %s\n' "$(date '+%FT%T%z')" "$rc" "$(basename "$2")" \
  "$(printf '%s' "$saida" | grep -m1 'DO PERFIL' | tr -d '\n')" >> "$LOG" 2>/dev/null
if [ "$rc" -eq 0 ] && [ "${OV_RESUME_MATCHER_REQUIRED:-0}" = "1" ]; then
  BRIDGE=${OV_RESUME_MATCHER_BRIDGE:-$AQUI/resume_matcher_bridge.py}
  rm_saida=$(python3 "$BRIDGE" parse-check --pdf "$(readlink -f "$2")" --announcement "$(readlink -f "$1")" \
    --manifest-dir "$MANIFEST_DIR"); rm_rc=$?
  rm_status=$(python3 -c 'import json,sys; print(json.load(sys.stdin).get("status", "UNVERIFIABLE"))' <<<"$rm_saida" 2>/dev/null || echo UNVERIFIABLE)
  rm_score=$(python3 -c 'import json,sys; print(json.load(sys.stdin).get("overall_score", ""))' <<<"$rm_saida" 2>/dev/null || true)
  rm_hash=$(python3 -c 'import json,sys; print(json.load(sys.stdin).get("sha256", ""))' <<<"$rm_saida" 2>/dev/null || true)
  rm_job_hash=$(python3 -c 'import json,sys; print(json.load(sys.stdin).get("job_description_sha256", ""))' <<<"$rm_saida" 2>/dev/null || true)
  rm_manifest_id=$(python3 -c 'import json,sys; print(json.load(sys.stdin).get("manifest_id", ""))' <<<"$rm_saida" 2>/dev/null || true)
  job_now=$(hash_file "$1")
  pdf_now=$(hash_file "$2")
  if [ "$rm_status" = "APPROVED" ] && { [ -z "$JOB_SHA_BEFORE" ] || [ -z "$PDF_SHA_BEFORE" ] \
      || [ "$JOB_SHA_BEFORE" != "$rm_job_hash" ] || [ "$PDF_SHA_BEFORE" != "$rm_hash" ] \
      || [ "$JOB_SHA_BEFORE" != "$job_now" ] || [ "$PDF_SHA_BEFORE" != "$pdf_now" ]; }; then
    rm_status=UNVERIFIABLE
    rm_rc=2
    rm_saida='{"status":"UNVERIFIABLE","error_code":"INPUT_CHANGED_OR_HASH_MISMATCH"}'
  fi

  verify_saida=
  verify_status=
  verify_manifest_id=
  if [ "$rm_rc" -eq 0 ] && [ "$rm_status" = "APPROVED" ]; then
    verify_saida=$(python3 "$BRIDGE" verify-manifest --pdf "$(readlink -f "$2")" \
      --announcement "$(readlink -f "$1")" --manifest-dir "$MANIFEST_DIR"); verify_rc=$?
    verify_status=$(python3 -c 'import json,sys; print(json.load(sys.stdin).get("status", "UNVERIFIABLE"))' <<<"$verify_saida" 2>/dev/null || echo UNVERIFIABLE)
    verify_manifest_id=$(python3 -c 'import json,sys; print(json.load(sys.stdin).get("manifest_id", ""))' <<<"$verify_saida" 2>/dev/null || true)
    if [ "$verify_rc" -ne 0 ] || [ "$verify_status" != "APPROVED" ] \
        || [ -z "$rm_manifest_id" ] || [ "$rm_manifest_id" != "$verify_manifest_id" ]; then
      rm_status=UNVERIFIABLE
      rm_rc=2
      rm_saida='{"status":"UNVERIFIABLE","error_code":"MANIFEST_VERIFICATION_FAILED"}'
    fi
  fi
  if ! printf '%s rm_status=%s rm_score=%s manifest_id=%s job_sha256=%s pdf_sha256=%s cv=%s\n' "$(date '+%FT%T%z')" \
      "$rm_status" "$rm_score" "$rm_manifest_id" "$rm_job_hash" "$rm_hash" "$(basename "$2")" >> "$LOG" 2>/dev/null; then
    if [ "$rm_status" = "APPROVED" ]; then
      rm_status=UNVERIFIABLE
      rm_rc=2
      rm_saida='{"status":"UNVERIFIABLE","error_code":"AUDIT_LOG_UNAVAILABLE"}'
    fi
  fi
  if [ "$rm_status" = "APPROVED" ] && [ -n "$verify_saida" ]; then
    merged=$(python3 -c 'import json,sys; result=json.loads(sys.argv[1]); verified=json.loads(sys.argv[2]); result.update(pdf_sha256=verified["pdf_sha256"], manifest_verified=True, verified_at=verified["verified_at"], resume_matcher_revision=verified["resume_matcher_revision"], verifier_policy_version=verified["verifier_policy_version"]); print(json.dumps(result, ensure_ascii=False, sort_keys=True))' "$rm_saida" "$verify_saida" 2>/dev/null)
    merge_rc=$?
    if [ "$merge_rc" -ne 0 ]; then
      rm_status=UNVERIFIABLE
      rm_rc=2
      rm_saida='{"status":"UNVERIFIABLE","error_code":"MANIFEST_RESULT_INVALID"}'
    else
      rm_saida=$merged
    fi
  fi
  printf '%s\n' "$rm_saida"
  if [ "$rm_rc" -ne 0 ] || [ "$rm_status" != "APPROVED" ]; then
    echo "NAO ANEXE este PDF (Resume-Matcher: $rm_status)."
    [ "$rm_rc" -eq 2 ] && exit 2
    exit 1
  fi
fi
if [ "$rc" -eq 0 ]; then
  echo "ANEXAR $(readlink -f "$2")"
else
  echo "NAO ANEXE este PDF (check_ats rc=$rc)."
fi
exit "$rc"
