# PostGIS acceptance test — gis2dgs

La prueba de aceptación real permanece en:

`tests/integration/test_postgis_real_v061.py`

Requiere una base PostGIS accesible y la variable:

`GIS2DGS_POSTGIS_TEST_URL`

Sin esa variable la prueba se omite de forma explícita y no se sustituye por un mock.
