from setuptools import setup, find_packages

setup(
    name="trading_strategie_bot",
    version="0.1",
    packages=find_packages(where="trading_strategie_bot/src"),
    package_dir={"": "trading_strategie_bot/src"},
    install_requires=[
        "SQLAlchemy",
        "pytest"
    ],
)