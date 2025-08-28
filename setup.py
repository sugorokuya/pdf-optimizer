from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="pdf-optimizer",
    version="1.0.0",
    author="maltakoji",
    description="Advanced PDF optimization with enhanced pikepdf",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/maltakoji/pdf-optimizer",
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: Mozilla Public License 2.0 (MPL-2.0)",
        "Operating System :: OS Independent",
    ],
    python_requires=">=3.10",
    install_requires=[
        "pikepdf>=9.0.0",
        "pillow>=10.0.0",
        "numpy>=1.24.0",
        "pymupdf>=1.23.0",
    ],
)
