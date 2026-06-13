#!/usr/bin/env bash
# Regenerate the scanned circular used to exercise the OCR pipeline.
#
# douane.gov.ma blocks automated download, so we synthesize a genuine scan from
# the dangerous-goods pages (13-16) of the Casablanca port regulation: render to
# grayscale images at 150 DPI and recombine into an image-only PDF. The result
# has NO text layer — OCR must recover the French text (accents included).
#
# Requires: poppler-utils (pdftoppm), imagemagick (convert)
set -euo pipefail

RAW="$(dirname "$0")/../data/corpus/raw"
SRC="$RAW/anp-reglement-casablanca-fr.pdf"
OUT="$RAW/circulaire-securite-md-scan-fr.pdf"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

pdftoppm -gray -r 150 -f 13 -l 16 "$SRC" "$TMP/pg" -png
convert "$TMP"/pg-*.png "$OUT"
echo "Wrote $OUT"
echo "sha256: $(sha256sum "$OUT" | cut -d' ' -f1)"
