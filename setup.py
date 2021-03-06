import setuptools


setuptools.setup(
    name="flash",
    version="0.2.1",
    packages=["."],
    install_requires=["click>=8.0.0", "toml==0.10.2", "dacite==1.6.0"],
    entry_points={"console_scripts": ["flash=flash:cli"]},
    classifiers=[
        "Programming Language :: Python :: 3",
        "Operating System :: OS Independent",
    ],
    python_requires=">=3.6",
)
