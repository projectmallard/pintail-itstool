from setuptools import setup

import subprocess
import sys

if sys.version_info[0] != 3:
    sys.stderr.write("pintail-itstool requires python 3\n")
    sys.exit(1)

status, output = subprocess.getstatusoutput('itstool --version')
if status != 0:
    sys.stderr.write("pintail-itstool requires itstool >= 2.0.2\n")
    sys.exit(1)
version = tuple(int(x) for x in output.split()[-1].split('.'))
if version < (2, 0, 2):
    sys.stderr.write("pintail-itstool requires itstool >= 2.0.2\n")
    sys.exit(1)

setup(
    name='pintail-itstool',
    version='0.2',
    description='Use ITSTool to translate Pintail sites.',
    packages=['pintail', 'pintail.itstool'],
    namespace_packages=['pintail'],
    package_data={
    },
    install_requires=['pintail>=0.4'],
    author='Shaun McCance',
    author_email='shaunm@gnome.org',
    license='GPLv2+',
    classifiers=[
        'Development Status :: 3 - Alpha',
        'Environment :: Console',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3 :: Only',
        'Topic :: Documentation',
        'Topic :: Software Development :: Documentation',
        'Topic :: Text Processing :: Markup',
        'Topic :: Text Processing :: Markup :: XML',
        'License :: OSI Approved :: GNU General Public License v2 or later (GPLv2+)'
    ],
)
