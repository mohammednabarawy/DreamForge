@echo off
echo Installing PyTorch 2.7.1 with CUDA 12.8 for RTX 5060 Ti Blackwell support...
python_embeded\python.exe -m pip install --upgrade torch==2.7.1+cu128 torchvision==0.22.1+cu128 torchaudio==2.7.1+cu128 --index-url https://download.pytorch.org/whl/cu128
echo Done.
pause
