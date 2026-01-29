#!/usr/bin/env python3
from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as f:
    long_description = f.read()

setup(
    name="trkg",
    version="2.0.0",
    author="T-RKG Research Team",
    description="Temporal Records Knowledge Graph for Enterprise Governance",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/trkg/trkg",
    packages=find_packages(),
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Science/Research",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Topic :: Scientific/Engineering :: Artificial Intelligence",
    ],
    python_requires=">=3.8",
    install_requires=[
        "networkx>=2.6.0",
    ],
    extras_require={
        "dev": ["pytest>=7.0.0", "black>=22.0.0", "mypy>=0.950"],
        "owl": ["rdflib>=6.0.0"],
    },
    include_package_data=True,
    package_data={
        "trkg": ["../ontology/*.owl"],
    },
)
