from setuptools import setup, find_packages

setup(
    name="moltbook-sdk",
    version="0.1.0",
    description="Python SDK for Moltbook — the social network for AI agents",
    author="ScoutSI",
    url="https://github.com/scout-si/moltbook-sdk",
    packages=find_packages(),
    install_requires=["requests>=2.25.0"],
    python_requires=">=3.8",
    license="MIT",
)
