import os
import serialRcv
import dashboard

if __name__ == '__main__':
    pid = os.fork()
    if (pid > 0):
        os.system("streamlit run application/dashboard.py")
    else:
        serialRcv.serialRcv()