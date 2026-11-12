#!/usr/bin/env bash
# Sets up this computer's MCP servers for the jam repo. Run once per computer.
#
# The shared .mcp.json only holds `unreal`, because http://127.0.0.1:8000/mcp means
# "this machine's editor" on every OS. Blender's server needs a real folder path, and
# that path differs on every computer, so it is registered at USER scope here instead.
# See CLAUDE.md, "Blender", and docs/SETUP_TEAMMATE.md.
#
# Usage:
#   ./tools/setup_mcp.sh                 # use $BLENDER_MCP_DIR, or ~/blender_mcp
#   ./tools/setup_mcp.sh --clone         # clone blender_mcp if it isn't there yet
#   ./tools/setup_mcp.sh --dir /path/to/blender_mcp

set -euo pipefail

BLENDER_MCP_DIR="${BLENDER_MCP_DIR:-$HOME/blender_mcp}"
CLONE=0
while [ $# -gt 0 ]; do
  case "$1" in
    --clone) CLONE=1; shift ;;
    --dir)   BLENDER_MCP_DIR="$2"; shift 2 ;;
    *) echo "unknown option: $1" >&2; exit 2 ;;
  esac
done

repo="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
say() { printf '  %s\n' "$1"; }

printf '\nMCP setup for this computer\n'
echo "repo: $repo"

# --- 1. Approve the shared servers on this computer (per-machine, gitignored) ---
mkdir -p "$repo/.claude"
settings="$repo/.claude/settings.local.json"
if [ ! -f "$settings" ]; then
  printf '%s\n' '{' '  "enableAllProjectMcpServers": true' '}' > "$settings"
elif grep -q '"enableAllProjectMcpServers"' "$settings"; then
  : # already set; leave the rest of the file alone
elif command -v python3 >/dev/null 2>&1; then
  # Merge rather than overwrite: this file also holds each person's permission allowlist.
  python3 - "$settings" <<'JSONEDIT'
import json, sys
path = sys.argv[1]
with open(path) as f:
    data = json.load(f)
data["enableAllProjectMcpServers"] = True
with open(path, "w") as f:
    json.dump(data, f, indent=2)
    print(file=f)
JSONEDIT
else
  echo "  !! $settings exists but python3 is missing, so it was left untouched."
  echo '     Add this to it by hand:  "enableAllProjectMcpServers": true'
fi
say "approved shared .mcp.json servers -> .claude/settings.local.json"

# --- 2. uv must be on PATH ----------------------------------------------------
if ! command -v uv >/dev/null 2>&1; then
  echo "  uv is not on PATH. Install it, then re-run:"
  echo "    curl -LsSf https://astral.sh/uv/install.sh | sh"
  echo "  (Unreal still works without uv; only Blender needs it.)"
  exit 1
fi
say "uv: $(command -v uv)"

# --- 3. Find (or clone) blender_mcp ------------------------------------------
mcp_dir="$BLENDER_MCP_DIR/mcp"
if [ ! -d "$mcp_dir" ]; then
  if [ "$CLONE" -eq 1 ]; then
    say "cloning blender_mcp -> $BLENDER_MCP_DIR"
    git clone https://projects.blender.org/lab/blender_mcp.git "$BLENDER_MCP_DIR"
    uv --directory "$mcp_dir" sync
  else
    echo "  No blender_mcp at $mcp_dir."
    echo "  Re-run with --clone, or pass --dir <path> if it lives elsewhere."
    echo "  Unreal is set up regardless; stopping before the Blender step."
    exit 1
  fi
fi
mcp_dir="$(cd "$mcp_dir" && pwd)"
say "blender_mcp: $mcp_dir"

# --- 4. Register the servers at USER scope (this machine, any folder) ---------
# User scope means chats pick them up wherever the session starts, not just in the repo.
for name in blender unreal; do
  claude mcp remove "$name" -s user >/dev/null 2>&1 || true
done
claude mcp add blender -s user -- uv --directory "$mcp_dir" run blender-mcp
claude mcp add --transport http unreal -s user http://127.0.0.1:8000/mcp
say "registered 'blender' and 'unreal' at user scope"

printf '\nDone. Check with:  claude mcp list\n'
echo "Blender's own add-on still has to be running (port 9876) before Blender tools answer."
printf 'Servers are read when a session starts, so open a NEW session to pick them up.\n\n'
