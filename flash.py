#!/usr/bin/env python3
import os
import pprint
from dataclasses import dataclass
from pathlib import Path
from shutil import which
from typing import List, Optional, Union

import click
import toml
from click import ClickException
from dacite import from_dict

config_dir = Path(os.environ.get("FLASH_CONFIG_DIR", "."))
LINK_CONFIG_FILE_NAME = ".flash.toml"


@dataclass
class EntryFile:
    name: str
    rename: Optional[str]


@dataclass
class ManagerConf:
    name: str
    package: Optional[str]


# dacite doesn't support the `T1 | T2` syntax of Python 3.10
ManagerConfs = list[Union[str, ManagerConf]]


@dataclass
class Entry:
    cmd: str
    install_cmds: Union[str, list[str]]
    location: str
    files: Union[list[str], list[EntryFile]]
    managers: Optional[list[ManagerConf]]


@dataclass
class Dependency:
    cmd: str
    install_cmds: Optional[list[str]]
    uninstall_cmds: Optional[list[str]]
    managers: Optional[ManagerConfs]


@dataclass
class Config:
    Entry: Entry
    Deps: Optional[list[Dependency]]
    OptionalDeps: Optional[list[Dependency]]


def unify_manager_confs(cmd: str, confs: ManagerConfs):
    return [
        ManagerConf(name=v, package=cmd) if isinstance(v, str) else v for v in confs
    ]


def read_config(entry_name) -> dict:
    entry_dir = config_dir / entry_name
    if not entry_dir.exists():
        raise ClickException("Entry not exists")

    config_file = entry_dir / LINK_CONFIG_FILE_NAME
    if not config_file.exists():
        raise ClickException("Config file not exists")

    with open(config_file) as f:
        return toml.loads(f.read())


def warn(message):
    click.secho("WARN", fg="yellow", nl=False)
    click.echo(f": {message}")


def error(message):
    click.secho("ERROR", fg="red", nl=False, err=True)
    click.echo(f": {message}", err=True)
    # TODO: More error code
    exit(1)


def error_msg(message):
    """Just print message."""
    click.secho("ERROR", fg="red", nl=False, err=True)
    click.echo(f": {message}", err=True)


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
    config = read_config(name)
    handler = LinkHandler(interactive, config)
    entry = config.get("Entry")
    if entry == None:
        raise click.ClickException("Entry section not found in config")

    cmd = entry.get("cmd", "")
    install_cmds = entry.get("install_cmds", [])
    cmd_install_command(interactive, cmd, install_cmds)
    handler.handle_deps()
    handler.handle_optional_deps()

    entry_dir = config_dir / name
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
                error(f"Directory `{parent}` not found")

            if not click.confirm(f"Create `{parent}`?"):
                continue

            link.parent.mkdir(parents=True)
            link.symlink_to(entry_item.resolve())
        except NotADirectoryError:
            error(f"Not a directory: {link}")

        print(f"Restore {entry_item} -> {link}")
        links.append(link)

    do_after_action(config.get("After"))


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


def exec_command(cmd: str) -> int:
    click.secho(f"RUN", fg="green", nl=False)
    click.echo(f": {cmd}")
    return os.system(cmd)


def handle_package(package: str, manager: str, link: bool = True) -> str:
    if manager in ["pacman", "yay"]:
        op = "-S" if link else "-Rs"
        cmd = f"{manager} {op} {package}"
        if manager == "pacman":
            cmd = f"sudo {cmd}"
    elif manager == "brew":
        cmd = f"{manager} {'install' if link else 'uninstall'} {package}"
    else:
        return f"unknown package manager: {manager}"

    if exec_command(cmd) != 0:
        return f"failed to install {package} with {manager}"
    return ""


def handle_package_managers(
    cmd: str, managers: list[ManagerConf] = [], link: bool = True
):
    """If MANAGERS is empty, use supported installed managers and CMD as package name."""
    supported_managers = {"pacman", "yay", "brew"}
    if not managers:
        installed = [
            ManagerConf(m, cmd) for m in supported_managers if command_exits(m)
        ]
    else:
        supported = [m for m in managers if m.name in supported_managers]
        if not supported:
            return "no supported package manager found"
        else:
            installed = [m for m in supported if command_exits(m.name)]

    if not installed:
        return "no installed package manager found"
    for m in installed:
        p = m.package if m.package else cmd
        if err := handle_package(p, m.name, link):
            warn(err)
        else:
            return ""
    return "failed"


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


class LinkHandler:
    def __init__(self, interactive: bool, config: dict, link: bool = True):
        self.interactive = interactive
        self.config = config
        self.step_num = 0
        self.link = link

    def _handle_dep(self, d: str | dict):
        if isinstance(d, str):
            dep = Dependency(d, None, None, None)
        else:
            dep = from_dict(Dependency, d)
        if dep.install_cmds:
            cmds = dep.install_cmds if self.link else dep.uninstall_cmds
            if cmds:
                cmd_install_command(self.interactive, dep.cmd, cmds)
            elif not self.interactive:
                raise ClickException(f"cant handle dependency: {dep}")
            elif not click.confirm(f"cant handle dependency: {dep}, continue?"):
                raise click.Abort
        else:
            managers = dep.managers if dep.managers else []
            managers = unify_manager_confs(dep.cmd, managers)
            try:
                handle_package_managers(dep.cmd, managers, self.link)
            except Exception as e:
                # We can try next manager
                warn(e)
                if self.interactive and click.confirm("Abort?"):
                    raise click.Abort
        if not self.link:
            return
        if not command_exits(dep.cmd):
            if not self.interactive:
                raise ClickException(f"{dep.cmd} not found")
            if not click.confirm(f"{dep.cmd} not found, continue?"):
                raise click.Abort

    def step(self, title):
        self.step_num += 1
        click.secho(f"STEP {self.step_num}", fg="green", nl=False)
        click.echo(f": {title}")

    def handle_deps(self):
        deps = self.config.get("Deps", [])
        if len(deps) == 0:
            return

        self.step("Dependencies")
        for dep in deps:
            self._handle_dep(dep)

    def handle_optional_deps(self):
        deps = self.config.get("OptionalDeps", [])
        if len(deps) == 0:
            return

        self.step("Optional dependencies")
        for dep in deps:
            try:
                self._handle_dep(dep)
            except click.Abort as e:
                raise e
            except Exception as e:
                warn(e)


def do_after_action(action):
    if action == None:
        return

    if not click.confirm("Do after action?"):
        return

    last_waitstatus = 0
    for idx, cmd in enumerate(action.get("cmds", [])):
        click.echo(f"\nCmd {idx+1}: {cmd}")
        if not click.confirm("Run?"):
            continue

        last_waitstatus = os.system(cmd)
        if last_waitstatus != 0:
            error_msg(f"Failed")

    exit(os.waitstatus_to_exitcode(last_waitstatus))


@cli.command()
@click.argument("name")
def show(name):
    """Show entry config."""
    # pprint() is more compact than json.dumps()
    pprint.pp(read_config(name))


if __name__ == "__main__":
    cli()
