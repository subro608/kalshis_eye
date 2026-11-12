#!/bin/bash
# US state topology (us-atlas, pre-projected Albers USA) + Census congressional-district gazetteer (119th)
set -e
D=$(dirname "$0")/../data/geo; mkdir -p "$D"
curl -sfL -o "$D/states-albers-10m.json" https://cdn.jsdelivr.net/npm/us-atlas@3.0.1/states-albers-10m.json
curl -sfL -o "$D/cd_gaz.zip" https://www2.census.gov/geo/docs/maps-data/data/gazetteer/2025_Gazetteer/2025_Gaz_119CDs_national.zip
ls -la "$D"
