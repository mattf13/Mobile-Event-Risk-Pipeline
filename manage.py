import subprocess
import sys
from pathlib import Path
from typing import Callable, Dict


class PipelineManager:
    """
    Manages the lifecycle of the Mobile Event Risk Pipeline using Docker Compose.
    """

    def __init__(self):
        self.env_path = Path(".env")
        # Map commands to their respective methods
        self.commands: Dict[str, Callable] = {
            "up": self.up,
            "down": self.down,
            "build": self.build,
            "logs": self.logs,
            "restart": self.restart,
            "clean": self.clean,
        }

    def _execute(self, cmd: str) -> None:
        """Helper to run shell commands safely."""
        try:
            subprocess.run(cmd, shell=True, check=True)
        except subprocess.CalledProcessError as e:
            print(f"\n[ERROR] Command failed with exit code {e.returncode}: {cmd}")
            sys.exit(e.returncode)

    def _ensure_env(self) -> None:
        """Validate that the environment configuration exists."""
        if not self.env_path.exists():
            print(f"\n[ERROR] Configuration file '{self.env_path}' not found.")
            print("Please create it before starting the services.")
            sys.exit(1)

    def up(self) -> None:
        """Start services in detached mode."""
        self._ensure_env()
        print("--- Starting Pipeline Services ---")
        self._execute("docker-compose up -d")

    def down(self) -> None:
        """Stop and remove containers."""
        print("--- Stopping Services ---")
        self._execute("docker-compose down")

    def build(self) -> None:
        """Rebuild service images without using cache."""
        self._ensure_env()
        print("--- Rebuilding Images (No-Cache) ---")
        self._execute("docker-compose build --no-cache")

    def logs(self) -> None:
        """Stream logs from all containers."""
        self._execute("docker-compose logs -f")

    def restart(self) -> None:
        """Restart all services."""
        print("--- Restarting Services ---")
        self._execute("docker-compose restart")

    def clean(self) -> None:
        """Full cleanup: remove containers, volumes, and orphans."""
        print("--- Performing Deep System Clean ---")
        self._execute("docker-compose down --volumes --remove-orphans")

    def run(self, action: str) -> None:
        """Dispatches the action to the corresponding method."""
        handler = self.commands.get(action)
        if handler:
            handler()
        else:
            print(f"Unknown command: {action}")
            self.print_help()
            sys.exit(1)

    def print_help(self) -> None:
        print("\nMobile Event Risk Pipeline Manager")
        print("Usage: python manage.py [command]")
        print("\nAvailable Commands:")
        for cmd in self.commands:
            # Uses docstrings of methods as command descriptions
            doc = self.commands[cmd].__doc__
            print(f"  {cmd:<10} {doc}")


if __name__ == "__main__":
    manager = PipelineManager()

    if len(sys.argv) < 2:
        manager.print_help()
    else:
        manager.run(sys.argv[1].lower())
