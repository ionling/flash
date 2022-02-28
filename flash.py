#!/usr/bin/env python3
import os
from pathlib import Path
from shutil import which
from typing import List, Union

import click
import toml

config_dir = Path(os.environ.get("FLASH_CONFIG_DIR", "."))
LINK_CONFIG_FILE_NAME = ".flash.toml"


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
    entry_dir = config_dir / name
    if not entry_dir.exists():
        error("Entry not exists")
    with open(entry_dir / LINK_CONFIG_FILE_NAME) as f:
        config = toml.loads(f.read())

    entry = config.get("Entry")
    if entry == None:
        raise click.ClickException("Entry section not found in config")

    cmd = entry.get("cmd", "")
    install_cmds = entry.get("install_cmds", [])
    cmd_install_command(interactive, cmd, install_cmds)

    location = Path(config["Entry"]["location"]).expanduser()
    filenames: List[Union[str, dict]] = config["Entry"]["files"]

    if not filenames:
        dir_items = [
            path for path in entry_dir.iterdir() if path.name != LINK_CONFIG_FILE_NAME
        ]
        if len(dir_items) > 0:
            error(
                f"Multiple files found except the `{LINK_CONFIG_FILE_NAME}`. "
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

            if not click.confirm(f"Replace `{link}`?"):
                continue

            link.unlink()
            link.symlink_to(entry_item.resolve())
        except FileNotFoundError:
            parent = link.parent
            if not interactive:
                error(f"Directory `{parent}` not fouond")

            if not click.confirm(f"Create `{parent}`?"):
                continue

            link.parent.mkdir(parents=True)
            link.symlink_to(entry_item.resolve())
        except NotADirectoryError:
            error(f"Not a directory: {link}")

        print(f"Restore {entry_item} -> {link}")
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
        if path.is_dir() and (path / LINK_CONFIG_FILE_NAME).exists()
    ]
    print("\t".join(names))


def cmd_install_command(interactive: bool, cmd: str, install_cmds: list[str]):
    if cmd != "" and not command_exits(cmd):
        if not interactive:
            raise click.ClickException(f"Command {cmd} not found")

        if not click.confirm(f"Install {cmd}?", abort=True):
            pass

        if len(install_cmds) == 0:
            raise click.ClickException("No install_cmds")

        try:
            install_command(install_cmds)
        except Exception as e:
            raise click.ClickException(str(e))


def command_exits(cmd: str) -> bool:
    return which(cmd) is not None


# TODO User personal error type
def install_command(commands: list[str]):
    valid_commands = [
        c
        for c in commands
        if (stripped := c.strip()) != "" and command_exits(stripped.split()[0])
    ]
    if len(valid_commands) == 0:
        raise Exception("no valid command")

    installed = False
    for command in commands:
        if os.system(command) != 0:
            continue

        installed = True

    if not installed:
        raise Exception("install failed")


if __name__ == "__main__":
    cli()
