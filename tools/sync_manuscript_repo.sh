#!/usr/bin/env bash
# Sync tex/, protocol/, refs/ between this repo and the standalone
# cheetah-connectivity-manuscript repo that Overleaf is connected to.
#
# Usage:
#   tools/sync_manuscript_repo.sh push   # this repo -> manuscript repo (normal case)
#   tools/sync_manuscript_repo.sh pull   # manuscript repo -> this repo (after editing in Overleaf)
#
# "push" is what you want after any commit here that touches tex/, protocol/
# or refs/. It does NOT touch anything else in this repo (no gis/, no
# handoff/, no LFS content ever crosses into the manuscript repo).
#
# The manuscript repo is cloned into a sibling directory the first time this
# runs, then reused on later runs.

set -euo pipefail

MAIN_REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
MIRROR_DIR="$MAIN_REPO_ROOT/../cheetah-connectivity-manuscript"
MIRROR_URL="https://github.com/liamcrettol/cheetah-connectivity-manuscript.git"
DIRS=(tex protocol refs)

mode="${1:-push}"
if [[ "$mode" != "push" && "$mode" != "pull" ]]; then
  echo "Usage: $0 [push|pull]" >&2
  exit 1
fi

if [[ ! -d "$MIRROR_DIR/.git" ]]; then
  echo "Cloning manuscript mirror into $MIRROR_DIR ..."
  git clone -q "$MIRROR_URL" "$MIRROR_DIR"
fi

cd "$MIRROR_DIR"
git pull -q origin main

if [[ "$mode" == "push" ]]; then
  for d in "${DIRS[@]}"; do
    rsync -a --delete \
      --exclude='*.aux' --exclude='*.bbl' --exclude='*.bcf' --exclude='*.blg' \
      --exclude='*.fdb_latexmk' --exclude='*.fls' --exclude='*.lof' --exclude='*.log' \
      --exclude='*.lot' --exclude='*.out' --exclude='*.run.xml' --exclude='*.synctex.gz' \
      --exclude='*.toc' --exclude='*.nav' --exclude='*.snm' \
      "$MAIN_REPO_ROOT/$d/" "$MIRROR_DIR/$d/"
  done
  cd "$MIRROR_DIR"
  if git status --porcelain | grep -q .; then
    git add -A
    git commit -q -m "Sync from cheetah-connectivity ($(cd "$MAIN_REPO_ROOT" && git rev-parse --short HEAD))"
    git push -q origin main
    echo "Pushed to manuscript repo."
  else
    echo "Nothing changed, manuscript repo already up to date."
  fi
else
  for d in "${DIRS[@]}"; do
    rsync -a --delete \
      --exclude='*.aux' --exclude='*.bbl' --exclude='*.bcf' --exclude='*.blg' \
      --exclude='*.fdb_latexmk' --exclude='*.fls' --exclude='*.lof' --exclude='*.log' \
      --exclude='*.lot' --exclude='*.out' --exclude='*.run.xml' --exclude='*.synctex.gz' \
      --exclude='*.toc' --exclude='*.nav' --exclude='*.snm' \
      "$MIRROR_DIR/$d/" "$MAIN_REPO_ROOT/$d/"
  done
  echo "Pulled manuscript repo changes into $MAIN_REPO_ROOT/{tex,protocol,refs}."
  echo "Now: cd '$MAIN_REPO_ROOT' && git add tex protocol refs && git commit && git push"
fi
