"""First-party transport extension packages.

Each subpackage is a standalone transport extension program:
its folder carries an `extension.json` manifest of kind
"transport" (api_version 1), and the runner supervises the
program as a child process, talking to it only through the
file channel under <base_dir>/transport-extensions/<name>/.
Nothing here is imported by the runner.
"""
