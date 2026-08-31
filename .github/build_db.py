# Copyright (c) 2022-2025 José Manuel Barroso Galindo <theypsilon@gmail.com>

# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.

# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

# You can download the latest version of this tool from:
# https://github.com/theypsilon/DB-Template_MiSTer

import base64
import shutil
import subprocess
import os
import re
import sys
import tempfile
import traceback
import zipfile
from datetime import datetime, timezone

def main():
    dryrun = False
    if len(sys.argv) >= 2 and sys.argv[1] in ['-d', '--dry-run']:
        log('Dry run')
        dryrun = True

    checkout_auth_config_key = None
    try:
        if not dryrun and os.getenv('GITHUB_ACTIONS') == 'true':
            checkout_auth_config_key = github_actions_checkout()
        main_impl(dryrun)
    finally:
        cleanup_github_actions_checkout_auth(checkout_auth_config_key)

def main_impl(dryrun):
    log('Building database...')

    github_repo = os.getenv('GITHUB_REPOSITORY', 'theypsilon/test')
    db_id = os.getenv('DB_ID', None)
    if db_id is None:
        db_id = github_repo

    if not dryrun:
        run(['git', 'config', '--global', 'user.email', 'theypsilon@gmail.com'])
        run(['git', 'config', '--global', 'user.name', 'The CI/CD Bot'])

        cleanup_build_py(github_repo)

    log('downloading db_operator.py')
    curl('https://raw.githubusercontent.com/MiSTer-devel/Distribution_MiSTer/main/.github/db_operator.py',
         '/tmp/distribution_db_operator.py')

    db_url = os.getenv('DB_URL', f'https://raw.githubusercontent.com/{github_repo}/db/db.json.zip')
    base_files_url = f'https://raw.githubusercontent.com/{github_repo}/%s/'

    subprocess.run(['rm *.sh'], shell=True, stderr=subprocess.STDOUT)

    run(['python3', '-m', 'pip', 'install', 'Pillow'])
    
    external_files = 'external_files.csv'
    external_repos_check = subprocess.run(["git", "ls-remote", "--heads", "origin", "external_repos_files"],
                                          stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if 'refs/heads/external_repos_files' in external_repos_check.stdout:
        run(["git", "fetch", "origin", "external_repos_files"])
        run(["git", "checkout", "FETCH_HEAD", "--", "external_repos_files.csv"])
        external_files = 'external_files.csv external_repos_files.csv'
        log('Added external_repos_files.csv from branch external_repos_files!')

    run(['python3', '/tmp/distribution_db_operator.py', 'build', '.'], env={
        'DB_ID': db_id,
        'DB_URL': db_url,
        'DB_JSON_NAME': 'db.json',
        'BASE_FILES_URL': base_files_url,
        'FINDER_IGNORE': os.getenv('FINDER_IGNORE', '') + ' ' + external_files,
        'BROKEN_MRAS_IGNORE': os.getenv('BROKEN_MRAS_IGNORE', 'true'),
        'EXTERNAL_FILES': external_files,
        'OMIT_DUAL_SDRAM_CORES': os.getenv('OMIT_DUAL_SDRAM_CORES', 'false')
    })

    if not dryrun and os.path.exists('db.json') and passes_db_tests(db_id):
        log('Pushing database...')
        run(['zip', 'db.json.zip', 'db.json'])
        run(['git', 'checkout', '--orphan','db'])
        run(['git', 'reset'])
        run(['git', 'add', 'db.json.zip', *create_drop_in_database_files(db_id, db_url)])
        run(['git', 'commit', '-m','Creating database'])
        run(['git', 'push', '--force','origin', 'db'])

        if os.getenv('TRACK_RELEASE', 'true').lower() != 'false':
            try:
                log('Tracking release...')
                db_commit_hash = subprocess.run(['git', 'rev-parse', 'HEAD'],
                                                stdout=subprocess.PIPE, text=True, check=True).stdout.strip()
                releases_check = subprocess.run(['git', 'ls-remote', '--heads', 'origin', 'db-releases'],
                                                       stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                if 'refs/heads/db-releases' in releases_check.stdout:
                    run(['git', 'fetch', 'origin', 'db-releases'])
                    run(['git', 'checkout', 'db-releases'])
                else:
                    run(['git', 'checkout', '--orphan', 'db-releases'])

                run(['git', 'reset', '--hard'])

                with open('commits.txt', 'a') as f:
                    f.write(f"{datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}: {db_commit_hash}\n")

                run(['git', 'add', 'commits.txt'])
                run(['git', 'commit', '-m', f'Track release {db_commit_hash}'])
                run(['git', 'push', 'origin', 'db-releases'])
                run(['git', 'checkout', 'db'])
            except Exception as e:
                log(f'Warning: Failed to track release: {e}')
                log(traceback.format_exc())

    return 0

def passes_db_tests(db_id):
    log('\nTesting database...\n')

    with tempfile.TemporaryDirectory() as temp_folder:
        curl('https://github.com/MiSTer-devel/Downloader_MiSTer/releases/download/latest/downloader_test.py', temp_folder + '/downloader_test.py')
        run(['chmod', '+x', 'downloader_test.py'], cwd=temp_folder)
        run(['./downloader_test.py', db_id, f'{os.getcwd()}/db.json'], cwd=temp_folder)

    log('\nThe test went well.\n')    
    return True

def cleanup_build_py(github_repo):  
    if github_repo.lower().strip() == 'theypsilon/db-template_mister':
        log('Skipping cleanup_build_py')
        return

    needs_commit = False
    if os.path.exists('build_db.py'):
        run(['git', 'rm', 'build_db.py'])
        needs_commit = True

    if os.path.exists('.github/build_db.py'):
        run(['git', 'rm', '.github/build_db.py'])
        needs_commit = True

    if needs_commit:
        run(['git', 'commit', '-m','BOT: Cleaning build_db.py'])
        run(['git', 'push'])

def create_drop_in_database_files(db_id, db_url):
    try:
        sanitized_db_id = sanitize_db_id_for_filename(db_id)
        drop_in_ini = f'downloader_{sanitized_db_id}.ini'
        drop_in_zip = f'downloader_{sanitized_db_id}.zip'
        drop_in_contents = f'[{db_id}]\ndb_url = {db_url}\n'

        with open(drop_in_ini, 'w', encoding='utf-8', newline='\n') as f:
            f.write(drop_in_contents)

        with zipfile.ZipFile(drop_in_zip, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
            archive.writestr(drop_in_ini, drop_in_contents)

        return [drop_in_ini, drop_in_zip]
    except Exception as e:
        log(f'Warning: Failed to create drop-in database files: {e}')
        log(traceback.format_exc())
        return []

def sanitize_db_id_for_filename(db_id):
    sanitized_db_id = re.sub(r'[^A-Za-z0-9._-]+', '_', db_id).strip('._-')
    if sanitized_db_id == '':
        raise ValueError(f'Unable to derive a drop-in filename from DB_ID "{db_id}"')
    return sanitized_db_id

## GIT CHECKOUT

def github_actions_checkout():
    workspace = os.environ['GITHUB_WORKSPACE']
    repo = os.environ['GITHUB_REPOSITORY']
    token = os.environ['GITHUB_TOKEN']
    ref = os.environ.get('GITHUB_REF', 'refs/heads/main')
    commit = os.environ.get('GITHUB_SHA', '')
    server_url = os.environ.get('GITHUB_SERVER_URL', 'https://github.com')

    os.chdir(workspace)

    if os.path.exists('.git'):
        log('Repository already checked out.')
        return None

    log(f'Checking out {repo}@{ref}...')

    git_version_out = subprocess.run(['git', 'version'], capture_output=True, text=True, check=True).stdout.strip()
    git_version_match = re.search(r'\d+\.\d+(\.\d+)?', git_version_out)
    if not git_version_match:
        raise RuntimeError(f'Unable to determine git version from: {git_version_out}')

    # Matches GitCommandManager.gitEnv — inherited by every git subprocess
    os.environ['GIT_TERMINAL_PROMPT'] = '0'
    os.environ['GCM_INTERACTIVE'] = 'Never'
    os.environ['GIT_LFS_SKIP_SMUDGE'] = '1'
    os.environ['GIT_HTTP_USER_AGENT'] = f'git/{git_version_match.group(0)} (github-actions-checkout)'

    token_b64 = base64.b64encode(f'x-access-token:{token}'.encode()).decode()
    auth_header = f'AUTHORIZATION: basic {token_b64}'

    # Matches git-auth-helper.ts configureTempGlobalConfig() + safe.directory setup
    # (git-source-provider.ts getSource(), settings.setSafeDirectory = true by default)
    runner_temp = os.environ.get('RUNNER_TEMP', tempfile.gettempdir())
    temp_home = tempfile.mkdtemp(dir=runner_temp)
    original_home = os.environ.get('HOME')
    src_gitconfig = os.path.join(original_home or os.path.expanduser('~'), '.gitconfig')
    dst_gitconfig = os.path.join(temp_home, '.gitconfig')
    if os.path.exists(src_gitconfig):
        shutil.copy2(src_gitconfig, dst_gitconfig)
    else:
        open(dst_gitconfig, 'w').close()
    os.environ['HOME'] = temp_home

    try:
        run(['git', 'config', '--global', '--add', 'safe.directory', workspace])

        # Matches git-source-provider.ts getSource() + git-auth-helper.ts configureToken()
        run(['git', 'init', workspace])
        run(['git', 'remote', 'add', 'origin', f'{server_url}/{repo}'])
        run(['git', 'config', '--local', 'gc.auto', '0'])
        auth_config_key = f'http.{server_url}/.extraheader'
        placeholder = 'AUTHORIZATION: basic ***'
        run(['git', 'config', '--local', auth_config_key, placeholder])
        git_config_path = os.path.join(workspace, '.git', 'config')
        content = open(git_config_path, encoding='utf-8').read()
        if content.count(placeholder) != 1:
            raise RuntimeError(f'Unable to replace auth placeholder in {git_config_path}')
        with open(git_config_path, 'w', encoding='utf-8') as f:
            f.write(content.replace(placeholder, auth_header, 1))

        refspec = get_github_actions_checkout_refspec(ref, commit)
        run(['git', '-c', 'protocol.version=2', 'fetch', '--no-tags', '--prune', '--progress',
             '--no-recurse-submodules', '--depth=1', 'origin', *refspec])

        checkout_ref, checkout_start_point = get_github_actions_checkout_info(ref, commit)
        checkout_command = ['git', 'checkout', '--progress', '--force']
        if checkout_start_point:
            checkout_command.extend(['-B', checkout_ref, checkout_start_point])
        else:
            checkout_command.append(checkout_ref)
        run(checkout_command)
        return auth_config_key
    except Exception:
        cleanup_github_actions_checkout_auth(auth_config_key if 'auth_config_key' in locals() else None)
        raise
    finally:
        # Matches authHelper.removeGlobalConfig()
        if original_home is not None:
            os.environ['HOME'] = original_home
        else:
            os.environ.pop('HOME', None)
        shutil.rmtree(temp_home, ignore_errors=True)

def get_github_actions_checkout_info(ref, commit):
    if not ref and not commit:
        raise RuntimeError('Args ref and commit cannot both be empty')

    ref_kind, ref_name, full_ref = parse_github_actions_checkout_ref(ref)

    if ref_kind == 'sha':
        return commit, ''
    if ref_kind == 'branch':
        return ref_name, f'refs/remotes/origin/{ref_name}'
    if ref_kind == 'pull':
        return f'refs/remotes/pull/{ref_name}', ''
    if ref_kind in ('tag', 'ref'):
        return commit or full_ref, ''
    if git_branch_exists(f'origin/{ref_name}', remote=True):
        return ref_name, f'refs/remotes/origin/{ref_name}'
    if git_tag_exists(ref_name):
        return f'refs/tags/{ref_name}', ''
    raise RuntimeError(f"A branch or tag with the name '{ref}' could not be found")

def get_github_actions_checkout_refspec(ref, commit):
    if not ref and not commit:
        raise RuntimeError('Args ref and commit cannot both be empty')

    ref_kind, ref_name, full_ref = parse_github_actions_checkout_ref(ref)

    if commit:
        if ref_kind == 'branch':
            return [f'+{commit}:refs/remotes/origin/{ref_name}']
        if ref_kind == 'pull':
            return [f'+{commit}:refs/remotes/pull/{ref_name}']
        if ref_kind == 'tag':
            return [f'+{commit}:{full_ref}']
        return [commit]
    if ref_kind == 'unqualified':
        return [
            f'+refs/heads/{ref}*:refs/remotes/origin/{ref}*',
            f'+refs/tags/{ref}*:refs/tags/{ref}*'
        ]
    if ref_kind == 'branch':
        return [f'+{full_ref}:refs/remotes/origin/{ref_name}']
    if ref_kind == 'pull':
        return [f'+{full_ref}:refs/remotes/pull/{ref_name}']
    return [f'+{full_ref}:{full_ref}']

def parse_github_actions_checkout_ref(ref):
    if not ref:
        return 'sha', '', ''

    heads_prefix = 'refs/heads/'
    pull_prefix = 'refs/pull/'
    tags_prefix = 'refs/tags/'
    upper_ref = ref.upper()

    if upper_ref.startswith(heads_prefix.upper()):
        return 'branch', ref[len(heads_prefix):], ref
    if upper_ref.startswith(pull_prefix.upper()):
        return 'pull', ref[len(pull_prefix):], ref
    if upper_ref.startswith(tags_prefix.upper()):
        return 'tag', ref[len(tags_prefix):], ref
    if upper_ref.startswith('REFS/'):
        return 'ref', ref, ref
    return 'unqualified', ref, ref

def git_branch_exists(branch, remote=False):
    command = ['git', 'branch', '--list']
    if remote:
        command.append('--remote')
    command.append(branch)
    output = subprocess.run(command, capture_output=True, text=True, check=True).stdout
    return output.strip() != ''

def git_tag_exists(tag):
    output = subprocess.run(['git', 'tag', '--list', tag], capture_output=True, text=True, check=True).stdout
    return output.strip() != ''

def cleanup_github_actions_checkout_auth(auth_config_key):
    if not auth_config_key:
        return

    log(f'Cleaning up checkout auth for {auth_config_key}')
    subprocess.run(['git', 'config', '--local', '--unset-all', auth_config_key], check=False,
                   stderr=subprocess.STDOUT)

## GENERAL UTILS

def run(commands, env=None, cwd=None):
    log(' '.join(commands))
    if env is not None: log('with env:', env)
    if cwd is not None: log('with cwd:', cwd)
    subprocess.run(commands, cwd=cwd, env=env, check=True, stderr=subprocess.STDOUT)

def curl(url, output_path):
    log(f'Downloading {url} to {output_path}')
    run(['curl', '--fail', '--location', '--output', output_path, url])

def log(*text): print(*text, flush=True)

if __name__ == '__main__':
    exit(main())
