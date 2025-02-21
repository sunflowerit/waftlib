# Uninstall all the modules listed in
# etc/uninstall-modules.txt
import os
import sys
import traceback


def load_all_dependent_modules(module_name):
    dependent_modules = load_dependent_modules(module_name)
    for dependent_module in dependent_modules:
        sub_dependent_modules = load_all_dependent_modules(dependent_module)
        for sub_dependent_module in sub_dependent_modules:
            if not sub_dependent_module in dependent_modules:
                dependent_modules.append(sub_dependent_module)
    return dependent_modules


def load_dependent_modules(module_name):
    env.cr.execute(
        """
        SELECT immd.name
        FROM ir_module_module_dependency AS immd
        LEFT JOIN ir_module_module AS imm ON immd.module_id = imm.id
        WHERE imm.name = %s
    """,
        [module_name],
    )
    return [r[0] for r in env.cr.fetchall()]


def reorder_modules(module_names):
    if not module_names:
        return module_names

    new_list = [module_names[0]]
    for i in range(1, len(module_names)):
        module_name = module_names[i]
        dependent_modules = load_all_dependent_modules(module_name)

        print("Dependent modules of %s: %s" % (module_name, dependent_modules))

        # Insert the module in the new list where there are no modules dependent
        # on it above it in the list
        position = len(new_list)
        for j in reversed(range(len(new_list))):
            # print("X", new_list[j], new_list[j] in dependent_modules)
            if new_list[j] in dependent_modules:
                print(
                    "%s is dependent of %s, so will be inserting it at: %i"
                    % (new_list[j], module_name, j)
                )
                position = j
        # print("INSERT AT %i", j)
        new_list.insert(position, module_name)

    return new_list


def uninstall_modules_downstream(module):
    if module.state == "uninstalled":
        return

    env.cr.execute(
        """
       SELECT module_id FROM ir_module_module_dependency WHERE name = %s
    """,
        [module.name],
    )
    dependencies = [x[0] for x in env.cr.fetchall()]
    for dependency_id in dependencies:
        dependency = env["ir.module.module"].browse(dependency_id)
        if dependency.state != "uninstalled":
            uninstall_modules_downstream(dependency)
    if module.state != "uninstalled":
        print("Un (%s)" % module.state, module.name)
        module.button_immediate_uninstall()
        env.cr.commit()


try:
    file = open(MIGRATION_PATH + "/etc/uninstall-modules.txt", "r")
except Exception as e:
    if type(e) == "FileNotFoundError":
        logging.warning(
            "%s/etc/uninstall-modules.txt doesn't exist, no modules will be uninstalled.",
            MIGRATION_PATH,
        )
        exit(0)
    if isinstance(e, IOError):
        logging.warning(
            "%s/etc/uninstall-modules.txt can't be opened, no modules will be uninstalled",
            MIGRATION_PATH,
        )
        traceback.print_exc()
        exit(0)
    # else:
    logging.error("Unable to open %s/etc/uninstall-modules.txt:", MIGRATION_PATH)
    traceback.print_exc()
    exit(1)

module_names = []
for line in file:
    module_name = line.strip()
    if module_name:
        module_names.append(module_name)

logging.info(
    "Uninstalling %i modules..." % len(module_names),
)


def uninstall_module_list(module_names):
    to_uninstall = []
    modules = [env["ir.module.module"].search([("name", "=", m)]) for m in module_names]
    for module in modules:
        if not module:
            continue
        if module.state in ("installed", "to upgrade"):
            print("Going to uninstall %s (%s)" % (module.name, module.state))
            to_uninstall.append(module)
        elif module.state == "uninstalled":
            continue
        else:
            raise Exception(
                "Unexpected module state for module %s: %s"
                % (module.name, module.state)
            )

    for module in to_uninstall:
        print("Uninstalling %s (%s)..." % (module.name, module.state))
        uninstall_modules_downstream(module)
    return len(to_uninstall)


reordered_list = reorder_modules(module_names)
uninstall_module_list(reordered_list)
