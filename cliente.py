import SocketTCP

address = ("localhost", 8000)

# client
client_socketTCP = SocketTCP.SocketTCP()
client_socketTCP.connect(address)
print("Handshake completado. Destino:", client_socketTCP.dest_address)

# test 1
message = "Mensje de len=16".encode()
client_socketTCP.send(message)
# test 2
message = "Mensaje de largo 19".encode()
client_socketTCP.send(message)
# test 3
message = "Mensaje de largo 19".encode()
client_socketTCP.send(message)