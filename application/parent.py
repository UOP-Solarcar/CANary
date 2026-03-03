import os
import serialRcv
import dashboard
import subprocess
from multiprocessing import Process

if __name__ == "__main__":
    '''q = Queue()

    p1 = Process(target=serialRcv.serialRcv(), args=(q,))
    p2 = Process(target=dashboard.dashboardStart(), args=(q,))

    p1.start()
    p2.start()

    p1.join()
    p2.terminate()'''

if __name__ == "__main__":
    p = Process(target=serialRcv.serialRcv())
    p.start()
    #result = subprocess.run(["streamlit", "run", "dashboard.py"])
    #print(f"Command finished with return code: {result.returncode}")
    p.join()
    
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