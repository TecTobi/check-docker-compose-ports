from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="check-docker-compose-ports",
    version="1.0.0",
    author="TecTobi (Tobias Puetz)",
    author_email="mail@tectobi.com",
    description="A CLI tool to check port conflicts in docker-compose files",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/tectobi/check-docker-compose-ports",
    packages=find_packages(),
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
    ],
    python_requires=">=3.7",
    install_requires=[
        "PyYAML>=5.4.0",
        "psutil>=5.8.0",
    ],
    entry_points={
        "console_scripts": [
            "check-docker-compose-ports=check_docker_compose_ports.cli:main",
        ],
    },
)
