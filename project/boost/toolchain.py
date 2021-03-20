# Copyright (c) 2020 Egor Tensin <Egor.Tensin@gmail.com>
# This file is part of the "cmake-common" project.
# For details, see https://github.com/egor-tensin/cmake-common.
# Distributed under the MIT License.

# See docs/boost.md for a more thorough description of my pain.

import abc
from contextlib import contextmanager
import logging
import os.path
import shutil

import project.mingw
import project.os
from project.toolchain import ToolchainType
from project.utils import temp_file


class BootstrapToolchain(abc.ABC):
    @abc.abstractmethod
    def get_bootstrap_bat_args(self):
        pass

    @abc.abstractmethod
    def get_bootstrap_sh_args(self):
        pass

    @staticmethod
    def detect(hint):
        if hint is ToolchainType.AUTO:
            return BootstrapAuto()
        if hint is ToolchainType.MSVC:
            return BootstrapMSVC()
        if hint is ToolchainType.GCC:
            return BootstrapGCC()
        if hint is ToolchainType.MINGW:
            return BootstrapMinGW()
        if hint is ToolchainType.CLANG:
            return BootstrapClang()
        if hint is ToolchainType.CLANG_CL:
            return BootstrapClangCL()
        raise NotImplementedError(f'unrecognized toolset: {hint}')


class BootstrapAuto(BootstrapToolchain):
    # Let Boost.Build do the detection.  Most commonly it means GCC on
    # Linux-likes and MSVC on Windows.

    def get_bootstrap_bat_args(self):
        return []

    def get_bootstrap_sh_args(self):
        return []


class BootstrapMSVC(BootstrapAuto):
    # bootstrap.bat picks up MSVC by default.
    pass


class BootstrapGCC(BootstrapToolchain):
    def get_bootstrap_bat_args(self):
        return ['gcc']

    def get_bootstrap_sh_args(self):
        return ['--with-toolset=gcc']


def _gcc_or_auto():
    if shutil.which('gcc') is not None:
        return ['gcc']
    return []


class BootstrapMinGW(BootstrapToolchain):
    def get_bootstrap_bat_args(self):
        # On Windows, prefer GCC if it's available.
        return _gcc_or_auto()

    def get_bootstrap_sh_args(self):
        return []


class BootstrapClang(BootstrapToolchain):
    def get_bootstrap_bat_args(self):
        # As of 1.74.0, bootstrap.bat isn't really aware of Clang, so try GCC,
        # then auto-detect.
        return _gcc_or_auto()

    def get_bootstrap_sh_args(self):
        # bootstrap.sh, on the other hand, is very much aware of Clang, and
        # it can build b2 using this compiler.
        return ['--with-toolset=clang']


class BootstrapClangCL(BootstrapClang):
    # There's no point in building b2 using clang-cl; clang though, presumably
    # installed alongside clang-cl, should still be used if possible.
    pass


class Toolchain(abc.ABC):
    def __init__(self, platform):
        self.platform = platform

    def b2_args(self, configuration):
        return self.platform.b2_args(configuration)

    @staticmethod
    @contextmanager
    def detect(hint, platform):
        if hint is ToolchainType.AUTO:
            yield Auto(platform)
        elif hint is ToolchainType.MSVC:
            yield MSVC(platform)
        elif hint is ToolchainType.GCC:
            with GCC.setup(platform) as toolchain:
                yield toolchain
        elif hint is ToolchainType.MINGW:
            with MinGW.setup(platform) as toolchain:
                yield toolchain
        elif hint is ToolchainType.CLANG:
            with Clang.setup(platform) as toolchain:
                yield toolchain
        elif hint is ToolchainType.CLANG_CL:
            yield ClangCL(platform)
        else:
            raise NotImplementedError(f'unrecognized toolset: {hint}')


class Auto(Toolchain):
    # Let Boost.Build do the detection.  Most commonly it means GCC on
    # Linux-likes and MSVC on Windows.
    pass


class MSVC(Auto):
    def b2_args(self, configuration):
        return super().b2_args(configuration) + [
            'toolset=msvc',
        ]


def _full_exe_name(exe):
    if project.os.on_linux():
        # There's no PATHEXT on Linux.
        return exe
    # b2 on Windows/Cygwin doesn't like it when the executable name doesn't
    # include the extension.
    dir_path = os.path.dirname(exe) or None
    path = shutil.which(exe, path=dir_path)
    if not path:
        raise RuntimeError(f"executable '{exe}' could not be found")
    if project.os.on_cygwin():
        # On Cygwin, shutil.which('gcc') == '/usr/bin/gcc' and shutil.which('gcc.exe')
        # == '/usr/bin/gcc.exe'; we want the latter version.  shutil.which('clang++')
        # == '/usr/bin/clang++' is fine though, since it _is_ the complete path
        # (clang++ is a symlink).
        if os.path.exists(path) and os.path.exists(path + '.exe'):
            path += '.exe'
    if dir_path:
        # If it was found in a specific directory, include the directory in the
        # result.  shutil.which returns the executable name prefixed with the
        # path argument.
        return path
    # If it was found in PATH, just return the basename (which includes the
    # extension).
    return os.path.basename(path)


class BoostBuildToolset:
    CUSTOM = 'custom'

    def __init__(self, compiler, path, options):
        if not compiler:
            raise RuntimeError('compiler type is required (like gcc, clang, etc.)')
        self.compiler = compiler
        self.version = BoostBuildToolset.CUSTOM
        path = path or ''
        path = path and _full_exe_name(path)
        self.path = path
        options = options or []
        self.options = options

    @property
    def toolset(self):
        if self.version:
            return f'{self.compiler}-{self.version}'
        return self.compiler

    def b2_toolset(self):
        return f'toolset={self.toolset}'

    def b2_args(self):
        return [self.b2_toolset()]

    def _format_using_options(self):
        return ''.join(f'\n    <{name}>{val}' for name, val in self.options)

    def format_using(self):
        version = self.version and f'{self.version} '
        path = self.path and f'{self.path} '
        return f'''using {self.compiler} : {version}: {path}:{self._format_using_options()}
;'''


class ConfigFile(Toolchain):
    def __init__(self, platform, config_path, toolset):
        super().__init__(platform)
        self.config_path = config_path
        self.toolset = toolset

    @staticmethod
    @abc.abstractmethod
    def get_toolset(platform):
        pass

    @staticmethod
    @abc.abstractmethod
    def format_config(toolset):
        pass

    @classmethod
    @contextmanager
    def setup(cls, platform):
        toolset = cls.get_toolset(platform)
        config = cls.format_config(toolset)
        logging.info('Using user config:\n%s', config)
        tmp = temp_file(config, mode='w', prefix='user_config_', suffix='.jam')
        with tmp as path:
            yield cls(platform, path, toolset)

    def b2_args(self, configuration):
        # All the required options and the toolset definition should be in the
        # user configuration file.
        args = super().b2_args(configuration)
        args.append(f'--user-config={self.config_path}')
        args += self.toolset.b2_args()
        return args


class GCC(ConfigFile):
    # Force GCC.  We don't care whether it's a native Linux GCC or a
    # MinGW-flavoured GCC on Windows.
    COMPILER = 'gcc'

    @staticmethod
    def get_options():
        return [
            # TODO: this is a petty attempt to get rid of build warnings in
            # older Boost versions.  Revise and expand this list or remove it?
            # warning: 'template<class> class std::auto_ptr' is deprecated
            ('cxxflags', '-Wno-deprecated-declarations'),
            # warning: unnecessary parentheses in declaration of 'assert_arg'
            ('cxxflags', '-Wno-parentheses'),
        ]

    @staticmethod
    def get_toolset(platform):
        return BoostBuildToolset(GCC.COMPILER, 'g++', GCC.get_options())

    @staticmethod
    def format_config(toolset):
        return toolset.format_using()


class MinGW(GCC):
    # It's important that Boost.Build is actually smart enough to detect the
    # GCC prefix (like "x86_64-w64-mingw32" and prepend it to other tools like
    # "ar").

    @staticmethod
    def get_toolset(platform):
        paths = project.mingw.MinGW(platform)
        compiler = paths.gxx()
        return BoostBuildToolset(MinGW.COMPILER, compiler, MinGW.get_options())


class Clang(ConfigFile):
    COMPILER = 'clang'

    @staticmethod
    def get_toolset(platform):
        options = [
            ('cxxflags', '-DBOOST_USE_WINDOWS_H'),
            # TODO: this is a petty attempt to get rid of build warnings in
            # older Boost versions.  Revise and expand this list or remove it?
            # warning: unused typedef 'boost_concept_check464' [-Wunused-local-typedef]
            ('cxxflags', '-Wno-unused-local-typedef'),
            # error: constant expression evaluates to -105 which cannot be narrowed to type 'boost::re_detail::cpp_regex_traits_implementation<char>::char_class_type' (aka 'unsigned int')
            ('cxxflags', '-Wno-c++11-narrowing'),
        ] + GCC.get_options()
        if project.os.on_windows():
            # Prefer LLVM binutils:
            if shutil.which('llvm-ar') is not None:
                options.append(('archiver', 'llvm-ar'))
            if shutil.which('llvm-ranlib') is not None:
                options.append(('ranlib', 'llvm-ranlib'))
        return BoostBuildToolset(Clang.COMPILER, 'clang++', options)

    @staticmethod
    def format_config(toolset):
        # To make clang.exe/clang++.exe work on Windows, some tweaks are
        # required.  I borrowed them from CMake's Windows-Clang.cmake [1].
        # Adding them globally to Boost.Build options is described in [2].
        #
        # [1]: https://github.com/Kitware/CMake/blob/v3.18.4/Modules/Platform/Windows-Clang.cmake
        # [2]: https://stackoverflow.com/questions/2715106/how-to-create-a-new-variant-in-bjam
        return f'''project : requirements
    <target-os>windows:<define>_MT
    <target-os>windows,<variant>debug:<define>_DEBUG
    <target-os>windows,<runtime-link>static,<variant>debug:<cxxflags>"-Xclang -flto-visibility-public-std -Xclang --dependent-lib=libcmtd"
    <target-os>windows,<runtime-link>static,<variant>release:<cxxflags>"-Xclang -flto-visibility-public-std -Xclang --dependent-lib=libcmt"
    <target-os>windows,<runtime-link>shared,<variant>debug:<cxxflags>"-D_DLL -Xclang --dependent-lib=msvcrtd"
    <target-os>windows,<runtime-link>shared,<variant>release:<cxxflags>"-D_DLL -Xclang --dependent-lib=msvcrt"
;
{toolset.format_using()}
'''


class ClangCL(Toolchain):
    def b2_args(self, configuration):
        return super().b2_args(configuration) + [
            'toolset=clang-win',
            'define=BOOST_USE_WINDOWS_H',
        ]
