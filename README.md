# pyconfmerge

## Introduction

Configuration files come in all shapes, sizes, and syntaxes.  For some
projects, it makes sense to use Python syntax for the configuration
files and `import` or `eval` the text in the file to get the values.
While this is somewhat dangerous when people not familiar with Python
programming are filling in values in the configuration files, it does
allow for sophisticated imports, values that depend on other values,
defining complex data types like procedures, etc.

When the configured program is updated, sometimes the configuration
file content needs to be updated for a new configuration parameter or
a revised structure to a existing parameter.  Users of the configured
program need to merge their custom configuration with the updated
config file template.  This can be very complex, especially for people
not familiar with Python programming or source code merge tools.

Enter pyconfmerge.  This tool is designed to merge Python files to
preserve the structure of the configuration template while merging in
the values of an existing configuration file.  It can be run automatically
or interactively to produce new configuration files.  It looks for
assignments or definitions in the templates and config files, and
preserves the customized values where possible.

## Requirements

To use pyconfmerge, you'll need the RedBaron Python parser,
https://pypi.python.org/pypi/redbaron/
and the pygments python syntax highlighter,
http://pygments.org
If you use `pip`, you can install these modules by running
`pip install redbaron pygments`.
