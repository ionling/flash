#!/usr/bin/env python3
from pathlib import Path
from typing import List, Union

import click
import toml

_root_dir = Path.cwd()


def error(message):
    click.secho("ERROR", fg="red", nl=False, err=True)
    click.echo(f": {message}", err=True)
    # TODO: More error code
    exit(1)


@click.group()
def cli():
    pass


@cli.command()
@click.option(
    "-i", "--interactive", is_flag=True, help="Prompt whether to remove destinations."
)
@click.argument("name")
def link(name, interactive):
    """Link a entry to system."""
    entry_dir = _root_dir / name
    if not entry_dir.exists():
        error("Entry not exists")
    with open(entry_dir / ".flash") as f:
        config = toml.loads(f.read())

    location = Path(config["Entry"]["location"]).expanduser()
    filenames: List[Union(str, dict)] = config["Entry"]["files"]

    if not filenames:
        dir_items = [path for path in entry_dir.iterdir() if path.name != ".flash"]
        if len(dir_items) > 0:
            error(
                "Multiple files found except the `.flash`. "
                "You must specify the `files` configuration item."
            )
        filenames = [dir_items[0].name]

    links = []
    for f in filenames:
        if isinstance(f, str):
            name, rename = f, f
        elif "rename" in f:
            name, rename = f["name"], f["rename"]
        else:
            name, rename = f["name"], f["name"]

        link = location / rename
        entry_item = entry_dir / name

        try:
            link.symlink_to(entry_item.resolve())
        except FileExistsError:
            if not interactive:
                error(f"File `{link}` exists")
                # Fallback
                [link.unlink() for link in links]
                return

            if click.confirm(f"Replace `{link}`?"):
                link.unlink()
                link.symlink_to(entry_item.resolve())
        else:
            print(f"link {entry_item} -> {link}")

        links.append(link)


@cli.command()
@click.argument("name")
def unlink(name):
    """Unlink a entry."""


@cli.command()
def ls():
    """List all entries."""
    names = [
        path.name
        for path in _root_dir.iterdir()
        if path.is_dir() and (path / ".flash").exists()
    ]
    print("\t".join(names))


if __name__ == "__main__":
    cli()
