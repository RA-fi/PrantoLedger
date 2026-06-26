@echo off
cd /d D:\prantoledger
python -u scripts\_prd_audit.py > scripts\_audit.out 2>&1
echo DONE >> scripts\_audit.out
