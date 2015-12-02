"""cfnlambda setup module

This Source Code Form is subject to the terms of the Mozilla Public
License, v. 2.0. If a copy of the MPL was not distributed with this
file, You can obtain one at http://mozilla.org/MPL/2.0/.
"""

from setuptools import setup
from codecs import open
from os import path

here = path.abspath(path.dirname(__file__))

with open(path.join(here, 'README.rst'), encoding='utf-8') as f:
    long_description = f.read()

setup(
    name='cfnlambda',

    # Versions should comply with PEP440.  For a discussion on single-sourcing
    # the version across setup.py and the project code, see
    # https://packaging.python.org/en/latest/single_source_version.html
    version='1.0.1',

    description='Collection of tools to enable use of AWS Lambda with '
                'CloudFormation.',
    long_description=long_description,
    url='https://github.com/gene1wood/cfnlambda',
    author='Gene Wood',
    author_email='gene_wood@cementhorizon.com',
    license='MPL-2.0',

    # See https://pypi.python.org/pypi?%3Aaction=list_classifiers
    classifiers=[
        'Development Status :: 4 - Beta',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: Mozilla Public License 2.0 (MPL 2.0)',
        'Programming Language :: Python :: 2.7',
    ],
    keywords='aws lambda cloudformation',
    py_modules=['cfnlambda'],
    install_requires=['boto3',
                      'botocore'],
)
