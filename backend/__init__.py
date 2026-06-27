import os
import sys
import asyncio

# Inject local packages path to bypass Windows path limit issues
packages_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "packages"))
if packages_path not in sys.path:
    sys.path.insert(0, packages_path)

if sys.platform == 'win32':
    # Ensure Windows uses ProactorEventLoop to support subprocesses (required by Playwright)
    try:
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    except Exception as e:
        print(f"Failed to set WindowsProactorEventLoopPolicy: {e}")


