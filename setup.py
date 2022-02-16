#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# This file is part of the AIO Modbus project
#
# Copyright (c) 2020 Tiago Coutinho
# Distributed under the GNU General Public License v3. See LICENSE for more info.

"""The setup script."""

from setuptools import setup, find_packages

with open("README.md") as readme_file:
    readme = readme_file.read()

with open("HISTORY.md") as history_file:
    history = history_file.read()

requirements = [
    "umodbus", "connio", "numpy"
]

setup_requirements = ["pytest-runner"]

test_requirements = ["pytest>=3"]

setup(
    author="Tiago Coutinho",
    author_email="coutinhotiago@gmail.com",
    python_requires=">=3.5",
    classifiers=[
        "Development Status :: 2 - Pre-Alpha",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: GNU General Public License v3 (GPLv3)",
        "Natural Language :: English",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.5",
        "Programming Language :: Python :: 3.6",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
    ],
    description="Async ModBus python library",
    install_requires=requirements,
    license="GNU General Public License v3",
    long_description=readme + "\n\n" + history,
    long_description_content_type="text/markdown",
    include_package_data=True,
    keywords="async_modbus, asyncio, modbus",
    name="async_modbus",
    py_modules=['async_modbus'],
    setup_requires=setup_requirements,
    test_suite="tests",
    tests_require=test_requirements,
    url="https://github.com/tiagocoutinho/async_modbus",
    project_urls={
        "Documentation": "https://tiagocoutinho.github.io/async_modbus/",
        "Source": "https://github.com/tiagocoutinho/async_modbus/",
    },
    version="0.1.4",
    zip_safe=False,
)
