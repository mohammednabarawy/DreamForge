import os
import sys
import subprocess
import time
from pathlib import Path

# Try to import rich for pretty UI, otherwise fallback to standard print
try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.prompt import Prompt
    from rich.text import Text
    import rich
    RICH_AVAILABLE = True
    console = Console()
except ImportError:
    RICH_AVAILABLE = False

DREAMFORGE_ROOT = Path(__file__).resolve().parent

def clear_screen():
    os.system('cls' if os.name == 'nt' else 'clear')

def print_header():
    clear_screen()
    if RICH_AVAILABLE:
        console.print(Panel(
            Text("DREAMFORGE LAUNCHER", justify="center", style="bold cyan"), 
            expand=False, 
            border_style="cyan"
        ))
    else:
        print("=" * 60)
        print("                DREAMFORGE LAUNCHER")
        print("=" * 60)
    print()

def get_input(prompt_text):
    if RICH_AVAILABLE:
        return Prompt.ask(prompt_text)
    else:
        return input(prompt_text + " ")

def start_dreamforge():
    print_header()
    if RICH_AVAILABLE:
        console.print("[green]Starting DreamForge Web/Desktop UI...[/green]\n")
    else:
        print("Starting DreamForge Web/Desktop UI...\n")
    
    bat_path = DREAMFORGE_ROOT / "dreamforge.bat"
    
    try:
        subprocess.run([str(bat_path)])
    except KeyboardInterrupt:
        pass
    print()
    input("Press Enter to continue...")

def model_manager():
    print_header()
    if RICH_AVAILABLE:
        console.print("[yellow]Starting DreamForge Model Manager...[/yellow]\n")
    else:
        print("Starting DreamForge Model Manager...\n")
        
    repair_script = DREAMFORGE_ROOT / "backend" / "dreamforge_repair.py"
    
    try:
        # Run repair script with model check argument if it exists, otherwise just run it
        subprocess.run([sys.executable, str(repair_script)])
    except KeyboardInterrupt:
        pass
    print()
    input("Press Enter to continue...")

def repair_dreamforge():
    print_header()
    if RICH_AVAILABLE:
        console.print("[red]Repairing DreamForge Environment...[/red]\n")
    else:
        print("Repairing DreamForge Environment...\n")
        
    repair_script = DREAMFORGE_ROOT / "backend" / "dreamforge_repair.py"
    
    try:
        subprocess.run([sys.executable, str(repair_script)])
    except KeyboardInterrupt:
        pass
    print()
    input("Press Enter to continue...")

def menu():
    while True:
        print_header()
        if RICH_AVAILABLE:
            console.print("1. [bold green]Start DreamForge[/bold green] (Web UI / Desktop)")
            console.print("2. [bold yellow]Model Manager[/bold yellow] (Download/Check Models)")
            console.print("3. [bold red]Update / Repair DreamForge[/bold red]")
            console.print("4. [bold]Exit[/bold]")
            console.print()
            choice = Prompt.ask("Select an option", choices=["1", "2", "3", "4"], default="1")
        else:
            print("1. Start DreamForge (Web UI / Desktop)")
            print("2. Model Manager (Download/Check Models)")
            print("3. Update / Repair DreamForge")
            print("4. Exit")
            print()
            choice = input("Select an option [1-4]: ").strip()
            
        if choice == '1':
            start_dreamforge()
        elif choice == '2':
            model_manager()
        elif choice == '3':
            repair_dreamforge()
        elif choice == '4':
            if RICH_AVAILABLE:
                console.print("\n[dim]Exiting...[/dim]")
            else:
                print("\nExiting...")
            sys.exit(0)

if __name__ == '__main__':
    try:
        menu()
    except KeyboardInterrupt:
        print("\nExiting...")
        sys.exit(0)
