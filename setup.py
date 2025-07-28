"""Setup script for Japanese Receipt OCR tool."""

from setuptools import setup, find_packages
from pathlib import Path

# Read README
readme_path = Path(__file__).parent / "README.md"
long_description = readme_path.read_text(encoding="utf-8") if readme_path.exists() else ""

# Read requirements
requirements_path = Path(__file__).parent / "requirements.txt"
requirements = []
if requirements_path.exists():
    requirements = requirements_path.read_text().strip().split('\n')

setup(
    name="japanese-receipt-ocr",
    version="1.0.0",
    description="A Python CLI tool for processing Japanese receipts with OCR and extracting transaction data",
    long_description=long_description,
    long_description_content_type="text/markdown",
    author="",
    author_email="",
    url="",
    packages=find_packages(),
    package_dir={"": "src"},
    install_requires=requirements,
    entry_points={
        'console_scripts': [
            'receipts=cli:cli',
        ],
    },
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Operating System :: OS Independent",
        "Topic :: Office/Business :: Financial :: Accounting",
        "Topic :: Scientific/Engineering :: Image Recognition",
    ],
    python_requires=">=3.10",
    include_package_data=True,
    package_data={
        "": ["rules/*.yml"],
    },
)