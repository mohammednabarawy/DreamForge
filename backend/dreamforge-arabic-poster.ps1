$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
& "$ScriptDir\..\python_embeded\python.exe" -s "$ScriptDir\arabic_poster_pipeline.py" @args
