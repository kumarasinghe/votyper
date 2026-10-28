#!/usr/bin/env bash
# votyper installer.
#
# Creates a private Python environment (no system Python needed), installs
# votyper and its speech model into it, and adds a `votyper` command.
# Everything lives under ~/.local; nothing else on the system is modified,
# except the optional steps that ask for sudo (system libraries, input group).
#
# Usage:
#   curl -fsSL https://raw.githubusercontent.com/kumarasinghe/votyper/main/scripts/install.sh | bash
#   scripts/install.sh [--uninstall]      (from a checkout of the project)

set -euo pipefail


# ============================================================================
# Settings
# ============================================================================

APP="votyper"
PYTHON_VERSION="3.12"       # private Python that uv downloads for us
UV_VERSION="0.13.5"         # pinned so every install uses the same uv
MIN_GLIBC="2.34"            # Moonshine's native library needs at least this

REPO="kumarasinghe/votyper"
DEFAULT_SOURCE_URL="https://github.com/$REPO/archive/refs/heads/main.tar.gz"
SOURCE_OVERRIDE="${VOTYPER_SOURCE:-}"   # a .tar.gz URL to install from (used for testing)

INSTALL_DIR="${VOTYPER_HOME:-$HOME/.local/share/$APP}"
VENV_DIR="$INSTALL_DIR/venv"
ICON_FILE="$INSTALL_DIR/$APP.png"
BIN_DIR="$HOME/.local/bin"
DESKTOP_FILE="$HOME/.local/share/applications/$APP.desktop"
AUTOSTART_FILE="$HOME/.config/autostart/$APP.desktop"

# Command-line switches (set by parse_args).
UNINSTALL=0

# Filled in as the install runs.
ARCH=""
STARTED=0                   # 1 once start_votyper has it running
UV=""
SOURCE_DIR=""       # the project files to install
WORK_DIR=""         # scratch space, removed when the script ends


# ============================================================================
# Helpers
# ============================================================================

say()  { printf '\033[1m==>\033[0m %s\n' "$*"; }
warn() { printf '\033[33mwarning:\033[0m %s\n' "$*" >&2; }
die()  { printf '\033[31merror:\033[0m %s\n' "$*" >&2; exit 1; }
have() { command -v "$1" >/dev/null 2>&1; }
need_curl() { have curl || die "curl is required to download files."; }

# Ask a yes/no question on the terminal (default yes). Fails when not interactive.
confirm() {
    local answer
    [ -r /dev/tty ] || return 1
    read -r -p "$1 [Y/n] " answer < /dev/tty
    [[ -z "$answer" || "$answer" =~ ^[Yy] ]]
}

# True when version $1 is at least version $2 (e.g. 2.35 >= 2.34).
version_at_least() {
    [ "$(printf '%s\n%s\n' "$2" "$1" | sort -V | head -n1)" = "$2" ]
}

# Print the distro's package manager: apt, dnf, pacman, zypper (or nothing).
detect_package_manager() {
    local pm
    for pm in apt-get dnf pacman zypper; do
        if have "$pm"; then
            echo "${pm%-get}"
            return
        fi
    done
}

# Print the system packages we need (audio library and Tk) for a package manager.
system_packages() {
    case "$1" in
        apt)    echo "libportaudio2 libtk8.6" ;;
        dnf)    echo "portaudio tk" ;;
        pacman) echo "portaudio tk" ;;
        zypper) echo "libportaudio2 tk" ;;
    esac
}

# Print the command that installs packages "$2..." with package manager "$1".
install_command() {
    local pm="$1"; shift
    case "$pm" in
        apt)    echo "sudo apt-get install -y $*" ;;
        dnf)    echo "sudo dnf install -y $*" ;;
        pacman) echo "sudo pacman -S --needed $*" ;;
        zypper) echo "sudo zypper install -y $*" ;;
    esac
}


# ============================================================================
# Machine checks (hard requirements stop the install; soft ones only warn)
# ============================================================================

check_platform() {
    [ "$(uname -s)" = "Linux" ] || die "votyper supports Linux only."

    case "$(uname -m)" in
        x86_64)         ARCH="x86_64" ;;
        aarch64|arm64)  ARCH="aarch64" ;;
        *) die "Unsupported CPU: $(uname -m) (need x86_64 or aarch64)." ;;
    esac

    local glibc
    glibc="$(getconf GNU_LIBC_VERSION 2>/dev/null | awk '{print $2}')"
    [ -n "$glibc" ] || die "glibc not found. Distros without it (e.g. Alpine) are not supported."
    version_at_least "$glibc" "$MIN_GLIBC" \
        || die "glibc $glibc is too old; Moonshine needs $MIN_GLIBC or newer."
    say "Platform OK: Linux $ARCH, glibc $glibc"
}

# The audio library cannot live in our private environment, so look for it.
# (Output is captured first: `grep -q` in a pipe can trip `set -o pipefail`.)
audio_library_present() {
    local libraries
    libraries="$(ldconfig -p 2>/dev/null || true)"
    [[ "$libraries" == *"libportaudio.so"* ]]
}

# True when the current user is in the `input` group.
in_input_group() {
    [[ " $(id -nG) " == *" input "* ]]
}

# Typing and hotkeys need the `input` group and the uinput kernel device.
check_input_access() {
    if [ -w /dev/uinput ] && in_input_group; then
        say "Input access OK (group 'input', /dev/uinput writable)"
    else
        warn "No access to /dev/uinput. Typing and hotkeys need your user in the 'input' group."
    fi
}

# The tray icon needs a desktop that offers a StatusNotifier tray area.
check_tray_host() {
    if have busctl && busctl --user status org.kde.StatusNotifierWatcher >/dev/null 2>&1; then
        say "Tray area found"
    else
        warn "No tray area found; votyper still works, but its icon will not show."
    fi
}

preflight() {
    check_platform
    audio_library_present && say "Audio library found (libportaudio)" \
        || warn "libportaudio is missing (installed in a later step)."
    check_input_access
    check_tray_host
}


# ============================================================================
# Step 1: find the project files (a local checkout, or a download)
# ============================================================================

# Print the project folder when this script is a file inside a checkout of it.
# Piped from curl there is no script file at all, so this fails and we download.
checkout_root() {
    local file="${BASH_SOURCE[0]:-}" root
    [ -n "$file" ] && [ -f "$file" ] || return 1
    root="$(cd "$(dirname "$(readlink -f "$file")")/.." && pwd)"
    [ -f "$root/pyproject.toml" ] && [ -f "$root/$APP/__init__.py" ] || return 1
    echo "$root"
}

find_source() {
    local root
    if [ -z "$SOURCE_OVERRIDE" ] && root="$(checkout_root)"; then
        SOURCE_DIR="$root"
        say "Installing from the local checkout"
        return
    fi

    need_curl
    local url="${SOURCE_OVERRIDE:-$DEFAULT_SOURCE_URL}"
    say "Downloading Votyper"
    mkdir -p "$WORK_DIR/source"
    curl -fsSL "$url" | tar -xz -C "$WORK_DIR/source" --strip-components=1 \
        || die "Could not download Votyper from $url"
    [ -f "$WORK_DIR/source/pyproject.toml" ] || die "The download does not look like Votyper."
    SOURCE_DIR="$WORK_DIR/source"
}


# ============================================================================
# Step 2: uv, the tool that builds the private Python environment
# ============================================================================

install_uv() {
    if have uv; then
        UV="$(command -v uv)"
        say "Using the uv already installed at $UV"
        return
    fi

    UV="$INSTALL_DIR/uv/uv"
    [ -x "$UV" ] && return

    need_curl
    local name="uv-$ARCH-unknown-linux-gnu"
    local url="https://github.com/astral-sh/uv/releases/download/$UV_VERSION/$name.tar.gz"

    say "Downloading uv $UV_VERSION"
    curl -fsSL -o "$WORK_DIR/$name.tar.gz"        "$url"
    curl -fsSL -o "$WORK_DIR/$name.tar.gz.sha256" "$url.sha256"
    # The checksum catches a corrupted download; it comes from the same host.
    (cd "$WORK_DIR" && sha256sum -c "$name.tar.gz.sha256" >/dev/null) \
        || die "uv download failed its checksum."

    mkdir -p "$INSTALL_DIR/uv"
    tar -xzf "$WORK_DIR/$name.tar.gz" -C "$INSTALL_DIR/uv" --strip-components=1
}


# ============================================================================
# Step 3: private Python environment with votyper installed
# ============================================================================

create_environment() {
    say "Creating a private Python $PYTHON_VERSION environment in $INSTALL_DIR"
    export UV_PYTHON_INSTALL_DIR="$INSTALL_DIR/python"   # keep uv's Python inside our folder
    # --clear: replace an environment from an earlier install without asking
    "$UV" venv --clear --python "$PYTHON_VERSION" "$VENV_DIR"
}

install_votyper() {
    say "Installing votyper and its dependencies"
    "$UV" pip install --python "$VENV_DIR/bin/python" "$SOURCE_DIR"
}


# ============================================================================
# Step 4: system pieces the private environment cannot provide
# ============================================================================

# Tk (the settings window) must be importable from the private Python.
tk_works() {
    "$VENV_DIR/bin/python" -c "import tkinter" >/dev/null 2>&1
}

# Offer to install the audio library and Tk with the distro's package manager.
ensure_system_libraries() {
    audio_library_present && tk_works && return

    local pm; pm="$(detect_package_manager)"
    [ -n "$pm" ] || { warn "Please install the PortAudio and Tk libraries for your distro."; return; }

    local command; command="$(install_command "$pm" "$(system_packages "$pm")")"
    warn "Missing system libraries (audio and/or Tk)."
    if confirm "Run '$command'?"; then
        $command < /dev/tty             # a package manager may ask questions of its own
    else
        warn "Skipped. Run it yourself later: $command"
    fi
}

# Add the user to the `input` group so typing and hotkeys work.
ensure_input_access() {
    in_input_group && return

    warn "Your user is not in the 'input' group."
    if confirm "Run 'sudo usermod -aG input $USER'? (you must log out and in afterwards)"; then
        sudo usermod -aG input "$USER"
        warn "Log out and back in so the group change takes effect."
    else
        warn "Skipped. Run it yourself later: sudo usermod -aG input $USER"
    fi
}


# ============================================================================
# Step 5: speech model
# ============================================================================

# Moonshine downloads the model into its own cache (~/.cache/moonshine_voice).
download_model() {
    say "Downloading the speech model (about 260 MB, only the first time)"
    "$VENV_DIR/bin/python" -c \
        "from moonshine_voice.download import get_model_for_language; get_model_for_language('en')"
}


# ============================================================================
# Step 6: the `votyper` command, menu entry, and start at login
# ============================================================================

write_desktop_entry() {
    mkdir -p "$(dirname "$1")"
    cat > "$1" <<EOF
[Desktop Entry]
Type=Application
Name=Votyper
Comment=Voice typing: press a hotkey, speak, and the words are typed
Exec=$BIN_DIR/$APP
Icon=$ICON_FILE
Terminal=false
Categories=Utility;Accessibility;
EOF
}

install_launchers() {
    mkdir -p "$BIN_DIR"
    ln -sf "$VENV_DIR/bin/$APP" "$BIN_DIR/$APP"
    cp "$SOURCE_DIR/$APP/assets/$APP.png" "$ICON_FILE"
    write_desktop_entry "$DESKTOP_FILE"
    write_desktop_entry "$AUTOSTART_FILE"    # the desktop starts it at every login

    case ":$PATH:" in
        *":$BIN_DIR:"*) ;;
        *) warn "$BIN_DIR is not on your PATH; add it to run 'votyper' from anywhere." ;;
    esac
}


# ============================================================================
# Step 7: start it now
# ============================================================================

# Start Votyper in the background so it keeps running after this script ends.
# It is not started when it could not work yet (no desktop session, or the
# `input` group is not active until the next login); then it starts at login.
start_votyper() {
    if [ -z "${DISPLAY:-}${WAYLAND_DISPLAY:-}" ]; then
        say "Installed. Votyper starts at your next login (no desktop session here to start it in)."
        return
    fi
    if ! in_input_group; then
        say "Installed. Log out and back in; Votyper then starts by itself."
        return
    fi

    # An older copy from a previous install would keep running the old code.
    pkill -f "$VENV_DIR/bin/python" || true
    sleep 1

    # setsid: its own session, so closing this terminal does not stop it.
    # No input and no output attached: it logs to ~/.local/state/votyper/votyper.log.
    setsid "$BIN_DIR/$APP" > /dev/null 2>&1 < /dev/null &
    disown
    sleep 2

    if pgrep -f "$VENV_DIR/bin/python" > /dev/null; then
        STARTED=1
        say "Installed and started. Votyper is loading; its tray icon shows when it is ready."
    else
        warn "Votyper did not stay running. See ~/.local/state/$APP/$APP.log"
    fi
}


# Tell the user how to try it.
show_how_to_try() {
    if [ "$STARTED" = 1 ]; then
        say "Try it now: click into any text field and press Ctrl+Space, then speak."
    else
        say "Once Votyper is running: click into any text field and press Ctrl+Space, then speak."
    fi
    echo "    Press Ctrl+Space again to stop."
    echo "    Click the tray icon to change the hotkey or use Meeting mode."
}


# ============================================================================
# Uninstall
# ============================================================================

uninstall() {
    say "Removing votyper (the model cache and your settings are kept)"
    rm -f "$BIN_DIR/$APP" "$DESKTOP_FILE" "$AUTOSTART_FILE"
    rm -rf "$INSTALL_DIR"
    say "Done. To also delete the model and settings:"
    echo "    rm -rf ~/.cache/moonshine_voice ~/.config/$APP"
}


# ============================================================================
# Main
# ============================================================================

usage() {
    cat <<TEXT
Votyper installer.

Install:    curl -fsSL https://raw.githubusercontent.com/$REPO/main/scripts/install.sh | bash
Uninstall:  curl -fsSL https://raw.githubusercontent.com/$REPO/main/scripts/install.sh | bash -s -- --uninstall
TEXT
}

parse_args() {
    local arg
    for arg in "$@"; do
        case "$arg" in
            --uninstall)  UNINSTALL=1 ;;
            -h|--help)    usage; exit 0 ;;
            *) die "Unknown option: $arg (try --help)" ;;
        esac
    done
}

main() {
    parse_args "$@"

    if [ "$UNINSTALL" = 1 ]; then
        uninstall
        exit 0
    fi

    preflight

    WORK_DIR="$(mktemp -d)"
    trap "rm -rf '$WORK_DIR'" EXIT      # expanded now: the variable is gone when the trap runs

    find_source
    install_uv
    create_environment
    install_votyper
    ensure_system_libraries
    ensure_input_access
    download_model
    install_launchers
    start_votyper
    show_how_to_try
}

# Run when executed or piped from curl (no script file), but not when sourced for testing.
if [[ -z "${BASH_SOURCE[0]:-}" || "${BASH_SOURCE[0]}" == "$0" ]]; then
    main "$@"
fi
