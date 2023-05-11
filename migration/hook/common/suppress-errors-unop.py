# Just run Odoo once. It may cause a view validation error for some
# for some modules. For some reason the error doesn't happen anymore
# after it occured once, so we trigger it on purpose.
#
# X-Supports: 13.0 14.0
# X-Session-Unopened: true

for i in range(3):
    try:
        __session.open()
        __session.close()
        break
    except Exception as e:
        print("Suppressing Error: %s" % e)