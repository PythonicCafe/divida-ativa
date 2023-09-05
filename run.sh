#!/bin/bash

set -e

python divida_ativa.py download
python divida_ativa.py import
cat sql/urlid.sql | psql $DATABASE_URL
cat sql/divida_ativa.sql | psql $DATABASE_URL
