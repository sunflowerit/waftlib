# X-Modules: mass_editing

exec(open('build-12.0/auto/addons/mass_editing/migrations/12.0.2.0.1/pre-migration.py').read())
migrate(env.cr, '13.0')
exec(open('build-12.0/auto/addons/mass_editing/migrations/12.0.2.0.2/pre-migration.py').read())
migrate(env.cr, '13.0')
exec(open('build-12.0/auto/addons/mass_editing/migrations/12.0.2.0.1/post-migration.py').read())
migrate(env.cr, '13.0')
exec(open('build-12.0/auto/addons/mass_editing/migrations/12.0.2.0.2/post-migration.py').read())
migrate(env.cr, '13.0')