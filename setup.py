#!/usr/bin/env python
# coding: utf-8

import setuptools

with open("README.md", "r") as fh:
    long_description = fh.read()

setuptools.setup(
    name='ecg_plot',
    version='0.2.2',
    # scripts=['ecg_plot'] ,
    author="dy1901",
    author_email="dy1901@gmail.com",
    license='MIT License',
    description="Plot standard ECG chart from data",
    long_description=open("README.md").read(),
    long_description_content_type="text/markdown",
    url="https://github.com/dy1901/ecg_plot",
    # packages=setuptools.find_packages(),
    # py_modules=['src.ecg_plot'],
    packages = ['ecg_plot'],
    install_requires=[],
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
 )