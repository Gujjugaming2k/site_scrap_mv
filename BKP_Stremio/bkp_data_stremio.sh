
#!/usr/bin/env bash
set -euo pipefail

# --- Fetch encrypted token from repo (force latest with cache-busting) ---
curl -sS -L "https://raw.githubusercontent.com/Gujjugaming2k/site_scrap_mv/main/BKP_Stremio/token.enc?t=$(date +%s)" -o token.enc
TOKEN_ENC="token.enc"

# --- Passphrase (default 'abc'; override by export TOKEN_PASSPHRASE="...") ---
PASSPHRASE="${TOKEN_PASSPHRASE:-abc}"

# --- Decrypt token into variable (no temp plaintext files) ---
TKEN="$(openssl enc -d -aes-256-cbc -salt -pbkdf2 -in "$TOKEN_ENC" -pass pass:"$PASSPHRASE")" || {
  echo "❌ Decryption failed (wrong passphrase or missing token.enc)" >&2
  exit 1
}
: "${TKEN:?Decryption failed}"

# --- Repo config ---
OWNER="Gujjugaming2k"
REPO="site_scrap_mv"
BRANCH="main"
REMOTE_DIR="BKP_Stremio"

# Set to "true" to force overwrite by delete+recreate (even if identical)
FORCE="${FORCE:-false}"

FILES=(
  "Stremio/data/catalogs.json"
  "Stremio/data/movies.json"
  "Stremio/data/series.json"
  "Stremio/data/users.json"
  "Stremio/data/providers.json"
  "Stremio/data/settings.json"
  "Stremio/data/analytics.json"
)

# ===== HELPERS =====

base64_one_line() {
  local file="$1"
  if base64 --help 2>/dev/null | grep -q '\-w'; then
    base64 -w0 "$file"        # GNU coreutils
  else
    base64 "$file" | tr -d '\n'  # macOS/BSD
  fi
}

get_remote_metadata() {
  local repo_path="$1"
  local url="https://api.github.com/repos/${OWNER}/${REPO}/contents/${repo_path}?ref=${BRANCH}"
  curl -sS -H "Authorization: Bearer ${TKEN}" \
            -H "Accept: application/vnd.github+json" \
            "$url"
}

extract_json_field() {
  # naive extractor: extract first occurrence of "field": "value"
  local field="$1"
  sed -n "s/.*\"${field}\"[[:space:]]*:[[:space:]]*\"\([^\"]\+\)\".*/\1/p" | head -n1
}

put_file() {
  local repo_path="$1"
  local content_b64="$2"
  local sha="${3:-}"
  local message="$4"

  local tmp_body
  tmp_body="$(mktemp)"

  # Build valid JSON (no trailing comma). If sha is present, include it.
  if [[ -n "$sha" ]]; then
    cat > "$tmp_body" <<JSON
{
  "message": "${message}",
  "content": "${content_b64}",
  "branch": "${BRANCH}",
  "sha": "${sha}"
}
JSON
  else
    cat > "$tmp_body" <<JSON
{
  "message": "${message}",
  "content": "${content_b64}",
  "branch": "${BRANCH}"
}
JSON
  fi

  curl -sS -X PUT \
    -H "Authorization: Bearer ${TKEN}" \
    -H "Accept: application/vnd.github+json" \
    --data-binary @"$tmp_body" \
    "https://api.github.com/repos/${OWNER}/${REPO}/contents/${repo_path}"
  rm -f "$tmp_body"
}

delete_file() {
  local repo_path="$1"
  local sha="$2"
  local message="$3"

  local tmp_body
  tmp_body="$(mktemp)"
  cat > "$tmp_body" <<JSON
{
  "message": "${message}",
  "sha": "${sha}",
  "branch": "${BRANCH}"
}
JSON

  curl -sS -X DELETE \
    -H "Authorization: Bearer ${TKEN}" \
    -H "Accept: application/vnd.github+json" \
    --data-binary @"$tmp_body" \
    "https://api.github.com/repos/${OWNER}/${REPO}/contents/${repo_path}"
  rm -f "$tmp_body"
}

# ===== MAIN =====
for local_file in "${FILES[@]}"; do
  if [[ ! -f "$local_file" ]]; then
    echo "❌ Missing local file: $local_file" >&2
    continue
  fi

  remote_name="$(basename "$local_file")"
  repo_path="${REMOTE_DIR}/${remote_name}"

  echo "➡️  Processing: $local_file  ->  ${OWNER}/${REPO}:${BRANCH}/${repo_path}"

  # Get remote metadata (sha + existing content)
  meta="$(get_remote_metadata "$repo_path")" || meta=""
  remote_sha="$(echo "$meta" | extract_json_field sha || true)"
  # Note: For large files, 'content' may be empty with 'encoding: none', so identical check may be skipped.
  remote_b64="$(echo "$meta" | sed -n 's/.*"content"[[:space:]]*:[[:space:]]*"\([^"]\+\)".*/\1/p' | head -n1 | tr -d '\n')"
  local_b64="$(base64_one_line "$local_file")"

  # If FORCE=true and file exists, delete first
  if [[ "$FORCE" == "true" && -n "$remote_sha" ]]; then
    echo "🗑️  Deleting existing file (force overwrite)…"
    del_resp="$(delete_file "$repo_path" "$remote_sha" "Delete ${repo_path} before overwrite")"
    if echo "$del_resp" | grep -q '"commit"'; then
      echo "✅ Deleted ${repo_path}"
      remote_sha=""   # reset
      remote_b64=""   # reset
    else
      echo "⚠️  Delete failed:"
      echo "$del_resp"
      continue
    fi
  fi

  # If exists and content identical (no FORCE), report and skip
  if [[ -n "$remote_sha" && -n "$remote_b64" && "$remote_b64" == "$local_b64" ]]; then
    echo "ℹ️  Remote content is identical. No update performed."
    echo "    Set FORCE=true to delete+recreate and create a new commit."
    continue
  fi

  # Create or update
  action="Create"
  [[ -n "$remote_sha" ]] && action="Update"
  put_resp="$(put_file "$repo_path" "$local_b64" "$remote_sha" "${action} ${repo_path}")"

  if echo "$put_resp" | grep -q '"commit"'; then
    path="$(echo "$put_resp" | sed -n 's/.*"path"[[:space:]]*:[[:space:]]*"\([^"]\+\)".*/\1/p' | head -n1)"
    sha_new="$(echo "$put_resp" | sed -n 's/.*"sha"[[:space:]]*:[[:space:]]*"\([^"]\+\)".*/\1/p' | head -n1)"
    echo "✅ ${action}d: ${path} (sha: ${sha_new})"
  elif echo "$put_resp" | grep -qi 'identical'; then
    echo "ℹ️  Remote says identical; no commit created. Try FORCE=true."
  else
    echo "❌ ${action} failed. API response:"
    echo "$put_resp"
  fi
done

echo "🎉 Done."

