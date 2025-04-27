#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
TempusLoom - Setup Script
"""

from setuptools import setup, find_packages

setup(
    name="tempusloom",
    version="0.1.0",
    description="TempusLoom - Advanced Image Editing Application",
    author="TempusLoom Team",
    author_email="info@tempusloom.com",
    url="https://github.com/tempusloom/tempusloom",
    packages=find_packages(),
    install_requires=[
        "PyQt6>=6.4.0",
        "numpy>=1.23.0",
        "Pillow>=9.2.0",
        "opencv-python>=4.6.0",
    ],
    entry_points={
        "console_scripts": [
            "tempusloom=tempusloom.main:main",
        ],
    },
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: End Users/Desktop",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.10",
        "Topic :: Multimedia :: Graphics :: Editors",
    ],
    python_requires=">=3.10",
) 