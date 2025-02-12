# import server
import socketio
from ultraleap import UltraLeap, UltraLeapListener

############################################# 
# UltraLeap Socket listener 
############################################# 
class UltraLeapSocketListener(UltraLeapListener):
    def __init__(self, url):
        super().__init__()
        self.connect_socket(url)

    def connect_socket(self,url):
        self.sio = socketio.Client()
        try:
            self.sio.connect(url)
            print(f"[SocketIO] Connected to {url}")
        except Exception as e:
            print(f"[SocketIO] Connection failed: {e}")
    
    def dispatch(self,data):
        if self.sio.connected:
            try:
                self.sio.emit("tracking_data", data)  # send to server
            except Exception as e:
                print(f"[SocketIO] Emit failed: {e}")

    def dispose(self):
        self.sio.disconnect()

if __name__ == "__main__":
    # Process(target=UltraLeap,args={UltraLeapSocketListener(url="http://localhost:5000"),},daemon=True).start()
    # while True:
    #     __name__
    UltraLeap(UltraLeapSocketListener(url="http://localhost:5000"))
    
    