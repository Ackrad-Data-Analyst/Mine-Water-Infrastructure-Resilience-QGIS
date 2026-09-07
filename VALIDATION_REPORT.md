# Validation report

## Release

- Product: Mine Water & Infrastructure Resilience — QGIS 1.0
- Plugin provider ID: `mineresilience`
- Primary algorithm ID: `mineresilience:mine_resilience_screening`
- Minimum QGIS version: 3.44

## Automated checks completed

- Python syntax compilation: passed.
- Pure engineering calculations: passed.
- Workspace/source-protection helpers: passed.
- Copernicus tile selection helpers: passed.
- ESA WorldCover tile-grid helpers: passed.
- OpenStreetMap response conversion helpers: passed.
- Install ZIP structure and required-file validation: passed.
- ZIP CRC/integrity test: passed.
- Total synthetic unit tests: 13 passed, 0 failed.

## Environment limitation

QGIS is not installed in the build environment, so a live QGIS GUI/Processing execution could
not be performed here. The plugin includes a Preflight algorithm that refuses a run when QGIS,
Native, GDAL, GRASS, or folder-write requirements are not met. A controlled workstation pilot
must be completed before operational deployment. This limitation is not hidden in the release.

## Required commissioning test

1. Install the ZIP in QGIS 3.44+.
2. Run Preflight and retain `MINE_RESILIENCE_QGIS_PREFLIGHT.json`.
3. Run a small synthetic/manual DEM case first.
4. Confirm CRS, DEM units, flow accumulation sign/convention, stream threshold, and output counts.
5. Inspect at least five ranked crossings against imagery/terrain.
6. Replace public screening layers with authoritative mine/survey inputs before engineering use.
