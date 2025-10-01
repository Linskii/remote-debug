import sys
from click.testing import CliRunner
from unittest.mock import patch, ANY
import os
from remote_debug.cli import cli


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
