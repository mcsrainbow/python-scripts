# Description: Check and update configurations of GitLab
# Author: Damon Guo guosuiyu@gmail.com

# pip install python-gitlab
import gitlab

def get_gitlab_groups_n_projects(gl, search_list):
    projects = []

    for search_item in search_list:
        print(f"INFO: Searching GitLab Groups and Projects in: {search_item}...")
        groups = gl.groups.list(search=search_item, all_available=True, get_all=True)

        if not groups:
            print(f"ERROR: No such group: {search_item}")
            continue

        for group_item in groups:
            group_id = group_item.id
            group = gl.groups.get(group_id)
            projects.extend(group.projects.list(all=True))

    return {'groups':groups,'projects':projects}

# https://python-gitlab.readthedocs.io/en/stable/gl_objects/variables.html
def check_gitlab_groups(gl, groups, keywords, old_token, new_token):

    for group in groups:
        try:
            group_info = gl.groups.get(group.id)

            variables = group_info.variables.list()

            if len(variables) > 0:
                print(f"INFO: CI/CD Variables in GitLab Group: {group_info.full_path}")
                for variable in variables:
                    if any(kw in variable.key for kw in keywords):
                        print(f"    Key: {variable.key}, Value: {variable.value}")
                        if variable.value == old_token:
                            variable.value = new_token
                            variable.save()
                            print(f"    Updated {variable.key} to new token.")
                    else:
                        print(f"    Key: {variable.key}")

        except Exception as e:
            print(f"ERROR: Failed to check GitLab Group: {group_info.full_path}: {e}")

    return True

# https://python-gitlab.readthedocs.io/en/stable/gl_objects/variables.html
def check_gitlab_projects(gl, projects, keywords, old_token, new_token):

    for project in projects:
        project_path = project.path_with_namespace
        if "-deleted-" not in project_path:
            try:
                project_info = gl.projects.get(project.id)

                variables = project_info.variables.list()

                if len(variables) > 0:
                    print(f"INFO: CI/CD Variables in GitLab Repo: {project_path}")
                    for variable in variables:
                        if any(kw in variable.key for kw in keywords):
                            print(f"    Key: {variable.key}, Value: {variable.value}")
                            if variable.value == old_token:
                                variable.value = new_token
                                variable.save()
                                print(f"    Updated {variable.key} to new token.")
                        else:
                            print(f"    Key: {variable.key}")

            except Exception as e:
                print(f"ERROR: Failed to check GitLab Repo: {project_path}: {e}")

    return True

def main():
    gitlab_url = 'https://jihulab.com'
    private_token = 'YourAPIToken'

    old_token='YourOLDToken'
    new_token='YourNEWToken'

    search_list = [
        "PATH NAME/TO/GROUP"
    ]

    keywords = [
        "TOKEN"
    ]

    gl = gitlab.Gitlab(gitlab_url, private_token=private_token)

    groups_n_projects = get_gitlab_groups_n_projects(gl, search_list)
    groups = groups_n_projects['groups']
    projects = groups_n_projects['projects']

    check_gitlab_groups(gl, groups, keywords, old_token, new_token)

    check_gitlab_projects(gl, projects, keywords, old_token, new_token)

if __name__ == "__main__":
    main()
