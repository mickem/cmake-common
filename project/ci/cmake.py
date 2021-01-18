# Copyright (c) 2020 Egor Tensin <Egor.Tensin@gmail.com>
# This file is part of the "cmake-common" project.
# For details, see https://github.com/egor-tensin/cmake-common.
# Distributed under the MIT License.

import argparse
import logging
import sys

from project.cmake.build import BuildParameters, build
from project.toolchain import ToolchainType


def _parse_args(dirs, argv=None):
    if argv is None:
        argv = sys.argv[1:]
    logging.info('Command line arguments: %s', argv)

    parser = argparse.ArgumentParser(
        description=dirs.get_cmake_help(),
        formatter_class=argparse.RawDescriptionHelpFormatter)

    parser.add_argument('--install', action='store_true',
                        help='install the project')
    parser.add_argument('--boost', metavar='DIR', dest='boost_dir',
                        help='set Boost directory path')
    parser.add_argument('--toolset', metavar='TOOLSET',
                        type=ToolchainType.parse,
                        help='toolset to use')
    parser.add_argument('cmake_args', nargs='*', metavar='CMAKE_ARG', default=[],
                        help='additional CMake arguments, to be passed verbatim')
    return parser.parse_args(argv)


def build_ci(dirs, argv=None):
    args = _parse_args(dirs, argv)

    install_dir = dirs.get_install_dir() if args.install else None
    params = BuildParameters(dirs.get_src_dir(),
                             build_dir=dirs.get_cmake_dir(),
                             install_dir=install_dir,
                             platform=dirs.get_platform(),
                             configuration=dirs.get_configuration(),
                             boost_dir=args.boost_dir or dirs.get_boost_dir(),
                             toolset=args.toolset,
                             cmake_args=dirs.get_cmake_args() + args.cmake_args)
    build(params)
