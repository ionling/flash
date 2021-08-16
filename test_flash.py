import pytest
import click

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
