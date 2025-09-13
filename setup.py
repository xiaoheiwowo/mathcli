from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

with open("requirements.txt", "r", encoding="utf-8") as fh:
    requirements = [line.strip() for line in fh if line.strip() and not line.startswith("#")]

setup(
    name="mathcli",
    version="0.2.0",
    packages=find_packages(),
    install_requires=requirements,
    entry_points={
        'console_scripts': [
            'mathcli=mathcli.cli:main',
        ],
    },
    author="Math Grader Team",
    author_email="team@mathgrader.com",
    description="AI-powered math homework grading tool with OCR and intelligent analysis",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/mathgrader/mathcli",
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Topic :: Education",
        "Topic :: Scientific/Engineering :: Mathematics",
    ],
    python_requires='>=3.8',
)
