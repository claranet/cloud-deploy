# -*- coding: utf-8 -*-
#!/usr/bin/env python

"""
    Library to have common git operations
"""
import os
import sys
from ghost_log import log
from sh import git

def git_wait_lock(mirror_path, log_file):
    """
    Checks if an 'index.lock' file is present,
    waits until it's gone
    """
    # If an index.lock file exists in the mirror, wait until it disappears before trying to update the mirror
    while os.path.exists('{m}/index.lock'.format(m=mirror_path)):
        log('The git mirror is locked by another process, waiting 5s...', log_file)
        sleep(5000)

def git_remap_submodule(git_local_repo, submodule_repo, submodule_mirror, log_file):
    """
    Edits the '.gitmodules' file in order to replace the remote git by a local bare mirror
    """
    log('Updating submodule config: now using "{mirror}" for "{repo}" repo'.format(repo=submodule_repo, mirror=submodule_mirror), log_file)
    with open(git_local_repo + '/.gitmodules', 'r') as submodule_config:
        filedata = submodule_config.read()
    filedata = filedata.replace(submodule_repo, submodule_mirror)
    with open(git_local_repo + '/.gitmodules', 'w') as submodule_config:
        submodule_config.write(filedata)

def git_ls_remote_branches_tags(git_repo, log_file=None):
    """
    This function trigger the `ls-remote` git command on the remote git repo
    and retrieve all available branches and tags, sorted by name.
    """
    revs = []
    branches = []
    tags = []
    try:
        for line in git("--no-pager", "ls-remote", git_repo, _tty_out=False, _timeout=20, _iter=True):
            refs = line.strip().split("\t")
            if refs[1].endswith('{}'): # ignore github releases
                continue
            if refs[1].startswith('refs/pull'): # ignore PR
                continue
            if refs[1].startswith('refs/remotes'): # ignore remotes
                continue
            key = refs[1].replace('refs/heads/', '').replace('refs/tags/', '')
            val = refs[1].replace('refs/heads/', 'branch: ').replace('refs/tags/', 'tag: ')
            if val.startswith('tag'):
                tags.append( (key, val) )
            elif val.startswith('branch'):
                branches.append( (key, val) )
            else:
                revs.append( (key, val) )
    except Exception as e:
        print str(e)
        if log_file:
            log('git_ls_remote_branches_tags("{git}") call failed: {ex}'.format(git=git_repo, ex=str(e)), log_file)
    return revs + sorted(tags, key=lambda k: k[0], reverse=True) + sorted(branches, key=lambda k: k[0])
