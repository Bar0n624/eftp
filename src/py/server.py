import socket
import threading
import time
import os
import ip_util
from ip_util import data, control, greet, chunksize
from handshakes import (
    perform_handshake,
    receive_handshake,
    create_socket,
    send_pub_key,
    receive_session_key,
)
import select
import crypto_utils as cu


busy = 0


def handle_receive(conn, addr, handshake_mode, data_socket):
    global busy
    if busy:
        perform_handshake(conn, "reject")
        return
    print(f"Connection established with {addr} {handshake_mode.split(' ')[1]}")
    pub = conn.recv(1024)
    with open("../../keys/pubclient.pem", "wb") as f:
        f.write(pub)
    public_key = "../../keys/pubclient.pem"
    send_pub_key(conn)
    session_key = receive_session_key(conn, True)

    print(
        f"Incoming file {handshake_mode.split(' ')[2]} {handshake_mode.split(' ')[3]}MB transfer request. Do you want to accept? (yes/no): "
    )
    user_input = input().lower()

    if user_input == "yes":
        busy = 1
        perform_handshake(conn, "send", public_key)
        data_socket.setblocking(True)
        conn, addr = data_socket.accept()
        receive_file(
            conn,
            handshake_mode.split(" ")[2],
            handshake_mode.split(" ")[3],
            session_key,
        )
    else:
        perform_handshake(conn, "reject")


def handle_ping(conn):
    print("ping")
    if busy:
        perform_handshake(conn, "reject")
    else:
        perform_handshake(conn, hostname)


def handle_client(conn, addr, data_socket):
    handshake_mode = receive_handshake(conn)
    if handshake_mode.startswith("receive"):
        handle_receive(conn, addr, handshake_mode, data_socket)
    elif handshake_mode.startswith("ping"):
        handle_ping(conn)


def receive_file(sock, file_name, size, session_key):
    global busy
    with open(f"../../files/{file_name}.tmp", "wb") as file:
        received = 0
        data = sock.recv(chunksize)
        while data:
            file.write(data)
            data = sock.recv(chunksize)
            received = os.path.getsize(f"../../files/{file_name}.tmp")
            if received >= float(size) * 1024 * 1024:
                received = float(size) * 1024 * 1024
            print(f"Received {received/(1024*1024)}/{size} MB", end="\r")
    print(f"Received {received/(1024*1024)}/{size} MB")
    cu.decryptFile(
        session_key,
        f"../../files/{file_name}.tmp",
        f"../../files/{file_name}",
        chunksize,
    )
    os.remove(f"../../files/{file_name}.tmp")
    print("Decrypting file...")
    print(f"File '{file_name}' received successfully")
    os.remove(f"../../keys/pubclient.pem")
    busy = 0


def start_server(ip):
    threads = []
    data_socket = create_socket(ip, data)
    data_socket.listen()

    greet_socket = create_socket(ip, greet)
    greet_socket.listen()

    control_socket = create_socket(ip, control)
    control_socket.listen()

    socks = [greet_socket, control_socket]

    print(f"Server listening on socket {ip}")

    while True:
        readable, _, _ = select.select(socks, [], [])

        for i in readable:
            conn, addr = i.accept()
            threading.Thread(
                target=handle_client, args=(conn, addr, data_socket)
            ).start()


if __name__ == "__main__":
    ip_addr, hostname = ip_util.get_ip()
    ip = ip_util.choose_ip(ip_addr, hostname)
    start_server(ip)
