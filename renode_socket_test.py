import socket
import time

HOST = "127.0.0.1"
PORT = 25000

print("Connecting to Renode...")

with socket.create_connection((HOST, PORT)) as s:

    print("Connected!")

    for i in range(10):

        msg = f"NS={i};EW={10-i}\n"

        print("Sending:", msg.strip())

        s.sendall(msg.encode())

        time.sleep(1)

print("Done")