#!/usr/bin/env python3
"""Isolasi penyebab 'CDP target never appeared' di seed_visitor."""
import os
import sys
import time

sys.path.insert(0, "/root/captcha-solver")
os.environ["DISPLAY"] = ":99"

from perimeterx.seed import seed_visitor     # noqa: E402

PROXY = open("/tmp/_pxproxy.env").read().strip().split("'")[1]
APP = "PXzC5j78di"
VID = "33787df6-c977-11f1-b097-31232c7aa85c"

for label, proxy in (("TANPA proxy", None), ("DENGAN proxy", PROXY)):
    prof = f"/tmp/_iso_{int(time.time())}"
    print(f"\n=== {label} ===")
    t0 = time.time()
    rep = seed_visitor(prof, APP, VID, proxy)
    print(f"  waktu : {time.time()-t0:.0f}s")
    for k in ("seeded", "cookie", "localstorage", "in_memory_pxvid",
              "cookie_visible_to_js", "persisted", "error"):
        print(f"  {k:22}: {rep.get(k)}")
    import subprocess
    subprocess.run(["rm", "-rf", prof], check=False)
