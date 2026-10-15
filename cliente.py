import sys
import SocketTCP

host = sys.argv[1]
port = int(sys.argv[2])

data = sys.stdin.buffer.read()

client_socketTCP = SocketTCP.SocketTCP()
client_socketTCP.connect((host, port))
client_socketTCP.send(data)
client_socketTCP.close()