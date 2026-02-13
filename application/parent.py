import os
import serialRcv
import dashboard

if __name__ == '__main__':
    pid = os.fork()
    if (pid > 0):
        serialRcv.serialRcv()
    else:
        os.system("streamlit run dashboard.py")