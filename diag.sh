#!/usr/bin/env bash
# =============================================================================
# diag-final.sh — universal, unattended, idempotent, non-destructive diagnostic
# =============================================================================
# Collects hardware, firmware, storage, thermal, power, network, GPU, kernel and
# service health from ANY Linux PC (installed system or live ISO), runs bounded
# stress/benchmark tests, analyses everything, and ends with a ranked list of
# FAIL / WARN / INFO findings.
#
# Supported package-manager families (for auto-installing missing tools):
#   pacman (Arch, CachyOS, Manjaro, EndeavourOS...), apt (Debian, Ubuntu, Mint...),
#   dnf/yum (Fedora, RHEL family), zypper (openSUSE). On anything else the script
#   simply uses whatever tools are already present.
#
# Guarantees:
#   * Never writes to any disk device or filesystem outside its own report dir
#     (fio runs --readonly, SMART self-tests are NOT started, nothing is formatted,
#     no stale package-manager locks are removed on installed systems).
#   * Idempotent: every run creates its own timestamped directory, a second run
#     installs nothing new, leaves no processes or temp files behind, and an
#     flock prevents two copies from running (and skewing stress results) at once.
#   * Unattended: no prompts. Every external command has a timeout.
#   * Safe stress: CPU/GPU stress aborts automatically if a CPU/GPU sensor
#     reaches the abort temperature (default 98 °C).
#
# Usage:  sudo ./diag-final.sh [options]
#   -q, --quick            skip the stress/benchmark phase and the slowest collectors
#       --no-stress        skip only the stress/benchmark phase
#       --no-install       never install packages; use only tools already present
#   -Q, --quiet            run quietly (suppress report streaming and per-section terminal lines)
#   -t, --stress-secs N    length of each CPU/RAM stress phase (default 30, 5..600)
#   -o, --out DIR          parent directory for the report directory (default: CWD)
#   -v, --verbose          stream the complete report to the terminal
#                          (automatic when stdout is not a terminal)
#       --redact           mask serial numbers, MAC addresses, UUIDs and hostname
#                          in the saved files (best effort — review before sharing)
#       --no-archive       do not create the .tar.gz next to the report directory
#   -h, --help             show this help
# =============================================================================

# shellcheck disable=SC2016 # bash -c '...' snippets are single-quoted on purpose: $vars expand in the child shell
set -uo pipefail
IFS=$'\n\t'
shopt -s nullglob
export LC_ALL=C LANG=C
export PATH="${PATH:+$PATH:}/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
umask 022

VERSION="3.0"

if ((BASH_VERSINFO[0] < 4 || (BASH_VERSINFO[0] == 4 && BASH_VERSINFO[1] < 4))); then
    echo "diag.sh needs bash >= 4.4 (found $BASH_VERSION)." >&2
    exit 1
fi

# ── 0. CLI ───────────────────────────────────────────────────────────────────
QUICK=0
NO_STRESS=0
NO_INSTALL=0
QUIET=0
STRESS_SECS=30
OUT_PARENT=""
VERBOSE=0
REDACT=0
ARCHIVE=1
TEMP_ABORT=98 # °C: abort stress when a CPU/GPU sensor reaches this

# --help prints the "Usage:" block of the header comment above, so the two can never drift apart
usage() {
    if [[ -r "${BASH_SOURCE[0]:-}" ]]; then
        sed -n '/^# Usage:/,/^# ====.*$/{ /^# ====/!s/^# \{0,1\}//p }' "${BASH_SOURCE[0]}"
    else
        echo "Usage:  sudo ./diag-final.sh [options]   (run from a file to see the full option list)"
    fi
}

ORIG_ARGS=("$@") # kept for the sudo re-exec below (the parser consumes "$@")
while (($#)); do
    case "$1" in
    -q | --quick) QUICK=1 ;;
    -Q | --quiet) QUIET=1 ;;
    --no-stress) NO_STRESS=1 ;;
    --no-install) NO_INSTALL=1 ;;
    -t | --stress-secs)
        (($# >= 2)) || {
            echo "Missing value for $1" >&2
            exit 2
        }
        STRESS_SECS="$2"
        shift
        ;;
    -o | --out)
        (($# >= 2)) || {
            echo "Missing value for $1" >&2
            exit 2
        }
        OUT_PARENT="$2"
        shift
        ;;
    -v | --verbose) VERBOSE=1 ;;
    --redact) REDACT=1 ;;
    --no-archive) ARCHIVE=0 ;;
    -h | --help)
        usage
        exit 0
        ;;
    *)
        echo "Unknown option: $1 (try --help)" >&2
        exit 2
        ;;
    esac
    shift
done
if ! [[ "$STRESS_SECS" =~ ^[0-9]+$ ]] || ((STRESS_SECS < 5 || STRESS_SECS > 600)); then
    echo "--stress-secs must be an integer between 5 and 600." >&2
    exit 2
fi

# ── 1. root (self-elevate, unattended when possible) ─────────────────────────
if [[ $EUID -ne 0 ]]; then
    SELF=$(readlink -f -- "${BASH_SOURCE[0]}" 2>/dev/null || true)
    if [[ -z "${SUDO_OFF:-}" && -n "$SELF" && -r "$SELF" ]] && command -v sudo &>/dev/null; then
        if sudo -n true 2>/dev/null; then
            printf 'Elevating to root via passwordless sudo...\n' >&2
            exec sudo -n -- bash "$SELF" ${ORIG_ARGS[@]+"${ORIG_ARGS[@]}"}
        elif [[ -t 0 ]]; then
            printf 'Root privileges required — re-running with sudo...\n' >&2
            exec sudo -- bash "$SELF" ${ORIG_ARGS[@]+"${ORIG_ARGS[@]}"}
        fi
    fi
    if ! command -v sudo &>/dev/null; then
        printf 'sudo is not installed on this system.\n' >&2
    elif [[ -n "${SUDO_OFF:-}" ]]; then
        printf 'sudo is disabled by SUDO_OFF=1 (test mode).\n' >&2
    fi
    printf 'diag-final.sh must run as root and neither passwordless sudo nor an\n' >&2
    printf 'interactive sudo is available.\n' >&2
    printf 'Re-run with:  sudo bash %s [options]\n' "${SELF:-$0}" >&2
    exit 1
fi

# ── 2. single-instance lock ──────────────────────────────────────────────────
LOCK_FILE=/run/hwdiag.lock
[[ -w /run ]] || LOCK_FILE=/tmp/hwdiag.lock
if command -v flock &>/dev/null; then
    exec 9>"$LOCK_FILE"
    if ! flock -n 9; then
        echo "Another diag.sh instance is already running (lock: $LOCK_FILE)." >&2
        exit 3
    fi
fi

# ── 3. report directory (never overwrites anything) ──────────────────────────
STAMP=$(date +%Y%m%d-%H%M%S)
HOST_TAG=$(hostname 2>/dev/null | tr -cd '[:alnum:]_.-')
[[ -n "$HOST_TAG" ]] || HOST_TAG=host
((REDACT)) && HOST_TAG=redacted # keep the hostname out of the directory/archive name too

free_mb() { df -Pm "$1" 2>/dev/null | awk 'NR==2 {print $4+0}'; }

REPORT_DIR=""
_try_base() {
    local base="$1" d n=1 fm
    [[ -n "$base" && -d "$base" && -w "$base" ]] || return 1
    fm=$(free_mb "$base")
    [[ "${fm:-0}" -ge 150 ]] || return 1
    d="$base/diag-${HOST_TAG}-${STAMP}"
    while [[ -e "$d" ]]; do
        d="$base/diag-${HOST_TAG}-${STAMP}-$n"
        n=$((n + 1))
    done
    mkdir -p "$d"/{details,logs,temps,acpi} 2>/dev/null || return 1
    REPORT_DIR="$d"
}
if [[ -n "$OUT_PARENT" ]]; then
    mkdir -p "$OUT_PARENT" 2>/dev/null || true
    _try_base "$(readlink -f -- "$OUT_PARENT" 2>/dev/null || echo "$OUT_PARENT")" || {
        echo "Cannot use --out '$OUT_PARENT' (missing, read-only or <150 MB free)." >&2
        exit 2
    }
else
    for _b in "$(pwd)" /var/tmp /tmp "${HOME:-/root}"; do
        _try_base "$_b" && break
    done
fi
if [[ -z "$REPORT_DIR" ]]; then
    echo "No writable location with >=150 MB free for the report." >&2
    exit 2
fi

REPORT="$REPORT_DIR/report.txt"
DETAILS="$REPORT_DIR/details"
MAIN_LOG="$REPORT_DIR/logs/main.log"
TEMP_LOG="$REPORT_DIR/temps/temperatures.log"
ACPI_DIR="$REPORT_DIR/acpi"
FINDINGS_FILE="$REPORT_DIR/findings.txt"
SUMMARY_FILE="$REPORT_DIR/summary.txt"
: >"$REPORT"
: >"$MAIN_LOG"
: >"$TEMP_LOG"
: >"$FINDINGS_FILE"

TMPDIR=$(mktemp -d /tmp/hwdiag.XXXXXX)
KLOG_FILE="$TMPDIR/klog.txt"
export REPORT_DIR REPORT DETAILS MAIN_LOG TEMP_LOG ACPI_DIR FINDINGS_FILE SUMMARY_FILE TMPDIR KLOG_FILE TEMP_ABORT STRESS_SECS

# ── 4. output plumbing ───────────────────────────────────────────────────────
# fd 3 = the real terminal (progress + final summary). stdout/stderr = report.
REPORT="$REPORT_DIR/report.txt"
exec 3>&1
if ((QUIET)); then
    VERBOSE=0
elif [[ -t 3 ]]; then
    VERBOSE=1 # interactive: stream the full report to the terminal
else
    VERBOSE=1 # non-interactive: still stream to fd 3 so pipe consumers see it
fi
TEE_PID=""
if ((VERBOSE)); then
    exec > >(tee -a "$REPORT" >&3) 2>&1
    TEE_PID=$!
else
    exec >>"$REPORT" 2>&1
fi

BG_PIDS=()
CLEANED=0
START_EPOCH=$(date +%s)

# literal identifiers of THIS machine (disk/board/USB serials, WWNs, DMI UUID, MACs,
# machine-id): masked wherever they appear, whatever the tool's output format is.
_collect_identifiers() {
    local f
    {
        lsblk -dnro SERIAL,WWN 2>/dev/null | tr ' ' '\n'
        lsblk -nro UUID,PARTUUID 2>/dev/null | tr ' ' '\n'
        for f in /sys/class/dmi/id/product_serial /sys/class/dmi/id/board_serial /sys/class/dmi/id/chassis_serial \
            /sys/class/dmi/id/product_uuid /sys/class/dmi/id/board_asset_tag /sys/class/dmi/id/chassis_asset_tag \
            /sys/class/dmi/id/board_version /sys/class/dmi/id/product_family \
            /sys/class/nvme/*/serial /sys/bus/usb/devices/*/serial /sys/block/*/device/serial /sys/block/*/device/wwid \
            /sys/class/net/*/address /sys/class/net/*/perm_address /etc/machine-id; do
            [[ -r "$f" ]] && cat "$f" 2>/dev/null
        done
    } | sed -E 's/^[[:space:]]+//; s/[[:space:]]+$//' |
        awk 'BEGIN {
                 n = split("none|n/a|unknown|not specified|not available|default string|to be filled by o.e.m.|system serial number|chassis serial number|base board serial number|0123456789|00:00:00:00:00:00|ff:ff:ff:ff:ff:ff", g, "|")
                 for (i = 1; i <= n; i++) generic[g[i]] = 1 }
             length($0) >= 6 && !(tolower($0) in generic) && $0 !~ /^0+$/ && $0 !~ /^[0-9a-fA-F]{4}:[0-9a-fA-F]{2}:[0-9a-fA-F]{2}\.[0-9a-fA-F]$/ && !seen[$0]++'
}

redact_tree() {
    local host id sedf="$TMPDIR/redact.sed"
    : >"$sedf"
    while IFS= read -r id; do
        # escape BRE metacharacters so each identifier is replaced literally
        printf 's/%s/<REDACTED>/g\n' "$(printf '%s' "$id" | sed 's/[][\/.^$*]/\\&/g')" >>"$sedf"
    done < <(_collect_identifiers)
    host=$(hostname 2>/dev/null)
    host=${host//[^A-Za-z0-9_.-]/}
    case "${host,,}" in
    "" | localhost | localhost.localdomain | archiso | linux) ;; # generic names identify nobody (and would mangle text)
    *) printf 's/\\b%s\\b/<HOSTNAME>/g\n' "${host//./\\.}" >>"$sedf" ;;
    esac
    find "$REPORT_DIR" -type f ! -name '*.dat' ! -name '*.tar.gz' -print0 2>/dev/null |
        xargs -0 -r sed -i -f "$sedf" 2>/dev/null
    find "$REPORT_DIR" -type f ! -name '*.dat' ! -name '*.tar.gz' -print0 2>/dev/null |
        xargs -0 -r sed -i -E \
            -e 's/([0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}/XX:XX:XX:XX:XX:XX/g' \
            -e 's/[0-9A-Fa-f]{8}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{12}/<UUID>/g' \
            -e 's/((PART|PT)?UUID=)("[^"]*"|[^[:space:]]+)/\1<UUID>/g' \
            -e 's/^([[:space:]]*(Serial Number|Serial number|SerialNumber|serial_number|Asset Tag|iSerial|sn|SN|WWN|wwn)[[:space:]]*[:= ]+([0-9]+ )?)[^[:space:]].*$/\1<REDACTED>/' \
            -e 's/(Serial( Number)?[[:space:]]*:[[:space:]]*)[^[:space:]|,;]+/\1<REDACTED>/Ig' \
            -e 's/(ID_SERIAL(_SHORT)?=)[^[:space:]]+/\1<REDACTED>/g' \
            -e 's/(SERIAL=)"[^"]*"/\1"<REDACTED>"/g' 2>/dev/null
}

cleanup() {
    local rc=$? p archive=""
    ((CLEANED)) && return "$rc"
    CLEANED=1
    # stop samplers / helpers (and their children) so nothing outlives the script
    for p in ${BG_PIDS[@]+"${BG_PIDS[@]}"}; do
        [[ -n "$p" ]] || continue
        command -v pkill &>/dev/null && pkill -TERM -P "$p" 2>/dev/null
        kill "$p" 2>/dev/null
    done
    for p in ${BG_PIDS[@]+"${BG_PIDS[@]}"}; do
        [[ -n "$p" ]] && wait "$p" 2>/dev/null
    done
    # flush the report tee before touching the files (bounded: never hang on exit)
    exec 1>/dev/null 2>&1
    if [[ -n "$TEE_PID" ]]; then
        for p in {1..50}; do
            kill -0 "$TEE_PID" 2>/dev/null || break
            sleep 0.1
        done
    fi
    ((REDACT)) && redact_tree
    if ((ARCHIVE)) && command -v tar &>/dev/null && command -v gzip &>/dev/null; then
        archive="${REPORT_DIR}.tar.gz"
        tar -C "$(dirname "$REPORT_DIR")" -czf "$archive" "$(basename "$REPORT_DIR")" 2>/dev/null || archive=""
    fi
    if [[ -n "${SUDO_UID:-}" && -n "${SUDO_GID:-}" && "$SUDO_UID" != "0" ]]; then
        chown -R "${SUDO_UID}:${SUDO_GID}" "$REPORT_DIR" ${archive:+"$archive"} 2>/dev/null
    fi
    rm -rf "$TMPDIR"
    local elapsed=$(($(date +%s) - START_EPOCH))
    # terminal-facing summary (fd 3 is the real tty)
    {
        printf '\n========== DIAGNOSTIC COMPLETE ==========\n'
        printf 'Report directory : %s\n' "$REPORT_DIR"
        [[ -n "${archive:-}" ]] && printf 'Archive          : %s\n' "$archive"
        printf 'Findings file    : %s\n' "$SUMMARY_FILE"
        printf 'Sections         : %d\n' "$STEP"
        printf 'Runtime          : %ds\n' "$elapsed"
        if ((${#BG_PIDS[@]})); then
            printf 'Background jobs  : %d (cleaned up)\n' "${#BG_PIDS[@]}"
        fi
        if ((QUIET)) && ((${#SECTION_TITLES[@]})); then
            printf '\nLast sections:\n'
            printf '  %s\n' ${SECTION_TITLES[@]+"${SECTION_TITLES[@]: -10}"}
        fi
    } | tee -a "$REPORT" >&3
    return "$rc"
}
trap 'echo "Interrupted — partial report kept." >&3; exit 130' INT
trap 'echo "Terminated — partial report kept." >&3; exit 143' TERM
trap cleanup EXIT # installed last: runs after the summary (§28) and creates the archive

# ── 5. helpers (exported where collectors running in child shells need them) ─
have() { command -v "$1" &>/dev/null; }
# to SECS cmd... : run with timeout, killing stragglers
to() {
    local s="$1"
    shift
    timeout -k 3 "$s" "$@"
}
# finding LEVEL CATEGORY message... (safe from any subshell: appends to a file)
finding() {
    local lvl="$1" cat="$2"
    shift 2
    printf '%s|%s|%s\n' "$lvl" "$cat" "$*" >>"$FINDINGS_FILE"
    printf '>>> [%s] %s: %s\n' "$lvl" "$cat" "$*"
}
# num VALUE : strip to a plain integer (or empty)
num() {
    local v="${1//[^0-9-]/}"
    [[ "$v" =~ ^-?[0-9]+$ ]] && printf '%s' "$v"
}
# kv_get "KEY=\"v\" KEY2=\"v2\"" KEY : read value out of `lsblk -P` style output
kv_get() {
    local line="$1" key="$2"
    if [[ "$line" =~ (^|[[:space:]])${key}=\"([^\"]*)\" ]]; then
        printf '%s' "${BASH_REMATCH[2]}"
    fi
}
# smart_field FILE "Field Name" : value of "Field Name: value" in smartctl output
smart_field() {
    awk -F':' -v k="$2" '
        { key=$1; gsub(/[ \t]+/, " ", key); sub(/^ /, "", key); sub(/ $/, "", key) }
        key == k { v=$2; sub(/^[ \t]+/, "", v); sub(/[ \t].*$/, "", v); gsub(/,/, "", v); print v; exit }' "$1" 2>/dev/null
}
# dur_to_sec "1min 5.2s" → seconds
dur_to_sec() {
    awk '{ t=0
        for (i=1; i<=NF; i++) {
            if ($i ~ /min$/) { v=$i; sub(/min/, "", v); t+=v*60 }
            else if ($i ~ /ms$/) { v=$i; sub(/ms/, "", v); t+=v/1000 }
            else if ($i ~ /s$/) { v=$i; sub(/s/, "", v); t+=v }
        }
        printf "%.1f\n", t }' <<<"$1"
}
export -f have to finding num kv_get smart_field dur_to_sec

_sanitize_title() {
    printf '%s' "$1" | tr ' /:' '___' | tr -cd '[:alnum:]_.-' | cut -c1-120
}

STEP=0
SECTION_TITLES=()
section() {
    STEP=$((STEP + 1))
    SECTION_TITLES+=("$*")
    printf '\n\n========== %s ==========\n' "$*"
    printf 'Timestamp: %s\n' "$(date -Is)"
    if ((QUIET)); then
        : # quiet: suppress per-section terminal progress; last 10 printed in footer
    else
        printf '[%03d] %s\n' "$STEP" "$*" >&3
    fi
}

declare -A USED_DETAIL=()
LAST_DETAIL=""
set_detail() {
    local s n=1 p
    s=$(_sanitize_title "$1")
    [[ -n "$s" ]] || s=unnamed
    p="$DETAILS/${s}.txt"
    while [[ -n "${USED_DETAIL[$p]:-}" ]]; do
        n=$((n + 1))
        p="$DETAILS/${s}_${n}.txt"
    done
    USED_DETAIL[$p]=1
    LAST_DETAIL="$p"
}

# run_cmd TITLE TIMEOUT cmd args...  — output → report + details/<title>.txt
run_cmd() {
    local title="$1" tmo="$2" cmd_str rc
    shift 2
    set_detail "$title"
    section "$title"
    printf -v cmd_str '%q ' "$@"
    echo "Command: ${cmd_str% }"
    echo "--- Output ---"
    if ! have "$1"; then
        echo "NOTE: '$1' is not installed — skipped."
        echo "--- Exit code: 127 ---"
        return 127
    fi
    to "$tmo" "$@" </dev/null 2>&1 | tee "$LAST_DETAIL"
    rc=${PIPESTATUS[0]}
    [[ -s "$LAST_DETAIL" ]] || echo "(no output)" | tee "$LAST_DETAIL"
    echo "--- Exit code: $rc ---"
    [[ $rc -eq 124 ]] && echo "NOTE: timed out after ${tmo}s."
    return "$rc"
}

# run_fn TITLE TIMEOUT function args... — function runs in a child bash with a hard timeout
run_fn() {
    local title="$1" tmo="$2" fn="$3" rc
    shift 3
    set_detail "$title"
    section "$title"
    echo "Collector: $fn $*"
    echo "--- Output ---"
    export -f "${fn?}"
    timeout -k 5 "$tmo" bash -O nullglob -c "$fn \"\$@\"" _ "$@" </dev/null 2>&1 | tee "$LAST_DETAIL"
    rc=${PIPESTATUS[0]}
    [[ -s "$LAST_DETAIL" ]] || echo "(no output)" | tee "$LAST_DETAIL"
    echo "--- Exit code: $rc ---"
    [[ $rc -eq 124 ]] && echo "NOTE: collector timed out after ${tmo}s (partial output kept)."
    return 0
}

# ── 6. environment detection ─────────────────────────────────────────────────
KVER=$(uname -r)
MACH=$(uname -m)
NPROC=$(nproc 2>/dev/null || echo 1)

OS_ID="unknown"
OS_LIKE=""
OS_PRETTY="unknown"
if [[ -r /etc/os-release ]]; then
    OS_ID=$(. /etc/os-release 2>/dev/null && printf '%s' "${ID:-unknown}")
    OS_LIKE=$(. /etc/os-release 2>/dev/null && printf '%s' "${ID_LIKE:-}")
    OS_PRETTY=$(. /etc/os-release 2>/dev/null && printf '%s' "${PRETTY_NAME:-unknown}")
fi

PM=""
if have pacman; then
    PM=pacman
elif have apt-get; then
    PM=apt
elif have dnf; then
    PM=dnf
elif have yum; then
    PM=yum
elif have zypper; then
    PM=zypper
fi

IS_LIVE=0
if [[ -d /run/archiso || -d /run/miso || -e /run/live || -d /lib/live/mount || -d /run/initramfs/live || -d /cdrom/casper ]] ||
    grep -qE '(^|[[:space:]])(boot=(casper|live)|rd\.live\.image|archiso|misobasedir|live-media|cow_spacesize|rd\.live\.)' /proc/cmdline 2>/dev/null; then
    IS_LIVE=1
fi

IS_LAPTOP=0
if compgen -G "/sys/class/power_supply/BAT*" >/dev/null; then
    IS_LAPTOP=1
elif [[ -r /sys/class/dmi/id/chassis_type ]]; then
    case "$(cat /sys/class/dmi/id/chassis_type 2>/dev/null)" in
    8 | 9 | 10 | 11 | 14 | 30 | 31 | 32) IS_LAPTOP=1 ;;
    esac
fi

VIRT_ENV="none"
IS_CONTAINER=0
if have systemd-detect-virt; then
    VIRT_ENV=$(systemd-detect-virt 2>/dev/null)
    [[ -n "$VIRT_ENV" ]] || VIRT_ENV="none"
    systemd-detect-virt -c &>/dev/null && IS_CONTAINER=1
fi
[[ -f /.dockerenv ]] && IS_CONTAINER=1
export KVER MACH NPROC OS_ID OS_LIKE PM IS_LIVE IS_LAPTOP VIRT_ENV IS_CONTAINER QUICK

# ── 7. desktop-session detection (for GL/Vulkan probes & GPU stress) ─────────
DESKTOP_USER=""
DESKTOP_UID=""
DESKTOP_HOME=""
DESKTOP_RUNTIME=""
DESKTOP_DISPLAY=""
DESKTOP_WAYLAND=""
DESKTOP_XAUTH=""
DESKTOP_DBUS=""
HAS_GUI_SESSION=0
GUI_USABLE=0

_detect_gui_session() {
    local cand_user="" sid="" stype="" sactive="" sremote="" suser=""

    if [[ -n "${SUDO_USER:-}" && "$SUDO_USER" != "root" ]]; then
        cand_user="$SUDO_USER"
    elif have loginctl; then
        while IFS=' ' read -r sid _ suser _; do
            [[ -z "$sid" || "$suser" == "root" ]] && continue
            stype=$(loginctl show-session "$sid" -p Type --value 2>/dev/null)
            sactive=$(loginctl show-session "$sid" -p Active --value 2>/dev/null)
            sremote=$(loginctl show-session "$sid" -p Remote --value 2>/dev/null)
            if [[ "$sactive" == "yes" && "$sremote" == "no" && ("$stype" == "wayland" || "$stype" == "x11") ]]; then
                cand_user="$suser"
                break
            fi
        done < <(loginctl list-sessions --no-legend 2>/dev/null)
    fi

    [[ -z "$cand_user" ]] && return 0
    DESKTOP_USER="$cand_user"
    DESKTOP_UID=$(id -u "$DESKTOP_USER" 2>/dev/null)
    [[ -z "$DESKTOP_UID" ]] && return 0
    DESKTOP_HOME=$(getent passwd "$DESKTOP_USER" 2>/dev/null | cut -d: -f6)
    [[ -n "$DESKTOP_HOME" ]] || DESKTOP_HOME="/tmp"
    DESKTOP_RUNTIME="/run/user/$DESKTOP_UID"

    DESKTOP_DISPLAY="${DISPLAY:-}"
    DESKTOP_WAYLAND="${WAYLAND_DISPLAY:-}"
    DESKTOP_XAUTH="${XAUTHORITY:-}"
    DESKTOP_DBUS="${DBUS_SESSION_BUS_ADDRESS:-}"

    local pid line env_dump
    for pid in $(pgrep -u "$DESKTOP_UID" 2>/dev/null | head -n 40); do
        [[ -r "/proc/$pid/environ" ]] || continue
        env_dump=$(tr '\0' '\n' <"/proc/$pid/environ" 2>/dev/null)
        while IFS= read -r line; do
            case "$line" in
            DISPLAY=*) [[ -z "$DESKTOP_DISPLAY" ]] && DESKTOP_DISPLAY="${line#DISPLAY=}" ;;
            WAYLAND_DISPLAY=*) [[ -z "$DESKTOP_WAYLAND" ]] && DESKTOP_WAYLAND="${line#WAYLAND_DISPLAY=}" ;;
            XAUTHORITY=*) [[ -z "$DESKTOP_XAUTH" ]] && DESKTOP_XAUTH="${line#XAUTHORITY=}" ;;
            DBUS_SESSION_BUS_ADDRESS=*) [[ -z "$DESKTOP_DBUS" ]] && DESKTOP_DBUS="${line#DBUS_SESSION_BUS_ADDRESS=}" ;;
            esac
        done <<<"$env_dump"
        [[ -n "$DESKTOP_DISPLAY" && -n "$DESKTOP_WAYLAND" && -n "$DESKTOP_XAUTH" ]] && break
    done

    local sock xs xa
    if [[ -z "$DESKTOP_WAYLAND" && -d "$DESKTOP_RUNTIME" ]]; then
        for sock in "$DESKTOP_RUNTIME"/wayland-*; do
            [[ -S "$sock" && "$sock" != *.lock ]] && {
                DESKTOP_WAYLAND="${sock##*/}"
                break
            }
        done
    fi
    if [[ -z "$DESKTOP_DISPLAY" ]]; then
        for xs in /tmp/.X11-unix/X*; do
            [[ -S "$xs" ]] && {
                DESKTOP_DISPLAY=":${xs##*X}"
                break
            }
        done
    fi
    if [[ -z "$DESKTOP_XAUTH" ]]; then
        for xa in "$DESKTOP_RUNTIME"/xauth_* "$DESKTOP_RUNTIME"/.mutter-Xwaylandauth.* "$DESKTOP_RUNTIME"/.Xauthority* "${DESKTOP_HOME}/.Xauthority"; do
            [[ -r "$xa" ]] && {
                DESKTOP_XAUTH="$xa"
                break
            }
        done
    fi
    if [[ -z "$DESKTOP_DBUS" && -S "$DESKTOP_RUNTIME/bus" ]]; then
        DESKTOP_DBUS="unix:path=$DESKTOP_RUNTIME/bus"
    fi
    [[ -n "$DESKTOP_DISPLAY" || -n "$DESKTOP_WAYLAND" ]] && HAS_GUI_SESSION=1
    return 0
}
_detect_gui_session

# run a command inside the desktop user's session environment
run_in_session() {
    local env_args=()
    [[ -n "$DESKTOP_RUNTIME" ]] && env_args+=("XDG_RUNTIME_DIR=$DESKTOP_RUNTIME")
    [[ -n "$DESKTOP_DISPLAY" ]] && env_args+=("DISPLAY=$DESKTOP_DISPLAY")
    [[ -n "$DESKTOP_WAYLAND" ]] && env_args+=("WAYLAND_DISPLAY=$DESKTOP_WAYLAND")
    [[ -n "$DESKTOP_XAUTH" ]] && env_args+=("XAUTHORITY=$DESKTOP_XAUTH")
    [[ -n "$DESKTOP_DBUS" ]] && env_args+=("DBUS_SESSION_BUS_ADDRESS=$DESKTOP_DBUS")
    if [[ -n "$DESKTOP_USER" && "$DESKTOP_USER" != "root" ]] && have runuser; then
        env_args+=("HOME=${DESKTOP_HOME:-/tmp}")
        runuser -u "$DESKTOP_USER" -- env ${env_args[@]+"${env_args[@]}"} "$@"
    else
        env ${env_args[@]+"${env_args[@]}"} "$@"
    fi
}

# run_session_cmd TITLE TIMEOUT cmd... — like run_cmd but inside the desktop session
run_session_cmd() {
    local title="$1" tmo="$2" cmd_str rc
    shift 2
    set_detail "$title"
    section "$title"
    printf -v cmd_str '%q ' "$@"
    echo "Command (session=${DESKTOP_USER:-root}): ${cmd_str% }"
    echo "--- Output ---"
    if ! have "$1"; then
        echo "NOTE: '$1' is not installed — skipped."
        echo "--- Exit code: 127 ---"
        return 127
    fi
    run_in_session timeout -k 3 "$tmo" "$@" </dev/null 2>&1 | tee "$LAST_DETAIL"
    rc=${PIPESTATUS[0]}
    [[ -s "$LAST_DETAIL" ]] || echo "(no output)" | tee "$LAST_DETAIL"
    echo "--- Exit code: $rc ---"
    [[ $rc -eq 124 ]] && echo "NOTE: timed out after ${tmo}s."
    return "$rc"
}

# ── 8. banner ────────────────────────────────────────────────────────────────
# Note: the script does not print its own $0; if you see it, it came from the launching shell.
if [[ $EUID -eq 0 ]]; then
    printf 'Running as root (euid=0).\n'
    if ! ((VERBOSE)); then
        printf 'Running as root (euid=0).\n' >&3
    fi
fi
banner_text=$(
    cat <<EOF
diag.sh v$VERSION — universal hardware & system diagnostic
Started : $(date -Is)   Host: $(hostname 2>/dev/null)
OS      : $OS_PRETTY (id=$OS_ID like=$OS_LIKE)   Kernel: $KVER   Arch: $MACH   CPUs: $NPROC
Context : live=$IS_LIVE laptop=$IS_LAPTOP virt=$VIRT_ENV container=$IS_CONTAINER pkgmgr=${PM:-none}
Options : quick=$QUICK no-stress=$NO_STRESS no-install=$NO_INSTALL stress-secs=$STRESS_SECS redact=$REDACT quiet=$QUIET
Output  : $REPORT_DIR
EOF
)
printf '%s\n' "$banner_text"
if ! ((VERBOSE)); then
    printf '%s\n' "$banner_text" >&3
fi

# ── 9. kernel log capture (used by every log analyser) ───────────────────────
KLOG_SRC="dmesg"
capture_klog() {
    if have journalctl && journalctl -k -b --no-pager -o short-iso >"$KLOG_FILE" 2>/dev/null && [[ -s "$KLOG_FILE" ]]; then
        KLOG_SRC="journalctl -k -b (full current boot)"
    else
        { dmesg -T 2>/dev/null || dmesg 2>/dev/null; } >"$KLOG_FILE"
        KLOG_SRC="dmesg ring buffer"
    fi
    [[ -s "$KLOG_FILE" ]] || echo "(kernel log unavailable — container or restricted dmesg)" >"$KLOG_FILE"
    cp "$KLOG_FILE" "$DETAILS/kernel-log-full.txt" 2>/dev/null
}
capture_klog
DMESG_LINES_BEFORE_STRESS=$(dmesg 2>/dev/null | wc -l)

# ── 10. tool catalogue: "command|family=package[/alternative],..." ───────────
# families: pacman apt dnf zypper   ("*" = same name everywhere, "-" = not packaged)
# shellcheck disable=SC2034 # Referenced indirectly via tier loop (${!arr})
TOOLS_CORE=(
    'ip|pacman=iproute2,apt=iproute2,dnf=iproute,zypper=iproute2'
    'ping|pacman=iputils,apt=iputils-ping,dnf=iputils,zypper=iputils'
    'lspci|*=pciutils'
    'lsusb|*=usbutils'
    'dmidecode|*=dmidecode'
    'smartctl|*=smartmontools'
    'nvme|*=nvme-cli'
    'sensors|pacman=lm_sensors,apt=lm-sensors,dnf=lm_sensors,zypper=sensors'
    'lshw|*=lshw'
    'inxi|*=inxi'
    'ethtool|*=ethtool'
    'iw|*=iw'
    'fio|*=fio'
    'stress-ng|*=stress-ng'
    'memtester|*=memtester'
    'hdparm|*=hdparm'
    'efibootmgr|*=efibootmgr'
    'lsscsi|*=lsscsi'
)
# shellcheck disable=SC2034 # Referenced indirectly via tier loop (${!arr})
TOOLS_EXTRA=(
    'sysbench|*=sysbench'
    'acpidump|pacman=acpica,apt=acpica-tools,dnf=acpica-tools,zypper=acpica'
    'cpupower|pacman=cpupower,apt=linux-cpupower/linux-tools-common,dnf=kernel-tools,zypper=cpupower'
    'turbostat|pacman=turbostat,apt=linux-tools-generic/linux-tools-common,dnf=kernel-tools,zypper=-'
    'bluetoothctl|pacman=bluez-utils,apt=bluez,dnf=bluez,zypper=bluez'
    'upower|*=upower'
    'acpi|*=acpi'
    'aplay|*=alsa-utils'
    'evtest|*=evtest'
    'libinput|pacman=libinput,apt=libinput-tools,dnf=libinput-utils,zypper=libinput-tools'
    'v4l2-ctl|*=v4l-utils'
    'i2cdetect|*=i2c-tools'
    'mokutil|*=mokutil'
    'tpm2_getcap|*=tpm2-tools'
    'boltctl|*=bolt'
    'numactl|*=numactl'
    'hwinfo|*=hwinfo'
    'ipmitool|*=ipmitool'
    'fwupdmgr|*=fwupd'
    'ras-mc-ctl|*=rasdaemon'
    'btrfs|*=btrfs-progs'
    'pvs|*=lvm2'
    'mdadm|*=mdadm'
    'cryptsetup|*=cryptsetup'
    'edid-decode|*=edid-decode'
    'xrandr|pacman=xorg-xrandr,apt=x11-xserver-utils,dnf=xrandr,zypper=xrandr'
)
# shellcheck disable=SC2034 # Referenced indirectly via tier loop (${!arr})
TOOLS_GFX=(
    'glxinfo|pacman=mesa-utils,apt=mesa-utils,dnf=glx-utils/mesa-demos,zypper=Mesa-demo-x/Mesa-demo'
    'vulkaninfo|*=vulkan-tools'
    'clinfo|*=clinfo'
    'vainfo|pacman=libva-utils,apt=vainfo,dnf=libva-utils,zypper=libva-utils'
    'drm_info|pacman=drm_info,apt=drm-info,dnf=drm_info,zypper=-'
    'glmark2|pacman=glmark2,apt=glmark2-x11/glmark2,dnf=glmark2,zypper=glmark2'
    'vkmark|*=vkmark'
)

PM_KEY="$PM"
[[ "$PM" == yum ]] && PM_KEY=dnf

spec_lookup() { # spec → alternatives string for this package-manager family
    local spec="$1" kv def="" hit="" parts
    IFS=',' read -ra parts <<<"$spec"
    for kv in ${parts[@]+"${parts[@]}"}; do
        case "${kv%%=*}" in
        "$PM_KEY") hit="${kv#*=}" ;;
        '*') def="${kv#*=}" ;;
        esac
    done
    printf '%s' "${hit:-$def}"
}

pm_pkg_available() {
    local p="$1" c
    case "$PM" in
    pacman) pacman -Si "$p" &>/dev/null ;;
    apt)
        c=$(apt-cache policy "$p" 2>/dev/null | awk '/Candidate:/ {print $2; exit}')
        [[ -n "$c" && "$c" != "(none)" ]]
        ;;
    *) true ;; # dnf/zypper: cheap pre-check unavailable; the install itself decides
    esac
}

resolve_pkg() { # "a/b/c" → first alternative the repos actually have
    local alts="$1" a arr
    IFS='/' read -ra arr <<<"$alts"
    for a in ${arr[@]+"${arr[@]}"}; do
        [[ -z "$a" || "$a" == "-" ]] && continue
        pm_pkg_available "$a" && {
            printf '%s' "$a"
            return 0
        }
    done
    return 1
}

pacman_wait_lock() {
    local lck=/var/lib/pacman/db.lck i
    [[ -e "$lck" ]] || return 0
    for ((i = 0; i < 60; i++)); do
        pgrep -x pacman &>/dev/null || break
        [[ $i -eq 0 ]] && echo "pacman is running elsewhere; waiting up to 2 min..."
        sleep 2
    done
    if pgrep -x pacman &>/dev/null; then
        echo "pacman still busy — skipping package installation."
        return 1
    fi
    if [[ -e "$lck" ]]; then
        if ((IS_LIVE)); then
            rm -f "$lck" # ephemeral live system: a stale lock is harmless to drop
        else
            echo "Stale $lck exists (no pacman running). Not removing it on an installed system;"
            echo "remove it manually if you are sure, then re-run. Skipping installs."
            return 1
        fi
    fi
    return 0
}

pm_refresh() {
    case "$PM" in
    pacman) ((IS_LIVE)) && to 180 pacman -Sy --noconfirm ;; # live ISO only (ephemeral root)
    apt) to 240 env DEBIAN_FRONTEND=noninteractive apt-get update -qq ;;
    zypper) to 240 zypper --non-interactive --quiet refresh ;;
    dnf | yum) to 240 "$PM" -q makecache ;;
    esac </dev/null &>>"$MAIN_LOG"
    return 0
}

pm_install() {
    case "$PM" in
    pacman) to 900 pacman -S --needed --noconfirm "$@" ;;
    apt) to 900 env DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends -o DPkg::Lock::Timeout=180 "$@" ;;
    dnf | yum) to 900 "$PM" -y install --setopt=install_weak_deps=False "$@" ;;
    zypper) to 900 zypper --non-interactive --quiet install --no-recommends "$@" ;;
    *) return 1 ;;
    esac </dev/null &>>"$MAIN_LOG"
}

pm_install_retry() { # retry a few times when someone else holds the package lock
    local n
    for _ in 1 2 3; do
        pm_install "$@" && return 0
        tail -n 8 "$MAIN_LOG" 2>/dev/null | grep -qiE 'lock|another process|is being used' || return 1
        sleep 20
    done
    return 1
}

_network_up() { # TCP probe — needs no ping/curl
    local h
    for h in 1.1.1.1 8.8.8.8 9.9.9.9; do
        timeout 4 bash -c "exec 3<>/dev/tcp/$h/443" 2>/dev/null && return 0
    done
    return 1
}

INSTALLED_TOOLS=()
UNAVAIL_TOOLS=()

install_missing_tools() {
    section "Diagnostic tool installation (idempotent)"
    if ((NO_INSTALL)); then
        echo "Skipped (--no-install)."
        return 0
    fi
    if [[ -z "$PM" ]]; then
        echo "No supported package manager (pacman/apt/dnf/yum/zypper) — using tools already installed."
        return 0
    fi

    local tier arr entry cmd any=0
    for tier in TOOLS_CORE TOOLS_EXTRA TOOLS_GFX; do
        arr="${tier}[@]"
        for entry in "${!arr}"; do
            have "${entry%%|*}" || any=1
        done
    done
    if ((! any)); then
        echo "All diagnostic tools are already present — nothing to install."
        return 0
    fi

    ((IS_CONTAINER)) && echo "NOTE: running in a container — hardware probes will be limited."

    # Arch live ISOs keep their root in a small RAM overlay: enlarge it when RAM allows.
    if ((IS_LIVE)) && mountpoint -q /run/archiso/cowspace 2>/dev/null; then
        local mem_mb
        mem_mb=$(awk '/MemTotal:/ {print int($2/1024)}' /proc/meminfo)
        if [[ "${mem_mb:-0}" -ge 3000 ]]; then
            mount -o remount,size=1G /run/archiso/cowspace 2>/dev/null && echo "Enlarged live overlay (cowspace) to 1G."
        fi
    fi

    if [[ "$PM" == pacman ]]; then
        pacman_wait_lock || return 0
    fi
    if ! _network_up; then
        echo "NOTE: no direct internet route detected; trying the package manager anyway (local mirror?)."
    fi
    echo "Refreshing package metadata ($PM)..."
    pm_refresh

    local alts pick avail p spec
    for tier in TOOLS_CORE TOOLS_EXTRA TOOLS_GFX; do
        arr="${tier}[@]"
        local -a pkgs=()
        local -A seen=()
        for entry in "${!arr}"; do
            cmd="${entry%%|*}"
            spec="${entry#*|}"
            have "$cmd" && continue
            alts=$(spec_lookup "$spec")
            if [[ -z "$alts" || "$alts" == "-" ]] || ! pick=$(resolve_pkg "$alts"); then
                UNAVAIL_TOOLS+=("$cmd")
                continue
            fi
            [[ -n "${seen[$pick]:-}" ]] && continue
            seen[$pick]=1
            pkgs+=("$pick")
        done
        ((${#pkgs[@]})) || continue
        if ((IS_LIVE)); then
            avail=$(free_mb /)
            if [[ "${avail:-0}" -lt 120 ]]; then
                echo "Live root has only ${avail:-0} MB free — skipping ${tier#TOOLS_} tier."
                for p in ${pkgs[@]+"${pkgs[@]}"}; do UNAVAIL_TOOLS+=("$p"); done
                continue
            fi
        fi
        echo "Installing (${tier#TOOLS_}): ${pkgs[*]}"
        if pm_install_retry ${pkgs[@]+"${pkgs[@]}"}; then
            INSTALLED_TOOLS+=(${pkgs[@]+"${pkgs[@]}"})
        else
            echo "Batch install failed — retrying package by package (details: $MAIN_LOG)."
            for p in ${pkgs[@]+"${pkgs[@]}"}; do
                if pm_install_retry "$p"; then
                    INSTALLED_TOOLS+=("$p")
                else
                    UNAVAIL_TOOLS+=("$p")
                fi
            done
        fi
    done
    hash -r

    if ((${#INSTALLED_TOOLS[@]})); then
        echo "Installed: ${INSTALLED_TOOLS[*]}"
    fi
    # re-evaluate which tools are still missing
    local -a still=()
    for tier in TOOLS_CORE TOOLS_EXTRA TOOLS_GFX; do
        arr="${tier}[@]"
        for entry in "${!arr}"; do
            have "${entry%%|*}" || still+=("${entry%%|*}")
        done
    done
    if ((${#still[@]})); then
        echo "Still unavailable (sections depending on them are skipped): ${still[*]}"
        finding INFO tools "Optional tools not available on this system: ${still[*]} — related sections were skipped."
    fi
    if ((${#INSTALLED_TOOLS[@]})); then
        finding INFO tools "Installed ${#INSTALLED_TOOLS[@]} diagnostic package(s) during this run (see logs/main.log): ${INSTALLED_TOOLS[*]}"
    fi
    return 0
}
install_missing_tools

# ── 11. GL / Vulkan reachability (decides whether GUI/GPU tests can run) ─────
NVRM_MISMATCH=0
GUI_NOTE=""
probe_gui_stack() {
    grep -q 'NVRM: API mismatch' "$KLOG_FILE" 2>/dev/null && NVRM_MISMATCH=1
    ((HAS_GUI_SESSION)) || {
        GUI_NOTE="no reachable X/Wayland desktop session"
        return 0
    }
    if (have glxinfo && run_in_session timeout 10 glxinfo -B </dev/null &>/dev/null) ||
        (have vulkaninfo && run_in_session timeout 10 vulkaninfo --summary </dev/null &>/dev/null) ||
        (have eglinfo && run_in_session timeout 10 eglinfo -B </dev/null &>/dev/null); then
        GUI_USABLE=1
    elif ((NVRM_MISMATCH)); then
        GUI_NOTE="GL/Vulkan probes failed: NVIDIA kernel/userspace version mismatch (reboot required)"
    elif ! have glxinfo && ! have vulkaninfo && ! have eglinfo; then
        GUI_NOTE="no GL/Vulkan probe tools installed"
    else
        GUI_NOTE="desktop session found but GL/Vulkan probes failed"
    fi
    return 0
}
probe_gui_stack
section "Environment summary"
echo "Kernel log source : $KLOG_SRC"
echo "Desktop session   : detected=$HAS_GUI_SESSION user=${DESKTOP_USER:-none} DISPLAY=${DESKTOP_DISPLAY:-unset} WAYLAND=${DESKTOP_WAYLAND:-unset}"
echo "GUI GPU tests     : usable=$GUI_USABLE ${GUI_NOTE:+($GUI_NOTE)}"

# ── 12. system, firmware, boot & virtualization ──────────────────────────────
run_cmd "OS and kernel" 10 uname -a
run_cmd "Distribution release" 5 cat /etc/os-release
run_cmd "Hostname and machine" 10 hostnamectl
run_cmd "Date and timezone" 5 timedatectl
run_cmd "Uptime and load" 5 bash -c 'uptime; echo; cat /proc/loadavg'
run_cmd "Kernel command line" 5 cat /proc/cmdline
run_cmd "Kernel taint, virtualization & IOMMU" 15 bash -c '
    echo "kernel.tainted = $(cat /proc/sys/kernel/tainted 2>/dev/null || echo 0)"
    echo "systemd-detect-virt = $(systemd-detect-virt 2>/dev/null || echo none)"
    ls -l /dev/kvm /dev/vhost* 2>/dev/null
    echo "IOMMU groups: $(find /sys/kernel/iommu_groups -mindepth 1 -maxdepth 1 2>/dev/null | wc -l)"
    grep -iE "iommu|dmar|amd-vi|sev|tdx|sgx" "$KLOG_FILE" | head -40'

run_cmd "UEFI firmware & bootctl" 15 bash -c '
    if [[ -d /sys/firmware/efi ]]; then
        echo "Boot mode: UEFI ($(cat /sys/firmware/efi/fw_platform_size 2>/dev/null || echo ?)-bit)"
    else
        echo "Boot mode: Legacy BIOS"
    fi
    bootctl status 2>/dev/null || true'
run_cmd "UEFI boot entries" 10 efibootmgr -v
run_cmd "Secure Boot state" 5 mokutil --sb-state
run_cmd "TPM devices" 10 bash -c 'ls -l /dev/tpm* 2>/dev/null || echo "No TPM devices."'
have tpm2_getcap && run_cmd "TPM capabilities" 10 tpm2_getcap properties-fixed
have tpm2_pcrread && [[ -e /dev/tpmrm0 ]] && run_cmd "TPM PCR banks (sha256)" 10 tpm2_pcrread sha256
if have fwupdmgr && ((QUICK == 0)); then
    run_cmd "fwupd devices (read-only)" 30 fwupdmgr get-devices --no-authenticate
    run_cmd "fwupd available firmware updates (cached metadata)" 30 fwupdmgr get-updates --no-authenticate
fi

run_cmd "Systemd boot time" 15 systemd-analyze time
run_cmd "Systemd blame (top 30)" 20 bash -c 'systemd-analyze blame 2>/dev/null | head -30'
run_cmd "Systemd critical chain" 15 systemd-analyze critical-chain
run_cmd "Failed systemd units" 10 systemctl --failed --no-pager
run_cmd "Enabled systemd services" 15 systemctl list-unit-files --type=service --state=enabled --no-pager
have coredumpctl && run_cmd "Systemd coredumps" 15 coredumpctl list --no-pager
run_cmd "Security posture (SELinux/AppArmor/lockdown/firewall)" 20 bash -c '
    have() { command -v "$1" &>/dev/null; }
    have getenforce && echo "SELinux: $(getenforce 2>&1)"
    have aa-status && echo "AppArmor: $(aa-status --enabled 2>&1 && echo enabled)"
    echo "Kernel lockdown: $(cat /sys/kernel/security/lockdown 2>/dev/null || echo n/a)"
    have ufw && ufw status 2>&1 | head -5
    have firewall-cmd && echo "firewalld: $(firewall-cmd --state 2>&1)"
    have nft && echo "nftables rules: $(nft list ruleset 2>/dev/null | wc -l) lines"
    echo "Encrypted (dm-crypt) mappings: $(lsblk -rno TYPE 2>/dev/null | grep -c crypt)"'

an_system() {
    local IFS=$'\n\t'
    local -a taint_names=("proprietary module loaded" "module force-loaded" "SMP kernel on non-SMP hardware" "module force-unloaded" "machine check exception" "bad page referenced" "taint requested by user" "kernel died (oops/BUG)" "ACPI table overridden" "kernel warning issued" "staging driver loaded" "firmware workaround applied" "out-of-tree module loaded" "unsigned module loaded" "soft lockup occurred" "kernel live-patched" "auxiliary taint" "struct randomization plugin" "in-kernel test run")
    local t i st failed n u v f td line total secs
    echo "--- kernel taint ---"
    t=$(num "$(cat /proc/sys/kernel/tainted 2>/dev/null)")
    t=${t:-0}
    echo "kernel.tainted = $t"
    if ((t > 0)); then
        for ((i = 0; i < ${#taint_names[@]}; i++)); do
            if (((t >> i) & 1)); then
                echo "  bit $i: ${taint_names[$i]}"
                case $i in
                4 | 5 | 7 | 14) finding WARN kernel "Kernel taint: ${taint_names[$i]} (bit $i) — evidence of a hardware or driver fault; check the kernel log analysis." ;;
                esac
            fi
        done
    fi

    echo "--- pending reboot ---"
    if ((IS_CONTAINER == 0 && IS_LIVE == 0)) && [[ ! -d "/lib/modules/$KVER" && ! -d "/usr/lib/modules/$KVER" ]]; then
        finding WARN reboot "Running kernel $KVER has no module tree on disk: the kernel was upgraded without a reboot. Reboot — GPU, Wi-Fi, USB-storage and container-network drivers can fail until you do."
    fi
    if [[ -e /var/run/reboot-required ]]; then
        finding INFO reboot "A reboot is pending (/var/run/reboot-required: $(tr '\n' ' ' </var/run/reboot-required.pkgs 2>/dev/null))."
    fi

    echo "--- systemd state ---"
    if have systemctl && [[ -d /run/systemd/system ]]; then
        st=$(systemctl is-system-running 2>/dev/null)
        echo "is-system-running = $st"
        failed=$(systemctl --failed --no-legend --plain --no-pager 2>/dev/null |
            awk '{for(i=1;i<=NF;i++) if ($i ~ /\.(service|socket|mount|timer|target|device|path|slice|scope|swap|automount)$/) {print $i; break}}')
        if [[ -n "$failed" ]]; then
            n=$(wc -l <<<"$failed")
            finding WARN systemd "$n failed unit(s): $(tr '\n' ' ' <<<"$failed")— root cause is usually in the unit logs below (a stopped docker/network/mount unit is often a side effect of a driver or reboot problem)."
            for u in $(head -8 <<<"$failed"); do
                echo "=== $u ==="
                to 10 systemctl status --no-pager -n 12 "$u" 2>&1 | head -30
                to 15 journalctl -u "$u" -b --no-pager -n 25 2>&1
            done
        elif [[ "$st" == degraded ]]; then
            finding WARN systemd "systemd reports a degraded state but lists no failed unit."
        fi
    else
        echo "(systemd not running)"
    fi

    echo "--- time ---"
    if have timedatectl; then
        td=$(timedatectl 2>/dev/null)
        if ((IS_LIVE == 0)) && grep -qiE '(NTP|clock) synchronized: no' <<<"$td"; then
            finding INFO time "System clock is not NTP-synchronised (enable systemd-timesyncd/chrony; drifting time breaks TLS and package signatures)."
        fi
        if grep -q 'RTC in local TZ: yes' <<<"$td"; then
            finding INFO time "RTC is kept in local time (normal for Windows dual-boot). Use UTC if Linux-only: timedatectl set-local-rtc 0."
        fi
    fi

    echo "--- CPU vulnerabilities ---"
    for f in /sys/devices/system/cpu/vulnerabilities/*; do
        v=$(<"$f")
        printf '  %-28s %s\n' "${f##*/}" "$v"
        [[ "$v" == Vulnerable* ]] && finding INFO cpu "CPU vulnerability '${f##*/}' is NOT mitigated ($v) — update kernel/microcode."
    done

    echo "--- boot time ---"
    if ((IS_LIVE == 0 && IS_CONTAINER == 0)) && have systemd-analyze; then
        line=$(to 20 systemd-analyze time 2>/dev/null | head -1)
        echo "$line"
        total=$(sed -nE 's/.*= *(.*)$/\1/p' <<<"$line")
        if [[ -n "$total" ]]; then
            secs=$(dur_to_sec "$total")
            if awk -v s="$secs" 'BEGIN{exit !(s > 60)}'; then
                finding INFO boot "Boot takes $total — breakdown: ${line#Startup finished in }"
            fi
        fi
    fi
    return 0
}
run_fn "Analysis: system state, reboot, services, time" 90 an_system

# ── 13. hardware inventory ───────────────────────────────────────────────────
run_cmd "DMI/SMBIOS full decode" 30 dmidecode
run_cmd "inxi full report" 90 inxi -Fxz --tty
if ((QUICK == 0)); then
    run_cmd "lshw inventory" 150 bash -c 'lshw -json 2>/dev/null || lshw 2>/dev/null || echo "lshw unavailable"'
    run_cmd "hwinfo short summary" 60 hwinfo --short
    run_cmd "SCSI/SATA/USB-storage devices (lsscsi)" 15 lsscsi -s
fi

run_cmd "CPU information" 10 lscpu
run_cmd "CPU extended topology" 10 lscpu -e
run_cmd "CPU /proc/cpuinfo save" 10 bash -c 'cp /proc/cpuinfo "$1"; echo "saved: $1"' _ "$DETAILS/cpuinfo.txt"
run_cmd "CPU microcode" 10 bash -c '
    grep -iE "microcode" "$KLOG_FILE" | head -5 || echo "no microcode lines in kernel log"
    grep -m4 "microcode" /proc/cpuinfo
    case "$PM" in
    pacman) pacman -Q amd-ucode intel-ucode 2>/dev/null ;;
    apt) dpkg -l "amd64-microcode" "intel-microcode" 2>/dev/null | grep "^ii" ;;
    dnf | yum) rpm -q microcode_ctl linux-firmware 2>/dev/null ;;
    zypper) rpm -q ucode-intel ucode-amd 2>/dev/null ;;
    esac
    true'
run_cmd "CPU frequency info" 15 cpupower frequency-info
run_cmd "CPU scaling policies" 10 bash -c '
    echo "SMT: $(cat /sys/devices/system/cpu/smt/control 2>/dev/null || echo n/a)"
    for p in /sys/devices/system/cpu/cpufreq/policy*; do
        [[ -d "$p" ]] || continue
        printf "%s: drv=%s gov=%s epp=%s cur=%s min=%s max=%s\n" "${p##*/}" \
            "$(cat "$p/scaling_driver" 2>/dev/null || echo ?)" "$(cat "$p/scaling_governor" 2>/dev/null || echo ?)" \
            "$(cat "$p/energy_performance_preference" 2>/dev/null || echo n/a)" "$(cat "$p/scaling_cur_freq" 2>/dev/null || echo ?)" \
            "$(cat "$p/scaling_min_freq" 2>/dev/null || echo ?)" "$(cat "$p/scaling_max_freq" 2>/dev/null || echo ?)"
    done'
run_cmd "CPU idle states" 10 cpupower idle-info
if have turbostat; then
    run_cmd "Turbostat sample" 20 bash -c '
        turbostat --Summary --quiet --num_iterations 1 --interval 2 2>/dev/null \
        || timeout 6 turbostat --quiet --show PkgWatt,CorWatt,GFXWatt,CPU%c1,CPU%c6 2>/dev/null \
        || echo "(turbostat unsupported on this platform)"'
fi
have numactl && run_cmd "NUMA topology" 10 numactl --hardware

# ── 14. memory ───────────────────────────────────────────────────────────────
run_cmd "Memory layout" 10 lsmem
run_cmd "Memory usage" 5 free -h
run_cmd "Memory /proc/meminfo" 5 cat /proc/meminfo
run_cmd "Per-DIMM memory details" 30 dmidecode -t memory
run_cmd "ZRAM & swap" 10 bash -c 'swapon --show; echo "---"; zramctl 2>/dev/null; true'
if have decode-dimms && compgen -G "/sys/bus/i2c/drivers/*ee1004*/*" >/dev/null; then
    run_cmd "SPD DIMM EEPROM decode" 20 decode-dimms
fi

an_memory() {
    local IFS=$'\n\t'
    local total avail swt swf pct used f ue ce loc sz sp cs spn csn mism=""
    total=$(awk '/^MemTotal:/ {print $2}' /proc/meminfo)
    avail=$(awk '/^MemAvailable:/ {print $2}' /proc/meminfo)
    swt=$(awk '/^SwapTotal:/ {print $2}' /proc/meminfo)
    swf=$(awk '/^SwapFree:/ {print $2}' /proc/meminfo)
    echo "MemTotal=${total} kB  MemAvailable=${avail} kB  SwapTotal=${swt} kB  SwapFree=${swf} kB"
    if [[ "${total:-0}" -gt 0 && -n "$avail" ]] && ((IS_LIVE == 0)); then
        pct=$((avail * 100 / total))
        ((pct < 10)) && finding WARN memory "Only ${pct}% of RAM is available right now — the system is memory-starved (check for leaks; consider more RAM/zram)."
    fi
    if [[ "${swt:-0}" -gt 0 ]]; then
        used=$(((swt - swf) * 100 / swt))
        ((used >= 50)) && finding INFO memory "Swap is ${used}% in use — the machine is under memory pressure."
    fi
    for f in /sys/devices/system/edac/mc/mc*/ue_count; do
        ue=$(num "$(cat "$f" 2>/dev/null)")
        [[ "${ue:-0}" -gt 0 ]] && finding FAIL memory "ECC: ${ue} UNCORRECTABLE memory error(s) on ${f%/*} — replace the DIMM and run a full memtest."
    done
    for f in /sys/devices/system/edac/mc/mc*/ce_count; do
        ce=$(num "$(cat "$f" 2>/dev/null)")
        [[ "${ce:-0}" -gt 0 ]] && finding WARN memory "ECC: ${ce} corrected memory error(s) on ${f%/*} — a DIMM is degrading; monitor and plan replacement."
    done
    echo "--- populated DIMMs (locator | size | rated | configured) ---"
    if have dmidecode && [[ -d /sys/firmware/dmi ]]; then
        while IFS='|' read -r loc sz sp cs; do
            [[ -n "$loc" ]] || continue
            printf '  %-22s %-10s rated=%-14s configured=%s\n' "$loc" "$sz" "$sp" "$cs"
            spn=$(num "${sp%% *}")
            csn=$(num "${cs%% *}")
            if [[ -n "$spn" && -n "$csn" && "$spn" -gt 0 && "$csn" -gt 0 && "$csn" -lt "$spn" ]]; then
                mism+="$loc ($csn<$spn) "
            fi
        done < <(to 20 dmidecode -t memory 2>/dev/null | awk '
            /^Memory Device$/ { inb=1; sz=""; sp=""; cs=""; loc=""; next }
            inb && /^[ \t]*Locator:/ { loc=$0; sub(/^[^:]*:[ ]*/, "", loc) }
            inb && /^[ \t]*Size:/ { sz=$0; sub(/^[^:]*:[ ]*/, "", sz) }
            inb && /^[ \t]*Speed:/ { sp=$0; sub(/^[^:]*:[ ]*/, "", sp) }
            inb && /^[ \t]*Configured (Memory|Clock) Speed:/ { cs=$0; sub(/^[^:]*:[ ]*/, "", cs) }
            inb && /^[ \t]*$/ { if (sz != "" && sz !~ /No Module/) print loc "|" sz "|" sp "|" cs; inb=0 }
            END { if (inb && sz != "" && sz !~ /No Module/) print loc "|" sz "|" sp "|" cs }')
        [[ -n "$mism" ]] && finding INFO memory "RAM runs below its rated speed: ${mism}— XMP/EXPO/DOCP is probably disabled in firmware (or the CPU/board limits it)."
    else
        echo "(DMI memory table unavailable)"
    fi
    return 0
}
run_fn "Analysis: memory" 40 an_memory

# ── 15. PCI / PCIe ───────────────────────────────────────────────────────────
run_cmd "PCI device tree" 60 lspci -vvv -nnk
run_cmd "PCI topology" 10 lspci -t

collect_pcie_health() {
    local IFS=$'\n\t'
    local dev addr cls cap_spd cap_wid cur_spd cur_wid name f key v
    echo "--- PCIe link speed/width audit (devices running below capability) ---"
    for dev in /sys/bus/pci/devices/*; do
        [[ -f "$dev/current_link_speed" ]] || continue
        addr="${dev##*/}"
        cls=$(cat "$dev/class" 2>/dev/null)
        cls="${cls#0x}"
        cap_spd=$(cat "$dev/max_link_speed" 2>/dev/null || echo "?")
        cap_wid=$(cat "$dev/max_link_width" 2>/dev/null || echo "?")
        cur_spd=$(cat "$dev/current_link_speed" 2>/dev/null || echo "?")
        cur_wid=$(cat "$dev/current_link_width" 2>/dev/null || echo "?")
        [[ "$cur_spd" == Unknown* || "$cur_wid" == "0" ]] && continue
        if [[ "$cur_spd" != "$cap_spd" || "$cur_wid" != "$cap_wid" ]]; then
            name=$(lspci -s "$addr" 2>/dev/null | cut -d' ' -f2-)
            printf '%s (%s): cur=%s x%s | max=%s x%s\n' "$addr" "${name:-class $cls}" "$cur_spd" "$cur_wid" "$cap_spd" "$cap_wid"
            case "${cls:0:4}" in
            0604 | 0600 | 0601 | 0680) continue ;; # bridges / host: asymmetric by design
            esac
            case "${cls:0:2}${cls:2:2}" in
            03*) # GPUs downtrain constantly at idle: only a width loss is worth a note
                [[ "$cur_wid" != "$cap_wid" ]] && finding INFO pcie "GPU $addr ($name) link width x$cur_wid (max x$cap_wid) — normal if slot is shared/bifurcated, otherwise reseat the card."
                ;;
            0100 | 0106 | 0107 | 0108 | 02* | 0c03 | 0c0a)
                if [[ "$cur_wid" != "$cap_wid" ]]; then
                    finding WARN pcie "$addr ($name) negotiated x$cur_wid but supports x$cap_wid — lost PCIe lanes (reseat the device, check slot sharing/bifurcation or M.2 slot wiring); this directly cuts throughput."
                elif [[ "$cur_spd" != "$cap_spd" ]]; then
                    finding INFO pcie "$addr ($name) runs at $cur_spd (device supports $cap_spd) — slot/chipset limit or ASPM power saving."
                fi
                ;;
            esac
        fi
    done
    echo "--- PCIe AER counters (sysfs) ---"
    for dev in /sys/bus/pci/devices/*; do
        addr="${dev##*/}"
        for key in aer_dev_correctable aer_dev_nonfatal aer_dev_fatal; do
            f="$dev/$key"
            [[ -r "$f" ]] || continue
            v=$(awk '/^TOTAL_ERR/ {print $2}' "$f" 2>/dev/null)
            v=$(num "$v")
            [[ "${v:-0}" -gt 0 ]] || continue
            name=$(lspci -s "$addr" 2>/dev/null | cut -d' ' -f2-)
            printf '%s (%s): %s total=%s\n' "$addr" "$name" "$key" "$v"
            case "$key" in
            aer_dev_fatal | aer_dev_nonfatal) finding WARN pcie "$addr ($name) logged $v ${key#aer_dev_} PCIe error(s) — failing device, riser/cable or slot." ;;
            aer_dev_correctable) [[ "$v" -gt 1000 ]] && finding INFO pcie "$addr ($name) logged $v corrected PCIe errors — marginal link signal integrity (reseat; try pcie_aspm=off)." ;;
            esac
        done
    done
    echo "--- PCIe AER / lane errors (lspci) ---"
    lspci -vvv 2>/dev/null | awk '
        /^[0-9a-f]{2}:[0-9a-f]{2}\.[0-9]/ { dev=$0 }
        /UESta:|CESta:|LaneErrStat:/ { if ($0 ~ /\+/ || $0 ~ /LaneErr at/) print dev "\n  " $0 }'
    return 0
}
run_fn "PCIe link & AER status audit" 60 collect_pcie_health

# ── 16. USB ──────────────────────────────────────────────────────────────────
run_cmd "USB device tree" 30 lsusb -tv
((QUICK == 0)) && run_cmd "USB descriptors (full)" 120 lsusb -v
collect_usb_sysfs() {
    local IFS=$'\n\t'
    local d
    for d in /sys/bus/usb/devices/*; do
        [[ -f "$d/idVendor" ]] || continue
        echo "=== $d ==="
        printf 'ID: %s:%s | USB: %s | Speed: %s Mbps | MaxPower: %s | PowerCtrl: %s\n' \
            "$(cat "$d/idVendor" 2>/dev/null || echo ?)" "$(cat "$d/idProduct" 2>/dev/null || echo ?)" \
            "$(tr -d ' \n' <"$d/version" 2>/dev/null || echo ?)" "$(cat "$d/speed" 2>/dev/null || echo ?)" \
            "$(cat "$d/bMaxPower" 2>/dev/null || echo ?)" "$(cat "$d/power/control" 2>/dev/null || echo ?)"
        printf 'Vendor: %s | Product: %s | Serial: %s\n' \
            "$(cat "$d/manufacturer" 2>/dev/null || echo -)" "$(cat "$d/product" 2>/dev/null || echo -)" \
            "$(cat "$d/serial" 2>/dev/null || echo -)"
    done
    return 0
}
run_fn "USB per-device sysfs" 30 collect_usb_sysfs

# ── 17. storage: layout, mounts, RAID/LVM/LUKS/Btrfs/ZFS ─────────────────────
declare -a DISKS=()
declare -A D_TRAN=() D_ROTA=() D_SIZE=() D_MODEL=()
while IFS= read -r _line; do
    _name=$(kv_get "$_line" NAME)
    [[ "$(kv_get "$_line" TYPE)" == disk && -n "$_name" ]] || continue
    [[ "$_name" =~ /(zram|loop|ram|fd|nbd|sr)[0-9]*$ ]] && continue
    _size=$(num "$(kv_get "$_line" SIZE)")
    [[ "${_size:-0}" -gt 0 ]] || continue
    DISKS+=("$_name")
    D_TRAN[$_name]=$(kv_get "$_line" TRAN)
    D_ROTA[$_name]=$(kv_get "$_line" ROTA)
    D_SIZE[$_name]=$_size
    D_MODEL[$_name]=$(kv_get "$_line" MODEL)
done < <(lsblk -dnPpb -o NAME,TYPE,TRAN,ROTA,RM,SIZE,MODEL 2>/dev/null)

run_cmd "Block devices" 20 bash -c '
    lsblk -a -o NAME,KNAME,SIZE,TYPE,FSTYPE,LABEL,MOUNTPOINTS,MODEL,SERIAL,WWN,ROTA,SCHED,TRAN,STATE 2>/dev/null \
    || lsblk -a -o NAME,KNAME,SIZE,TYPE,FSTYPE,LABEL,MOUNTPOINT,MODEL,SERIAL,ROTA,TRAN,STATE'
run_cmd "Filesystem UUIDs (blkid)" 20 blkid
run_cmd "Filesystem mounts" 15 findmnt --real
run_cmd "Disk space & inode usage" 10 bash -c 'df -hT; echo "---"; df -iT'
if ((${#DISKS[@]})); then
    run_cmd "Partition tables" 40 bash -c '
        for d in "$@"; do
            echo "=== $d ==="
            fdisk -l "$d" 2>/dev/null || parted -s "$d" print 2>/dev/null
        done; true' _ ${DISKS[@]+"${DISKS[@]}"}
else
    section "Partition tables"
    echo "No physical disks detected (virtual/containerised environment?)."
fi

collect_volume_stack() {
    local IFS=$'\n\t'
    local dm mp
    echo "--- /etc/fstab ---"
    cat /etc/fstab 2>/dev/null
    echo "--- /etc/crypttab ---"
    cat /etc/crypttab 2>/dev/null
    echo "--- dmsetup tree ---"
    have dmsetup && to 10 dmsetup ls --tree 2>/dev/null
    if have cryptsetup; then
        echo "--- active dm-crypt mappings ---"
        for dm in /dev/mapper/*; do
            [[ -b "$dm" && "${dm##*/}" != "control" ]] || continue
            to 10 cryptsetup status "${dm##*/}" 2>/dev/null
        done
    fi
    if have btrfs; then
        echo "--- Btrfs filesystems & device error stats ---"
        to 15 btrfs filesystem show 2>/dev/null
        while IFS= read -r mp; do
            [[ -n "$mp" ]] || continue
            echo "=== Btrfs: $mp ==="
            to 15 btrfs filesystem df "$mp" 2>/dev/null
            to 15 btrfs device stats "$mp" 2>/dev/null
            to 15 btrfs scrub status "$mp" 2>/dev/null
        done < <(findmnt -rn -t btrfs -o TARGET 2>/dev/null | awk '!seen[$0]++')
    fi
    if [[ -r /proc/mdstat ]]; then
        echo "--- mdadm / RAID ---"
        cat /proc/mdstat
        have mdadm && to 15 mdadm --detail --scan 2>/dev/null
    fi
    if have pvs; then
        echo "--- LVM ---"
        to 15 pvs 2>/dev/null
        to 15 vgs 2>/dev/null
        to 15 lvs 2>/dev/null
    fi
    if have zpool; then
        echo "--- ZFS ---"
        to 15 zpool status 2>/dev/null
    fi
    return 0
}
run_fn "Filesystems, LUKS, Btrfs, LVM & RAID" 120 collect_volume_stack

an_storage() {
    local IFS=$'\n\t'
    local pct mnt fs type opts mp m a out n z
    local excl=(-x tmpfs -x devtmpfs -x squashfs -x iso9660 -x overlay -x efivarfs -x ramfs -x proc -x sysfs -x cgroup2 -x erofs -x fuse.portal -x fuse.gvfsd-fuse)

    echo "--- space / inode usage ---"
    while IFS=' ' read -r pct mnt fs type; do
        pct=${pct%\%}
        [[ "$pct" =~ ^[0-9]+$ ]] || continue
        if ((pct >= 95)); then
            finding FAIL storage "$mnt ($fs, $type) is ${pct}% full — writes will start failing; free space now."
        elif ((pct >= 90)); then
            finding WARN storage "$mnt ($fs, $type) is ${pct}% full."
        fi
    done < <(df -PT ${excl[@]+"${excl[@]}"} 2>/dev/null | awk 'NR>1 {print $6, $7, $1, $2}')
    while IFS=' ' read -r pct mnt fs type; do
        pct=${pct%\%}
        [[ "$pct" =~ ^[0-9]+$ ]] || continue
        ((pct >= 90)) && finding WARN storage "$mnt ($fs, $type) has ${pct}% of its inodes used — too many small files (caches, mail spool, node_modules...)."
    done < <(df -PiT ${excl[@]+"${excl[@]}"} 2>/dev/null | awk 'NR>1 {print $6, $7, $1, $2}')

    echo "--- boot/ESP free space ---"
    for m in /boot /boot/efi /efi; do
        mountpoint -q "$m" 2>/dev/null || continue
        a=$(df -Pm "$m" 2>/dev/null | awk 'NR==2 {print $4+0}')
        echo "$m: ${a} MB free"
        [[ "${a:-999}" -lt 40 ]] && finding WARN storage "$m has only ${a} MB free — kernel/initramfs/bootloader updates will fail. Remove old kernels or enlarge the partition."
    done

    echo "--- read-only mounts ---"
    while IFS=' ' read -r mnt type opts; do
        case "$mnt" in /run/* | /sys/* | /proc/* | /snap/* | /var/lib/snapd/*) continue ;; esac
        case "$type" in ext2 | ext3 | ext4 | xfs | btrfs | f2fs | vfat | exfat | ntfs | ntfs3 | fuseblk | jfs | reiserfs | nilfs2 | bcachefs) ;; *) continue ;; esac
        if [[ ",$opts," == *,ro,* ]]; then
            echo "$mnt ($type) is read-only: $opts"
            finding WARN storage "$mnt ($type) is mounted READ-ONLY — configured that way, dirty/hibernated NTFS, or remounted by the kernel after I/O errors (see kernel log analysis)."
        fi
    done < <(findmnt -rn -o TARGET,FSTYPE,OPTIONS 2>/dev/null)

    echo "--- software RAID ---"
    if [[ -r /proc/mdstat ]]; then
        if grep -Eq '\[[U_]*_[U_]*\]' /proc/mdstat; then
            finding FAIL storage "mdadm RAID array is DEGRADED (see /proc/mdstat) — a member disk failed or is missing; replace it before another fails."
        fi
        grep -Eq 'resync|recovery|reshape|check' /proc/mdstat && finding INFO storage "A RAID resync/rebuild/check is running; disk benchmarks will be slower."
    fi

    echo "--- ZFS ---"
    if have zpool; then
        out=$(to 15 zpool status -x 2>&1)
        echo "$out"
        if [[ -n "$out" ]] && ! grep -qiE 'all pools are healthy|no pools available' <<<"$out"; then
            finding FAIL storage "ZFS reports an unhealthy pool: $(head -3 <<<"$out" | tr '\n' ' ')"
        fi
    fi

    echo "--- Btrfs ---"
    if have btrfs; then
        while IFS= read -r mp; do
            [[ -n "$mp" ]] || continue
            if ! to 20 btrfs device stats -c "$mp" &>/dev/null; then
                finding FAIL storage "Btrfs $mp has non-zero device error counters (btrfs device stats) — failing disk or cable; run a scrub and check SMART."
            fi
            out=$(to 20 btrfs scrub status "$mp" 2>&1)
            if grep -qiE 'uncorrectable_errors?: *[1-9]|unrecoverable|Error summary: *.*(csum|verify|read|uncorrectable)=[1-9]' <<<"$out"; then
                finding FAIL storage "Btrfs $mp: the last scrub found uncorrectable errors."
            fi
        done < <(findmnt -rn -t btrfs -o TARGET 2>/dev/null | awk '!seen[$0]++')
    fi

    echo "--- fstab sanity (findmnt --verify) ---"
    if findmnt --help 2>&1 | grep -q -- '--verify'; then
        out=$(to 30 findmnt --verify --verbose 2>&1)
        grep -E '\[(E|W)\]|errors?, |warnings?' <<<"$out" | head -30
        n=$(grep -c '\[E\]' <<<"$out")
        z=$(grep -c '\[W\]' <<<"$out")
        if ((n > 0)); then
            finding WARN storage "fstab has $n error(s) (e.g. a UUID/label/device that does not exist) — a non-'nofail' entry like that can drop the boot to emergency mode: $(grep -m2 '\[E\]' <<<"$out" | sed 's/^[ \t]*//' | tr '\n' ';')"
        fi
        ((z > 0)) && finding INFO storage "fstab has $z warning(s): $(grep -m2 '\[W\]' <<<"$out" | sed 's/^[ \t]*//' | tr '\n' ';')"
    else
        echo "(findmnt --verify unsupported by this util-linux)"
    fi
    return 0
}
run_fn "Analysis: filesystems, free space, RAID, fstab" 150 an_storage

# ── 18. per-disk health (read-only) ──────────────────────────────────────────
section "Storage health (read-only)"
NVME_SMART_CMD=(nvme smart-log)
NVME_ERROR_CMD=(nvme error-log)
NVME_SELFTEST_CMD=(nvme self-test-log)
NVME_IDCTRL_CMD=(nvme id-ctrl)
NVME_FWLOG_CMD=(nvme fw-log)
if have nvme; then
    nvme log smart --help &>/dev/null && NVME_SMART_CMD=(nvme log smart)
    nvme log error --help &>/dev/null && NVME_ERROR_CMD=(nvme log error)
    nvme log self-test --help &>/dev/null && NVME_SELFTEST_CMD=(nvme log self-test)
    nvme id ctrl --help &>/dev/null && NVME_IDCTRL_CMD=(nvme id ctrl)
    nvme log fw --help &>/dev/null && NVME_FWLOG_CMD=(nvme log fw)
    run_cmd "NVMe list" 15 nvme list
    run_cmd "NVMe list-subsys" 15 nvme list-subsys
fi

declare -A SMART_TYPE=()
if have smartctl; then
    while IFS=' ' read -r _sdev _sflag _stype _; do
        [[ "$_sdev" == /dev/* && "$_sflag" == "-d" && -n "$_stype" ]] && SMART_TYPE["$_sdev"]="$_stype"
    done < <(to 30 smartctl --scan-open 2>/dev/null)
fi

nvlog_field() { # nvme-cli "key : value" format
    awk -F':' -v k="$2" '{ key=$1; gsub(/[ \t]+/, "", key) }
        key == k { v=$2; sub(/^[ \t]+/, "", v); sub(/[ \t(%].*$/, "", v); gsub(/,/, "", v); print v; exit }' "$1" 2>/dev/null
}

declare -A NVME_LINK=()
an_nvme_link() { # records the negotiated PCIe link of an NVMe controller
    local dev="$1" b ctrl pcidir cs cw ms mw
    b="${dev##*/}"
    ctrl="${b%n[0-9]*}"
    pcidir=$(readlink -f "/sys/class/nvme/$ctrl/device" 2>/dev/null) || return 0
    [[ -r "$pcidir/current_link_speed" ]] || return 0
    cs=$(cat "$pcidir/current_link_speed" 2>/dev/null)
    cw=$(cat "$pcidir/current_link_width" 2>/dev/null)
    ms=$(cat "$pcidir/max_link_speed" 2>/dev/null)
    mw=$(cat "$pcidir/max_link_width" 2>/dev/null)
    NVME_LINK[$dev]="$cs x$cw (device max $ms x$mw)"
    echo "PCIe link of $dev ($ctrl @ ${pcidir##*/}): ${NVME_LINK[$dev]}"
}

NVERR_KIND="none"
an_nvme_errlog() { # summarise unique error statuses from `nvme error-log`
    local f="$1" dev="$2" top
    NVERR_KIND="none"
    top=$(awk -F':' '/status_field/ { v=$2; gsub(/^[ \t]+|[ \t]+$/, "", v); if (v !~ /^(0x0*|0)([ \t]|$)/) print v }' "$f" 2>/dev/null | sort | uniq -c | sort -rn | head -5)
    [[ -n "$top" ]] || return 0
    echo "Unique non-zero error statuses in the last entries of $dev:"
    echo "$top"
    if ! grep -qvEi 'INVALID_FIELD|0x[24]00[24]|Invalid Field' <<<"$top"; then
        NVERR_KIND="benign"
    else
        NVERR_KIND="mixed"
    fi
}

an_nvme_smart() { # dev smartctl-file nvme-smart-log-file
    local dev="$1" sf="$2" nf="${3:-}" crit spare thr used media temp unsafe errs wt ct pc overall
    overall=$(sed -nE 's/^SMART overall-health self-assessment test result: *(.*)$/\1/p' "$sf" 2>/dev/null | head -1)
    [[ -n "$overall" && "$overall" != PASSED* ]] && finding FAIL storage "$dev: SMART overall health = $overall — back up immediately and replace the drive."
    crit=$(smart_field "$sf" "Critical Warning")
    spare=$(smart_field "$sf" "Available Spare")
    thr=$(smart_field "$sf" "Available Spare Threshold")
    used=$(smart_field "$sf" "Percentage Used")
    media=$(smart_field "$sf" "Media and Data Integrity Errors")
    temp=$(smart_field "$sf" "Temperature")
    unsafe=$(smart_field "$sf" "Unsafe Shutdowns")
    errs=$(smart_field "$sf" "Error Information Log Entries")
    wt=$(smart_field "$sf" "Warning Comp. Temperature Time")
    ct=$(smart_field "$sf" "Critical Comp. Temperature Time")
    pc=$(smart_field "$sf" "Power Cycles")
    if [[ -z "$crit" && -n "$nf" && -s "$nf" ]]; then
        crit=$(nvlog_field "$nf" critical_warning)
        spare=$(nvlog_field "$nf" available_spare)
        thr=$(nvlog_field "$nf" available_spare_threshold)
        used=$(nvlog_field "$nf" percentage_used)
        media=$(nvlog_field "$nf" media_errors)
        temp=$(nvlog_field "$nf" temperature)
        unsafe=$(nvlog_field "$nf" unsafe_shutdowns)
        errs=$(nvlog_field "$nf" num_err_log_entries)
        wt=$(nvlog_field "$nf" warning_temp_time)
        ct=$(nvlog_field "$nf" critical_comp_time)
        pc=$(nvlog_field "$nf" power_cycles)
    fi
    spare=$(num "$spare")
    thr=$(num "$thr")
    used=$(num "$used")
    media=$(num "$media")
    temp=$(num "$temp")
    unsafe=$(num "$unsafe")
    errs=$(num "$errs")
    wt=$(num "$wt")
    ct=$(num "$ct")
    echo "Parsed $dev: crit=${crit:-?} spare=${spare:-?}%/thr=${thr:-?}% used=${used:-?}% media_err=${media:-?} temp=${temp:-?}C unsafe_shutdowns=${unsafe:-?} power_cycles=${pc:-?} errlog=${errs:-?}"
    if [[ -n "$crit" && ! "$crit" =~ ^(0x)?0+$ ]]; then
        finding FAIL storage "$dev: NVMe critical-warning flags $crit (0x01 spare below threshold, 0x02 over-temperature, 0x04 reliability degraded, 0x08 read-only, 0x10 volatile-memory backup failed)."
    fi
    if [[ -n "$spare" && -n "$thr" ]]; then
        if ((spare <= thr)); then
            finding FAIL storage "$dev: available spare ${spare}% is at/below its threshold ${thr}% — the drive is wearing out."
        elif ((spare < 50)); then
            finding WARN storage "$dev: available spare is down to ${spare}%."
        fi
    fi
    if [[ -n "$used" ]]; then
        if ((used >= 100)); then
            finding WARN storage "$dev: ${used}% of rated endurance used — past its warranty life; keep verified backups."
        elif ((used >= 90)); then
            finding WARN storage "$dev: ${used}% of rated endurance used."
        fi
    fi
    if [[ -n "$media" && "$media" -gt 0 ]]; then
        if ((media >= 50)); then
            finding FAIL storage "$dev: $media media/data-integrity errors — the NAND is failing; back up and replace."
        else
            finding WARN storage "$dev: $media media/data-integrity error(s) recorded."
        fi
    fi
    if [[ -n "$temp" ]]; then
        if ((temp >= 80)); then
            finding FAIL storage "$dev: drive temperature is ${temp}°C — near the throttle/shutdown point; fix airflow/heatsink."
        elif ((temp >= 70)); then
            finding WARN storage "$dev: drive temperature is ${temp}°C — likely to throttle under load; check heatsink contact and airflow."
        fi
    fi
    [[ -n "$wt" && "$wt" -gt 0 ]] && finding WARN storage "$dev: has spent ${wt} minute(s) above its warning temperature (thermal throttling happened)."
    [[ -n "$ct" && "$ct" -gt 0 ]] && finding FAIL storage "$dev: has spent ${ct} minute(s) above its CRITICAL temperature."
    if [[ -n "$unsafe" && "$unsafe" -ge 20 ]]; then
        finding INFO storage "$dev: ${unsafe} unsafe shutdowns (power cycles: ${pc:-?}) — power loss/hard resets; not a defect by itself, but it risks filesystem corruption."
    fi
    if [[ -n "$errs" && "$errs" -ge 10 ]]; then
        case "$NVERR_KIND" in
        benign) finding INFO storage "$dev: ${errs} NVMe error-log entries, all 'Invalid Field in Command' — usually harmless (a monitoring tool or smartctl probing unsupported log pages), not a media fault." ;;
        mixed) finding WARN storage "$dev: ${errs} NVMe error-log entries including non-benign status codes — inspect details/NVMe_errors_*.txt." ;;
        *) finding INFO storage "$dev: ${errs} NVMe error-log entries (see NVMe errors section)." ;;
        esac
    fi
}

an_ata_smart() { # dev smartctl-file
    local dev="$1" f="$2" overall rea pend unc crc val temp errc st name
    overall=$(sed -nE 's/^SMART overall-health self-assessment test result: *(.*)$/\1/p; s/^SMART Health Status: *(.*)$/\1/p' "$f" 2>/dev/null | head -1)
    if [[ -n "$overall" && "$overall" != PASSED* && "$overall" != OK* ]]; then
        finding FAIL storage "$dev: SMART overall health = $overall — back up immediately and replace the drive."
    fi
    rea=$(num "$(awk '$2=="Reallocated_Sector_Ct" {print $10; exit}' "$f" 2>/dev/null)")
    pend=$(num "$(awk '$2=="Current_Pending_Sector" {print $10; exit}' "$f" 2>/dev/null)")
    unc=$(num "$(awk '$2=="Offline_Uncorrectable" || $2=="Reported_Uncorrect" {print $10; exit}' "$f" 2>/dev/null)")
    crc=$(num "$(awk '$2=="UDMA_CRC_Error_Count" {print $10; exit}' "$f" 2>/dev/null)")
    temp=$(num "$(awk '$2=="Temperature_Celsius" || $2=="Airflow_Temperature_Cel" || $2=="Temperature_Internal" {print $10; exit}' "$f" 2>/dev/null)")
    echo "Parsed $dev: reallocated=${rea:-n/a} pending=${pend:-n/a} uncorrectable=${unc:-n/a} crc=${crc:-n/a} temp=${temp:-n/a}"
    [[ -n "$rea" && "$rea" -gt 0 ]] && finding WARN storage "$dev: $rea reallocated sector(s) — the surface is degrading; verify backups and watch the count."
    [[ -n "$pend" && "$pend" -gt 0 ]] && finding FAIL storage "$dev: $pend pending (unreadable) sector(s) — data at risk; back up now."
    [[ -n "$unc" && "$unc" -gt 0 ]] && finding FAIL storage "$dev: $unc offline-uncorrectable sector(s) — failing media."
    [[ -n "$crc" && "$crc" -gt 0 ]] && finding WARN storage "$dev: $crc UDMA CRC error(s) — usually a bad/loose SATA cable or port, not the disk itself."
    if [[ -n "$temp" ]]; then
        if ((temp >= 60)); then
            finding WARN storage "$dev: drive temperature ${temp}°C is too high."
        fi
    fi
    # SSD wear gauges report a normalised VALUE (100 = new)
    for name in Wear_Leveling_Count Media_Wearout_Indicator Percent_Lifetime_Remain SSD_Life_Left Remaining_Lifetime_Perc; do
        val=$(num "$(awk -v n="$name" '$2==n {print $4; exit}' "$f" 2>/dev/null)")
        [[ -n "$val" ]] || continue
        if ((val <= 3)); then
            finding FAIL storage "$dev: SSD wear indicator ${name}=${val} — end of life."
        elif ((val <= 10)); then
            finding WARN storage "$dev: SSD wear indicator ${name}=${val} — nearly worn out."
        fi
        break
    done
    errc=$(sed -nE 's/^ATA Error Count: *([0-9]+).*/\1/p' "$f" 2>/dev/null | head -1)
    [[ -n "$errc" && "$errc" -gt 0 ]] && finding WARN storage "$dev: the drive's ATA error log has $errc entr(y/ies)."
    st=$(grep -E 'Completed: (read failure|unknown failure|electrical failure|servo/seek failure|handling damage)|Completed: .*failure' "$f" 2>/dev/null | head -2)
    [[ -n "$st" ]] && finding WARN storage "$dev: a SMART self-test in its log FAILED: $(tr -s ' ' <<<"$st" | tr '\n' ';')"
    local grown
    grown=$(num "$(sed -nE 's/^Elements in grown defect list: *([0-9]+).*/\1/p' "$f" 2>/dev/null | head -1)")
    [[ -n "$grown" && "$grown" -gt 0 ]] && finding WARN storage "$dev: $grown element(s) in the grown defect list."
    return 0
}

for d in ${DISKS[@]+"${DISKS[@]}"}; do
    echo
    echo "--- $d  [${D_MODEL[$d]:-?}  tran=${D_TRAN[$d]:-?}  rota=${D_ROTA[$d]:-?}  size=$((${D_SIZE[$d]:-0} / 1000000000)) GB] ---"
    nv_smart_f=""
    sm_f=""
    if [[ "$d" == /dev/nvme* ]] && have nvme; then
        run_cmd "NVMe SMART $d" 30 ${NVME_SMART_CMD[@]+"${NVME_SMART_CMD[@]}"} "$d"
        nv_smart_f="$LAST_DETAIL"
        run_cmd "NVMe errors $d" 30 ${NVME_ERROR_CMD[@]+"${NVME_ERROR_CMD[@]}"} --log-entries=16 "$d"
        an_nvme_errlog "$LAST_DETAIL" "$d"
        run_cmd "NVMe id-ctrl $d" 20 ${NVME_IDCTRL_CMD[@]+"${NVME_IDCTRL_CMD[@]}"} "$d"
        run_cmd "NVMe fw-log $d" 15 ${NVME_FWLOG_CMD[@]+"${NVME_FWLOG_CMD[@]}"} "$d"
        run_cmd "NVMe self-test-log $d" 15 ${NVME_SELFTEST_CMD[@]+"${NVME_SELFTEST_CMD[@]}"} "$d"
        an_nvme_link "$d"
    fi
    if have smartctl; then
        dtype="${SMART_TYPE[$d]:-}"
        if [[ -z "$dtype" && "$d" == /dev/nvme* ]]; then
            dtype="${SMART_TYPE[${d%n[0-9]*}]:-}"
        fi
        smart_args=()
        [[ -n "$dtype" ]] && smart_args+=(-d "$dtype")
        if run_cmd "SMART -x $d" 30 smartctl -x ${smart_args[@]+"${smart_args[@]}"} "$d"; then
            sm_f="$LAST_DETAIL"
        else
            sm_f="$LAST_DETAIL"
            if [[ "${D_TRAN[$d]:-}" == usb && "$dtype" != "sat" ]]; then
                if run_cmd "SMART -x -d sat $d" 30 smartctl -x -d sat "$d"; then
                    sm_f="$LAST_DETAIL"
                else
                    echo "NOTE: USB bridge of $d does not pass SMART/SAT commands."
                fi
            fi
        fi
        if [[ "$d" == /dev/nvme* ]]; then
            an_nvme_smart "$d" "$sm_f" "$nv_smart_f"
        elif [[ -s "$sm_f" ]] && grep -qE 'SMART overall-health|SMART Health Status|ID# ATTRIBUTE_NAME' "$sm_f"; then
            an_ata_smart "$d" "$sm_f"
        else
            echo "NOTE: no SMART data available for $d (virtual disk, RAID controller or unsupported bridge)."
        fi
    elif [[ "$d" == /dev/nvme* && -n "$nv_smart_f" ]]; then
        an_nvme_smart "$d" "/dev/null" "$nv_smart_f"
    fi
    if have hdparm && [[ "$d" == /dev/sd* && "${D_TRAN[$d]:-}" != usb ]]; then
        run_cmd "hdparm -I $d" 15 hdparm -I "$d"
    fi
done

# ── 19. sensors, thermals, cooling, power ────────────────────────────────────
if have sensors; then
    run_cmd "lm-sensors output" 15 sensors
    run_cmd "lm-sensors JSON" 15 sensors -j
fi

collect_thermals_and_hwmon() {
    local IFS=$'\n\t'
    local tz cdv h f base lbl val human hname c crit warn fail found=0 gt
    echo "--- Thermal zones ---"
    for tz in /sys/class/thermal/thermal_zone*; do
        [[ -f "$tz/temp" ]] || continue
        found=1
        printf '%s (%s): %s°C policy=%s mode=%s\n' "${tz##*/}" "$(cat "$tz/type" 2>/dev/null || echo ?)" \
            "$(awk '{printf "%.1f", $1/1000}' "$tz/temp" 2>/dev/null || echo ?)" \
            "$(cat "$tz/policy" 2>/dev/null || echo n/a)" "$(cat "$tz/mode" 2>/dev/null || echo n/a)"
    done
    ((found)) || echo "(no thermal_zone entries)"

    echo "--- Cooling devices ---"
    found=0
    for cdv in /sys/class/thermal/cooling_device*; do
        [[ -d "$cdv" ]] || continue
        found=1
        printf '%s (%s): state=%s / max=%s\n' "${cdv##*/}" "$(cat "$cdv/type" 2>/dev/null || echo ?)" \
            "$(cat "$cdv/cur_state" 2>/dev/null || echo ?)" "$(cat "$cdv/max_state" 2>/dev/null || echo ?)"
    done
    ((found)) || echo "(no cooling devices)"

    echo "--- hwmon readout (temperatures are checked against safe limits) ---"
    for h in /sys/class/hwmon/hwmon*; do
        [[ -d "$h" ]] || continue
        hname=$(cat "$h/name" 2>/dev/null || echo unknown)
        echo "=== $h ($hname) ==="
        for f in "$h"/{temp*_input,fan*_input,in*_input,power*_input,power*_average,curr*_input,pwm[0-9]}; do
            [[ -r "$f" ]] || continue
            base="${f%_*}"
            lbl=$(cat "${base}_label" 2>/dev/null)
            val=$(cat "$f" 2>/dev/null) || val="?"
            human="$val"
            case "${f##*/}" in
            temp*_input)
                [[ "$val" =~ ^-?[0-9]+$ ]] || continue
                human=$(awk -v v="$val" 'BEGIN{printf "%.1f °C", v/1000}')
                if ((val > -50000 && val < 200000)); then
                    case "$hname" in
                    nvme) warn=80000 fail=90000 ;;
                    drivetemp) warn=60000 fail=70000 ;;
                    *) warn=85000 fail=100000 ;;
                    esac
                    crit=$(cat "${base}_crit" 2>/dev/null)
                    if [[ "$crit" =~ ^[0-9]+$ ]] && ((crit > 20000 && crit < 150000 && val >= crit)); then
                        finding FAIL thermal "$hname (${lbl:-${f##*/}}) = $((val / 1000))°C is at/above its own critical limit ($((crit / 1000))°C)."
                    elif ((val >= fail)); then
                        finding FAIL thermal "$hname (${lbl:-${f##*/}}) = $((val / 1000))°C — dangerously hot; check cooling, thermal paste, fans, dust."
                    elif ((val >= warn)); then
                        finding WARN thermal "$hname (${lbl:-${f##*/}}) = $((val / 1000))°C — hot even at diagnostic time."
                    fi
                fi
                ;;
            in*_input) human=$(awk -v v="$val" 'BEGIN{printf "%.3f V", v/1000}') ;;
            curr*_input) human=$(awk -v v="$val" 'BEGIN{printf "%.3f A", v/1000}') ;;
            power*_input | power*_average) human=$(awk -v v="$val" 'BEGIN{printf "%.2f W", v/1000000}') ;;
            fan*_input) human="${val} RPM" ;;
            esac
            printf '  %-22s %-20s = %s (raw=%s)\n' "${f##*/}" "${lbl:+($lbl)}" "$human" "$val"
        done
    done

    echo "--- Intel/AMD thermal throttle counters ---"
    found=0
    for c in /sys/devices/system/cpu/cpu*/thermal_throttle/{core,package}_throttle_count; do
        [[ -r "$c" ]] || continue
        found=1
        gt=$(cat "$c")
        [[ "${gt:-0}" -gt 0 ]] && echo "$c = $gt"
    done
    ((found)) || echo "(not exposed by this CPU/kernel)"

    echo "--- RAPL / powercap ---"
    found=0
    for c in /sys/class/powercap/*:*; do
        [[ -d "$c" ]] || continue
        found=1
        printf '%s (%s): energy_uj=%s\n' "${c##*/}" "$(cat "$c/name" 2>/dev/null || echo ?)" "$(cat "$c/energy_uj" 2>/dev/null || echo n/a)"
    done
    ((found)) || echo "(no powercap/RAPL entries)"

    if have vcgencmd; then
        echo "--- Raspberry Pi firmware flags ---"
        gt=$(vcgencmd get_throttled 2>/dev/null | sed 's/.*=//')
        echo "get_throttled=$gt"
        if [[ "$gt" =~ ^0x[0-9a-fA-F]+$ ]]; then
            ((gt & 0x50005)) && finding WARN power "Raspberry Pi reports under-voltage/throttling ($gt) — use a proper power supply/cable and improve cooling."
        fi
    fi
    return 0
}
run_fn "Thermals, cooling, hwmon values & powercap" 60 collect_thermals_and_hwmon

if [[ -e /dev/ipmi0 || -e /dev/ipmidev/0 ]] && have ipmitool; then
    run_cmd "IPMI sensors (BMC)" 40 ipmitool sdr elist
    run_cmd "IPMI system event log (last 40)" 40 bash -c 'ipmitool sel elist 2>&1 | tail -40'
fi

collect_power() {
    local IFS=$'\n\t'
    local p t full design health cap lvl cyc status found=0 attr
    for p in /sys/class/power_supply/*; do
        [[ -d "$p" ]] || continue
        echo "=== $p ==="
        for attr in type status present online capacity capacity_level cycle_count health technology \
            energy_full energy_full_design energy_now charge_full charge_full_design voltage_now current_now power_now manufacturer model_name; do
            [[ -r "$p/$attr" ]] && printf '  %-22s: %s\n' "$attr" "$(cat "$p/$attr" 2>/dev/null)"
        done
        t=$(cat "$p/type" 2>/dev/null)
        [[ "$t" == Battery ]] || continue
        [[ "$(cat "$p/scope" 2>/dev/null)" == Device ]] && continue # wireless mouse/headset batteries
        found=1
        full=$(num "$(cat "$p/energy_full" 2>/dev/null || cat "$p/charge_full" 2>/dev/null)")
        design=$(num "$(cat "$p/energy_full_design" 2>/dev/null || cat "$p/charge_full_design" 2>/dev/null)")
        cap=$(num "$(cat "$p/capacity" 2>/dev/null)")
        lvl=$(cat "$p/capacity_level" 2>/dev/null)
        cyc=$(num "$(cat "$p/cycle_count" 2>/dev/null)")
        status=$(cat "$p/status" 2>/dev/null)
        if [[ -n "$full" && -n "$design" && "$design" -gt 0 ]]; then
            health=$((full * 100 / design))
            echo "  => battery health: ${health}% of design capacity (cycles: ${cyc:-n/a}, charge ${cap:-?}%, $status)"
            if ((health < 50)); then
                finding WARN power "Battery ${p##*/} holds only ${health}% of its design capacity — worn out; replace it."
            elif ((health < 80)); then
                finding INFO power "Battery ${p##*/} is at ${health}% of design capacity (${cyc:-?} cycles) — noticeably degraded."
            fi
        fi
        [[ "$lvl" == Critical ]] && finding WARN power "Battery ${p##*/} is at critical charge level."
        [[ "$(cat "$p/health" 2>/dev/null)" =~ ^(Dead|Over\ voltage|Overheat|Cold|Unspecified\ failure)$ ]] &&
            finding WARN power "Battery ${p##*/} health flag: $(cat "$p/health")."
    done
    ((found)) || echo "(no system battery)"
    return 0
}
if [[ $IS_LAPTOP -eq 1 ]] || compgen -G "/sys/class/power_supply/*" >/dev/null; then
    have upower && run_cmd "Battery / AC (upower)" 15 upower -d
    have acpi && run_cmd "ACPI verbose" 15 acpi -V
    run_fn "Power supplies & battery health" 30 collect_power
fi

# ── 20. display / GPU ────────────────────────────────────────────────────────
collect_drm_and_edid() {
    local IFS=$'\n\t'
    local card c e dev f any=0 drvname
    echo "--- DRM cards & telemetry ---"
    for card in /sys/class/drm/card[0-9]; do
        [[ -d "$card" ]] || continue
        dev="$card/device"
        echo "=== ${card##*/} ==="
        drvname=$(basename "$(readlink -f "$dev/driver" 2>/dev/null)" 2>/dev/null)
        [[ -r "$dev/vendor" ]] && echo "  PCI: $(cat "$dev/vendor"):$(cat "$dev/device" 2>/dev/null) driver=${drvname:-none}"
        for f in gpu_busy_percent mem_info_vram_total mem_info_vram_used mem_info_gtt_total mem_info_gtt_used \
            vbios_version power_dpm_state power_dpm_force_performance_level current_link_speed current_link_width; do
            [[ -r "$dev/$f" ]] && echo "  $f: $(cat "$dev/$f" 2>/dev/null)"
        done
    done
    echo "--- DRM connectors ---"
    for c in /sys/class/drm/card*-*; do
        [[ -f "$c/status" ]] && echo "$c: $(cat "$c/status") (enabled=$(cat "$c/enabled" 2>/dev/null || echo ?), dpms=$(cat "$c/dpms" 2>/dev/null || echo ?))"
    done
    echo "--- EDID decode ---"
    for e in /sys/class/drm/card*-*/edid; do
        [[ -s "$e" ]] || continue
        any=1
        echo "=== $e ==="
        if have edid-decode; then
            to 10 edid-decode "$e" 2>&1
        elif have di-edid-decode; then
            to 10 di-edid-decode <"$e" 2>&1
        elif have parse-edid; then
            to 10 parse-edid <"$e" 2>&1
        else
            od -An -tx1 "$e" | head -20
        fi
    done
    ((any)) || echo "(no readable EDID blobs — normal on laptops without external displays or in VMs)"
    return 0
}
run_fn "DRM sysfs, connectors & EDID" 60 collect_drm_and_edid
have drm_info && run_cmd "DRM info (drm_info)" 20 drm_info

if ((GUI_USABLE)); then
    run_session_cmd "OpenGL renderer (session)" 20 glxinfo -B
    run_session_cmd "EGL summary (session)" 20 eglinfo -B
    run_session_cmd "Vulkan summary (session)" 20 vulkaninfo --summary
    run_session_cmd "OpenCL info (session)" 20 clinfo -l
    run_session_cmd "VA-API video acceleration (session)" 20 vainfo
    [[ -n "$DESKTOP_DISPLAY" ]] && run_session_cmd "Xrandr outputs & properties" 15 xrandr --verbose
    run_session_cmd "KDE KScreen outputs" 15 kscreen-doctor -o
    [[ -n "$DESKTOP_WAYLAND" ]] && run_session_cmd "Wayland outputs (wlr-randr)" 15 wlr-randr
else
    section "GUI / GL / Vulkan info"
    echo "Skipped: ${GUI_NOTE:-no usable desktop session}."
    # headless probes still work without a desktop
    have vulkaninfo && run_cmd "Vulkan summary (headless)" 20 vulkaninfo --summary
    have clinfo && run_cmd "OpenCL info (headless)" 20 clinfo -l
    have vainfo && run_cmd "VA-API (headless)" 20 vainfo
fi

an_gpu() {
    local IFS=$'\n\t'
    local out rc modver dev cls addr name
    echo "--- NVIDIA ---"
    if grep -q '^nvidia ' /proc/modules 2>/dev/null; then
        modver=$(cat /sys/module/nvidia/version 2>/dev/null)
        echo "Kernel module version: ${modver:-unknown}"
        cat /proc/driver/nvidia/version 2>/dev/null
        if have nvidia-smi; then
            out=$(to 25 nvidia-smi 2>&1)
            rc=$?
            if grep -qi 'mismatch' <<<"$out"; then
                finding FAIL gpu "NVIDIA kernel module (${modver:-?}) and user-space libraries have different versions — the driver was upgraded without a reboot (or a stale module is loaded). Reboot; if it persists, reinstall the nvidia packages for this kernel."
            elif ((rc != 0)); then
                finding WARN gpu "nvidia-smi failed (exit $rc) while the nvidia module is loaded: $(head -1 <<<"$out")"
            else
                head -25 <<<"$out"
                to 20 nvidia-smi --query-gpu=name,driver_version,temperature.gpu,power.draw,pcie.link.gen.current,pcie.link.gen.max,pcie.link.width.current,pcie.link.width.max --format=csv 2>&1
            fi
        else
            echo "nvidia-smi not installed."
        fi
    else
        echo "(nvidia kernel module not loaded)"
    fi
    if grep -q 'NVRM: API mismatch' "$KLOG_FILE" 2>/dev/null; then
        echo "--- NVRM API mismatch details ---"
        grep -A3 'NVRM: API mismatch' "$KLOG_FILE" | head -12
        finding FAIL gpu "Kernel log contains 'NVRM: API mismatch' — NVIDIA module/library version mismatch; reboot."
    fi

    echo "--- devices without a bound kernel driver ---"
    for dev in /sys/bus/pci/devices/*; do
        cls=$(cat "$dev/class" 2>/dev/null)
        cls="${cls#0x}"
        [[ -e "$dev/driver" ]] && continue
        addr="${dev##*/}"
        name=$(lspci -s "$addr" 2>/dev/null | cut -d' ' -f2-)
        case "${cls:0:2}" in
        03) finding WARN gpu "Display controller $addr ($name) has no kernel driver bound — missing/blacklisted/failed driver, so no acceleration (or no display at all)." ;;
        02) finding WARN network "Network controller $addr ($name) has no kernel driver bound — missing driver or firmware." ;;
        01)
            [[ "${cls:0:4}" == 0108 || "${cls:0:4}" == 0106 || "${cls:0:4}" == 0104 ]] &&
                finding WARN storage "Storage controller $addr ($name) has no kernel driver bound — disks behind it are invisible."
            ;;
        04) [[ "${cls:0:4}" == 0403 ]] && finding INFO audio "Audio controller $addr ($name) has no kernel driver bound — no sound (check SOF/firmware packages)." ;;
        0c) [[ "${cls:0:4}" == 0c03 ]] && finding INFO usb "USB controller $addr ($name) has no kernel driver bound." ;;
        esac
    done
    return 0
}
run_fn "Analysis: GPU drivers & unbound devices" 60 an_gpu
if grep -q '^nvidia ' /proc/modules 2>/dev/null && have nvidia-smi; then
    run_cmd "NVIDIA full query (nvidia-smi -q)" 40 nvidia-smi -q
fi

# ── 21. audio, input, camera ─────────────────────────────────────────────────
run_cmd "ALSA playback & capture" 15 bash -c 'aplay -l 2>/dev/null; echo "---"; arecord -l 2>/dev/null; true'
run_cmd "ALSA proc cards & codecs" 10 bash -c '
    cat /proc/asound/cards 2>/dev/null || echo "no /proc/asound/cards"
    echo "--- /proc/asound/pcm ---"
    cat /proc/asound/pcm 2>/dev/null
    for c in /proc/asound/card*/codec#*; do
        [[ -r "$c" ]] && { echo "=== $c ==="; head -35 "$c"; }
    done; true'
if have alsa-info.sh; then
    run_cmd "ALSA info dump" 40 bash -c '
        alsa-info.sh --no-upload --output "$1" 2>&1
        [[ -s "$1" ]] && echo "Saved to $1 ($(stat -c%s "$1") bytes)"; true' _ "$DETAILS/alsa-info.txt"
fi
if [[ -n "$DESKTOP_USER" ]]; then
    run_session_cmd "PipeWire / WirePlumber status" 15 wpctl status
    run_session_cmd "PulseAudio/PipeWire sinks & cards" 15 pactl list short sinks
fi

run_cmd "libinput devices" 20 libinput list-devices
run_cmd "Input devices (/proc)" 10 cat /proc/bus/input/devices
if have evtest; then
    run_cmd "Input capabilities (evtest, 2s per device)" 60 bash -c '
        for e in /dev/input/event*; do
            [[ -e "$e" ]] || continue
            echo "=== $e ==="
            timeout 2 evtest "$e" </dev/null 2>&1 | head -20
        done; true'
fi
if have v4l2-ctl && compgen -G "/dev/video*" >/dev/null; then
    run_cmd "V4L2 camera devices" 20 bash -c '
        v4l2-ctl --list-devices 2>&1
        for c in /dev/video*; do echo "=== $c ==="; v4l2-ctl -d "$c" --all 2>&1 | head -40; done; true'
fi

# ── 22. network ──────────────────────────────────────────────────────────────
run_cmd "Network interfaces" 20 ip -details link show
run_cmd "IP addresses & routes" 10 bash -c '
    ip -br addr show
    echo "--- Routes ---"
    ip route show table all 2>/dev/null || ip route show'
run_cmd "Per-interface statistics" 15 ip -s link show
run_cmd "Listening sockets" 10 bash -c 'ss -tulpn 2>/dev/null || netstat -tulpn 2>/dev/null; true'
run_cmd "NIC details (ethtool)" 40 bash -c '
    for i in /sys/class/net/*; do
        n="${i##*/}"; [[ "$n" == lo || ! -e "$i/device" ]] && continue
        echo "=== $n ==="; ethtool "$n" 2>/dev/null; ethtool -i "$n" 2>/dev/null; ethtool -S "$n" 2>/dev/null | head -40
    done; true'
run_cmd "Wireless (iw) & regulatory" 20 bash -c 'iw reg get 2>/dev/null; echo "---"; iw dev 2>/dev/null; true'
run_cmd "Wireless PHY capabilities" 20 bash -c 'iw list 2>/dev/null | head -120; true'
run_cmd "RFKill" 10 rfkill list
run_cmd "Bluetooth controllers & devices" 20 bash -c '
    bluetoothctl list 2>/dev/null; echo "---"; bluetoothctl show 2>/dev/null; echo "---"; bluetoothctl devices 2>/dev/null; true'
have nmcli && run_cmd "NetworkManager status" 15 bash -c 'nmcli general status 2>/dev/null; echo "---"; nmcli device status 2>/dev/null; true'
have resolvectl && run_cmd "DNS / systemd-resolved" 10 resolvectl status

an_network() {
    local IFS=$'\n\t'
    local ifp ifn oper carrier speed duplex rxe txe rxd txd crc sig gw out loss wired up_phys=0
    echo "--- physical interfaces ---"
    for ifp in /sys/class/net/*; do
        ifn="${ifp##*/}"
        [[ "$ifn" == lo || ! -e "$ifp/device" ]] && continue
        oper=$(cat "$ifp/operstate" 2>/dev/null)
        carrier=$(cat "$ifp/carrier" 2>/dev/null)
        speed=$(cat "$ifp/speed" 2>/dev/null)
        duplex=$(cat "$ifp/duplex" 2>/dev/null)
        rxe=$(num "$(cat "$ifp/statistics/rx_errors" 2>/dev/null)")
        txe=$(num "$(cat "$ifp/statistics/tx_errors" 2>/dev/null)")
        rxd=$(num "$(cat "$ifp/statistics/rx_dropped" 2>/dev/null)")
        txd=$(num "$(cat "$ifp/statistics/tx_dropped" 2>/dev/null)")
        crc=$(num "$(cat "$ifp/statistics/rx_crc_errors" 2>/dev/null)")
        wired=1
        [[ -d "$ifp/wireless" || -d "$ifp/phy80211" ]] && wired=0
        printf '%-12s state=%s carrier=%s speed=%s duplex=%s wired=%s rx_err=%s tx_err=%s rx_drop=%s tx_drop=%s crc=%s\n' \
            "$ifn" "$oper" "${carrier:-?}" "${speed:-?}" "${duplex:-?}" "$wired" "${rxe:-0}" "${txe:-0}" "${rxd:-0}" "${txd:-0}" "${crc:-0}"
        [[ "$oper" == up ]] && up_phys=1
        [[ "${crc:-0}" -gt 0 ]] && finding WARN network "$ifn has $crc receive CRC errors — bad cable, connector or switch port."
        if (((${rxe:-0} + ${txe:-0}) > 100)); then
            finding INFO network "$ifn has ${rxe:-0} rx / ${txe:-0} tx errors since boot."
        fi
        if ((wired == 1)) && [[ "$carrier" == 1 && "$speed" =~ ^[0-9]+$ ]]; then
            if ((speed > 0 && speed <= 100)) && have ethtool && ethtool "$ifn" 2>/dev/null | grep -q '1000baseT'; then
                finding WARN network "$ifn linked at ${speed} Mb/s although it supports gigabit — damaged/Cat5 cable, bad port, or a 100M switch."
            fi
            [[ "$duplex" == half ]] && finding WARN network "$ifn negotiated HALF duplex — duplex mismatch/cable fault."
        fi
        if ((wired == 0)) && [[ "$oper" == up ]] && have iw; then
            sig=$(to 10 iw dev "$ifn" link 2>/dev/null | sed -nE 's/.*signal: *(-?[0-9]+) dBm.*/\1/p' | head -1)
            if [[ -n "$sig" ]]; then
                echo "  Wi-Fi signal on $ifn: ${sig} dBm"
                ((sig <= -75)) && finding INFO network "Wi-Fi signal on $ifn is weak (${sig} dBm) — move closer or use a better antenna/AP position."
            fi
        fi
    done

    echo "--- rfkill ---"
    if have rfkill; then
        while IFS=' ' read -r _ typ dev soft hard; do
            [[ -n "$typ" ]] || continue
            echo "$typ $dev soft=$soft hard=$hard"
            [[ "$hard" == blocked ]] && finding WARN network "$typ radio ($dev) is HARD-blocked — physical switch/Fn key or firmware setting."
            [[ "$soft" == blocked ]] && finding INFO network "$typ radio ($dev) is soft-blocked (rfkill unblock $typ to enable)."
        done < <(to 5 rfkill -n -o ID,TYPE,DEVICE,SOFT,HARD 2>/dev/null)
    fi

    echo "--- connectivity ---"
    gw=$(ip route show default 2>/dev/null | awk '{print $3; exit}')
    if [[ -z "$gw" ]]; then
        ((up_phys)) && finding INFO network "A network link is up but there is no default route (no DHCP lease / gateway)."
        echo "(no default route)"
    else
        echo "default gateway: $gw"
        if have ping; then
            out=$(to 15 ping -c 4 -W 2 -q "$gw" 2>&1)
            loss=$(sed -nE 's/.* ([0-9.]+)% packet loss.*/\1/p' <<<"$out" | head -1)
            echo "$out" | tail -3
            if [[ -n "$loss" ]]; then
                if awk -v l="$loss" 'BEGIN{exit !(l >= 50)}'; then
                    finding FAIL network "Gateway $gw: ${loss}% packet loss — the local link (cable/Wi-Fi/router) is failing."
                elif awk -v l="$loss" 'BEGIN{exit !(l > 0)}'; then
                    finding WARN network "Gateway $gw: ${loss}% packet loss — flaky local link (Wi-Fi interference, cable, driver)."
                fi
            fi
        fi
        if timeout 4 bash -c 'exec 3<>/dev/tcp/1.1.1.1/443' 2>/dev/null; then
            echo "internet route: OK (TCP 1.1.1.1:443)"
            if ! to 8 getent hosts example.com &>/dev/null; then
                finding WARN network "Internet works by IP but DNS lookups fail — check resolver config (systemd-resolved/NetworkManager/resolv.conf)."
            fi
        else
            echo "internet route: unreachable (TCP 1.1.1.1:443)"
            finding INFO network "Gateway answers but 1.1.1.1:443 is unreachable — upstream outage, captive portal or firewall."
        fi
    fi
    return 0
}
run_fn "Analysis: network links, errors, connectivity" 90 an_network

# ── 23. misc buses (IIO, Thunderbolt, Type-C, I2C, serial, RTC...) ───────────
collect_misc_buses() {
    local IFS=$'\n\t'
    local d found=0 tb_out
    echo "--- IIO sensors ---"
    for d in /sys/bus/iio/devices/iio:device*; do
        found=1
        echo "=== $d ($(cat "$d/name" 2>/dev/null || echo ?)) ==="
        ls "$d"
    done
    ((found)) || echo "(none)"
    echo "--- Thunderbolt / USB4 ---"
    tb_out=$(to 10 boltctl list 2>/dev/null)
    if [[ -n "$tb_out" ]]; then
        echo "$tb_out"
    elif compgen -G "/sys/bus/thunderbolt/devices/*" >/dev/null; then
        ls -la /sys/bus/thunderbolt/devices/
    else
        echo "(none)"
    fi
    echo "--- USB Type-C / PD ports ---"
    found=0
    for d in /sys/class/typec/*; do
        found=1
        echo "=== ${d##*/} ==="
        cat "$d"/{data_role,power_role,power_operation_mode,usb_typec_revision,usb_power_delivery_revision} 2>/dev/null
    done
    ((found)) || echo "(none)"
    echo "--- I2C / SMBus adapters ---"
    if have i2cdetect; then to 10 i2cdetect -l 2>/dev/null || echo "(none)"; else echo "(i2cdetect unavailable)"; fi
    echo "--- watchdog / RTC / serial ---"
    local wds=(/dev/watchdog*) rtcs=(/dev/rtc*) sers=(/dev/ttyS* /dev/ttyUSB* /dev/ttyACM* /dev/serial/by-id/*)
    ((${#wds[@]})) && ls -l ${wds[@]+"${wds[@]}"} || echo "watchdog: (none)"
    ((${#rtcs[@]})) && ls -l ${rtcs[@]+"${rtcs[@]}"} || echo "rtc: (none)"
    ((${#sers[@]})) && ls -l ${sers[@]+"${sers[@]}"} || echo "serial: (none)"
    return 0
}
run_fn "IIO, Thunderbolt, Type-C, I2C, serial & RTC" 60 collect_misc_buses

run_cmd "ACPI table list & dump" 40 bash -c '
    ls -l /sys/firmware/acpi/tables/ 2>/dev/null || echo "no sysfs ACPI tables"
    if command -v acpidump &>/dev/null; then
        if acpidump >"$1" 2>/dev/null; then echo "ACPI tables dumped to $1 ($(stat -c%s "$1") bytes)"; else echo "acpidump failed"; fi
    else echo "acpidump not installed"; fi' _ "$ACPI_DIR/acpidump.dat"

# ── 24. kernel modules, DKMS, packages ───────────────────────────────────────
run_cmd "Loaded kernel modules" 10 lsmod

an_kernel_pkgs() {
    local IFS=$'\n\t'
    local dk mods m cur bad
    echo "--- kernel packages ---"
    case "$PM" in
    pacman) pacman -Q 2>/dev/null | grep -E '^linux([0-9a-z-]*) ' | head -25 ;;
    apt) dpkg -l 2>/dev/null | awk '/^ii +linux-(image|headers)/ {print $2, $3}' | head -25 ;;
    dnf | yum) rpm -q kernel kernel-core 2>/dev/null | head -10 ;;
    zypper) rpm -q kernel-default 2>/dev/null | head -10 ;;
    esac
    if [[ -d "/lib/modules/$KVER" || -d "/usr/lib/modules/$KVER" ]]; then
        echo "Module tree for running kernel $KVER: present."
    else
        echo "WARNING: no module tree for running kernel $KVER (kernel upgraded without reboot?)."
    fi
    if have dkms; then
        echo "--- DKMS ---"
        dk=$(to 30 dkms status 2>&1)
        echo "$dk"
        if [[ -n "$dk" ]]; then
            mods=$(grep -E '^[A-Za-z0-9_.+-]+[/,]' <<<"$dk" | sed -E 's#[/,].*##' | sort -u)
            for m in $mods; do
                cur=$(grep -E "^${m}[/,]" <<<"$dk" | grep -F -- "$KVER")
                if [[ -z "$cur" ]]; then
                    finding WARN kernel "DKMS module '$m' is not built for the running kernel $KVER — it will not load (GPU/VirtualBox/Wi-Fi drivers). Reboot into the kernel it was built for, or run 'dkms autoinstall'."
                elif ! grep -q ': installed' <<<"$cur"; then
                    bad=$(tr -s ' ' <<<"$cur" | head -1)
                    finding WARN kernel "DKMS module '$m' failed/incomplete for $KVER: $bad"
                fi
            done
        fi
    fi
    echo "--- package database / file integrity ---"
    case "$PM" in
    pacman)
        local -a core
        mapfile -t core < <(pacman -Qq 2>/dev/null | grep -E '^(linux|amd-ucode|intel-ucode|nvidia|mesa|systemd|mkinitcpio|dracut|glibc|filesystem)')
        if ((${#core[@]})); then
            LC_ALL=C to 120 pacman -Qk ${core[@]+"${core[@]}"} 2>/dev/null | grep -v ' 0 missing files' || echo "(all checked core packages intact)"
        fi
        bad=$(find /etc /boot -xdev \( -name '*.pacnew' -o -name '*.pacsave' \) 2>/dev/null | head -20)
        if [[ -n "$bad" ]]; then
            echo "$bad"
            finding INFO packages "$(wc -l <<<"$bad") unmerged .pacnew/.pacsave file(s) in /etc or /boot (use pacdiff) — stale configs after upgrades cause odd breakage."
        fi
        ;;
    apt)
        bad=$(to 60 dpkg --audit 2>&1)
        [[ -n "$bad" ]] && {
            echo "$bad"
            finding WARN packages "dpkg reports half-installed/unconfigured packages — run 'dpkg --configure -a' and 'apt-get -f install'."
        }
        to 60 apt-get check 2>&1 | tail -3
        ;;
    dnf | yum)
        to 120 rpm -V kernel-core 2>&1 | head -10
        ;;
    zypper) to 60 zypper --non-interactive verify --dry-run 2>&1 | tail -5 ;;
    esac
    echo "--- modprobe options audit ---"
    local mp_f mp_line mp_mod mp_rest mp_token mp_p
    for mp_f in /etc/modprobe.d/*.conf /run/modprobe.d/*.conf /usr/lib/modprobe.d/*.conf; do
        [[ -r "$mp_f" ]] || continue
        while IFS= read -r mp_line; do
            [[ "$mp_line" =~ ^[[:space:]]*options[[:space:]]+([A-Za-z0-9_]+)[[:space:]]+(.*) ]] || continue
            mp_mod="${BASH_REMATCH[1]}"
            mp_rest="${BASH_REMATCH[2]}"
            [[ -d "/sys/module/$mp_mod" ]] || continue
            for mp_token in $mp_rest; do
                if [[ "$mp_token" =~ ^([A-Za-z0-9_]+)= ]]; then
                    mp_p="${BASH_REMATCH[1]}"
                    if [[ ! -e "/sys/module/$mp_mod/parameters/$mp_p" ]]; then
                        finding WARN modules "module $mp_mod: unknown parameter '$mp_p' in $mp_f (silently ignored by the kernel)"
                    fi
                fi
            done
        done <"$mp_f"
    done
    return 0
}
run_fn "Kernel packages, DKMS & package integrity" 240 an_kernel_pkgs

run_cmd "Interrupts (top 60)" 10 bash -c 'head -60 /proc/interrupts'
run_cmd "I/O memory map (top 60)" 10 bash -c 'head -60 /proc/iomem'
run_cmd "I/O ports (top 60)" 10 bash -c 'head -60 /proc/ioports'
run_cmd "Installed packages snapshot" 60 bash -c '
    case "$PM" in
    pacman) pacman -Q >"$1" 2>/dev/null; pacman -Qm >"$2" 2>/dev/null ;;
    apt) dpkg-query -W -f="\${Package} \${Version}\n" >"$1" 2>/dev/null; : >"$2" ;;
    dnf | yum | zypper) rpm -qa --qf "%{NAME} %{VERSION}-%{RELEASE}\n" | sort >"$1" 2>/dev/null; : >"$2" ;;
    *) : >"$1"; : >"$2" ;;
    esac
    echo "Package manager: ${PM:-none}"
    echo "Total installed packages: $(wc -l <"$1")"
    echo "Foreign/AUR packages:     $(wc -l <"$2")"
    echo "Saved lists to $1 and $2"' _ "$DETAILS/packages-all.txt" "$DETAILS/packages-foreign.txt"

# ── 25. kernel, journal, Xorg & package-manager log analysis ─────────────────
an_logs() {
    local IFS=$'
	'
    local kf="${1:-$KLOG_FILE}"
    [[ -r "$kf" ]] || return 0
    echo "--- kernel log analysis ($kf) ---"

    # 1. Hardware / MCE errors
    if grep -qiE 'mce:.*Hardware Error|Machine Check Exception|mce: \[Hardware Error\]' "$kf"; then
        finding FAIL kernel "Hardware error (MCE) detected in kernel log — potential CPU, memory or bus defect."
    fi

    # 2. PCIe AER uncorrected / fatal
    if grep -qiE 'AER:.*(Uncorrected|Fatal)' "$kf"; then
        finding FAIL pcie "PCIe AER Uncorrected/Fatal error in kernel log — hardware device or PCIe link failure."
    fi

    # 3. OOM killer
    if grep -qiE 'Out of memory: Killed process|invoked oom-killer' "$kf"; then
        finding WARN memory "OOM killer invoked in kernel log — system exhausted available RAM/swap."
    fi

    # 4. Filesystem remount-ro
    if grep -qiE 'remounting filesystem read-only|EXT4-fs.*error.*remounting|BTRFS.*error.*forced readonly|XFS.*Filesystem.*shut down' "$kf"; then
        finding FAIL storage "Filesystem forced to READ-ONLY by kernel after disk I/O or metadata errors."
    fi

    # 5. Hung task / soft lockup
    if grep -qiE 'blocked for more than.*seconds|soft lockup - CPU#[0-9]+ stuck|watchdog: BUG: soft lockup' "$kf"; then
        finding WARN kernel "Kernel hung task / soft lockup detected — task stalled or CPU core lockup."
    fi

    # 6. USB disconnects of storage devices
    local usb_disc
    usb_disc=$(grep -c -iE 'usb.*disconnect' "$kf" 2>/dev/null || true)
    usb_disc=$(num "$usb_disc")
    usb_disc=${usb_disc:-0}
    if ((usb_disc >= 3)); then
        finding INFO usb "Multiple USB disconnect events ($usb_disc) detected in kernel log (loose cable, power drop or failing device)."
    fi

    # 7. Thermal critical
    if grep -qiE 'critical temperature reached|thermal.*critical|overheat|Package temperature above threshold' "$kf"; then
        finding FAIL thermal "Critical temperature reached in kernel log — hardware throttling or safety shutdown triggered."
    fi

    # 8. Failed to load firmware
    local fw_cnt
    fw_cnt=$(grep -c -iE 'failed to load (firmware|direct-loading firmware)' "$kf" 2>/dev/null || true)
    fw_cnt=$(num "$fw_cnt")
    fw_cnt=${fw_cnt:-0}
    if ((fw_cnt >= 2)); then
        finding WARN firmware "Repeated ($fw_cnt) 'failed to load firmware' messages in kernel log (missing firmware package?)."
    elif ((fw_cnt == 1)); then
        finding INFO firmware "Firmware load failure detected in kernel log."
    fi
    return 0
}

run_cmd "dmesg err/warn" 15 bash -c '
    if dmesg --level=err,warn,crit,alert,emerg >/dev/null 2>&1; then
        dmesg --level=err,warn,crit,alert,emerg
    else
        dmesg | grep -iE "error|warn|crit|alert|emerg"
    fi'
run_cmd "dmesg full save" 30 bash -c '
    { dmesg -T 2>/dev/null || dmesg 2>/dev/null; } > "$1"
    echo "saved: $1 ($(wc -l < "$1") lines)"' _ "$DETAILS/dmesg-full.txt"
run_cmd "ACPI / BIOS log issues" 15 bash -c 'grep -iE "acpi|bios" "$KLOG_FILE" | grep -iE "error|fail|bug|warn|ae_" | head -60 || echo "none"'
run_cmd "PCIe / AER log issues" 15 bash -c 'grep -iE "pcie|aer|pci" "$KLOG_FILE" | grep -iE "error|fail|corrected|uncorrected|timeout" | head -60 || echo "none"'
run_cmd "Storage / Block log issues" 15 bash -c 'grep -iE "nvme|ahci|ata[0-9]|scsi|blk_update_request|i/o error|btrfs|ext4|xfs" "$KLOG_FILE" | grep -iE "error|fail|reset|timeout|corrupt|read-only|bad" | head -60 || echo "none"'
run_cmd "USB log issues" 15 bash -c 'grep -iE "usb.*(reset|disconnect|over-current|error|unable to enumerate|not accepting)" "$KLOG_FILE" | head -60 || echo "none"'
run_cmd "GPU / DRM / NVRM log issues" 15 bash -c 'grep -iE "drm|amdgpu|i915|xe|nouveau|nvrm|nvidia" "$KLOG_FILE" | grep -iE "error|fail|mismatch|hang|reset|timeout|ring|fault" | head -60 || echo "none"'
run_cmd "Network / WiFi / BT log issues" 15 bash -c 'grep -iE "r8169|iwlwifi|mt79|ath|rtw|btusb|bluetooth|firmware" "$KLOG_FILE" | grep -iE "error|fail|timeout|reset|crash" | head -60 || echo "none"'
run_cmd "Thermal / throttle log" 15 bash -c 'grep -iE "thermal|throttl|critical temperature|overheat" "$KLOG_FILE" | head -60 || echo "none"'
run_cmd "EDAC / MCE / RAS" 20 bash -c '
    if have ras-mc-ctl; then
        if ras-mc-ctl --help 2>&1 | grep -q -- "--status"; then
            ras-mc-ctl --status 2>&1 || true
            ras-mc-ctl --errors 2>&1 || true
            ras-mc-ctl --summary 2>&1 || true
        elif ras-mc-ctl --help 2>&1 | grep -q "database"; then
            ras-mc-ctl dimm --status 2>&1 || true
            if [[ -r /var/lib/rasdaemon/ras-mc_event.db ]]; then
                ras-mc-ctl database --summary 2>&1 || true
                ras-mc-ctl database --errors 2>&1 || true
            else
                echo "(rasdaemon database not present)"
            fi
        else
            ras-mc-ctl --help 2>&1 | head -30 || true
        fi
    else
        echo "(ras-mc-ctl not installed)"
    fi
    echo "--- /sys/devices/system/edac ---"
    grep -H . /sys/devices/system/edac/mc/mc*/*_count 2>/dev/null || echo "(no EDAC mc sysfs counters)"
    echo "--- dmesg MCE / Hardware Error ---"
    grep -iE "mce|machine check|edac|hardware error" "$KLOG_FILE" || echo "none"'

run_fn "Analysis: kernel log" 120 an_logs

run_cmd "Journal boot list" 15 journalctl --list-boots --no-pager
run_cmd "Journal full save" 60 bash -c '
    journalctl -b --no-pager > "$1"
    echo "saved: $1 ($(wc -l < "$1") lines)"' _ "$DETAILS/journal-boot.txt"
run_cmd "Journal errors (current boot, ranked)" 30 bash -c '
    journalctl -b -p 0..3 --no-pager > "$1"
    echo "Total priority 0..3 lines: $(wc -l < "$1")"
    echo "--- Top 120 deduplicated error patterns ---"
    sort "$1" | uniq -c | sort -rn | head -n 120 | tee "$2"' _ "$DETAILS/journal-boot-errors.txt" "$DETAILS/journal-boot-errors-ranked.txt"
run_cmd "Journal errors (previous boot, ranked)" 30 bash -c '
    journalctl -b -1 -p 0..3 --no-pager > "$1" 2>/dev/null || true
    if [[ -s "$1" ]]; then
        echo "Total prev-boot priority 0..3 lines: $(wc -l < "$1")"
        echo "--- Top 120 deduplicated error patterns ---"
        sort "$1" | uniq -c | sort -rn | head -n 120 | tee "$2"
    else
        echo "(no previous boot journal or no errors)"
    fi' _ "$DETAILS/journal-prev-boot-errors.txt" "$DETAILS/journal-prev-boot-errors-ranked.txt"

run_cmd "Xorg log highlights" 15 bash -c '
    for xl in /var/log/Xorg*.log /home/*/.local/share/xorg/Xorg*.log; do
        [[ -r "$xl" ]] || continue
        echo "=== $xl (EE/WW) ==="
        head -n 5000 "$xl" | grep -E "\((EE|WW)\)" | head -n 200 || true
    done'

run_cmd "Package manager log highlights" 15 bash -c '
    case "$PM" in
    pacman)
        if [[ -r /var/log/pacman.log ]]; then
            echo "=== Recent /var/log/pacman.log warnings/errors/pacnew ==="
            grep -iE "warning|error|pacnew|pacsave" /var/log/pacman.log 2>/dev/null | tail -30 || true
        fi
        ;;
    apt)
        if [[ -r /var/log/apt/history.log ]]; then
            echo "=== Recent /var/log/apt/history.log errors ==="
            tail -100 /var/log/apt/history.log 2>/dev/null | grep -iE "error|fail" | tail -30 || true
        fi
        if [[ -r /var/log/dpkg.log ]]; then
            echo "=== Recent /var/log/dpkg.log errors ==="
            tail -100 /var/log/dpkg.log 2>/dev/null | grep -iE "error|fail" | tail -30 || true
        fi
        ;;
    dnf | yum)
        for log in /var/log/dnf.log /var/log/yum.log; do
            if [[ -r "$log" ]]; then
                echo "=== Recent $log errors ==="
                tail -100 "$log" 2>/dev/null | grep -iE "error|fail" | tail -30 || true
            fi
        done
        ;;
    zypper)
        if [[ -r /var/log/zypp/history ]]; then
            echo "=== Recent /var/log/zypp/history errors ==="
            tail -100 /var/log/zypp/history 2>/dev/null | grep -iE "error|fail" | tail -30 || true
        fi
        ;;
    esac'

# ── 26. offline installed-root analysis ──────────────────────────────────────
for MNT in /mnt /target /run/media/*/* /media/*; do
    [[ -d "$MNT" && -f "$MNT/etc/os-release" && "$MNT" != "/" ]] || continue
    section "Offline installed system ($MNT)"
    if [[ -d "$MNT/var/log/journal" ]]; then
        run_cmd "Offline journal ($MNT)" 30 journalctl -D "$MNT/var/log/journal" -b -p 0..3 --no-pager
    fi
    case "$PM" in
    pacman)
        [[ -r "$MNT/var/log/pacman.log" ]] && run_cmd "Offline pacman.log tail ($MNT)" 10 tail -40 "$MNT/var/log/pacman.log"
        ;;
    apt)
        [[ -r "$MNT/var/log/dpkg.log" ]] && run_cmd "Offline dpkg.log tail ($MNT)" 10 tail -40 "$MNT/var/log/dpkg.log"
        ;;
    dnf | yum)
        [[ -r "$MNT/var/log/dnf.log" ]] && run_cmd "Offline dnf.log tail ($MNT)" 10 tail -40 "$MNT/var/log/dnf.log"
        ;;
    zypper)
        [[ -r "$MNT/var/log/zypp/history" ]] && run_cmd "Offline zypp history ($MNT)" 10 tail -40 "$MNT/var/log/zypp/history"
        ;;
    esac
done

# ── 27. non-destructive stress tests ─────────────────────────────────────────
section "Non-destructive stress tests"
if ((QUICK || NO_STRESS)); then
    echo "Skipped (--quick / --no-stress)."
else
    _LAST_TEMP_PID=0
    _STRESS_GUARD_SENTINEL="$TMPDIR/stress_abort_sentinel"

    an_logs_delta() {
        local kf="$1"
        [[ -s "$kf" ]] || return 0
        if grep -qiE 'mce:.*Hardware Error|Machine Check Exception' "$kf"; then
            finding FAIL stress "MCE / hardware error occurred during stress testing!"
        fi
        if grep -qiE 'AER:.*(Uncorrected|Fatal)' "$kf"; then
            finding FAIL stress "PCIe AER uncorrected error occurred during stress testing!"
        fi
        if grep -qiE 'critical temperature reached|thermal.*critical|overheat' "$kf"; then
            finding FAIL thermal "Thermal critical event triggered during stress testing!"
        fi
        if grep -qiE 'remounting filesystem read-only' "$kf"; then
            finding FAIL stress "Filesystem remounted read-only during stress testing!"
        fi
        if grep -qiE 'blocked for more than.*seconds|soft lockup' "$kf"; then
            finding FAIL stress "Kernel stall / soft lockup occurred during stress testing!"
        fi
    }

    start_temp_guard() {
        local name="$1" target_pid="$2"
        rm -f "$_STRESS_GUARD_SENTINEL"
        (
            while :; do
                local cur_t="" max_t=0 hottest_sensor=""
                echo "[$(date +%T)] $name:" >>"$TEMP_LOG"
                if have sensors; then
                    local s_out
                    s_out=$(sensors 2>/dev/null || true)
                    if [[ -n "$s_out" ]]; then
                        grep -iE 'Tctl|Tdie|Tccd|Package|Core|Composite|edge|junction|temp1' <<<"$s_out" >>"$TEMP_LOG" || true
                        # sensors can print "+NN.N°C" or "+NN.N C"; accept both
                        while IFS= read -r s_line; do
                            if [[ "$s_line" =~ :[[:space:]]*\+?([0-9]+(\.[0-9]+)?)[[:space:]]*°?[[:space:]]*C ]]; then
                                cur_t="${BASH_REMATCH[1]}"
                                cur_t_int="${cur_t%%.*}"
                                if ((cur_t_int > max_t)); then
                                    max_t=$cur_t_int
                                    hottest_sensor="${s_line%%:*}"
                                fi
                            fi
                        done <<<"$s_out"
                    fi
                else
                    for tz in /sys/class/thermal/thermal_zone*; do
                        [[ -f "$tz/temp" ]] || continue
                        local tz_type tz_raw tz_c tz_int
                        tz_type=$(cat "$tz/type" 2>/dev/null || echo "zone")
                        tz_raw=$(cat "$tz/temp" 2>/dev/null || echo 0)
                        tz_c=$(awk -v r="$tz_raw" 'BEGIN{printf "%.1f", r/1000}')
                        tz_int=$((tz_raw / 1000))
                        printf '  %s: %s°C\n' "$tz_type" "$tz_c" >>"$TEMP_LOG"
                        if ((tz_int > max_t)); then
                            max_t=$tz_int
                            hottest_sensor="$tz_type"
                        fi
                    done
                fi

                if ((max_t >= TEMP_ABORT)); then
                    echo "$hottest_sensor|$max_t" >"$_STRESS_GUARD_SENTINEL"
                    if [[ -n "$target_pid" && "$target_pid" -gt 0 ]]; then
                        kill -TERM "$target_pid" 2>/dev/null || true
                    fi
                    break
                fi
                sleep 2
            done
        ) &
        _LAST_TEMP_PID=$!
        BG_PIDS+=("$_LAST_TEMP_PID")
    }

    stop_temp_guard() {
        local lpid="$1"
        if [[ -n "$lpid" && "$lpid" -gt 0 ]]; then
            kill "$lpid" 2>/dev/null || true
            wait "$lpid" 2>/dev/null || true
        fi
    }

    stress_run() {
        local tmo="$1"
        shift
        local name="$1"
        shift
        local runner="$1"
        shift
        local outer_tmo=$((tmo + 15))
        section "STRESS TEST: $name (${tmo}s)"
        set_detail "stress_${name}"

        local stress_pid=""
        if [[ "$runner" == "session" ]]; then
            run_in_session timeout "$tmo" "$@" </dev/null >>"$LAST_DETAIL" 2>&1 &
            stress_pid=$!
        else
            timeout "$tmo" "$@" </dev/null >>"$LAST_DETAIL" 2>&1 &
            stress_pid=$!
        fi

        start_temp_guard "$name" "$stress_pid"
        local guard_pid="$_LAST_TEMP_PID"

        local rc=0 waited=0
        while kill -0 "$stress_pid" 2>/dev/null; do
            if [[ -f "$_STRESS_GUARD_SENTINEL" ]]; then
                echo "Thermal abort triggered! Stopping $name..."
                kill -TERM "$stress_pid" 2>/dev/null || true
                sleep 1
                kill -9 "$stress_pid" 2>/dev/null || true
                break
            fi
            sleep 1
            waited=$((waited + 1))
            if ((waited >= outer_tmo)); then
                echo "Outer timeout ceiling (${outer_tmo}s) reached."
                kill -TERM "$stress_pid" 2>/dev/null || true
                sleep 1
                kill -9 "$stress_pid" 2>/dev/null || true
                rc=124
                break
            fi
        done
        wait "$stress_pid" 2>/dev/null || rc=$?

        stop_temp_guard "$guard_pid"

        if [[ -f "$_STRESS_GUARD_SENTINEL" ]]; then
            local ab_info ab_sensor ab_t
            ab_info=$(cat "$_STRESS_GUARD_SENTINEL" 2>/dev/null)
            ab_sensor="${ab_info%%|*}"
            ab_t="${ab_info##*|}"
            finding FAIL thermal "Stress aborted: ${ab_sensor:-sensor} reached ${ab_t:-$TEMP_ABORT}°C (abort limit ${TEMP_ABORT}°C)."
            echo "ABORTED: thermal limit reached (${ab_t}°C >= ${TEMP_ABORT}°C)." | tee -a "$LAST_DETAIL"
            rm -f "$_STRESS_GUARD_SENTINEL"
            return 1
        fi

        if [[ $rc -eq 124 ]]; then
            echo "${tmo}s timeout reached (normal for continuous stress)." | tee -a "$LAST_DETAIL"
        elif [[ $rc -ne 0 ]]; then
            echo "Exit $rc — possible failure or unsupported feature." | tee -a "$LAST_DETAIL"
        else
            echo "Completed OK (exit 0)." | tee -a "$LAST_DETAIL"
        fi
        cat "$LAST_DETAIL" 2>/dev/null || true
        return 0
    }

    if have stress-ng; then
        stress_run "$STRESS_SECS" "CPU all cores (stress-ng)" root stress-ng --cpu 0 --timeout "${STRESS_SECS}s" --metrics-brief
    else
        stress_run "$STRESS_SECS" "CPU busy loop" root bash -c '
            for _ in $(seq 1 "'"$NPROC"'"); do (while :; do :; done) & done; wait'
    fi

    if have sysbench; then
        stress_run 15 "CPU benchmark (sysbench)" root sysbench cpu --threads="$NPROC" --time=10 run
    fi

    AVAIL_MB=$(awk '/MemAvailable:/ {printf "%d", $2/1024}' /proc/meminfo 2>/dev/null || echo 0)
    AVAIL_MB=${AVAIL_MB:-0}
    [[ "$AVAIL_MB" =~ ^[0-9]+$ ]] || AVAIL_MB=0

    if have stress-ng && ((AVAIL_MB > 1024)); then
        VM_MB=$((AVAIL_MB / 6))
        ((VM_MB > 1024)) && VM_MB=1024
        ((VM_MB < 128)) && VM_MB=128
        stress_run "$STRESS_SECS" "RAM 2x${VM_MB}MiB (stress-ng)" root stress-ng --vm 2 --vm-bytes "${VM_MB}M" --timeout "${STRESS_SECS}s" --metrics-brief
    fi
    if have memtester && ((AVAIL_MB > 1024)); then
        stress_run "$STRESS_SECS" "RAM pattern check 128M (memtester)" root memtester 128M 1
    fi

    if have fio; then
        fio_eng="psync"
        fio_qd=1
        if fio --enghelp 2>&1 | grep -q 'io_uring'; then
            fio_eng="io_uring"
            fio_qd=32
        elif fio --enghelp 2>&1 | grep -q 'libaio'; then
            fio_eng="libaio"
            fio_qd=32
        fi
        for d in ${DISKS[@]+"${DISKS[@]}"}; do
            [[ -b "$d" ]] || continue
            [[ "${D_TRAN[$d]:-}" == "usb" ]] && continue
            [[ "$d" == /dev/sd* && "${D_TRAN[$d]:-}" == "usb" ]] && continue
            stress_run 15 "Disk read-only fio ($d)" root fio --name=ro_scan --filename="$d" --readonly --rw=read --bs=1M --ioengine="$fio_eng" --iodepth="$fio_qd" --numjobs=1 --direct=1 --runtime=8 --time_based --group_reporting
        done
    fi

    if ((GUI_USABLE)); then
        if have glmark2; then
            stress_run 20 "GPU OpenGL (glmark2)" session glmark2 --run-forever
        elif have vkmark; then
            stress_run 20 "GPU Vulkan (vkmark)" session vkmark --duration 15
        elif have vkcube; then
            stress_run 15 "GPU Vulkan (vkcube)" session vkcube
        else
            echo "No GPU stress tool available."
        fi
    else
        echo "No accessible GUI session; GUI GPU stress skipped."
    fi

    if have v4l2-ctl; then
        for c in /dev/video*; do
            [[ -e "$c" ]] || continue
            v4l_info=$(v4l2-ctl -d "$c" --info 2>/dev/null || true)
            if grep -q "Video Capture" <<<"$v4l_info"; then
                stress_run 15 "Camera stream $c" root v4l2-ctl -d "$c" --stream-mmap --stream-count=30
            fi
        done
    fi

    tp_event=""
    touchpad_name=0
    while IFS= read -r tp_line; do
        if [[ "$tp_line" == N:*Touchpad* || "$tp_line" == N:*touchpad* ]]; then
            touchpad_name=1
            continue
        fi
        if [[ "$touchpad_name" -eq 1 && "$tp_line" == H:* ]]; then
            tp_event=$(grep -o 'event[0-9]*' <<<"$tp_line" | head -1 || true)
            break
        fi
        [[ -z "$tp_line" ]] && touchpad_name=0
    done </proc/bus/input/devices
    if [[ -n "$tp_event" ]] && have evtest; then
        stress_run 10 "Touchpad monitor $tp_event" root evtest "/dev/input/$tp_event"
    fi

    # Post-run dmesg delta
    stress_dmesg="$DETAILS/dmesg-during-stress.txt"
    dmesg 2>/dev/null | tail -n +$((DMESG_LINES_BEFORE_STRESS + 1)) >"$stress_dmesg" || true
    if [[ -s "$stress_dmesg" ]]; then
        echo "Captured $(wc -l <"$stress_dmesg") kernel log lines during stress phase."
        an_logs_delta "$stress_dmesg"
    fi
fi

# ── 28. peak temperatures & automated findings triage ────────────────────────
collect_summary_findings() {
    echo "--- Peak Temperatures Recorded During Stress ---"
    if [[ -s "$TEMP_LOG" ]]; then
        awk '
            # sensors can print "+NN.N°C" or "+NN.N C"; accept both
            /:/ {
                label=$1; sub(/:$/, "", label)
                for (i=2; i<=NF; i++) {
                    v=$i
                    gsub(/[+°]/, "", v)
                    sub(/C$/, "", v)
                    if (v ~ /^[0-9]+(\.[0-9]+)?$/) {
                        val = v + 0
                        if (!(label in max) || val > max[label]) max[label] = val
                        break
                    }
                }
            }
            END {
                if (length(max)==0) print "(no sensor peaks parsed)"
                else for (k in max) printf "  %-18s max = %.1f °C\n", k, max[k]
            }' "$TEMP_LOG" | sort
    else
        echo "(none recorded — --quick mode or no sensors)"
    fi

    echo ""
    echo "--- Automated Findings & Red Flags Summary ---"
    local fail_cnt=0 warn_cnt=0 info_cnt=0
    if [[ -s "$FINDINGS_FILE" ]]; then
        fail_cnt=$(grep -c '^FAIL|' "$FINDINGS_FILE" 2>/dev/null || true)
        warn_cnt=$(grep -c '^WARN|' "$FINDINGS_FILE" 2>/dev/null || true)
        info_cnt=$(grep -c '^INFO|' "$FINDINGS_FILE" 2>/dev/null || true)
    fi

    {
        echo "Counts: $fail_cnt FAIL, $warn_cnt WARN, $info_cnt INFO"
        if ((fail_cnt > 0)); then
            echo "--- FAIL ---"
            awk -F'|' '$1=="FAIL" { printf "[%-8s] %s\n", $2, $3 }' "$FINDINGS_FILE"
        fi
        if ((warn_cnt > 0)); then
            echo "--- WARN ---"
            awk -F'|' '$1=="WARN" { printf "[%-8s] %s\n", $2, $3 }' "$FINDINGS_FILE"
        fi
        if ((info_cnt > 0)); then
            echo "--- INFO ---"
            awk -F'|' '$1=="INFO" { printf "[%-8s] %s\n", $2, $3 }' "$FINDINGS_FILE"
        fi
        if ((fail_cnt == 0 && warn_cnt == 0)); then
            echo "[OK] No FAIL/WARN findings triggered."
        fi
    } | tee "$SUMMARY_FILE"

    {
        printf '\n========== FINDINGS SUMMARY ==========\n'
        cat "$SUMMARY_FILE"
    } | tee -a "$REPORT" >&3
    return 0
}
run_fn "Peak temperatures & automated findings triage" 30 collect_summary_findings

# ── 29. diagnostic complete ──────────────────────────────────────────────────
section "DIAGNOSTIC COMPLETE"
echo "Full report:      $REPORT"
echo "Per-command logs: $DETAILS/"
echo "Temperature log:  $TEMP_LOG"
echo "ACPI dump dir:    $ACPI_DIR/"
echo "Package log:      $MAIN_LOG"
echo "Findings summary: $SUMMARY_FILE"
if ((ARCHIVE)); then
    echo "Archive:          ${REPORT_DIR}.tar.gz"
fi
echo "Runtime:          $(($(date +%s) - START_EPOCH)) seconds"
echo ""
echo "Quick triage:"
echo "  cat '$SUMMARY_FILE'"
echo "  grep -Ei 'error|fail|warn|timeout|mismatch' '$REPORT'"
