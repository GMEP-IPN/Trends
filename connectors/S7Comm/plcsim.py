import ctypes
import time
from snap7.server import Server, SrvArea
from snap7 import util

def main():
    value = 0
    db_size = 16
    db_data = (ctypes.c_ubyte * db_size)()

    srv = Server()
    srv.register_area(SrvArea.DB, 1, db_data)

    # Старт сервера на нестандартном порту (например 2000)
    srv.start(2000)  # 👈 здесь указываем порт

    print("✅ Snap7 Server started on localhost (port 2000). Waiting for clients...")

    try:
        while True:
            value += 1
            print(value)
            util.set_int(db_data, 2, value)
            time.sleep(1)
    except KeyboardInterrupt:
        print("🛑 Server stopped by user.")
    finally:
        srv.destroy()

if __name__ == "__main__":
    main()
