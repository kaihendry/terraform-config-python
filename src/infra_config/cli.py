"""CLI entry point for infra-config."""

import json
import sys
from pathlib import Path
from typing import Annotated

import typer
import yaml
from pydantic import ValidationError
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from .models.config import InfraConfig
from .transformers.base import TransformContext, UserRole
from .transformers.database import DatabaseTransformer
from .transformers.storage import StorageTransformer

app = typer.Typer(
    name="infra-config",
    help="Config-to-Terraform Infrastructure Platform",
    no_args_is_help=True,
)
console = Console()
error_console = Console(stderr=True)


def load_config(config_path: Path) -> InfraConfig:
    """Load and parse configuration file."""
    if not config_path.exists():
        raise typer.BadParameter(f"Config file not found: {config_path}")

    with open(config_path) as f:
        raw_config = yaml.safe_load(f)

    return InfraConfig.model_validate(raw_config)


@app.command()
def validate(
    config_path: Annotated[Path, typer.Argument(help="Path to config.yaml file")],
    role: Annotated[
        UserRole, typer.Option("--role", "-r", help="User role for policy validation")
    ] = UserRole.DEVELOPER,
) -> None:
    """Validate configuration file without generating output."""
    try:
        config = load_config(config_path)
    except ValidationError as e:
        error_console.print("[bold red]Validation errors:[/bold red]")
        for error in e.errors():
            loc = " -> ".join(str(x) for x in error["loc"])
            error_console.print(f"  [red]•[/red] {loc}: {error['msg']}")
        raise typer.Exit(1)
    except yaml.YAMLError as e:
        error_console.print(f"[bold red]YAML parse error:[/bold red] {e}")
        raise typer.Exit(1)

    # Create context and validate policies
    ctx = TransformContext(config=config, role=role)

    transformers = [DatabaseTransformer(), StorageTransformer()]
    all_errors: list[str] = []

    for transformer in transformers:
        errors = transformer.validate_policies(ctx)
        all_errors.extend(errors)

    if all_errors:
        error_console.print("[bold yellow]Policy violations:[/bold yellow]")
        for error in all_errors:
            error_console.print(f"  [yellow]•[/yellow] {error}")
        raise typer.Exit(1)

    console.print(Panel.fit("[bold green]✓ Configuration is valid[/bold green]"))

    # Show summary
    table = Table(title="Configuration Summary")
    table.add_column("Setting", style="cyan")
    table.add_column("Value", style="green")

    table.add_row("Project", config.project)
    table.add_row("Environment", config.environment.value)
    table.add_row("Region", config.region)
    table.add_row("Database", "Configured" if config.database else "Not configured")
    table.add_row("Storage", "Configured" if config.storage else "Not configured")

    console.print(table)


@app.command()
def transform(
    config_path: Annotated[Path, typer.Argument(help="Path to config.yaml file")],
    output_dir: Annotated[
        Path, typer.Option("--output", "-o", help="Output directory for tfvars files")
    ] = Path("./output"),
    role: Annotated[
        UserRole, typer.Option("--role", "-r", help="User role for policy validation")
    ] = UserRole.DEVELOPER,
) -> None:
    """Transform configuration to Terraform variables."""
    # Load and validate config
    try:
        config = load_config(config_path)
    except ValidationError as e:
        error_console.print("[bold red]Validation errors:[/bold red]")
        for error in e.errors():
            loc = " -> ".join(str(x) for x in error["loc"])
            error_console.print(f"  [red]•[/red] {loc}: {error['msg']}")
        raise typer.Exit(1)
    except yaml.YAMLError as e:
        error_console.print(f"[bold red]YAML parse error:[/bold red] {e}")
        raise typer.Exit(1)

    # Create context
    ctx = TransformContext(config=config, role=role)

    # Validate policies
    transformers = {
        "postgresql": DatabaseTransformer(),
        "storage": StorageTransformer(),
    }
    all_errors: list[str] = []

    for transformer in transformers.values():
        errors = transformer.validate_policies(ctx)
        all_errors.extend(errors)

    if all_errors:
        error_console.print("[bold yellow]Policy violations:[/bold yellow]")
        for error in all_errors:
            error_console.print(f"  [yellow]•[/yellow] {error}")
        raise typer.Exit(1)

    # Ensure output directory exists
    output_dir.mkdir(parents=True, exist_ok=True)

    # Transform and write outputs
    generated_files: list[str] = []

    for name, transformer in transformers.items():
        result = transformer.transform(ctx)
        if result is not None:
            output_file = output_dir / f"{name}.tfvars.json"
            with open(output_file, "w") as f:
                json.dump(result, f, indent=2)
            generated_files.append(str(output_file))

    if not generated_files:
        console.print("[yellow]No resources configured to transform[/yellow]")
        raise typer.Exit(0)

    console.print(Panel.fit("[bold green]✓ Transformation complete[/bold green]"))

    table = Table(title="Generated Files")
    table.add_column("File", style="cyan")
    table.add_column("Status", style="green")

    for file_path in generated_files:
        table.add_row(file_path, "✓ Created")

    console.print(table)


if __name__ == "__main__":
    app()
