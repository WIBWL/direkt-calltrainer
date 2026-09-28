#!/usr/bin/env bash
#
# Builds the frontend, backend and worker images and pushes them to the internal
# registry, where WUD (What's Up Docker) picks them up. Background on buildx and
# provenance: ../direkt-infrastructure/public/README.md.
#
# Each image gets two tags: the v* git tag on HEAD (traceability) and :latest
# (what WUD watches; disable with PUSH_LATEST=0). HEAD must carry a v* tag that
# has been pushed.
#
#   scripts/build-and-push.sh                 # all three
#   scripts/build-and-push.sh frontend worker # some
#   PUSH_LATEST=0 scripts/build-and-push.sh
#   REGISTRY=registry.example.de scripts/build-and-push.sh
#   REMOTE=upstream scripts/build-and-push.sh
#
set -euo pipefail

# --- config (override via env) ---------------------------------------------
REGISTRY="${REGISTRY:-registry.internal.efre-direkt.de}"
BUILDER="${BUILDER:-wud}"
PLATFORM="${PLATFORM:-linux/amd64}"
REMOTE="${REMOTE:-origin}"
PUSH_LATEST="${PUSH_LATEST:-1}"

# The three images of ADR 0104, one Dockerfile target each.
declare -A IMAGES=(
  [frontend]="calltrainer-frontend"
  [backend]="calltrainer-backend"
  [worker]="calltrainer-worker"
)

if [ "$#" -gt 0 ]; then
  TARGETS=("$@")
else
  TARGETS=(frontend backend worker)
fi

# Run from the repo root so the build context is right.
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

# --- resolve the release version from the git tag on HEAD ------------------
mapfile -t HEAD_TAGS < <(git tag --points-at HEAD --list 'v*' --sort=-version:refname)

if [ "${#HEAD_TAGS[@]}" -eq 0 ]; then
  cat >&2 <<EOF
!! HEAD is not tagged with a v* version tag.
   Tag this commit and push the tag before building, e.g.:
     git tag v1.2.3
     git push $REMOTE v1.2.3
EOF
  exit 1
fi

VERSION="${HEAD_TAGS[0]}"
if [ "${#HEAD_TAGS[@]}" -gt 1 ]; then
  echo ">> note: multiple v* tags on HEAD (${HEAD_TAGS[*]}); using highest: $VERSION" >&2
fi

# --- verify the tag has been pushed to the remote --------------------------
local_sha="$(git rev-parse "${VERSION}^{commit}")"
remote_out="$(git ls-remote "$REMOTE" "refs/tags/${VERSION}" "refs/tags/${VERSION}^{}" 2>/dev/null || true)"

if [ -z "$remote_out" ]; then
  cat >&2 <<EOF
!! Tag '$VERSION' has not been pushed to '$REMOTE'.
   Push it before building, e.g.:
     git push $REMOTE $VERSION
EOF
  exit 1
fi

# Annotated tags: use the dereferenced commit (^{}). Lightweight: the plain ref.
remote_sha="$(printf '%s\n' "$remote_out" | awk '/\^\{\}$/ {print $1; exit}')"
[ -z "$remote_sha" ] && remote_sha="$(printf '%s\n' "$remote_out" | awk 'NR==1 {print $1}')"

if [ "$remote_sha" != "$local_sha" ]; then
  cat >&2 <<EOF
!! Tag '$VERSION' on '$REMOTE' points to $remote_sha
   but HEAD ($VERSION) is $local_sha.
   The pushed tag does not match this commit. Re-point and push the tag, e.g.:
     git tag -f $VERSION && git push --force $REMOTE $VERSION
EOF
  exit 1
fi

echo ">> building version $VERSION (commit $local_sha)"

# --- ensure the docker-container builder exists (one-time, idempotent) ------
if ! docker buildx inspect "$BUILDER" >/dev/null 2>&1; then
  echo ">> creating buildx builder '$BUILDER' (driver: docker-container)"
  docker buildx create --name "$BUILDER" --driver docker-container
fi

# --- build & push each target ----------------------------------------------
for target in "${TARGETS[@]}"; do
  image="${IMAGES[$target]:-}"
  if [ -z "$image" ]; then
    echo "!! unknown target '$target' (valid: ${!IMAGES[*]})" >&2
    exit 1
  fi

  tag_args=(-t "${REGISTRY}/${image}:${VERSION}")
  pushed_tags="${VERSION}"
  if [ "$PUSH_LATEST" != "0" ]; then
    tag_args+=(-t "${REGISTRY}/${image}:latest")
    pushed_tags="${VERSION}, latest"
  fi

  echo
  echo ">> building target '$target' -> ${REGISTRY}/${image} (${pushed_tags})"
  docker buildx build \
    --builder "$BUILDER" \
    --platform "$PLATFORM" \
    --provenance=true \
    --target "$target" \
    "${tag_args[@]}" \
    --push \
    .
done

echo
echo ">> done. pushed ${TARGETS[*]} as $VERSION$([ "$PUSH_LATEST" != "0" ] && echo " + latest")"
