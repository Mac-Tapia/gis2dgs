$ErrorActionPreference = "Stop"

python scripts/audit_release.py --output output/audit/audit_v081.json
pytest --cov=gis2dgs --cov-report=term-missing
