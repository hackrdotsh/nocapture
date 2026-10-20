#!/usr/bin/env bash
set -euo pipefail

scratch=$(mktemp -d)
trap 'rm -rf "$scratch"' EXIT
export NOCAPTURE_TEST_LOG="$scratch/calls"
printf '#!%s\n' "$(command -v bash)" >"$scratch/noctalia"
cat >>"$scratch/noctalia" <<'MOCK'
printf '%s\n' "$*" >> "$NOCAPTURE_TEST_LOG"
if [[ "$*" == 'msg plugins list' ]]; then
  echo '0xhckr/nocapture [local] 0.1.0 enabled'
  echo "noctalia/screen_recorder [official] 1.3.6 ${NOCAPTURE_TEST_RECORDER:-enabled}"
fi
exit "${NOCAPTURE_TEST_EXIT:-0}"
MOCK
chmod +x "$scratch/noctalia"
export PATH="$scratch:$PATH"

check_command() {
  local expected=$1
  shift
  bash bin/nocapture "$@"
  [[ $(tail -n 1 "$NOCAPTURE_TEST_LOG") == "$expected" ]]
}

check_command 'msg panel-toggle 0xhckr/nocapture:toolbar'
check_command 'msg panel-open 0xhckr/nocapture:toolbar' show
check_command 'msg panel-close 0xhckr/nocapture:toolbar' hide
check_command 'msg plugin noctalia/screen_recorder:service all stop' stop
bash bin/nocapture --help >/dev/null

for tool in niri gpu-screen-recorder slurp; do
  cp "$scratch/noctalia" "$scratch/$tool"
done
bash bin/nocapture doctor >/dev/null
if NOCAPTURE_TEST_RECORDER=disabled bash bin/nocapture doctor >/dev/null 2>&1; then
  echo 'Doctor accepted a disabled recorder' >&2
  exit 1
fi

if bash bin/nocapture invalid >/dev/null 2>&1; then
  echo 'Invalid action succeeded' >&2
  exit 1
fi
if bash bin/nocapture show extra >/dev/null 2>&1; then
  echo 'Extra argument succeeded' >&2
  exit 1
fi
export NOCAPTURE_TEST_EXIT=7
status=0
bash bin/nocapture show || status=$?
[[ $status == 7 ]]
echo 'CLI tests passed'
