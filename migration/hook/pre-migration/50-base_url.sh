if [ -z "$HOST" ]; then
	psql -d $PGDATABASE -c "UPDATE ir_config_parameter SET value = '$HOST' WHERE key = 'web.base.url'"
fi
