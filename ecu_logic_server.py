import socket

HOST = "127.0.0.1"
PORT = 25000

FIRMWARE_STATUS_FILE = "firmware_status.txt"


def read_firmware_version():
    try:
        with open(FIRMWARE_STATUS_FILE, "r") as f:
            return int(f.read().strip())
    except:
        return 1


server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
server.bind((HOST, PORT))
server.listen(1)

print("ECU Server Waiting...")

conn, addr = server.accept()
print("Connected:", addr)

while True:
    data = conn.recv(1024).decode()

    if not data:
        break

    data = data.strip()
    print("Received:", data)

    try:
        values = {}

        for item in data.split(";"):
            key, value = item.split("=")
            values[key] = int(value)

        ns = values.get("NS", 0)
        ew = values.get("EW", 0)
        ped = values.get("PED", 0)
        em = values.get("EM", 0)

        # Firmware version comes from FOTA status file
        fw = read_firmware_version()

        print("Firmware Version:", fw)

        if em == 1:
            if fw >= 2:
                decision = "EMERGENCY"
            else:
                print("Emergency blocked: FOTA V2 not installed")
                decision = "NS_GREEN" if ns > ew else "EW_GREEN"

        elif ped == 1:
            decision = "PEDESTRIAN"

        elif ns > ew:
            decision = "NS_GREEN"

        else:
            decision = "EW_GREEN"

        print("Decision:", decision)
        conn.sendall(decision.encode())

    except Exception as e:
        print("Error:", e)
        conn.sendall("SAFE_MODE".encode())

conn.close()
server.close()