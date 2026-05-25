import os
import sys

from _paths import BACKEND_ROOT, COMFY_ROOT, PROJECT_ROOT, REPOS_ROOT, extend_sys_path

extend_sys_path()
os.chdir(BACKEND_ROOT)

import shared
class MockGradio:
    def __init__(self):
        self.local_url = "headless"
        self.server_name = "localhost"
        self.server_port = "0"
        self.share = False
shared.gradio_root = MockGradio()

try:
    print("Importing async_worker...")
    import modules.async_worker as worker
    print("Import successful!")
except Exception as e:
    import traceback
    traceback.print_exc()
