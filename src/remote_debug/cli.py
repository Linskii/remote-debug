import click
import socket
import os
import sys
import runpy
import debugpy


@click.group()
def cli():
    """A helper tool for remote debugging on HPC clusters."""
    pass


@cli.command(
    context_settings=dict(
        ignore_unknown_options=True,
    )
)
@click.argument("script_path", type=click.Path(exists=True))
@click.argument("script_args", nargs=-1, type=click.UNPROCESSED)
def debug(script_path, script_args):
    """Wraps a python script to start a debugpy listener."""
    # 1. Find an open port.
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("", 0))
        port = s.getsockname()[1]

    # 2. Get the current hostname.
    hostname = socket.gethostname()

    # Print connection info for the user
    click.echo("--- Python Debugger Info ---")
    click.echo(f"Node: {hostname}")
    click.echo(f"Port: {port}")
    click.echo(f"Remote Path: {os.getcwd()}")
    click.echo("--------------------------")

    # Start listening for a connection.
    debugpy.listen(("0.0.0.0", port))

    click.echo("Script is paused, waiting for debugger to attach...")
    # This line blocks execution until you attach from VS Code.
    debugpy.wait_for_client()
    click.echo("Debugger attached! Resuming script.")

    # Execute the target script
    # Set sys.argv to what the script would expect
    sys.argv = [script_path] + list(script_args)
    # Add the script's directory to the path to allow for relative imports
    sys.path.insert(0, os.path.dirname(script_path))

    runpy.run_path(script_path, run_name="__main__")


@cli.command()
def init():
    """Initializes the project with a VS Code launch configuration."""
    click.echo("Initializing debug configuration...")
    # TODO: Implement logic to create/update .vscode/launch.json


@cli.command()
def tunnel():
    """Creates an SSH tunnel for a remote debugging session."""
    click.echo("Setting up SSH tunnel...")
    # TODO: Implement logic to create the SSH tunnel.


if __name__ == "__main__":
    cli()
