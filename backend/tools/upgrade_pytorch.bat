@echo off
echo Installing PyTorch 2.8.0 with CUDA 12.8 (unlocks ComfyUI Dynamic VRAM on Blackwell/Ada)...
python_embeded\python.exe -m pip install --upgrade torch==2.8.0+cu128 torchvision==0.23.0+cu128 torchaudio==2.8.0+cu128 --index-url https://download.pytorch.org/whl/cu128
echo Done.
pause
