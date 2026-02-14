import os
import serialRcv
import dashboard
import multiprocessing

if __name__ == '__main__':
    os.system("dir")
    os.system("streamlit run application/dashboard.py")
    multiprocessing.set_start_method("spawn", force=True) #
    p = multiprocessing.Process(target=serialRcv.serialRcv())
    p.start()
    #os.system("streamlit run application/dashboard.py")
    p.join()
    #if (pid > 0):
    #    os.system("streamlit run application/dashboard.py")
    #else:
    #    serialRcv.serialRcv()