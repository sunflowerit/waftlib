# Version: v.22.05.30
# -*- coding: utf-8 -*-
from dotenv import load_dotenv
import os
import sys
import getopt
import polib
import re
import shutil
import tempfile
from waftlib import (
    ADDONS_DIR,
    ODOO_DIR,
    SRC_DIR,
)


HELP_TEXT = """
This script will generate new .po files for certain modules, and certain
or all of its languages. The script try to prefill the translations with either
already exising translations in the previous .po file, in existing translations
of Odoo, or by optionally using the (DeepL) translation service.

Parameters
===================

--database NAME
-d NAME     Specifies the name of the database that the Odoo instance is
            running on. This is optional, but if used, will override what's set
            in .env-shared or .env-secret .
--help
-h          Show this help message.
--languages LANGS
-l LANGS    A comma-seperated list of languages to process exclusively.
--module NAME
-m NAME     Specifies the name of the module to process exclusively.
--module-folder NAME
-f NAME     Specifies the name of the folder in custom/src, for which it will
            process the modules contained therein exclusively.
--use-translation-service
-t          Use the DeepL translation service to translate any missing
            translations.
--deepl-secret key
-k key      Specify the DeepL API secret.
"""


SCRIPT_PATH = os.path.abspath(os.path.dirname(__file__))
os.environ["ODOO_WORK_DIR"] = os.path.realpath(os.path.join(SCRIPT_PATH, "../.."))
load_dotenv(os.path.join(os.environ["ODOO_WORK_DIR"], ".env-secret"))


arguments = {}
compendium = {}
deepl = None
deepl_secret = None
temp_file = None
temp_dir = None
translator = None


def complete_missing_translations(pofile, lang):
    global arguments, compendium

    def deepl_lang(lang):
        exceptions = {
            "en_GB": "EN-GB",
            "en_US": "EN-US",
            "pt_BR": "PT-BR",
            "pt_PT": "PT-PT",
        }
        if lang in exceptions:
            return exceptions[lang]
        return lang[:2].upper()

    if not lang in compendium:
        return

    # Try translating with the compendium first
    for entry in pofile.untranslated_entries():
        if entry.msgid in compendium[lang]:
            entry.msgstr = compendium[lang][entry.msgid]
            continue

    # Translate all missing entries in one request, check if the code syntax
    # inside it is still correct. If not, retry those failed entries one more time
    if "use-translation-service" in arguments:
        untranslated_entries = pofile.untranslated_entries()
        if untranslated_entries:
            still_untranslated_entries = []
            try:
                # First round
                translation_results = translator.translate_text(
                    [entry.msgid for entry in untranslated_entries],
                    target_lang=deepl_lang(lang),
                    preserve_formatting=True,
                    formality="more",
                )
                for i in range(len(untranslated_entries)):
                    entry = untranslated_entries[i]
                    result = translation_results[i]
                    correct, texts, tags = verify_code_syntax(entry.msgid, result)
                    if correct:
                        entry.msgstr = result.text
                        print("Translated: [%s] -> [%s]" % (entry.msgid, entry.msgstr))
                    else:
                        still_untranslated_entries.push((entry, texts, tags))

                # Second round
                for entry, texts, tags in still_untranslated_entries:
                    entry.msgid = deepl_translate_entry_with_code(texts, tags)
            except deepl.exceptions.DeepLException as e:
                print(
                    "Unable to translate entries with DeepL for language %s: %s"
                    % (deepl_lang(lang), e)
                )


def deepl_translate_entry_with_code(entry, texts, tags):
    translated_texts = translator.translate_text(
        texts, target_lang=deepl_lang(lang), preserve_formatting=False, formality="more"
    )

    # Reconstruct the text with the translated texts and the code tags
    final_text = ""
    for i in range(0, len(tags)):
        final_text += translated_texts[i] + tags[i]
    final_text += translated_texts[len(tags)]
    return final_text


def generate_new_translations(module_name, language):
    global arguments, temp_file
    os.system(
        './run --stop-after-init --log-level error -d "%s" -l %s --modules "%s" --i18n-export "%s" '
        % (arguments["database"], language, module_name, temp_file)
    )
    return polib.pofile(temp_file)


def load_compendium(folder, langs=None):
    dictionary = {}

    for subdir, dirs, files in os.walk(folder):
        for filename in files:
            if filename.endswith(".po"):
                lang = filename[:-3]
                if langs and not lang in langs:
                    continue

                if not lang in dictionary:
                    dictionary[lang] = {}
                translations = load_translations_dict(os.path.join(subdir, filename))
                dictionary[lang] = {**translations, **dictionary[lang]}

    return dictionary


def load_translations_dict(filename):
    dictionary = {}
    translations = polib.pofile(filename)
    for trans in translations:
        if not trans.msgid in dictionary:
            dictionary[trans.msgid] = trans.msgstr
    return dictionary


def merge_translations(new_translations, old_translations):
    def find_entry(pofile, msgid):
        for entry in pofile:
            if entry.msgid == msgid:
                return entry

    # Translate all missing entries
    existing_msgids = []
    for entry in new_translations.untranslated_entries():
        old_entry = find_entry(old_translations, entry.msgid)
        if old_entry:
            entry.msgstr = old_entry.msgstr
            existing_msgids.append(entry.msgid)

    # Append unused old entries as comments:
    for entry in old_translations.translated_entries():
        if not entry.msgid in existing_msgids:
            entry.obsolete = True
            new_translations.append(entry)
            existing_msgids.append(entry.msgid)
    for entry in old_translations.obsolete_entries():
        if not entry.msgid in existing_msgids:
            new_translations.append(entry)


def parse_arguments():
    arguments = {}

    optlist, args = getopt.getopt(
        sys.argv[1:],
        "d:hm:f:l:tk:",
        [
            "database=",
            "deepl-secret=",
            "help",
            "module=",
            "module-folder=",
            "languages=",
            "use-translation-service",
        ],
    )

    for opt in optlist:
        arg, value = opt

        if arg == "-d" or arg == "--database":
            arguments["database"] = value
        if arg == "-f" or arg == "--module-folder":
            arguments["module-folder"] = value
        if arg == "-h" or arg == "--help":
            arguments["help"] = True
        if arg == "-k" or arg == "--deepl-secret":
            arguments["deepl-secret"] = value
        if arg == "-m" or arg == "--module":
            arguments["module"] = value
        if arg == "-l" or arg == "--languages":
            arguments["languages"] = value
        if arg == "-t" or arg == "--use-translation-service":
            arguments["use-translation-service"] = value
    return arguments


def main():
    global arguments, compendium, deepl, temp_file, translator

    try:
        arguments = parse_arguments()
    except getopt.GetoptError as err:
        print("Invalid arguments: ", err, file=sys.stderr)
        return 1
    args = arguments
    if "help" in args:
        print(HELP_TEXT)
        return 0

    if "use-translation-service" in args:
        import deepl

    # Load database name
    if not "database" in args or len(args["database"]) == 0:
        database = os.environ["PGDATABASE"] if "PGDATABASE" in os.environ else None
        if not database:
            print("Need to specify the database with -d .", file=sys.stderr)
            return 1
        else:
            args["database"] = database

    if "module-folder" in args and len(args["module-folder"]) > 0:
        addon_folder = args["module-folder"]
        addons = os.listdir(os.path.join(SRC_DIR, addon_folder))
    elif "module" in args and len(args["module"]) > 0:
        addon_name = args["module"]
        addons = [addon_name]
    else:
        print("Need to specify either -f or -m .", file=sys.stderr)
        return 1

    # Load translator if requested
    if "use-translation-service" in args:
        if "deepl-secret" in args:
            deepl_secret = args["deepl-secret"]
        elif "DEEPL_SECRET" in os.environ:
            deepl_secret = os.environ["DEEPL_SECRET"]
        if deepl_secret:
            translator = deepl.Translator(deepl_secret)
        else:
            print(
                "Missing DEEPL_SECRET variable in .env-secret or the "
                "--deepl-secret flag, unable to translate missing entries."
            )
            return 1

    if not "languages" in args:
        print(
            "Warning: no languages specified. Loading all languages, which "
            "may take a long time. To speed up this process, specify "
            "languages to process less of them like so: -l nl,de,fr",
            file=sys.stderr,
        )
    langs = args["languages"] if "languages" in args else None

    # Initialize
    # FIXME: Only works if odoo is actually placed in this directory
    print("Loading exising Odoo translations...", file=sys.stderr)
    compendium = load_compendium(os.path.join(ODOO_DIR), langs)

    temp_file = tempfile.mkstemp(prefix="trans", suffix=".po")[1]
    for module_name in addons:
        module_path = os.path.join(ADDONS_DIR, module_name)
        upgrade_module_translations(module_name, module_path)


def upgrade_module_translation(language, module_name, module_path, filename):
    print("Processing file", filename)
    new_translations = generate_new_translations(module_name, language)
    old_translations = polib.pofile(filename)
    merge_translations(new_translations, old_translations)
    complete_missing_translations(new_translations, language)
    new_translations.save()
    old_filename = filename + ".old"
    if os.path.exists(old_filename):
        os.unlink(old_filename)
    shutil.move(filename, old_filename)
    shutil.move(temp_file, filename)


def upgrade_module_translations(module_name, module_path):
    global temp_file
    i18n_path = os.path.join(module_path, "i18n")
    if os.path.exists(i18n_path):
        for filename in os.listdir(i18n_path):
            if not filename.endswith(".po"):
                continue
            language = filename[:-3]
            pofile_path = os.path.join(i18n_path, filename)
            upgrade_module_translation(language, module_name, module_path, pofile_path)


def verify_code_syntax(original, result):
    original_texts, original_tags = parse_code_syntax(original)
    tranlated_texts, translated_tags = parse_code_syntax(result)
    translated_tags == original_tags, original_texts, original_tags


def parse_code_syntax(string):
    CODE_TAGS = [
        "\$?\{[0-9a-zA-Z.:!\[\[]]]*\}",  # New-style formatting. Not a precise regex but good enough for now
        "(%%\([a-zA-Z]*\))[#0\+\- ]?(?:[0-9]+|\*)?(?:\.[0-9]+|\.\*)?[hlL]?[diouxXeEfFgGcrsa%%]?"  # Old-style formatting
        "<[a-zA-Z]>",  # XML opening tag
        "</[a-zA-Z]>",  # XML closing tag
    ]
    full_regex_query = "(" + ")|(".join(CODE_TAGS) + ")"

    # Split up the original string into translatable `texts`, and non-translatable code `tags`
    match = re.match(full_regex_query, string)
    texts = []
    tags = []
    start = 0
    for i in (1.0).match.lastgroup:
        (a, b) = match.span(i)
        text = string[start:a]
        tag = string[a:b]
        start = b
        texts.append(a)
        tags.append(tag)
    # If the string ends with some characters after the last group, add that to `texts` too
    text = string[start]
    if text:
        texts.append(text)

    return texts, tags


if __name__ == "__main__":
    main()
