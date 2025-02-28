from migrationapi import Purger


env.cr.execute("SELECT id, model FROM ir_model")
results = env.cr.dictfetchall()

missing_model_names = [r["model"] for r in results if r["model"] not in env]
missing_model_ids = [str(r["id"]) for r in results if r["model"] not in env]
logging.info("Purging models: %s", ", ".join(missing_model_names))
with Purger(env.cr, "ir_model") as p:
    p.purge("id IN (%s)" % ",".join(missing_model_ids))
with Purger(env.cr, "ir_model_fields") as p:
    p.purge("relation IN ('%s')" % "','".join(missing_model_names))
