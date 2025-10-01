import sys
from click.testing import CliRunner
from unittest.mock import patch, ANY
import os
from remote_debug.cli import cli
import json


@patch("remote_debug.cli.runpy.run_path")
@patch("remote_debug.cli.debugpy.wait_for_client")
@patch("remote_debug.cli.debugpy.listen")
def test_debug_command(mock_listen, mock_wait_for_client, mock_run_path, tmp_path):
    """
    Tests the debug command.
    - Creates a temporary script file.
    - Mocks debugpy and runpy to avoid actual debugging and execution.
    - Verifies that the command prints the correct info.
    - Verifies that debugpy and runpy are called with the correct arguments.
    """
    # Create a dummy script file to be "debugged"
    script_dir = tmp_path / "project"
    script_dir.mkdir()
    script_path = script_dir / "myscript.py"
    script_path.write_text("print('hello from script')")

    runner = CliRunner()
    script_args = ["--foo", "bar", "baz"]

    # Keep track of the original sys.argv and sys.path
    original_argv = sys.argv
    original_path = sys.path[:]

    try:
        result = runner.invoke(
            cli, ["debug", str(script_path)] + script_args, catch_exceptions=False
        )

        assert result.exit_code == 0

        # Check that the connection info was printed
        assert "--- Python Debugger Info ---" in result.output
        assert "Node:" in result.output
        assert "Port:" in result.output
        assert f"Remote Path: {os.getcwd()}" in result.output
        assert "Script is paused, waiting for debugger to attach..." in result.output
        assert "Debugger attached! Resuming script." in result.output

        # Check that debugpy was set up correctly
        mock_listen.assert_called_once_with(("0.0.0.0", ANY))
        mock_wait_for_client.assert_called_once()

        # Check that the script was called correctly via runpy
        mock_run_path.assert_called_once_with(str(script_path), run_name="__main__")

        # Check that sys.argv and sys.path were correctly modified before runpy
        # The call to run_path happens inside the invoke, so we check the state of sys
        # after it has been modified by our command.
        # The first argument to run_path is a tuple of args.
        call_args, _ = mock_run_path.call_args

        # The test needs to check the state of sys.argv and sys.path *within* the invoked command's context.
        # Since runpy doesn't expose what sys.argv was, we can patch sys and check it.
        # For this example, we'll rely on the fact that runpy uses the global sys.
        # A more complex test could involve another mock.
        assert sys.argv == [str(script_path)] + script_args
        assert sys.path[0] == str(script_dir)

    finally:
        # Restore sys.argv and sys.path to avoid side effects
        sys.argv = original_argv
        sys.path = original_path


def test_init_new_config():
    """
    Tests that the init command creates a new .vscode/launch.json file correctly.
    """
    runner = CliRunner()
    with runner.isolated_filesystem() as td:
        result = runner.invoke(cli, ["init"], catch_exceptions=False)

        assert result.exit_code == 0
        assert "Initializing debug configuration..." in result.output
        assert (
            "Added 'Python Debugger: Remote Attach (via SSH Tunnel)' configuration."
            in result.output
        )
        assert (
            "Added 'Python Debugger: Attach to Compute Node' configuration."
            in result.output
        )
        assert f"Successfully updated '.vscode/launch.json'." in result.output

        launch_path = os.path.join(td, ".vscode", "launch.json")
        assert os.path.exists(launch_path)

        with open(launch_path, "r") as f:
            data = json.load(f)

        assert data["version"] == "0.2.0"
        assert len(data["configurations"]) == 2
        assert len(data["inputs"]) == 4
        assert (
            data["configurations"][0]["name"]
            == "Python Debugger: Remote Attach (via SSH Tunnel)"
        )
        assert data["inputs"][0]["id"] == "localTunnelPort"


def test_init_update_existing_config():
    """
    Tests that the init command correctly updates an existing launch.json
    without removing existing configurations.
    """
    runner = CliRunner()
    with runner.isolated_filesystem() as td:
        vscode_dir = os.path.join(td, ".vscode")
        os.makedirs(vscode_dir)
        launch_path = os.path.join(vscode_dir, "launch.json")

        # Create a pre-existing launch.json
        existing_config = {
            "version": "0.2.0",
            "configurations": [
                {"name": "Existing Config", "type": "python", "request": "launch"}
            ],
            "inputs": [],
        }
        with open(launch_path, "w") as f:
            json.dump(existing_config, f)

        result = runner.invoke(cli, ["init"], catch_exceptions=False)
        assert result.exit_code == 0

        with open(launch_path, "r") as f:
            data = json.load(f)

        # Should have the old config plus the two new ones
        assert len(data["configurations"]) == 3
        assert data["configurations"][0]["name"] == "Existing Config"
        assert (
            data["configurations"][1]["name"]
            == "Python Debugger: Remote Attach (via SSH Tunnel)"
        )

        # Should have the four new inputs
        assert len(data["inputs"]) == 4


def test_init_handles_malformed_config():
    """
    Tests that the init command handles a malformed launch.json by backing it up
    and creating a new one.
    """
    runner = CliRunner()
    with runner.isolated_filesystem() as td:
        vscode_dir = os.path.join(td, ".vscode")
        os.makedirs(vscode_dir)
        launch_path = os.path.join(vscode_dir, "launch.json")

        # Create a malformed launch.json
        with open(launch_path, "w") as f:
            f.write("{'invalid_json': True,}")

        result = runner.invoke(cli, ["init"], catch_exceptions=False)
        assert result.exit_code == 0

        # Check for the warning and backup file
        # The CLI prints a relative path, so we check for that specifically.
        relative_launch_path = os.path.join(".vscode", "launch.json")
        assert f"Warning: '{relative_launch_path}' is malformed." in result.output
        assert os.path.exists(launch_path + ".bak")

        # Check that a new, valid file was created
        with open(launch_path, "r") as f:
            data = json.load(f)
        assert len(data["configurations"]) == 2


def test_tunnel_command():
    """
    Tests that the tunnel command constructs the correct SSH command string.
    """
    runner = CliRunner()
    compute_node = "test-node-123"
    remote_port = 45678
    ssh_login = "user@login.cluster.edu"

    # Test with default local port
    result = runner.invoke(
        cli,
        ["tunnel", compute_node, str(remote_port), ssh_login],
        catch_exceptions=False,
    )

    assert result.exit_code == 0
    expected_command_default = (
        f"ssh -N -L 5678:{compute_node}:{remote_port} {ssh_login}"
    )
    assert expected_command_default in result.output
    assert "Run the following command in a new terminal" in result.output
    assert "attach your VS Code debugger to localhost:5678" in result.output

    # Test with a custom local port
    custom_local_port = 9999
    result_custom = runner.invoke(
        cli,
        [
            "tunnel",
            compute_node,
            str(remote_port),
            ssh_login,
            "--local-port",
            str(custom_local_port),
        ],
        catch_exceptions=False,
    )

    assert result_custom.exit_code == 0
    expected_command_custom = (
        f"ssh -N -L {custom_local_port}:{compute_node}:{remote_port} {ssh_login}"
    )
    assert expected_command_custom in result_custom.output
    assert (
        f"attach your VS Code debugger to localhost:{custom_local_port}"
        in result_custom.output
    )
