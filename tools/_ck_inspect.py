"""Inspeksi mentah blob cookie: prefix, panjang, dan apakah ada kunci di disk."""
import glob
import os
import shutil
import sqlite3
import subprocess

prof = "/tmp/x11fresh_profile"
tmp = "/tmp/_ck_inspect.db"
shutil.copy2(f"{prof}/Default/Cookies", tmp)
con = sqlite3.connect(tmp)
rows = con.execute("select name, host_key, encrypted_value, value, "
                   "length(encrypted_value) from cookies").fetchall()
print("baris:", len(rows))
for name, host, enc, plain, ln in rows:
    print(f"  {name:10} host={host:18} len={ln:5} prefix={enc[:4]!r} plain={plain!r}")

print("\n=== file kunci di sekitar profil / config ===")
for pat in (f"{prof}/Local State", "/root/.config/chromium/Local State",
            "/root/.config/chromium/Default/Local State"):
    print(f"{pat}: {'ADA' if os.path.exists(pat) else 'tidak ada'}")

print("\n=== cari 'os_crypt' / kunci di Local State ===")
for p in glob.glob(f"{prof}/**/Local State", recursive=True) + \
        glob.glob("/root/.config/chromium/**/Local State", recursive=True):
    try:
        s = open(p, "r", errors="ignore").read()
        for k in ("os_crypt", "encrypted_key", "password", "keyring"):
            i = s.find(k)
            if i >= 0:
                print(f"  {p}: '{k}' @ {i}")
    except Exception as e:
        print(f"  {p}: err {e}")

print("\n=== secret-service / keyring berjalan? ===")
print(subprocess.run(["pgrep", "-a", "gnome-keyring|kwallet|secret"],
                     capture_output=True, text=True).stdout or "  tidak ada")
