from __future__ import with_statement
import re
import os
import sys
from io import StringIO
import optparse
import pep8

try:
    # Python 2
    from ConfigParser import ConfigParser
except ImportError:
    # Python 3
    from configparser import ConfigParser

pep8style = None


def get_parser():
    """Create a custom OptionParser"""
    from flake8 import __version__
    import flakey
    parser = pep8.get_parser()

    def version(option, opt, value, parser):
        parser.print_usage()
        parser.print_version()
        sys.exit(0)

    parser.version = '{0} (pep8: {1}, flakey: {2})'.format(
        __version__, pep8.__version__, flakey.__version__)
    parser.remove_option('--version')
    parser.add_option('--builtins', default='', dest='builtins',
                      help="append builtin functions to flakey's "
                           "_MAGIC_BUILTINS")
    parser.add_option('--exit-zero', action='store_true', default=False,
                      help='Exit with status 0 even if there are errors')
    parser.add_option('--max-complexity', default=-1, action='store',
                      type='int', help='McCabe complexity threshold')
    parser.add_option('--install-hook', default=False, action='store_true',
                      help='Install the appropriate hook for this '
                      'repository.', dest='install_hook')
    # don't overlap with pep8's verbose option
    parser.add_option('-V', '--version', action='callback',
                      callback=version,
                      help='Print the version info for flake8')
    return parser


def read_config(opts, opt_parser):
    configs = ('.flake8', '.pep8', 'tox.ini', 'setup.cfg')
    parser = ConfigParser()
    files_found = parser.read(configs)
    if not (files_found and parser.has_section('flake8')):
        return

    if opts.verbose:
        print("Found local configuration file(s): {0}".format(
            ', '.join(files_found)))

    option_list = dict([(o.dest, o.type or o.action)
                        for o in opt_parser.option_list])

    for o in parser.options('flake8'):
        v = parser.get('flake8', o)

        if opts.verbose > 1:
            print(" {0} = {1}".format(o, v))

        normed = o.replace('-', '_')
        if normed not in option_list:
            print("Unknown option: {0}".format(o))

        opt_type = option_list[normed]

        if opt_type in ('int', 'count'):
            v = int(v)
        elif opt_type in ('store_true', 'store_false'):
            v = True if v == 'True' else False

        setattr(opts, normed, v)

    for attr in ('filename', 'exclude', 'ignore', 'select'):
        val = getattr(opts, attr)
        if hasattr(val, 'split'):
            setattr(opts, attr, val.split(','))


def merge_opts(pep8_opts, our_opts):
    pep8_parser = pep8.get_parser()

    for o in pep8_parser.option_list:
        if not (o.dest and getattr(our_opts, o.dest)):
            continue

        new_val = getattr(our_opts, o.dest)
        old_val = getattr(pep8_opts, o.dest)
        if isinstance(old_val, list):
            old_val.extend(new_val)
            continue
        elif isinstance(old_val, tuple):
            new_val = tuple(new_val)
        setattr(pep8_opts, o.dest, new_val)


def skip_warning(warning, ignore=[]):
    # XXX quick dirty hack, just need to keep the line in the warning
    if not hasattr(warning, 'message') or ignore is None:
        # McCabe's warnings cannot be skipped afaik, and they're all strings.
        # And we'll get a TypeError otherwise
        return False
    if warning.message.split()[0] in ignore:
        return True
    if not os.path.isfile(warning.filename):
        return False

    # XXX should cache the file in memory
    with open(warning.filename) as f:
        line = f.readlines()[warning.lineno - 1]

    return skip_line(line)


def skip_line(line):
    return line.strip().lower().endswith('# noqa')


_NOQA = re.compile(r'flake8[:=]\s*noqa', re.I | re.M)


def skip_file(path, source=None):
    """Returns True if this header is found in path

    # flake8: noqa
    """
    if os.path.isfile(path):
        f = open(path)
    elif source:
        f = StringIO(source)
    else:
        return False

    try:
        content = f.read()
    finally:
        f.close()
    return _NOQA.search(content) is not None


def _initpep8(config_file=True):
    # default pep8 setup
    global pep8style
    import pep8
    if pep8style is None:
        pep8style = pep8.StyleGuide(config_file=config_file)
    pep8style.options.physical_checks = pep8.find_checks('physical_line')
    pep8style.options.logical_checks = pep8.find_checks('logical_line')
    pep8style.options.counters = dict.fromkeys(pep8.BENCHMARK_KEYS, 0)
    pep8style.options.messages = {}
    if not pep8style.options.max_line_length:
        pep8style.options.max_line_length = 79
    pep8style.args = []
    return pep8style
