# Description: Count the lines of codes added and deleted by all authors in Git repositories
# Author: Damon Guo guosuiyu@gmail.com

# pip install gitpython python-gitlab
import gitlab
import csv
import os
import re
from git import Repo

def get_gitlab_projects(gl, search_list):
    projects = []
    for search_item in search_list:
        print(f"INFO: Searching GitLab Groups and Projects in: {search_item}...")
        groups = gl.groups.list(search=search_item, all_available=True)

        if not groups:
            print(f"ERROR: No such group: {search_item}")
            continue

        for group_item in groups:
            group_id = group_item.id
            group = gl.groups.get(group_id)
            projects.extend(group.projects.list(all=True))

    return projects

def process_gitlab_projects(projects, local_base_path, branch_list):

    stats_data = dict()

    for project in projects:
        git_url = project.ssh_url_to_repo
        if "-deleted-" not in git_url:
            print(f"INFO: Cloning Git Repo: {git_url}")

            pattern = r"git@jihulab\.com:(.*)\.git"
            re_match = re.search(pattern, git_url)
            project_path = re_match.group(1) if re_match else None

            local_path = f"{local_base_path}/{project_path}"
            print(f"INFO: Local Path: {local_path}")

            repo = None
            if os.path.exists(local_path) and os.path.isdir(local_path):
                repo = Repo(local_path)
                repo.remotes.origin.fetch()
                repo.remotes.origin.pull()
            else:
                repo = Repo.clone_from(project.ssh_url_to_repo, local_path)

            repo.remotes.origin.fetch()

            for branch_name in branch_list:
                if branch_name in repo.branches:
                    try:
                        repo.git.checkout(branch_name)
                    except Exception:
                        print(f"ERROR: Failed to checkout branch: {branch_name}")
                        continue

                    print(f"INFO: Processing branch: {branch_name}")
                    repo.git.checkout(branch_name)

                    total_added_lines = 0
                    total_removed_lines = 0
                    authors_data = dict()

                    for commit in repo.iter_commits(branch_name):
                        author_email = commit.author.email
                        author_name = commit.author.name
                        diff = commit.stats.total
                        added_lines = diff['insertions']
                        removed_lines = diff['deletions']

                        total_added_lines += added_lines
                        total_removed_lines += removed_lines

                        author_key = f"{author_name}__{author_email}"

                        if author_key not in authors_data:
                            authors_data[author_key] = {
                                'Added Lines': 0,
                                'Removed Lines': 0,
                            }
                        authors_data[author_key]['Added Lines'] += added_lines
                        authors_data[author_key]['Removed Lines'] += removed_lines

                    for author_key, author_info in authors_data.items():
                        author_info['Repository'] = project_path
                        author_info['Branch'] = branch_name
                        author_info['Author'] = author_key.split('__')[0]
                        author_info['Author Email'] = author_key.split('__')[1]
                        author_info['Total Added Lines'] = total_added_lines
                        author_info['Percentage of Added Lines'] = round((author_info['Added Lines'] / total_added_lines) * 100, 1) if total_added_lines > 0 else 0.0
                        unique_key = f"{project_path}_{branch_name}_{author_key}"
                        stats_data[unique_key] = author_info

    return stats_data

def write_to_csv(csv_file, csv_columns, stats_data):
    with open(csv_file, 'a', encoding='utf-8-sig') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=csv_columns)
        writer.writeheader()
        for data in stats_data.values():
            writer.writerow(data)

    print(f"INFO: See all git_commits_stats data in {csv_file}")

def main():
    gitlab_url = 'https://jihulab.com'
    private_token = 'your_private_token'

    local_base_path = '/your/local/base/path'

    search_list = [
        "PATH NAME/TO/GROUP"
    ]
    branch_list = ['dev', 'develop', 'main', 'master']

    csv_file = f'{local_base_path}/repos_stats.csv'
    csv_columns = [
        'Repository',
        'Branch',
        'Author',
        'Author Email',
        'Added Lines',
        'Removed Lines',
        'Total Added Lines',
        'Percentage of Added Lines'
    ]

    gl = gitlab.Gitlab(gitlab_url, private_token=private_token)

    projects = get_gitlab_projects(gl, search_list)
    stats_data = process_gitlab_projects(projects, local_base_path, branch_list)

    if os.path.exists(csv_file):
        os.remove(csv_file)
    write_to_csv(csv_file, csv_columns, stats_data)

if __name__ == "__main__":
    main()
