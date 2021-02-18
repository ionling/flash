import setuptools


setuptools.setup(
    name="flash",
    version="0.1.0",
    packages=["."],
    install_requires=["click==7.1.2", "toml==0.10.2"],
    entry_points={"console_scripts": ["flash=flash:cli"]},
    classifiers=[
        "Programming Language :: Python :: 3",
        "Operating System :: OS Independent",
    ],
    python_requires=">=3.6",
)
