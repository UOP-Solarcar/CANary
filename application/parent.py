import os
import serialRcv
import dashboard
from multiprocessing import Process, Queue

if __name__ == "__main__":
    q = Queue()

    p1 = Process(target=serialRcv.serialRcv(), args=(q,))
    p2 = Process(target=dashboard.dashboardStart(), args=(q,))

    p1.start()
    p2.start()

    p1.join()
    p2.terminate()
    
    '''os.system("streamlit run application/dashboard.py")
    multiprocessing.set_start_method("spawn", force=True)
    p = multiprocessing.Process(target=serialRcv.serialRcv())
    p.start()
    #os.system("streamlit run application/dashboard.py")
    p.join()
    #if (pid > 0):
    #    os.system("streamlit run application/dashboard.py")
    #else:
    #    serialRcv.serialRcv()'''