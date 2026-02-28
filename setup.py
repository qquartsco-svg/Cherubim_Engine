from setuptools import setup, find_packages

setup(
    name="cherubim-engine",
    version="1.0.0",
    description="Eden Basin Finder — Planetary Habitability Search Engine",
    long_description=open("README.md", encoding="utf-8").read(),
    long_description_content_type="text/markdown",
    author="GNJz (Qquarts)",
    url="https://github.com/qquartsco-svg/Cherubim_Engine",
    packages=find_packages(),
    install_requires=["numpy"],
    python_requires=">=3.9",
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Topic :: Scientific/Engineering :: Physics",
        "Topic :: Scientific/Engineering :: Astronomy",
    ],
    keywords="eden habitability exoplanet planet search state-basin physics",
)
