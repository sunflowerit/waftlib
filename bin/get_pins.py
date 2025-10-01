#!/usr/bin/env python
# Version: v.21.05.30
import os
import argparse
from string import Template
from subprocess import run, PIPE
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


current_heads = {}
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


def preprocess_merge(doc, repo, merge):
    remotes = doc[repo]["remotes"].keys()
    splitted_merge = [x for x in merge.split(" ") if x != ""]
    if splitted_merge[0] not in remotes:
        logger.debug("Invalid Remote on line: %s" % merge)
        raise ValueError
    repo_path = os.path.abspath(os.path.join(SRC_DIR, repo))
    if not os.path.exists(repo_path):
        logger.debug("build incomplete")
        exit()
    return repo_path, splitted_merge


def get_branchname(splitted_merge, merge_type):
    if merge_type in (1,3):
       return splitted_merge[1].replace("${ODOO_VERSION}", ODOO_VERSION)
    return False


def update_repo_commits_and_heads(repo_path, repo):
    os.chdir(repo_path)
    allrev = run(["git", "rev-list", "HEAD"], stdout=PIPE, stderr=PIPE)
    lrev = run(["git", "rev-parse", "HEAD"], stdout=PIPE, stderr=PIPE)
    # no return updating globals.
    current_heads[repo] = lrev.stdout.decode("utf-8").replace("\n", "").replace("'", "")
    all_commits[repo] = allrev.stdout.decode("utf-8").replace("\n", ",").split(",")


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


def process_depth(splitted_merge, branchname,
                  main_branch, main_branch_name, repo_path):
    os.chdir(repo_path)
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
    except:
        # if for some reason we have no common ancestor or rev-list errors out
        import pudb
        pudb.set_trace()
        return 5000

def process_merge(doc, repo, merge, index):
    repo_path, splitted_merge = preprocess_merge(doc, repo, merge)
    # will update all_commits[repo] and current_heads[repo] globals.
    update_repo_commits_and_heads(repo_path, repo)
    env = dict(os.environ, **doc.get("ENV", {}))
    wd = os.getcwd()
    merge_type = get_merge_type(splitted_merge, repo)
    if merge_type == 3:
        # merge_type #3
        branchname = get_branchname(splitted_merge, merge_type)
        current_pin = (
            run(
                [
                    "git",
                    "merge-base",
                    "HEAD",
                    "".join([splitted_merge[0], "/", branchname]),
                ],
                stdout=PIPE,
                stderr=PIPE,
            )
            .stdout.decode("utf-8")
            .replace("\n", "")
        )
        if splitted_merge[2] != current_pin:
            print("\t\t Updating pin on repo %s , branchname %s, from %s to %s" % 
                  (repo , branchname, splitted_merge[2], current_pin ))
            splitted_merge[2] = current_pin
    if merge_type == 2:
        # <remote> <PIN> merge_type line
        splitted_merge[1] = current_heads.get(repo, "")
    if merge_type == 1:
        # <remote> <branch> merge_type line
        # merge_type #1
        branchname = get_branchname(splitted_merge, merge_type)
        if branchname:
            current_pin = (
                run(
                    [
                        "git",
                        "merge-base",
                        "HEAD",
                        "".join([splitted_merge[0], "/", branchname]),
                    ],
                    stdout=PIPE,
                    stderr=PIPE,
                )
                .stdout.decode("utf-8")
                .replace("\n", "")
            )
            splitted_merge.append(current_pin)
            print("\t\t Adding pin to previously unpinned branch:  on repo %s , branchname %s,  %s" % 
                  (repo , branchname,  current_pin )
            )
    os.chdir(wd)
    if merge_type == 0:
        logger.debug("Invalid Repo of unrecognized merge_type: %s" % splitted_merge)
        raise ValueError
    return " ".join(splitted_merge)


def main():
    """
    parsing directly repos.yaml, if something is not in addons.yaml, branch will still
    be in folder, but may not be included in addons. Nothing changes.
    """
    with open(REPOS_YAML) as yaml_file:
        yaml_substituted = Template(yaml_file.read())
        yaml_substituted = yaml_substituted.substitute(os.environ)
        for doc in yaml.safe_load_all(yaml_substituted):
            for repo in doc:
                print("===>processing repo %s" % repo)
                repo_min_depth[repo] = 0
                if repo in {PRIVATE, "ONLY", "ENV"}:
                    continue
                target = doc[repo].get("target") or False
                has_target = target and True or False
                processed_target = False
                if has_target:
                    doc[repo]["target"] = process_merge(doc, repo, target, 0)
                # main branch is defined as target or in absence of target, merge[0]
                main_branch = target or doc[repo]["merges"][0]
                main_branch = split_line(main_branch)
                merge_type = get_merge_type(main_branch, repo)
                main_branch_name = get_branchname(main_branch, merge_type )
                for merge in doc[repo]["merges"]:
                    print("\t===>processing merge %s of repo %s" % (merge, repo))
                    index = doc[repo]["merges"].index(merge)
                    # if target exists and only base is selected , just pin target.
                    if (
                        (index > 0 or (has_target and index >= 0))
                        and bool(args.only_base)
                    ) == True:
                        continue
                    doc[repo]["merges"][index] = process_merge(doc, repo, merge, index)
                    repo_path, splitted_merge = preprocess_merge(doc, repo, merge)
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
                            waft_depth = doc[repo]["defaults"].get("depth")
                            if waft_depth == "${WAFT_DEPTH_MERGE}":
                                # waft_depth_merge, if not specified in env defaults to 100
                                waft_depth = os.environ.get("WAFT_DEPTH_MERGE") or 100
                            if waft_depth == "${WAFT_DEPTH_DEFAULT}":
                                waft_depth = os.environ.get("WAFT_DEPTH_DEFAULT") or 1
                            waft_depth = int(waft_depth)
                            if repo_min_depth[repo] > waft_depth:
                                print("\t\t Increasing depth of %s from %s to %s" % (
                                    repo, doc[repo]["defaults"]["depth"], 
                                    str(repo_min_depth[repo]))
                                )
                                doc[repo]["defaults"]["depth"] = str(repo_min_depth[repo])

            CustomDumper.add_representer(
                dict, CustomDumper.represent_dict_preserve_order
            )
            print("\n\n\n====================SCRIPT RESULTS======================\n\n\n")
            print(yaml.dump(doc, Dumper=CustomDumper))


if os.path.isfile(REPOS_YAML) and __name__ == "__main__":
    main()
else:
    logger.debug("no %s  repository file found" % REPOS_YAML)
    raise ValueError

