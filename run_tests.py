#!/usr/bin/env python

# The purpose of this script is to run all doctests in a single way that loads
# everything as modules to support relative imports.
# To be used with tox or virtualenv.

import doctest
import importlib
from pylxd import Client

modules = [
  "command",
  "commands.buildimage",
  "commands.deploy",
  "commands.executescript",
  "commands.redeploy",
  "ghost_api",
  "ghost_aws",
  "ghost_blueprints",
  "ghost_tools",
  "libs.blue_green",
  "libs.deploy",
  "libs.git_helper",
  "libs.host_deployment_manager",
  "libs.image_builder",
  "libs.image_builder_aws",
  "libs.provisioner",
  "libs.provisioner_salt",
  "libs.provisioner_ansible",
  "run",
  "run_rqworkers",
  "web_ui.app",
  "web_ui.forms.form_aws_helper",
  "web_ui.forms.form_helper",
  "web_ui.ghost_client",
  "web_ui.websocket"
]
try:
    if Client(): modules.append("container")
except:
    pass

runner = doctest.DocTestRunner(verbose=True)
finder = doctest.DocTestFinder(verbose=True, exclude_empty=False)

for module in modules:
  for test in finder.find(importlib.import_module(module)):
    runner.run(test)

test_result = runner.summarize() # return a tuple (f, t), where f is the total number of failed examples, and t is the total number of tried examples.
exit (test_result[0])
