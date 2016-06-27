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
  "ghost_blueprints",
  "ghost_tools",
  "libs.safe_deployment",
  "libs.deploy",
  "run",
  "run_rqworkers",
  "web_ui.forms",
  "web_ui.ghost_client",
  "web_ui.websocket"
]

runner = doctest.DocTestRunner(verbose=True)
finder = doctest.DocTestFinder(verbose=True, exclude_empty=False)

for module in modules:
  for test in finder.find(importlib.import_module(module)):
    runner.run(test)

runner.summarize()
