#!/bin/bash

# Default values
DB_HOST="localhost"
DB_PORT="5432"

# Check arguments
if [ "$#" -lt 2 ]; then
    echo "Usage: $0 DB_NAME DB_USER [DB_HOST] [DB_PORT]"
    exit 1
fi

# Assign arguments
DB_NAME="$1"
DB_USER="$2"

# Check if DB_HOST and DB_PORT are provided
if [ ! -z "$3" ]; then
    DB_HOST="$3"
fi

if [ ! -z "$4" ]; then
    DB_PORT="$4"
fi

# Get the database size
DB_SIZE=$(psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -t -c "SELECT pg_size_pretty(pg_database_size('$DB_NAME'));")

# Echo out the size
echo "Size of $DB_NAME: $DB_SIZE"
