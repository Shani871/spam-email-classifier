#!/bin/sh
# Downloads the "Phishing Email Curated Datasets" (Champa, Rabbi, Zibran; Zenodo record 8339691, CC BY 4.0)
# into dataset/external/zenodo_8339691/. About 450 MB. The files are not committed to git.
set -eu
cd "$(dirname "$0")/.."
DEST=dataset/external/zenodo_8339691
mkdir -p "$DEST"
for f in CEAS_08 SpamAssasin Enron Ling Nazario Nazario_5 Nigerian_Fraud Nigerian_5 TREC_05 TREC_06 TREC_07; do
  if [ ! -s "$DEST/$f.csv" ]; then
    echo "Downloading $f.csv"
    curl -fL --retry 3 --max-time 900 -o "$DEST/$f.csv.part" "https://zenodo.org/api/records/8339691/files/$f.csv/content"
    mv "$DEST/$f.csv.part" "$DEST/$f.csv"
  fi
done
shasum -a 256 "$DEST"/*.csv > "$DEST/SHA256SUMS"
echo "Done: $DEST"
