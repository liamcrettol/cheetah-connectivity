#!/usr/bin/env bash
# Build the manuscript. Requires TeX Live with biber.
set -e
cd "$(dirname "$0")"
latexmk -pdf -interaction=nonstopmode main.tex
echo "-> main.pdf"
