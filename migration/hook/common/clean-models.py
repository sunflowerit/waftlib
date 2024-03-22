from migrationapi import purge_model


missing_models = []
env.cr.execute("SELECT id, model FROM ir_model")
results = env.cr.dictfetchall()
for result in results:
    model_id = result['id']
    model_name = result['model']

    if not model_name in env:
        logging.info("Purging model %s...", model_name)
        purge_model(env, model_id)
        continue
