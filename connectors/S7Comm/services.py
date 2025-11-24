import snap7
from snap7.util import get_int

client = snap7.client.Client()
client.connect("127.0.0.1", 0, 1, tcp_port=2000)  # ✅ правильно: tcp_port

data = client.db_read(1, 2, 2)
value = get_int(data, 0)
print(f"📥 Read DB1.DBW2 = {value}")

client.disconnect()
