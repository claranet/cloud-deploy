# -*- coding: utf-8 -*-
#!/usr/bin/env python

"""
    Library to have common git operations
"""
import os
import sys
from sh import git

def git_wait_lock(mirror_path, log_file):
    # If an index.lock file exists in the mirror, wait until it disappears before trying to update the mirror
    while os.path.exists('{m}/index.lock'.format(m=mirror_path)):
        log('The git mirror is locked by another process, waiting 5s...', log_file)
        sleep(5000)
