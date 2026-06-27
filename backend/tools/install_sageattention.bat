@echo off
REM Install SageAttention 2.2 for Windows + PyTorch 2.8 + CUDA 12.8 (RTX 50xx / Blackwell).
REM Requires triton-windows (already bundled via torchruntime in DreamForge).
echo Installing SageAttention 2.2.0 (woct0rdho wheel, torch 2.8 cu128)...
python_embeded\python.exe -m pip install --no-deps --force-reinstall "https://github.com/woct0rdho/SageAttention/releases/download/v2.2.0-windows.post3/sageattention-2.2.0%%2Bcu128torch2.8.0.post3-cp39-abi3-win_amd64.whl"
echo.
echo Verifying import...
python_embeded\python.exe -c "from sageattention import sageattn; print('SageAttention OK:', sageattn)"
echo.
echo DreamForge will auto-enable --use-sage-attention on next GPU engine restart.
echo FlashAttention: no reliable torch 2.8+cu128+cp310 wheel on Windows; Sage is preferred anyway.
pause
