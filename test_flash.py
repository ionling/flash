import click
import pytest
from dacite import from_dict

import flash


def test_cmd_install_command():
    with pytest.raises(click.ClickException):
        flash.cmd_install_command(False, "xx", [])


def test_command_exits():
    assert flash.command_exits("ls") == True
    assert flash.command_exits("ls3") == False
    assert flash.command_exits("bash") == True


def test_install_command():
    with pytest.raises(Exception):
        flash.install_command(["", " ", "    "])

    with pytest.raises(Exception):
        flash.install_command(["xxx"])

    flash.install_command(["brew install fd"])
    flash.install_command(["brew uninstall fd"])


def test_unify_manager_confs():
    d = {"cmd": "bat", "managers": ["brew", {"name": "pacman", "package": "bat"}]}
    dep = from_dict(flash.Dependency, d)
    ms = dep.managers
    assert len(ms) == 2
    assert ms[0] == "brew"
    assert ms[1].name == "pacman"
    assert ms[1].package == "bat"

    flash.unify_manager_confs(dep.managers, dep.cmd)
    assert ms[0].name == "brew"
    assert ms[0].package == "bat"
    assert ms[1].name == "pacman"
    assert ms[1].package == "bat"
