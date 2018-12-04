#!/usr/bin/env python
import argparse
import os
import re
import requests
import sys


SERVER_ROOT = 'https://bytesalad.stsci.edu/artifactory/api/pypi'
DEFAULT_REPO = 'datb-pypi'
EXTS = ['.tar.gz', '.whl']
NAME_RE = re.compile(r'([0-9A-Za-z_\.]+)-(.*)\.(whl|tar\.gz)')
# Match:                ^Package_Name_^  ^Ver^  ^Ext______^

def check_name(name):
    if NAME_RE.match(name):
        return True
    return False


def make_status(status, s):
    return f'[{status:^7s}]: {s}'


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--repo', default=DEFAULT_REPO,
                        help='Named pypi repository')
    parser.add_argument('--verbose', action='store_true')
    parser.add_argument('package')
    args = parser.parse_args()

    repo = args.repo
    package = os.path.basename(args.package)
    package_local = os.path.abspath(args.package)
    pkg_temp = package

    if not os.path.exists(package_local):
        print(f'Local file does exist: {package_local}', file=sys.stderr)
        exit(2)

    if not check_name(package):
        print(f'Non-conformant Python package: "{package}"', file=sys.stderr)
        exit(3)

    # Drop file extensions
    for ext in EXTS:
        pkg_temp = pkg_temp.replace(ext, '')

    # Extract name and version data
    name, version = pkg_temp.split('-', 1)

    # "Sanitize" data so URLs function correctly
    name = name.replace('_', '-')  # '-' and '_' exist; only '-' is discoverable
    version = version.split('-', 1)[0]  # Drop components of wheel package names

    # Construct upstream URL
    url = '/'.join([SERVER_ROOT, repo,
                    'packages', name,
                    version, package])

    # Check upstream headers
    with requests.head(url) as header:
        if not header.ok and 'X-Checksum-Md5' not in header.headers:
            if args.verbose:
                print(make_status('MISSING', url), file=sys.stderr)
                print(os.path.abspath(args.package))
            exit(1)

    if args.verbose:
        print(make_status('OK', url), file=sys.stderr)
    exit(0)
