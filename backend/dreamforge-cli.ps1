$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
& "$ScriptDir\..\python_embeded\python.exe" -s "$ScriptDir\dreamforge_cli_direct.py" @args
