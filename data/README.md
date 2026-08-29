# Data Processing

This directory contains open-data processing work for the FIT5120 project.

## Folder structure

- `raw/` — original datasets stored locally or in team Google Drive and not committed to GitHub.
- `processed/` — cleaned and application-ready datasets.
- `scripts/` — repeatable data cleaning and spatial-processing scripts.
- `test/` — spatial lookup test fixtures.

## Iteration 1

### Designated Bushfire Prone Area (BPA)

Processed output:

`processed/bpa.parquet`

Purpose:

Given a latitude and longitude, determine whether the location falls inside a designated Bushfire Prone Area.

Processed CRS:

`EPSG:4326`