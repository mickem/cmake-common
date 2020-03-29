# Copyright (c) 2019 Egor Tensin <Egor.Tensin@gmail.com>
# This file is part of the "cmake-common" project.
# For details, see https://github.com/egor-tensin/cmake-common.
# Distributed under the MIT License.

R'''Build a CMake project on AppVeyor.

This is similar to build.py, but auto-fills some parameters for build.py from
the AppVeyor-defined environment variables.

The project is built in C:\Projects\build.
'''

import argparse
from enum import Enum
import logging
import os
import sys

from project.cmake.build import build
import project.utils


class Image(Enum):
    VS_2013 = 'Visual Studio 2013'
    VS_2015 = 'Visual Studio 2015'
    VS_2017 = 'Visual Studio 2017'
    VS_2019 = 'Visual Studio 2019'

    def __str__(self):
        return self.value


def _parse_image(s):
    try:
        return Image(s)
    except ValueError as e:
        raise ValueError(f'unsupported AppVeyor image: {s}') from e


class Generator(Enum):
    VS_2013 = 'Visual Studio 12 2013'
    VS_2015 = 'Visual Studio 14 2015'
    VS_2017 = 'Visual Studio 15 2017'
    VS_2019 = 'Visual Studio 16 2019'

    def __str__(self):
        return self.value

    @staticmethod
    def from_image(image):
        if image is Image.VS_2013:
            return Generator.VS_2013
        if image is Image.VS_2015:
            return Generator.VS_2015
        if image is Image.VS_2017:
            return Generator.VS_2017
        if image is Image.VS_2019:
            return Generator.VS_2019
        raise RuntimeError(f"don't know which generator to use for image: {image}")


class Platform(Enum):
    x86 = 'Win32'
    X64 = 'x64'

    def __str__(self):
        return self.value


def _parse_platform(s):
    try:
        return Platform(s)
    except ValueError as e:
        raise ValueError(f'unsupported AppVeyor platform: {s}') from e


def _env(name):
    if name not in os.environ:
        raise RuntimeError(f'undefined environment variable: {name}')
    return os.environ[name]


def _check_appveyor():
    if 'APPVEYOR' not in os.environ:
        raise RuntimeError('not running on AppVeyor')


def _get_src_dir():
    return _env('APPVEYOR_BUILD_FOLDER')


def _get_build_dir():
    return R'C:\Projects\build'


def _get_generator():
    image = _parse_image(_env('APPVEYOR_BUILD_WORKER_IMAGE'))
    return str(Generator.from_image(image))


def _get_platform():
    return str(_parse_platform(_env('PLATFORM')))


def _get_configuration():
    return _env('CONFIGURATION')


def _parse_args(argv=None):
    if argv is None:
        argv = sys.argv[1:]
    logging.info('Command line arguments: %s', argv)

    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)

    parser.add_argument('--install', metavar='DIR', dest='install_dir',
                        help='install directory')
    parser.add_argument('cmake_args', nargs='*', metavar='CMAKE_ARG', default=[],
                        help='additional CMake arguments, to be passed verbatim')
    return parser.parse_args(argv)


def build_appveyor(argv=None):
    args = _parse_args(argv)
    _check_appveyor()

    appveyor_argv = [
        '--build', _get_build_dir(),
        '--configuration', _get_configuration(),
    ]
    if args.install_dir is not None:
        appveyor_argv += [
            '--install', args.install_dir,
        ]
    appveyor_argv += [
        '--',
        _get_src_dir(),
        '-G', _get_generator(),
        '-A', _get_platform(),
    ]
    build(appveyor_argv + args.cmake_args)


def main(argv=None):
    with project.utils.setup_logging():
        build_appveyor(argv)


if __name__ == '__main__':
    main()
