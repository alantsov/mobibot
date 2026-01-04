#!/usr/bin/env bash
# Parallel wrapper for pdftoppm using 8 cores via xargs
# Usage: pdftoppm_parallel.sh [pdftoppm options] input.pdf [output_prefix]

set -euo pipefail

# Default parallelism
CORES=8

# Extract last two args (PDF and prefix)
if [ $# -lt 1 ]; then
  echo "Usage: $0 [pdftoppm options] input.pdf [output_prefix]"
  exit 1
fi

PDF="${@: -2:1}"
PREFIX="${@: -1}"

# If only one arg, assume prefix is not specified
if [[ ! -f "$PDF" ]]; then
  PDF="${@: -1}"
  PREFIX="$(basename "${PDF%.*}")"
  ARGS=("${@:1:$#-1}")
else
  ARGS=("${@:1:$#-2}")
fi

# Check dependencies
command -v pdftoppm >/dev/null 2>&1 || { echo "Error: pdftoppm not found"; exit 1; }
command -v pdfinfo >/dev/null 2>&1 || { echo "Error: pdfinfo not found"; exit 1; }

# Determine number of pages
PAGES=$(pdfinfo "$PDF" | awk '/^Pages:/ {print $2}')
if [ -z "$PAGES" ]; then
  echo "Error: Could not determine page count for $PDF"
  exit 1
fi

echo "Converting $PAGES pages from '$PDF' using $CORES parallel processes..."

# Export variables for xargs
export PDF PREFIX
export ARGS_STR="${ARGS[*]}"

# Run pdftoppm in parallel
seq 1 "$PAGES" | xargs -n 1 -P "$CORES" bash -c '
  PAGE="$0"
  pdftoppm $ARGS_STR -f "$PAGE" -l "$PAGE" "$PDF" "$PREFIX" >/dev/null 2>&1
  echo "Done page $PAGE"
'

echo "✅ Finished converting $PDF"