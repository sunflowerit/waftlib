# As part of migrating partner_coc, we need to clean up the temporary
# column company_registry_temp that was created.

# At this point, parter_coc is already uninstalled if it was installed
# before, so we can't use the X-Modules condition unfortunately. So we
# just check manually.
env.cr.execute(
    """
    SELECT * FROM information_schema.columns
    WHERE table_name = 'res_partner' AND
          column_name = 'company_registry_temp'
    """
)
if not env.cr.fetchone():
    exit(1)


env.cr.execute(
    """
    UPDATE res_partner SET company_registry = company_registry_temp
    WHERE company_registry_temp IS NOT NULL
    """
)
env.cr.execute(
    """
    ALTER TABLE res_partner DROP COLUMN company_registry_temp
    """
)
env.cr.commit()
