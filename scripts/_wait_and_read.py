"""Block until audit completes and dump file."""
import time, os
path = r"D:\prantoledger\scripts\_audit.out"
for i in range(60):
    if os.path.exists(path):
        size = os.path.getsize(path)
        if size > 2000 and ("DONE" in open(path, encoding="cp1252").read()[-200:] or "SUMMARY" in open(path, encoding="cp1252").read()):
            break
    time.sleep(1)
print(open(path, encoding="cp1252").read())