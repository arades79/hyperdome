# Load onionshare module and resources from the source code tree
import os
import sys
import threading
import time
#TODO there must be a cleaner way to do this
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.onionshare_dev_mode = True

import hyperdome_server
import hyperdome_client

def main():
    server_thread = threading.Thread(target=hyperdome_server.main)
    server_thread.start()
    time.sleep(5)
    hyperdome_client.main()

if __name__ == "__main__":
    main()
