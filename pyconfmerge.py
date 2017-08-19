#!/usr/bin/env python

from __future__ import print_function

# The pyconfmerge package is designed to merge template Python configuration
# files with customized versions of those files as users upgrade their
# configurations.
# See https://github.com/JMCanning78/pyconfmerge for full details.

from redbaron import RedBaron, base_nodes
import pygments
from pygments.lexers import PythonLexer

import argparse, os, sys, readline, operator
from glob import glob

import pyconfmerge_config

__doc__ = """
Merge Python configuration files with new templates for the configuration
file, preserving the customized values where possible.
"""

text_node_types = ['comment', 'space', 'endl']

def identifier(FST_node):
    if FST_node.type in ('class', 'def'):
        return FST_node.name
    elif FST_node.type == 'assignment':
        return str(FST_node.target)
    else:
        return None

marker = '-0'

def nodelist_append(nodelist, node):
    """Since RedBaron nodelists only have an insert_after method, and that
    can't be used on an empty nodelist, we use a single-node marker
    nodelist as the 'empty' list and replace the first node for the
    first append.  Subsequent appends are done using insert_after.
    """
    n = len(nodelist)
    if (n == 1 and nodelist.find("unitary_operator", marker[0]) and
        nodelist.find("int", marker[1])):
        nodelist[0].replace(node)
    else:
        nodelist[-1].insert_after(node)
        # RedBaron doesn't seem to always properly insert_after of blank lines
        # ('endl' type) in some nodelists.  This kludge repeats the insert
        # to make it take effect.
        if len(nodelist) == n and node.type == 'endl':
            nodelist[-1].insert_after(node)

def choose_action(id, t_nodes, c_nodes, t_comments, c_comments, default_action,
                  options):
    """Choose what action to take for a of contiguous sequence of
    template nodes and their 'matching' config file nodes.  The first node
    of the sequence defines the type of node and is used to lookup the
    default action to perform.
    """
    options.update({'identifier': id if id is not None else 
                    t_nodes[0].type if t_nodes is not None else c_nodes[0].type})
    output_choices = 'tcn'
    default_index = max(output_choices.find(default_action[0]), 0)
    agree = (t_nodes and c_nodes and t_nodes[0].type == c_nodes[0].type and
             str(t_nodes) == str(c_nodes))
    if agree:
        if options['verbose'] > 0:
            iprint('values_agree', options)
        return output_choices[default_index]
    choices = options['prompts']['choices']
    choice_chars = reduce(operator.concat, [ c[0].lower() for c in choices ])
    sep = '\n'
    if len(t_comments) > 0 and options['comments'][
            'show_template_comments_before_prompt']:
        print(sep)
        msg = "{0} {1}:".format(
            options['prompts']['comments'], options['prompts']['template_file'])
        iprint(msg, options)
        for line in [ t.value for t in t_comments ]:
            print_python_content(line, options)
        sep = ''
    if (len(c_comments) > 0 and options['comments'][
            'show_config_comments_before_prompt'] and
        (not options['comments']['show_template_comments_before_prompt'] or
         str(c_comments) != str(t_comments))):
        iprint(sep, options)
        msg = "{0} {1}:".format(
            options['prompts']['comments'], options['prompts']['config_file'])
        iprint(msg, options)
        for line in [ c.value for c in c_comments ]:
            print_python_content(line, options)
        sep = ''
    if sep:
        iprint(sep, options)
    iprint('values_disagree', options)
    msg = '{0}: '.format(options['prompts']['template_value'])
    iprint(msg, options)
    print_python_content(t_nodes, options)
    msg = '{0}: '.format(options['prompts']['config_value'])
    iprint(msg, options)
    print_python_content(c_nodes, options)

    formatted_choices = [
        choices[i].capitalize() if i == default_index else choices[i]
        for i in range(len(choices))]
    prompt = '{0} {1}, ?: '.format(
        options['prompts']['keep'], ', '.join(formatted_choices))
    resp = 'No response'
    while resp.lower() not in choice_chars:
        resp = iprint(prompt, options, prompt=True)
        if len(resp) == 0:
            resp = choice_chars[default_index]
        elif resp == '?':
            options['choices'] = formatted_choices
            iprint('instructions', options)
        elif resp[0].lower() in choice_chars:
            default_index = choice_chars.find(resp[0].lower())
            resp = resp[0]
        else:
            iprint('{0} "{1}"'.format(options['prompts']['unrecognized_option'],
                                      resp), options)
    return output_choices[default_index]

def iprint (msg_or_key, options, prompt=False, file=sys.stdout):
    """Print a msg on the given file, filling in values from the options
    dictionary and adding a distinguishing prefix.  If prompt is true,
    use the msg_or_key as a prompt and return user input."""
    if msg_or_key in options['prompts']:
        msg_or_key = options['prompts'][msg_or_key].strip()
    prefix = options['prompts'].get('prefix', '-*-> ')
    if prompt:
        if sys.version_info[0] == 2:
            return raw_input(prefix + msg_or_key.format(**options))
        else:
            resp = input(prefix + msg_or_key.format(**options))
    else:
        print(prefix + msg_or_key.format(**options), file=file)
        file.flush()

def print_python_content(text, options, file=sys.stdout):
    pygments.highlight(str(text), PythonLexer(), 
                       pyconfmerge_config.textFormatter, file)

def parse_py_config(text):
    """Parse text as Python config file.  This is basically the same as
    RedBaron, but we want comments, that come between the assignments
    and definitions to be in their own nodes, not as a LineProxyList
    attached to the definition.
    """
    FST = RedBaron(text)
    # Process in reverse order to preserve indexing while modifying the FST
    for i in range(len(FST)-1, 0, -1):
        if FST[i].type not in text_node_types:
            if isinstance(FST[i].value, base_nodes.LineProxyList):
                com = 0
                # Search backwards from end of LineProxyList for all comments
                # and text type nodes
                for com in range(len(FST[i].value) - 1, -1, -1):
                    if FST[i].value[com].type not in text_node_types:
                        break
                # Find first comment node among final comments and text
                while com < len(FST[i].value) and FST[i].value[com].type != 'comment':
                    com += 1
                # Everything from the first comment after this non-text node
                # gets inserted as later node
                if 0 <= com and com < len(FST[i].value):
                    for j in range(len(FST[i].value) - 1, com - 1, -1):
                        FST[i].insert_after(FST[i].value[j])
                    valuefst = FST[i].value.fst()
                    for j in range(1, len(valuefst) + 1):
                        if j >= len(valuefst) or valuefst[j]['type'] == 'comment':
                            break
                    FST[i].value = valuefst[0:j]
    return FST
    
def process_nodes_pair(
        merged_FST, id, t_FST, tnci, t0, t1, c_FST, cnci, c0, c1, options):
    """Process the merge of a sequence of template nodes and a
    corresponding sequence of config file nodes.  The sequences must
    be nodes of the same type.  The first node in the sequence
    determines the type of the sequence.  The t0, t1 and c0, c1
    indexes point to slices of nodes in the corresponding FST, or t0
    and c0 can be -1 to indicate no nodes.  One of them must point to a
    node and if it has an identifier such as an assignment or a def,
    that is in the 'id' argument.  The tnci and cnci indexes point to
    the last non-comment node in the corresponding FST preceding the node
    sequence (to show comments in interactive mode).
    The merged_FST is updated by appending whichever node sequence
    (or possibly neither) is selected to go in the output.
    """
    t_nodes = None if t0 < 0 else t_FST[t0:t1]
    c_nodes = None if c0 < 0 else c_FST[c0:c1]
    node_type = t_FST[t0].type if t_nodes is not None else c_FST[c0].type
    rule = options['merge_rules'].get(node_type,
                                      options['merge_rules']['DEFAULT'])
    action = apply(rule, (id, t_FST[t0] if t_nodes else None,
                          c_FST[c0] if c_nodes else None))
    if options['interactive']:
        action = choose_action(id, t_nodes, c_nodes, t_FST[tnci+1:max(t0,0)],
                               c_FST[cnci+1:max(c0,0)], action, options)
    if action.startswith('c'):
        if c_nodes:
            if options['verbose'] > 3:
                iprint('Copying config value to merged version', options)
            for c in range(c0, c1):
                nodelist_append(merged_FST, c_FST[c].copy())
    elif action.startswith('t'):
        if t_nodes:
            if options['verbose'] > 3:
                iprint('Copying template value to merged version', options)
            for t in range(t0, t1):
                nodelist_append(merged_FST, t_FST[t].copy())
    elif not action.startswith('n'):
        raise Exception('Unexpected action code "{0}" in rule for {1} nodes'
                        .format(action, node_type))
    elif options['verbose'] > 3:
        iprint('neither_copied', options)

def find_node(node, FST, start, only_within=text_node_types):
    """Find the next matching node from one FST in another starting at a
    particular index.  If the type of the node is among the
    only_within types, only search among the next nodes of that type,
    otherwise search all remaining nodes.
    For assignment/defintion nodes, find the next assignment/definition
    with a matching identifier, regardless of whether the values match.
    """
    node_within = node.type in only_within
    node_id = identifier(node)
    for i in range(start, len(FST)):
        if node.type == FST[i].type and (
                str(node.value) == str(FST[i].value) or
                (node_id is not None and node_id == identifier(FST[i]))):
            return i
        if node_within and FST[i].type not in only_within:
            return -1
    return -1
    
def merge_python_FST(templ_FST, config_FST, options):
    """Merge two parsed Python files based on the Full Syntax Trees"""
    ti = 0
    tnci = -1
    ci = 0
    cnci = -1
    merged = RedBaron(marker)
    while ti < len(templ_FST) or ci < len(config_FST):
        # For comments and text node types, group them into contiguous
        # blocks of text nodes
        for t1 in range(ti+1, len(templ_FST) + 1):
            if (templ_FST[ti].type not in text_node_types or
                t1 >= len(templ_FST) or
                templ_FST[t1].type not in text_node_types):
                break
        for c1 in range(ci+1, len(config_FST) + 1):
            if (config_FST[ci].type not in text_node_types or
                c1 >= len(config_FST) or
                config_FST[c1].type not in text_node_types):
                break
        if ti < len(templ_FST):
            if ci < len(config_FST):
                tmi = find_node(templ_FST[ti], config_FST, ci)
                cmi = find_node(config_FST[ci], templ_FST, ti)
                if tmi == ci:
                    process_nodes_pair(merged, identifier(templ_FST[ti]),
                                       templ_FST, tnci, ti, t1,
                                       config_FST, cnci, ci, c1, options)
                elif cmi > ti:
                    c1 = ci
                    process_nodes_pair(merged, identifier(templ_FST[ti]),
                                       templ_FST, tnci, ti, t1,
                                       config_FST, cnci, -1, c1, options)
                elif tmi > ci or templ_FST[ti].type in text_node_types:
                    t1 = ti
                    process_nodes_pair(merged, identifier(config_FST[ci]),
                                       templ_FST, tnci, -1, t1,
                                       config_FST, cnci, ci, c1, options)
                else:
                    c1 = ci
                    process_nodes_pair(merged, identifier(templ_FST[ti]),
                                       templ_FST, tnci, ti, t1,
                                       config_FST, cnci, -1, c1, options)
            else:
                c1 = ci
                process_nodes_pair(merged, identifier(templ_FST[ti]),
                                   templ_FST, tnci, ti, t1,
                                   config_FST, cnci, -1, c1, options)
        else:
            t1 = ti
            process_nodes_pair(merged, identifier(config_FST[ci]),
                               templ_FST, tnci, -1, t1,
                               config_FST, cnci, ci, c1, options)
        # Track the last non-comment expression in both FSTs
        if ti < len(templ_FST) and templ_FST[ti].type not in text_node_types:
            tnci = ti
        if ci < len(config_FST) and config_FST[ci].type not in text_node_types:
            cnci = ci
        ti = t1
        ci = c1
    
    return merged

def merge_python_files(
        templ_filename, config_filename, output_filename, options):
    options.update({
        'template_file': templ_filename,
        'config_file': config_filename,
        'output_file': output_filename,})
    if options['interactive'] or options['verbose'] > 0:
        iprint('processing', options)
    with open(templ_filename) as tfile:
        try:
            if options['verbose'] > 1:
                iprint('Parsing {0}'.format(templ_filename), options)
            ttree = parse_py_config(tfile.read())
        except Exception, e:
            print('Error during read or parsing of {0}'.format(
                templ_filename), file=sys.stderr)
            raise e
    if os.path.exists(config_filename):
        with open(config_filename) as cfile:
            try:
                if options['verbose'] > 1:
                    iprint('Parsing {0}'.format(config_filename), options)
                ctree = parse_py_config(cfile.read())
            except Exception, e:
                print('Error during read or parsing of {0}'.format(
                    config_filename), file=sys.stderr)
                raise e
    else:
        ctree = parse_py_config('')
    if os.path.exists(output_filename) and not options['force']:
        print(options['prompts']['output_exists'].format(**options),
              file=sys.stderr)
        return
    with open(output_filename, 'w') as ofile:
        ofile.write(merge_python_FST(ttree, ctree, options).dumps())

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__,
        formatter_class=argparse.ArgumentDefaultsHelpFormatter)

    parser.add_argument(
        'template', metavar="FILE-DIR-or-GLOB",
        help='Template file, directory of template files, or file glob '
        '(example: *.py).  If a directory or a glob, all config files must '
        'match the filename of one of the template files. '
        'Missing config files are assumed to be empty and a copy of the '
        'template will be output.')
    parser.add_argument(
        '-c', '--config', metavar="FILE-or-DIR",
        help='Configuration file or directory of configuration files.')
    parser.add_argument(
        '-o', '--output', metavar="FILE-or-DIR",
        help='Output file or directory of output files.')
    parser.add_argument(
        '-i', '--interactive', default=False, action='store_true',
        help='Interactively prompt user for merged values.')
    parser.add_argument(
        '-l', '--locale', default='EN', 
        choices=pyconfmerge_config.prompts.keys(),
        help='Locale for prompt language')
    parser.add_argument(
        '-f', '--force', default=False, action='store_true',
        help='Overwrite output files if they exist')
    parser.add_argument(
        '-v', '--verbose', default=0, action='count',
        help='Increase verbosity of progress and debugging messages')

    args = parser.parse_args()

    errors = []
    template_is_dir = False
    if args.template is None:
        errors.append('No template file or directory provided')
    elif not os.path.exists(args.template):
        errors.append('Template file {0} does not exist'.format(args.template))
    else:
        template_is_dir = os.path.isdir(args.template)
    if (args.template is not None and not template_is_dir and 
        not os.path.isfile(args.template)):
        template_is_dir = len(glob(args.template)) > 0
                      
    if args.output is None:
        errors.append('No output file or directory provided')
    elif not template_is_dir and os.path.exists(args.output) and not args.force:
        errors.append('Out file {0} exists and will not be overwritten'
                      .format(args.output))
    if template_is_dir and (args.config is None or 
                            not os.path.exists(args.config) or
                            not os.path.isdir(args.config)):
        errors.append('Must provide config directory to match template directory')
    if (template_is_dir and args.output is not None and 
        os.path.exists(args.output) and not os.path.isdir(args.output)):
        errors.append('Must provide output directory to match template directory')

    if len(errors) > 0:
        parser.error('\n'.join(['Errors:'] + errors))

    options = args.__dict__
    for key, val in pyconfmerge_config.__dict__.iteritems():
        if not key.startswith('_'):
            options[key] = val
    options['prompts'] = pyconfmerge_config.prompts[args.locale]
    
    if template_is_dir:
        tfiles = glob("{0}/*".format(args.template)
                      if os.path.isdir(args.template) else args.template)
    else:
        tfiles = [args.template]
    for tfilename in tfiles:
        path, base = os.path.split(tfilename)
        if template_is_dir:
            if args.config is None or not os.path.exists(
                os.path.join(args.config, base)):
                cfilename = ''
            else:
                cfilename = os.path.join(args.config, base)
            if args.verbose > 1:
                print("Matched '{0}' config file to '{1}' template file".format(
                    cfilename, tfilename))
        else:
            cfilename = '' if args.config is None else args.config
        merge_python_files(
            tfilename, cfilename,
            os.path.join(args.output, base) if template_is_dir else args.output,
            options)
                     
    
