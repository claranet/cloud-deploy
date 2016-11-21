# -*- coding: utf-8 -*-
#!/usr/bin/env python

"""
    Library to have common git operations
"""
import os
import sys
from sh import git

"""
    Checks if an 'index.lock' file is present,
    waits until it's gone
"""
def git_wait_lock(mirror_path, log_file):
    # If an index.lock file exists in the mirror, wait until it disappears before trying to update the mirror
    while os.path.exists('{m}/index.lock'.format(m=mirror_path)):
        log('The git mirror is locked by another process, waiting 5s...', log_file)
        sleep(5000)

"""
    Edits the '.gitmodules' file in order to replace the remote git by a local bare mirror
"""
def git_remap_submodule(git_local_repo, submodule_repo, summodule_mirror):
    with open(git_local_repo + '/.gitmodules', 'rw') as submodule_config:
        filedata = submodule_config.read()
        filedata = filedata.replace(submodule_repo, summodule_mirror)
        submodule_config.write(filedata)
