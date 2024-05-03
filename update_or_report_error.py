from github import Github
import subprocess
import json
import git
import sys

# args:
# 1 : repo name
# 2 : bot token

issue_title = 'Automatic upgrade has failed'

repo_name = sys.argv[1]
bot_token = sys.argv[2]

def get_dependencies():
    with open('lake-manifest.json', 'r') as lean_json:
        parsed_json = json.load(lean_json)
        return parsed_json['packages']


def error_on_upgrade(err):
    print('Error running `lake update`.')
    print(err)
    exit(1)


def up_to_date():
    print('Nothing to upgrade: everything is up to date.')
    exit(0)


def diff_url_from_dep(old_dep, new_dep):
    repo = old_dep['url'].strip('.git')
    prev = old_dep['rev']
    curr = new_dep['rev']
    return f'{repo}/compare/{prev}...{curr}'


def open_issue_on_failure(body):
    repo = Github(bot_token).get_repo(repo_name)
    issues = repo.get_issues()
    if any(i.title == issue_title for i in issues):
        return
    repo.create_issue(issue_title, body)


def find_dep_by_name(deps, name):
    for dep in deps:
        if dep["name"] == name:
            return dep
    return None


def error_on_build(original_deps, new_deps):
    print('Failure building after upgrade.')
    s = 'Oh no! We have failed to automatically upgrade your project to the latest version of mathlib.'
    s += '\n\nIf your project currently builds, this is probably because of changes made in its dependencies:'
    for dep in original_deps:
        dep_name = dep["name"]
        new = find_dep_by_name(new_deps, dep_name)
        if new is not None:
            diff_url = diff_url_from_dep(dep, new)
            s += f'\n* {dep_name}: [changes]({diff_url})'
        else:
            s += f'\n* {dep_name}: removed'
    s += """\n\nYou can see the errors by running:
```bash
lake update
lake build
```"""
    open_issue_on_failure(s)
    exit(0)


def close_open_issue():
    repo = Github(sys.argv[2]).get_repo(repo_name)
    issues = [i for i in repo.get_issues() if i.title == issue_title and i.state == 'open']
    for i in issues:
        i.create_comment('This issue has been resolved!')
        i.edit(state='closed')


def commit_and_push():
    repo = git.Repo('.')
    index = repo.index
    index.add(['lake-manifest.json', 'lean-toolchain'])
    author = git.Actor('leanprover-community-bot', 'leanprover.community@gmail.com')
    index.commit('auto update dependencies', author=author, committer=author)
    print('Pushing commit to remote')
    repo.remote().push()


def upgrade_and_build():
    original_deps = get_dependencies()

    proc = subprocess.Popen(['lake', 'update'])
    _out, err = proc.communicate()

    if proc.returncode != 0:
        error_on_upgrade(err)

    new_deps = get_dependencies()

    if new_deps == original_deps:
        up_to_date()

    proc = subprocess.Popen(['lake', 'build'])
    _out, err = proc.communicate()

    if proc.returncode != 0:
        error_on_build(original_deps, new_deps)
        return

    commit_and_push()
    close_open_issue()

upgrade_and_build()