#!/usr/bin/env python

# The purpose of this script is to run all doctests in a single way that loads
# everything as modules to support relative imports.
# To be used with tox or virtualenv.

import doctest
import importlib

modules = [
    "command",
    "commands.buildimage",
    "commands.deploy",
    "commands.executescript",
    "commands.redeploy",
    "ghost_api",
    "ghost_aws",
    "ghost_blueprints",
    "ghost_data",
    "ghost_tools",
    "libs.blue_green",
    "libs.deploy",
    "libs.git_helper",
    "libs.host_deployment_manager",
    "libs.builders.image_builder",
    "libs.builders.image_builder_aws",
    "libs.provisioners",
    "libs.provisioners.provisioner_salt",
    "libs.provisioners.provisioner_ansible",
    "pypacker",
    "run",
    "run_rqworkers",
    "websocket",
    "pypacker",
    "webhooks.parsers.base"
]

runner = doctest.DocTestRunner(verbose=True)
finder = doctest.DocTestFinder(verbose=True, exclude_empty=False)

for module in modules:
    for test in finder.find(importlib.import_module(module)):
        runner.run(test)

# return a tuple (f, t), where f is the total number of failed examples, and t is the total number of tried examples.
test_result = runner.summarize()
exit(test_result[0])
