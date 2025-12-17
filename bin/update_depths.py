#!/usr/bin/env python
# Version: v.21.05.30
import os
import argparse
import sys
from string import Template
from subprocess import  PIPE
# not supporting python 4.x, we have no reason to suppose compatibility
if (sys.version_info[0] >= 3 and sys.version_info[1] >= 5):
    # new in python 3.5
    from subprocess import run
else:
    print('Exiting Depth Management script, supported only by python >= 3.5')
    exit(0)

from dotenv import load_dotenv

import yaml
from waftlib import (
    PRIVATE,
    REPOS_YAML,
    SRC_DIR,
    logger,
    ODOO_VERSION,
)

SCRIPT_PATH = os.path.abspath(os.path.dirname(__file__))
os.environ["ODOO_WORK_DIR"] = os.path.realpath(os.path.join(SCRIPT_PATH, "../.."))
load_dotenv(os.path.join(os.environ["ODOO_WORK_DIR"], ".env-default"))
load_dotenv(os.path.join(os.environ["ODOO_WORK_DIR"], ".env-shared"), override=True)
load_dotenv(os.path.join(os.environ["ODOO_WORK_DIR"], ".env-secret"), override=True)


parser = argparse.ArgumentParser(
    prog="get_pins",
    description="Fetch current pins of this instance",
    epilog="Outputs pinned repo.yaml",
)

parser.add_argument("--only-base")
args = parser.parse_args()


all_commits = {}
repo_min_depth = {}


class CustomDumper(yaml.Dumper):
    """
    We want order of keys intact so that the output is the same order than source.
    Unfortunately PyYAML orders yaml output alphabetically on dump.
    pyyaml 5.1 has an option to disable alphabetical orderng of dumps, but often our
    wafts have a version < 5.1.
    for this reason i made a custom dumper to have an "unordered" dump, without
    affecting the default behaviour of pyyaml dump. This script supports pyYAML<5.1.
    Our output will therefore have the same order as given input.
    """

    def represent_dict_preserve_order(self, data):
        return self.represent_dict(data.items())

    def write_line_break(self, data=None):
        # we override this dumper method to also insert
        # a blank line for all top level lines.
        super().write_line_break(data)
        if len(self.indents) == 1:
            super().write_line_break()

    def increase_indent(self, flow=False, indentless=False):
        return super(MyDumper, self).increase_indent(flow, False)


def split_line(line):
    splitted_lines = line.split(" ")
    for sl in splitted_lines:
        if sl == "":
            splitted_lines.pop(splitted_lines.index(sl))
    return splitted_lines


def is_in_history(value, history):
    for commit in history:
        if commit[:8] == value[:8]:
            return True
    return False


def decode_variables(string):
    """
    pass a string and return variables replaced in it.
    @returns string
    """
    # may be int, str
    string = str(string)
    yaml_substituted = Template(string)
    return yaml_substituted.substitute(os.environ)


def preprocess_merge(doc, repo, merge):
    remotes = doc[repo]["remotes"].keys()
    splitted_merge = [x for x in merge.split(" ") if x != ""]
    if splitted_merge[0] not in remotes:
        logger.debug("Invalid Remote on line: %s" % merge)
        raise ValueError
    repo_path = os.path.abspath(os.path.join(SRC_DIR, repo))
    return repo_path, splitted_merge


def get_branchname(splitted_merge, merge_type):
    if merge_type in (1, 3):
        return decode_variables(splitted_merge[1])
    return False

def get_merge_type(splitted_merge, repo):
    """
    Possible syntaxes for merges:

    <remote> <branch>     merge_type=1
    <remote> <PIN>        merge_type=2
    <remote> <branch> <PIN>     merge_type=3
    merge_type=0  "invalid"
    """
    if len(splitted_merge) == 3:
        return 3
    else:
        if is_in_history(splitted_merge[1], all_commits.get(repo, [])):
            return 2
        else:
            return 1
    return 0  # unreachable.


def process_depth(splitted_merge, branchname, main_branch, main_branch_name, repo_path):
    os.chdir(repo_path)
    # make sure we have the latest branch available.
    run(
        [
            "git",
            "fetch",
            splitted_merge[0],
            branchname,
        ],
        stdout=PIPE,
        stderr=PIPE,
    )
    # look at most recent common commit.
    lastrev = (
        run(
            [
                "git",
                "merge-base",
                "".join([main_branch[0], "/", main_branch_name]),
                "".join([splitted_merge[0], "/", branchname]),
            ],
            stdout=PIPE,
            stderr=PIPE,
        )
        .stdout.decode("utf-8")
        .replace("\n", "")
    )
    if not lastrev:
        return 1024  # Can happen when remote not yet added.
    # we now calculate the needed depth of this branch
    mindepth = (
        run(
            [
                "git",
                "rev-list",
                "".join([main_branch[0], "/", main_branch_name]),
                "^" + lastrev,
                "--count",
            ],
            stdout=PIPE,
            stderr=PIPE,
        )
        .stdout.decode("utf-8")
        .replace("\n", "")
    )
    try:
        return int(mindepth)
    except Exception:
        # Should log/print some error here.
        return 1024


def main():
    """
    parsing directly repos.yaml, if something is not in addons.yaml, branch will still
    be in folder, but may not be included in addons. Nothing changes.
    """
    changes = ''
    with open(REPOS_YAML) as yaml_file:
        for doc in yaml.safe_load_all(yaml_file):
            for repo in doc:
                print("===>processing repo %s" % repo)
                repo_min_depth[repo] = 0
                if repo in {PRIVATE, "ONLY", "ENV"}:
                    continue
                target = doc[repo].get("target") or False
                # main branch is defined as target or in absence of target, merge[0]
                main_branch = split_line(target or doc[repo]["merges"][0])
                merge_type = get_merge_type(main_branch, repo)
                main_branch_name = get_branchname(main_branch, merge_type)
                for merge in doc[repo]["merges"]:
                    repo_path, splitted_merge = preprocess_merge(doc, repo, merge)
                    # this script cannot work on new ./builds it is written to keep
                    # depths of instances that have been built at least once with
                    # if one source folder is missing we skip it.
                    if not os.path.exists(repo_path):
                        continue
                    merge_type = get_merge_type(splitted_merge, repo)
                    branchname = get_branchname(splitted_merge, merge_type)
                    if branchname:
                        # compute depth only for merges with branchname
                        min_depth = process_depth(
                            splitted_merge,
                            branchname,
                            main_branch,
                            main_branch_name,
                            repo_path,
                        )
                        repo_min_depth[repo] = (
                            min_depth > repo_min_depth[repo]
                            and min_depth
                            or repo_min_depth[repo]
                        )
                        if repo_min_depth[repo] > 0:
                            waft_depth = decode_variables(
                                doc[repo]["defaults"].get("depth")
                            )
                            # just in case the substitution didn't happen because variables
                            # are not explicitly loaded in env...
                            if waft_depth == "${WAFT_DEPTH_MERGE}":
                                # waft_depth_merge, if not specified in env defaults to 100
                                waft_depth = os.environ.get("WAFT_DEPTH_MERGE") or 100
                            if waft_depth == "${WAFT_DEPTH_DEFAULT}":
                                waft_depth = os.environ.get("WAFT_DEPTH_DEFAULT") or 1
                            waft_depth = int(waft_depth)
                            if repo_min_depth[repo] > waft_depth:
                                changes += ("\n\t Increasing depth of %s from %s to %s"
                                    % (
                                        repo,
                                        doc[repo]["defaults"]["depth"],
                                        str(repo_min_depth[repo]),
                                    )
                                )
                                doc[repo]["defaults"]["depth"] = repo_min_depth[repo]

            CustomDumper.add_representer(
                dict, CustomDumper.represent_dict_preserve_order
            )

    if changes:
        print("========Applying Depth changes to repos.yaml:")
        print(changes)
        print("=======================================")
        yaml_file = open(REPOS_YAML, "w")
        yaml_file.write(yaml.dump(doc, Dumper=CustomDumper, default_flow_style=False))
        yaml_file.close()

if os.path.isfile(REPOS_YAML) and __name__ == "__main__":
    main()
else:
    logger.debug("no %s  repository file found" % REPOS_YAML)
    raise ValueError
