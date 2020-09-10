"""Setup file to build and install the REM PyPI package

Copyright:

    setup.py build and install REM PyPI package
    Copyright (C) 2020  Christopher Thornton

    This program is free software: you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.

    This program is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with this program.  If not, see <http://www.gnu.org/licenses/>.
"""
from setuptools import setup

setup(name='REM',
      version='0.2.3',
      packages=['REM', ],
      description='',
      classifiers=[
          'Development Status :: 4 - Beta',
          'Intended Audience :: Business Administration',
          'License :: OSI Approved :: GNU General Public License v3 (GPLv3)',
          'Natural Language :: English',
          'Operating System :: OS Independent',
          'Programming Language :: Python :: 3.6',
          'Topic :: Accounting :: Revenue & Expense :: Validation',
          'Topic :: Software Development :: Libraries :: Python Modules'
      ],
      keywords='account audit transaction validation',
      url='https://github.com/cnthornton/REM/',
      download_url='https://github.com/cnthornton/REM/archive/v0.1.1.tar.gz',
      author='Christopher Thornton',
      author_email='christopher.n.thornton@gmail.com',
      license='GPLv3',
      include_package_data=True,
      zip_safe=False,
      install_requires=['numpy', 'pandas', 'PySimpleGUI', 'pyodbc'],
      entry_points={
          'console_scripts': [
              'REM = REM.main_win:main',
          ]
      }
      )
