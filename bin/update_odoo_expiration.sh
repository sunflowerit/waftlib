#!/bin/bash

# Check arguments
if [ "$#" -lt 2 ]; then
    echo "Usage: $0 DB_NAME DB_USER [DB_HOST]"
    exit 1
fi

# Assign arguments with default values
DB_NAME="$1"
DB_USER="$2"
DB_HOST="${3:-localhost}"  # Default to localhost if not provided

# Execute the SQL commands
psql -h "$DB_HOST" -U "$DB_USER" -d "$DB_NAME" -a -f odoo_update_db_dates.sql
