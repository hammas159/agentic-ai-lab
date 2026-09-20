#!/bin/sh
# Fetch the datasets that are too large to commit.
#
# Everything small enough to commit already is: the GenBank records, the Loghub
# samples, the RFC texts, the eCFR version index, the TSPLIB instance with its
# proven optimum, and the two tables derived from the retail spreadsheet. The
# archives below are the bulk, and every test that needs one skips cleanly when
# it is missing — a fresh clone is green before any of this arrives.
#
#   sh scripts/fetch_data.sh
#
# Resumes, retries, and never overwrites a file that is already there.

set -e
cd "$(dirname "$0")/.."
mkdir -p data
cd data

log() { printf '[%s] %s\n' "$(date +%H:%M:%S)" "$*"; }

fetch() {
  name=$1; url=$2; out=$3
  if [ -s "$out" ]; then log "$name already present"; return; fi
  log "$name fetching..."
  if curl -sSL --retry 3 --retry-delay 5 --max-time 3000 -C - -o "$out.part" "$url"; then
    mv "$out.part" "$out"
    log "$name ok ($(du -h "$out" | cut -f1))"
  else
    rm -f "$out.part"
    log "$name FAILED - the test that needs it will skip"
  fi
}

# 04 ledger-brain, 16 shelf-ops. Then run make_invoices.py and make_prices.py.
fetch "online-retail-ii" \
  "https://archive.ics.uci.edu/static/public/502/online+retail+ii.zip" \
  online_retail_ii.zip

# 11 watchtower
fetch "osv-pypi" \
  "https://osv-vulnerabilities.storage.googleapis.com/PyPI/all.zip" \
  osv_pypi.zip

# 03 one-desk, 05 comms-desk
fetch "ami-annotations" \
  "https://groups.inf.ed.ac.uk/ami/AMICorpusAnnotations/ami_public_manual_1.6.2.zip" \
  ami_manual.zip

# 02 ward-sync, 18 campus-ops
fetch "synthea" \
  "https://synthetichealth.github.io/synthea-sample-data/downloads/latest/synthea_sample_data_csv_latest.zip" \
  synthea_csv.zip

# 07 hire-desk, 09 hermes-home
fetch "locomo" \
  "https://raw.githubusercontent.com/snap-research/locomo/main/data/locomo10.json" \
  locomo10.json

# 10 kyc-floor, second sanctions source
fetch "un-sanctions" \
  "https://scsanctions.un.org/resources/xml/en/consolidated.xml" \
  un_consolidated.xml

log "done"
log "next: python scripts/make_invoices.py && python scripts/make_prices.py"
