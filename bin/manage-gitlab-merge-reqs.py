# pip install requests
# pip install yaml
# pip install ruamel.yaml

import requests
import yaml
from ruamel.yaml import YAML
import argparse


# How to use it:
# python gitlab-script.py glpat-dummyToken789000000 https://gitlab.test.com/api/v4 155 repos.yaml OCA/test


def fetch_and_update_yaml(GITLAB_TOKEN, GITLAB_API_ENDPOINT, PROJECT_IDS,
                          YAML_FILE, REPO_SECTIONS):
    headers = {'Private-Token': GITLAB_TOKEN}
    s_yaml = YAML()
    # print(f"GITLAB TOKEN: {GITLAB_TOKEN} "
    #       f"URL ENDPOINT: {GITLAB_API_ENDPOINT} "
    #       f"PROJECT IDS: {PROJECT_IDS.split(',')} "
    #       f"REPO SECTIONS: {REPO_SECTIONS.split(',')}")
    for PROJECT_ID in PROJECT_IDS.split(','):
        # 1. Fetch merged branches using GitLab API
        try:
            response = requests.get(
                f'{GITLAB_API_ENDPOINT}/projects/{PROJECT_ID}/merge_requests?state=merged',
                headers=headers)
            response.raise_for_status()
        except requests.HTTPError as err:
            print(f"HTTP error occurred: {err}")
        else:
            branches_data = response.json()

            merged_branches = [b['source_branch'] for b in branches_data]
            merged_lst_branches = '\n'.join(merged_branches)
            print(f"LIST OF MERGED BRANCHES:\n============================\n"
                  f" {merged_lst_branches}\n\n")

            # 2. Load YAML file
            with open(YAML_FILE, 'r') as stream:
                # data = yaml.safe_load(stream)
                data = s_yaml.load(stream)

            for REPO_SECTION in REPO_SECTIONS.split(','):
                # 3. Remove merged branches from YAML for each repo section
                branches_in_yaml = data[REPO_SECTION]['merges']
                found_mr_yaml = ''.join(branches_in_yaml)
                print(f'FOUND MERGE REQUESTS ON {YAML_FILE} UNDER '
                      f'{REPO_SECTION}:'
                      f'\n===================================================\n'
                      f' {found_mr_yaml}\n')

                for branch in branches_in_yaml.copy():
                    branch_name = branch.split()[-1]
                    if branch_name in merged_branches:
                        print(f"Removing Branch: {branch_name} its already "
                              f"merged")
                        branches_in_yaml.remove(branch)

                # 4. Save updated YAML
                with open(YAML_FILE, 'w') as stream:
                    s_yaml.dump(data, stream)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description='Process branches with GitLab API and update a YAML file.')
    parser.add_argument('GITLAB_TOKEN', type=str,
                        help='Your GitLab private token')
    parser.add_argument('GITLAB_API_ENDPOINT', type=str,
                        help='GitLab API endpoint, e.g., https://gitlab.com/api/v4')
    parser.add_argument('PROJECT_IDS', type=str,
                        help='Comma-separated list of project IDs or URL-encoded namespace/project names')
    parser.add_argument('YAML_FILE', type=str, help='Path to your YAML file')
    parser.add_argument('REPO_SECTIONS', type=str,
                        help='Comma-separated list of repo sections in the '
                             'YAML to process, e.g., OCA/web,'
                             'ThinkTankOdoo/main')

    args = parser.parse_args()

    fetch_and_update_yaml(args.GITLAB_TOKEN, args.GITLAB_API_ENDPOINT,
                          args.PROJECT_IDS, args.YAML_FILE, args.REPO_SECTIONS)
