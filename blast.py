#!/usr/bin/env python
import contextlib
import os
import yaml
import subprocess
import sys
from packaging.specifiers import SpecifierSet
from packaging.version import Version, InvalidVersion


USER_CONFIG = os.path.expanduser('~/.blast/config.yaml')
USER_CONFIG_EXISTS = os.path.exists(USER_CONFIG)
SPECIFIERS = ['~', '!', '<', '>', '=']

@contextlib.contextmanager
def use_directory(path):
    prev = os.path.abspath(os.curdir)
    os.chdir(path)
    try:
        yield
    finally:
        os.chdir(prev)


class PyEnv:
    def __init__(self, version, venv):
        self.version = version
        self.venv = venv
        self.environ = None

    def _cmd(self, *args, **kwargs):
        if not args:
            raise ValueError('Expecting arguments to pass to pyenv. Got nothing.')

        command = []
        proc = None
        shell = False
        stdout = None
        stderr = None
        env = self.environ

        if kwargs.get('redirect', False):
            stdout = subprocess.PIPE
            stderr = subprocess.PIPE

        if kwargs.get('override', False):
            command = ['pyenv']

        for arg in args:
            command.append(arg)

        if kwargs.get('shell', False):
            shell = True
            command = ' '.join(command)  # convert to string

        try:
            proc = subprocess.run(command, env=env, shell=shell, stdout=stdout, stderr=stderr, check=True, encoding='utf-8')
        except subprocess.CalledProcessError as cpe:
            if cpe.returncode:
                print('Command (exit {}): {}'.format(cpe.returncode, command))
            return cpe

        return proc

    def run(self, *args, **kwargs):
        proc = self._cmd(*args, **kwargs)
        return proc

    def create(self):
        if os.environ.get('PYENV_ROOT'):
            if not os.path.exists(os.path.join(os.environ['PYENV_ROOT'], 'versions', self.version)):
                proc_inst = self._cmd('install', '-s', self.version, override=True)
                if proc_inst.stderr:
                    if not 'already' in proc_inst.stderr:
                        print(proc_inst.stderr)
                        exit(1)

            if not os.path.exists(os.path.join(os.environ['PYENV_ROOT'], 'versions', self.venv)):
                proc_venv = self._cmd('virtualenv', self.version, self.venv, override=True)
        else:
            raise RuntimeError('PYENV_ROOT is not defined.')
            exit(1)


    def activate(self):
        env = {}
        command = 'eval "$(pyenv init -)" ' \
                  '&& eval "$(pyenv virtualenv-init -)" ' \
                  '&& pyenv activate "{}" && pyenv rehash && printenv'.format(self.venv)

        proc = self._cmd(command,
                         shell=True, redirect=True)

        for record in proc.stdout.splitlines():
            if '=' not in record:
                continue
            k, v = record.split('=', 1)
            env[k] = v

        self.environ = env.copy()


class Git:
    def __init__(self, uri):
        self.uri = uri
        self.base = os.path.abspath(os.path.basename(self.uri).replace('.git', ''))
        self.basepath = self.base
        self._tags = []

    def _cmd(self, *args, **kwargs):
        if not args:
            raise ValueError('Expecting arguments to pass to Git. Got nothing.')

        command = ['git']
        proc = None

        for arg in args:
            command.append(arg)

        try:
            proc = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True, encoding='utf-8')
        except subprocess.CalledProcessError as cpe:
            print('Command (exit {}): {}'.format(cpe.returncode, command))
            print(cpe.stderr.strip())
            print(cpe)
            exit(1)

        return proc

    def _has_repo(self):
        if not os.path.exists('.git'):
            raise FileNotFoundError('No git repository present.')
        return True

    def clone(self):
        if os.path.exists(self.basepath):
            return self.basepath

        self._cmd('clone', self.uri)
        return self.basepath

    def fetch(self, *args, **kwargs):
        self._has_repo()
        self._cmd('fetch', *args, *kwargs)

    def checkout(self, ref, **kwargs):
        self._has_repo()
        self._cmd('checkout', ref, **kwargs)

    def reset(self, *args, **kwargs):
        self._has_repo()
        self._cmd('reset', *args, **kwargs)

    def clean(self, *args, **kwargs):
        self._has_repo()
        self._cmd('clean', *args, **kwargs)

    def describe(self, *args, **kwargs):
        self._has_repo()
        result = self._cmd('describe', *args, **kwargs)
        return result.stdout.strip()

    def tag_nearest(self):
        self._has_repo()
        return self.describe('--tags', '--abbrev=0')

    @property
    def tags(self):
        self._has_repo()
        tags = [x.strip() for x in self._cmd('tag', quiet=True).stdout.splitlines()]

        if len(self._tags) == len(tags):
            return self._tags

        self._tags = []  # Clear tags
        for tag in tags:
            self._tags.append(tag)

        return self._tags


def setuptools_inject():
    print("Injecting setuptools...")
    with open('setup.py', 'r') as script:
        orig = script.read().splitlines()

    orig.insert(0, 'import setuptools')

    with open('setup.py', 'w+') as script:
        new = '\n'.join(orig)
        script.write(new)


def eval_specifier(spec, tag, bad_patterns=None):
    # Determine if specifiers are present in spec string
    have_specifier = False
    for ch in spec:
        if ch in SPECIFIERS:
            have_specifier = True

    # When no specifier is present we need to prepend one
    # to satisfy SpecifierSet's basic input requirements
    if not have_specifier:
        spec = '==' + spec

    spec = SpecifierSet(spec)

    # Normalize non-standard tagging conventions
    if bad_patterns is not None:
        for pattern in bad_patterns:
            tag = tag.replace(pattern, '')

    try:
        tag = Version(tag)
    except InvalidVersion as e:
        print("{}".format(e), file=sys.stderr)
        tag = ''

    return tag in spec


if __name__ == '__main__':
    # import argparse
    # from pprint import pprint

    # parser = argparse.ArgumentParser()
    # parser.add_argument('-c', '--config', action='store', default=USER_CONFIG)
    # parser.add_argument('repofile', action='store')

    config = yaml.load("""
    host: https://github.com
    organization: spacetelescope

    global:
        python:
            - 3.5.5
            - 3.6.6
            - 3.7.0

        requires:
            - wheel

        version_latest: true

        version_bad_patterns:
            - 'release_'
            - '_release'
            - 'release-'
            - '-release'

    projects:
        #acstools:
        #    requires:
        #        - relic

        #asdf:
        #    requires: null

        #calcos:
        #    requires: null

        #costools:
        #    requires: null

        #crds:
        #    requires:
        #        - astropy
        #        - numpy
        #        - requests
        #    setuptools_inject: true

        #drizzle:
        #    requires: null

        #drizzlepac:
        #    requires:
        #        - astropy
        #        - numpy

        #fitsblender:
        #    requires: null

        #imexam:
        #    requires: null

        #nictools:
        #    requires: null

        #pysynphot:
        #    requires: null

        reftools:
            requires: null

        relic:
            requires: null

        stistools:
            requires: null

        stsci.convolve:
            requires: null

        stsci.distutils:
            requires: null

        stsci.image:
            requires: null

        stsci.imagemanip:
            requires: null

        stsci.imagestats:
            requires: null

        stsci.ndimage:
            requires: null

        stsci.numdisplay:
            requires: null

        stsci.stimage:
            requires: null

        stsci.skypac:
            requires: null

        stsci.sphere:
            requires: null

        stsci.tools:
            requires: null

        stregion:
            requires: null

        stwcs:
            requires: null

        wfpc2tools:
            requires: null

        wfc3tools:
            requires: null
    """)

    upload_dir = os.path.abspath(os.path.join(os.curdir, 'upload'))
    if not os.path.exists(upload_dir):
        os.mkdir(upload_dir)

    # Begin aliveness checks before we get too far
    check_keys = ['global', 'host', 'organization', 'projects']
    failed_keys = False
    failed_requires = False

    # Check general configuration keys
    for key in check_keys:
        if not config.get(key):
            print('Error: The `{}` key is required.'.format(key), file=sys.stderr)
            failed_keys = True

    if failed_keys:
        exit(1)

    # Check structure of project dictionaries
    for project, info in config['projects'].items():
        print(project, info)
        if info is None and not info.get('requires'):
            print('Error: {}: Missing `requires` list'.format(project), file=sys.stderr)
            failed_requires = True

    if failed_requires:
        exit(1)

    # Perform matrix tasks
    for project, info in config['projects'].items():
        url = '/'.join([config['host'], config['organization'], project])
        repo = Git(url)

        print('Repository: {}'.format(url))
        print('Source directory: {}'.format(repo.basepath))
        try:
            repo.clone()
        except FileNotFoundError as e:
            print('Skipping "{}" due to: {}'.format(project, e))
            continue

        with use_directory(repo.basepath):
            repo.fetch('--all', '--tags')
            for python_version in config['global']['python']:
                tags = []
                venv_name = 'py{}'.format(python_version.replace('.', ''))

                print('=> Using Python {} (virtual: {})...'.format(python_version, venv_name))
                pyenv = PyEnv(python_version, venv_name)
                pyenv.create()
                pyenv.activate()

                # Upgrade PIP
                pyenv.run('pip', 'install', '--upgrade', 'pip', redirect=True)

                # Generic setup
                if config.get('global'):
                    if config['global'].get('requires'):
                        for pkg in config['global']['requires']:
                            pyenv.run('pip', 'install', pkg, redirect=True)

                    if config['global'].get('version_latest'):
                        repo.reset('--hard')
                        repo.clean('-f', '-x', '-d')
                        repo.checkout('master')
                        tags = [repo.tag_nearest()]
                    else:
                        tags = repo.tags

                if info.get('requires'):
                    for pkg in info['requires']:
                        pyenv.run('pip', 'install', pkg)

                for tag in tags:
                    if info.get('build_versions'):
                        spec = info['build_versions']
                        sanitize = None

                        if config['global'].get('version_bad_patterns'):
                            sanitize = config['global']['version_bad_patterns']

                        if info.get('version_bad_patterns'):
                            sanitize += info['version_bad_patterns']

                        if not eval_specifier(spec, tag, sanitize):
                            continue

                    print('==> Building {}::{}'.format(project, tag))

                    repo.reset('--hard')
                    repo.clean('-f', '-x', '-d')
                    repo.checkout(tag)

                    if info.get('setuptools_inject', False):
                        setuptools_inject()

                    for build_command in ['sdist', 'bdist_egg', 'bdist_wheel']:
                        print('===> {}::{}: {}: '.format(project, tag, build_command), end='')
                        proc = pyenv.run('python', 'setup.py', build_command, '-d', upload_dir, redirect=True)
                        if proc.stderr and proc.returncode:
                            print("FAILED")
                            print('#{}'.format('!' * 78))
                            print(proc.stderr)
                            print('#{}'.format('!' * 78))
                        else:
                            print("SUCCESS")
