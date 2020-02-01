#!/usr/bin/env python3

# Copyright (c) 2019 Egor Tensin <Egor.Tensin@gmail.com>
# This file is part of the "cmake-common" project.
# For details, see https://github.com/egor-tensin/cmake-common.
# Distributed under the MIT License.

'''Download & build Boost on Travis.

This is similar to build.py, but auto-fills some parameters for build.py from
the Travis-defined environment variables.

Boost is built in $HOME/boost.
'''

import argparse
import logging
import os
import os.path
import sys


def _env(name):
    if name not in os.environ:
        raise RuntimeError(f'undefined environment variable: {name}')
    return os.environ[name]


def _check_travis():
    if 'TRAVIS' not in os.environ:
        raise RuntimeError('not running on Travis')


def _get_build_dir():
    return _env('HOME')


def _get_boost_dir():
    return os.path.join(_get_build_dir(), 'boost')


def _get_boost_version():
    return _env('travis_boost_version')


def _get_configuration():
    return _env('configuration')


def _get_platform():
    return _env('platform')


def _setup_logging():
    logging.basicConfig(
        format='%(asctime)s | %(levelname)s | %(message)s',
        level=logging.INFO)


def _parse_args(argv=None):
    if argv is None:
        argv = sys.argv[1:]
    logging.info('Command line arguments: %s', argv)

    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--link', metavar='LINKAGE', nargs='*',
                        help='how the libraries are linked')
    parser.add_argument('--runtime-link', metavar='LINKAGE',
                        help='how the libraries link to the runtime')
    parser.add_argument('b2_args', nargs='*', metavar='B2_ARG', default=[],
                        help='additional b2 arguments, to be passed verbatim')
    return parser.parse_args(argv)


def build_travis(argv=None):
    args = _parse_args(argv)
    _check_travis()

    this_module_dir = os.path.dirname(os.path.abspath(__file__))
    parent_module_dir = os.path.dirname(this_module_dir)
    sys.path.insert(1, parent_module_dir)
    from build import BoostVersion, main as build_main

    version = BoostVersion.from_string(_get_boost_version())
    travis_argv = [
        'download',
        '--unpack', _get_build_dir(),
        '--', str(version)
    ]
    build_main(travis_argv)

    unpacked_boost_dir = version.dir_path(_get_build_dir())
    boost_dir = _get_boost_dir()
    os.rename(unpacked_boost_dir, boost_dir)

    travis_argv = [
        'build',
        '--configuration', _get_configuration(),
        '--platform', _get_platform(),
    ]
    if args.link is not None:
        travis_argv.append('--link')
        travis_argv += args.link
    if args.runtime_link is not None:
        travis_argv += ['--runtime-link', args.runtime_link]
    travis_argv += ['--', boost_dir]
    build_main(travis_argv + args.b2_args)


def main(argv=None):
    _setup_logging()
    try:
        build_travis(argv)
    except Exception as e:
        logging.exception(e)
        raise


if __name__ == '__main__':
    main()
