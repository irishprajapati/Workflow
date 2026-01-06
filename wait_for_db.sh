#!/bin/sh
# wait_for_db.sh

echo "Waiting for PostgreSQL to be ready..."
while ! nc -z $DB_HOST $DB_PORT; do
  sleep 1
done
echo "PostgreSQL is ready!"

exec "$@"
