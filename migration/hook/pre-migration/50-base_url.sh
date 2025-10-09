if [ ! -z "$FULL_DOMAIN" ]; then
	psql -d $PGDATABASE -c "UPDATE ir_config_parameter SET value = 'https://$FULL_DOMAIN' WHERE key = 'web.base.url'"
fi
