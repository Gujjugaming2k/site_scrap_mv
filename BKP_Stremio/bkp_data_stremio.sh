#!/usr/bin/env bash
set -euo pipefail


TOKEN_ENC="token.enc"

# Read passphrase from env or prompt
PASSPHRASE="${TOKEN_PASSPHRASE:-}"
if [ -z "$PASSPHRASE" ]; then
  read -s -p "Token passphrase: " PASSPHRASE; echo
fi

# Decrypt into variable at runtime (no temp plaintext file)
TKEN="$(openssl enc -d -aes-256-cbc -salt -pbkdf2 -in "$TOKEN_ENC" -pass pass:"$PASSPHRASE")"
: "${TKEN:?Decryption failed}"

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
)

# ===== HELPERS =====

base64_one_line() {
  local file="$1"
  if base64 --help 2>/dev/null | grep -q '\-w'; then
    base64 -w0 "$file"
  else
    base64 "$file" | tr -d '\n'
  fi
}

get_remote_metadata() {
  local repo_path="$1"
  local url="https://api.github.com/repos/${OWNER}/${REPO}/contents/${repo_path}?ref=${BRANCH}"
  curl -sS -H "Authorization: Bearer ${TKEN}" \
            -H "Accept: application/vnd.github+json" "$url"
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
  {
    echo '{'
    echo "  \"message\": \"${message}\","
    echo "  \"content\": \"${content_b64}\","
    echo "  \"branch\": \"${BRANCH}\","
    if [[ -n "$sha" ]]; then
      echo "  \"sha\": \"${sha}\""
    fi
    echo '}'
  } > "$tmp_body"

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
  {
    echo '{'
    echo "  \"message\": \"${message}\","
    echo "  \"sha\": \"${sha}\","
    echo "  \"branch\": \"${BRANCH}\""
    echo '}'
  } > "$tmp_body"

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
  # Optional: detect identical content (download and compare)
  # Note: Contents API returns Base64 in 'content' field
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
  else
    # Surface errors like 409 identical, 403 protection, etc.
    echo "❌ ${action} failed. API response:"
    echo "$put_resp"
  fi
done

echo "🎉 Done."
