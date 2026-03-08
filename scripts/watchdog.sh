#!/usr/bin/env zsh
# watchdog.sh — keeps the TFT Stats server alive and GitHub README in sync.
#
# What it does:
#   1. Checks if localhost:5001 is healthy
#   2. If not → kills stale processes, restarts the Flask server
#   3. Kills any existing cloudflared tunnel, starts a fresh one
#   4. Extracts the new trycloudflare.com URL from cloudflared output
#   5. Updates the GitHub profile README via the GitHub API
#
# Requirements:
#   - SSH key added to GitHub (run: ssh -T git@github.com)
#   - cloudflared installed  (brew install cloudflared)
#   - curl, git, python3 available
#
# Usage:
#   ./scripts/watchdog.sh

set -euo pipefail

# ── Config ────────────────────────────────────────────────────────────────────
PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
VENV_PYTHON="$PROJECT_DIR/venv/bin/python3"
SERVER_LOG="/tmp/tft-server.log"
TUNNEL_LOG="/tmp/tft-cloudflared.log"
PORT=5001
HEALTH_URL="http://localhost:$PORT/tft-stats/euw1/LeeSIUU/SIUU/png"

# GitHub profile repo (the special <username>/<username> repo)
GITHUB_USER="johnzey-dev"
README_PATH="README.md"          # path inside the profile repo

# The image src line pattern to replace in README.md
IMG_PATTERN='trycloudflare\.com/tft-stats/euw1/LeeSIUU/SIUU/png'
IMG_REPLACEMENT_SUFFIX="/tft-stats/euw1/LeeSIUU/SIUU/png"

# ── Colours ───────────────────────────────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; CYAN='\033[0;36m'; NC='\033[0m'
log()  { echo -e "${CYAN}[watchdog]${NC} $*"; }
ok()   { echo -e "${GREEN}[  OK  ]${NC} $*"; }
warn() { echo -e "${YELLOW}[ WARN ]${NC} $*"; }
err()  { echo -e "${RED}[ ERR  ]${NC} $*"; }

# ── Checks ────────────────────────────────────────────────────────────────────
if ! command -v cloudflared &>/dev/null; then
  err "cloudflared not found. Install: brew install cloudflared"
  exit 1
fi

# Ensure ssh-agent is running and the key is loaded (handles passphrase keys)
if ! ssh-add -l &>/dev/null; then
  log "No keys in ssh-agent — adding default key (you'll be prompted for your passphrase) …"
  ssh-add ~/.ssh/id_ed25519 2>/dev/null || ssh-add ~/.ssh/id_rsa 2>/dev/null || ssh-add 2>/dev/null || {
    err "Could not add SSH key to agent. Run manually: ssh-add ~/.ssh/your_key"
    exit 1
  }
fi

# Verify GitHub SSH access
if ! ssh -T git@github.com 2>&1 | grep -q "successfully authenticated"; then
  err "SSH to GitHub failed. Make sure your key is added to GitHub:"
  echo "  https://github.com/settings/keys"
  exit 1
fi
ok "GitHub SSH access confirmed"

# ── Step 1: Check if server is healthy ────────────────────────────────────────
log "Checking server health at $HEALTH_URL …"
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" --max-time 10 "$HEALTH_URL" 2>/dev/null || echo "000")

if [[ "$HTTP_CODE" == "200" ]]; then
  ok "Server is already healthy (HTTP $HTTP_CODE)"
  SERVER_RUNNING=true
else
  warn "Server not healthy (HTTP $HTTP_CODE) — restarting …"
  SERVER_RUNNING=false
fi

# ── Step 2: (Re)start Flask server if needed ──────────────────────────────────
if [[ "$SERVER_RUNNING" == false ]]; then
  log "Stopping any process on port $PORT …"
  lsof -ti :$PORT | xargs kill -9 2>/dev/null && warn "Killed stale process on :$PORT" || true

  log "Starting Flask server …"
  cd "$PROJECT_DIR"
  PYTHONPATH=src nohup "$VENV_PYTHON" src/main.py >"$SERVER_LOG" 2>&1 &
  SERVER_PID=$!
  log "Flask PID: $SERVER_PID — waiting for it to be ready …"

  # Wait up to 30 seconds for the server to respond
  for i in $(seq 1 30); do
    sleep 1
    HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" --max-time 5 "$HEALTH_URL" 2>/dev/null || echo "000")
    if [[ "$HTTP_CODE" == "200" ]]; then
      ok "Server is up after ${i}s (HTTP $HTTP_CODE)"
      break
    fi
    if [[ $i -eq 30 ]]; then
      err "Server failed to start after 30s. Check $SERVER_LOG"
      tail -20 "$SERVER_LOG"
      exit 1
    fi
  done
fi

# ── Step 3: Kill old cloudflared tunnel ───────────────────────────────────────
log "Stopping any existing cloudflared tunnel …"
pkill -f "cloudflared tunnel" 2>/dev/null && warn "Killed existing cloudflared" || true
sleep 2

# ── Step 4: Start fresh cloudflared tunnel ────────────────────────────────────
log "Starting new cloudflared tunnel on port $PORT …"
cloudflared tunnel --url "http://localhost:$PORT" >"$TUNNEL_LOG" 2>&1 &
TUNNEL_PID=$!
log "Cloudflared PID: $TUNNEL_PID — waiting for URL …"

# Extract the trycloudflare.com URL from the log (wait up to 30s)
TUNNEL_URL=""
for i in $(seq 1 30); do
  sleep 1
  TUNNEL_URL=$(grep -oE 'https://[a-z0-9-]+\.trycloudflare\.com' "$TUNNEL_LOG" 2>/dev/null | head -1 || true)
  if [[ -n "$TUNNEL_URL" ]]; then
    ok "Tunnel URL: $TUNNEL_URL"
    break
  fi
  if [[ $i -eq 30 ]]; then
    err "Could not extract tunnel URL after 30s. Check $TUNNEL_LOG"
    tail -20 "$TUNNEL_LOG"
    exit 1
  fi
done

NEW_IMAGE_URL="${TUNNEL_URL}${IMG_REPLACEMENT_SUFFIX}"
log "New image URL: $NEW_IMAGE_URL"

# ── Step 5: Verify tunnel actually reaches the server ────────────────────────
log "Verifying tunnel …"
TUNNEL_HTTP=$(curl -s -o /dev/null -w "%{http_code}" --max-time 15 "$NEW_IMAGE_URL" 2>/dev/null || echo "000")
if [[ "$TUNNEL_HTTP" == "200" ]]; then
  ok "Tunnel verified (HTTP $TUNNEL_HTTP)"
else
  warn "Tunnel returned HTTP $TUNNEL_HTTP — proceeding anyway (camo may still cache OK)"
fi

# ── Step 6: Clone the GitHub profile repo via SSH ────────────────────────────
PROFILE_REPO="git@github.com:$GITHUB_USER/$GITHUB_USER.git"
PROFILE_DIR="/tmp/tft-profile-readme"

log "Cloning profile repo via SSH …"
rm -rf "$PROFILE_DIR"
if ! git clone --depth 1 "$PROFILE_REPO" "$PROFILE_DIR" 2>&1; then
  err "SSH clone failed. Make sure your SSH key is added to GitHub:"
  echo "  ssh -T git@github.com"
  exit 1
fi
ok "Profile repo cloned to $PROFILE_DIR"

# ── Step 7: Replace the image URL in README ───────────────────────────────────
log "Replacing image URL in README …"
OLD_CONTENT=$(cat "$PROFILE_DIR/$README_PATH")
sed -i '' -E "s|https://[a-z0-9-]+\.trycloudflare\.com${IMG_REPLACEMENT_SUFFIX}|${NEW_IMAGE_URL}|g" \
  "$PROFILE_DIR/$README_PATH"
NEW_CONTENT=$(cat "$PROFILE_DIR/$README_PATH")

if [[ "$OLD_CONTENT" == "$NEW_CONTENT" ]]; then
  warn "No URL change detected in README (pattern not found or URL already current)."
  warn "Expected a trycloudflare.com URL ending in: $IMG_REPLACEMENT_SUFFIX"
else
  ok "URL replaced in README."
fi

# ── Step 8: Commit and push via SSH ──────────────────────────────────────────
log "Committing and pushing README via SSH …"
cd "$PROFILE_DIR"
git config user.email "watchdog@local"
git config user.name "TFT Watchdog"
git add "$README_PATH"

if git diff --cached --quiet; then
  warn "Nothing to commit — README already has this URL."
else
  git commit -m "chore: update TFT stats image URL [watchdog]"
  if git push origin main 2>&1; then
    ok "README pushed to GitHub via SSH."
  else
    err "git push failed. Check SSH key permissions."
    exit 1
  fi
fi
cd "$PROJECT_DIR"

# ── Done ──────────────────────────────────────────────────────────────────────
echo ""
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}  All done!${NC}"
echo -e "  Flask server : ${CYAN}http://localhost:$PORT${NC}"
echo -e "  Tunnel URL   : ${CYAN}$TUNNEL_URL${NC}"
echo -e "  Image URL    : ${CYAN}$NEW_IMAGE_URL${NC}"
echo -e "  Profile repo : ${CYAN}https://github.com/$GITHUB_USER/$GITHUB_USER${NC}"
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
log "Tunnel is running in background (PID $TUNNEL_PID). Logs: $TUNNEL_LOG"
log "Server logs: $SERVER_LOG"
