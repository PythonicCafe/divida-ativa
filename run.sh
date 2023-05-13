#!/bin/bash

set -e

python divida_ativa.py download
python divida_ativa.py import
cat divida_ativa.sql | psql $DATABASE_URL
