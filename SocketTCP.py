import socket
import random

class SocketTCP:
    def __init__(self):
        self.udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.dest_address = None
        self.seq_num = 0
        self.expected_seq_num = 0
        self.timeout = 2.0
        self.recv_buffer = b""
        self.remaining_bytes = 0

    @staticmethod
    def create_segment(segment):
        flags = bytes([int(segment["ack"]), int(segment["syn"]), int(segment["fin"])])
        seq_bytes = segment["seq"].to_bytes(4, byteorder="big")
        data = segment["data"]

        if len(data) > 16:
            raise ValueError("Los datos no pueden superar los 16 bytes")

        return flags + seq_bytes + data

    @staticmethod
    def parse_segment(segment):
        if not 7 <= len(segment) <= 23:
            raise ValueError("Tamaño de segmento inválido")

        return {
            "ack": bool(segment[0]),
            "syn": bool(segment[1]),
            "fin": bool(segment[2]),
            "seq": int.from_bytes(segment[3:7], byteorder="big"),
            "data": segment[7:]
        }

    def bind(self, address):
        self.udp_socket.bind(address)

    def connect(self, address):
        #secuencia inicial aleatoria
        self.seq_num = random.randint(0, 100)

        #primer mensaje: SYN
        syn = {
            "ack": False,
            "syn": True,
            "fin": False,
            "seq": self.seq_num,
            "data": b""
        }
        self.udp_socket.sendto(self.create_segment(syn), address)

        #esperamos un SYN+ACK
        while True:
            response_bytes, server_address = self.udp_socket.recvfrom(23)
            response = self.parse_segment(response_bytes)

            if (response["syn"] and response["ack"] and not response["fin"] and 
                response["seq"] == self.seq_num + 1 and response["data"] == b""):
                break

        #la respuesta viene del nuevo socket del servidor, por lo que debemos actualizar 
        # la dirección de destino
        self.dest_address = server_address

        #tercer mensaje: ACK
        ack = {
            "ack": True,
            "syn": False,
            "fin": False,
            "seq": self.seq_num + 2,
            "data": b""
        }

        self.udp_socket.sendto(
            self.create_segment(ack),
            self.dest_address
        )

        #secuencia que se usara para enviar datos
        self.seq_num += 2

    def accept(self):
        #esperamos un SYN
        while True:
            syn_bytes, client_address = self.udp_socket.recvfrom(23)
            syn = self.parse_segment(syn_bytes)

            if (syn["syn"] and not syn["ack"] and not syn["fin"] and syn["data"] == b""):
                break

        #creamos un nuevo objeto para esta conexión
        connection_socketTCP = SocketTCP()

        #conservamos la IP local y pedimos otro puerto disponible
        local_ip = self.udp_socket.getsockname()[0]
        connection_socketTCP.bind((local_ip, 0))

        connection_socketTCP.dest_address = client_address
        new_address = connection_socketTCP.udp_socket.getsockname()

        #segundo mensaje: SYN+ACK desde el nuevo socket
        syn_ack = {
            "ack": True,
            "syn": True,
            "fin": False,
            "seq": syn["seq"] + 1,
            "data": b""
        }

        connection_socketTCP.udp_socket.sendto(self.create_segment(syn_ack), client_address)

        #esperamos el ACK final
        while True:
            ack_bytes, sender_address = (connection_socketTCP.udp_socket.recvfrom(23))
            ack = self.parse_segment(ack_bytes)

            if (sender_address == client_address and ack["ack"] and not ack["syn"] and 
                not ack["fin"] and ack["seq"] == syn["seq"] + 2 and ack["data"] == b""):
                break

        #secuencia esperada
        connection_socketTCP.expected_seq_num = syn["seq"] + 2

        return connection_socketTCP, new_address

    def send(self, message):
        message_len = len(message)

        #primero enviamos el largo del mensaje como un segmento de 4 bytes
        chunks = [message_len.to_bytes(4, byteorder="big")]

        # luego dividimos el mensaje en trozos de 16 bytes
        for i in range(0, message_len, 16):
            chunks.append(message[i:i + 16])

        # guardamos el timeout previo y establecemos el timeout para la espera de ACKs
        previous_timeout = self.udp_socket.gettimeout()
        self.udp_socket.settimeout(self.timeout)

        try:
            for chunk in chunks:
                #creamos el segmento con la secuencia actual
                segment = {
                    "ack": False,
                    "syn": False,
                    "fin": False,
                    "seq": self.seq_num,
                    "data": chunk
                }

                segment_bytes = self.create_segment(segment)
                confirmed = False

                while not confirmed:
                    #enviamos el segmento
                    self.udp_socket.sendto(segment_bytes, self.dest_address)

                    try:
                        while True:
                            #esperamos un ACK del mismo socket de destino
                            ack_bytes, sender_address = (self.udp_socket.recvfrom(23))

                            if sender_address != self.dest_address:
                                #si el ACK viene de otro socket, lo ignoramos
                                continue

                            #parseamos el ACK recibido
                            ack = self.parse_segment(ack_bytes)

                            if (ack["ack"] and not ack["syn"] and not ack["fin"] and 
                                ack["seq"] == self.seq_num + 1 and ack["data"] == b""):
                                #si el ACK es correcto, confirmamos y avanzamos la secuencia
                                confirmed = True
                                self.seq_num += 1
                                break

                    except socket.timeout:
                        #volvemos a enviar el mismo segmento
                        continue

        finally:
            self.udp_socket.settimeout(previous_timeout)

    def recv(self, buff_size):
        if buff_size < 0:
            raise ValueError("buff_size no puede ser negativo")

        if buff_size == 0:
            return b""

        waiting_length = self.remaining_bytes == 0

        if waiting_length:
            #si estamos esperando el tamaño del mensaje, no sabemos cuántos bytes recibir, 
            # así que no limitamos el tamaño
            tsize = None
        else:
            #el tamaño a recibir es el mínimo entre buff_size y los bytes restantes
            tsize = min(buff_size, self.remaining_bytes)

        message_received = b""

        while True:
            if not waiting_length:
                #si ya tenemos un tamaño definido, podemos recibir hasta tsize bytes
                chunk = self.recv_buffer[:tsize - len(message_received)]

                message_received += chunk
                self.recv_buffer = self.recv_buffer[len(chunk):]
                self.remaining_bytes -= len(chunk)

                if len(message_received) == tsize:
                    #si ya recibimos el tamaño esperado, retornamos el mensaje
                    return message_received

            segment_bytes, sender_address = self.udp_socket.recvfrom(23)

            if sender_address != self.dest_address:
                #si el segmento viene de otro socket, lo ignoramos
                continue

            segment = self.parse_segment(segment_bytes)

            if segment["ack"] or segment["syn"] or segment["fin"]:
                #si el segmento es un ACK, SYN o FIN, lo ignoramos
                continue

            if segment["seq"] == self.expected_seq_num:
                if waiting_length:
                    if len(segment["data"]) != 4:
                        #si el primer segmento no tiene 4 bytes, es un error
                        raise ValueError("Largo de mensaje inválido")

                    self.remaining_bytes = int.from_bytes(segment["data"], byteorder="big")
                    tsize = min(buff_size, self.remaining_bytes)
                    waiting_length = False

                else:
                    #si el segmento es el esperado, lo agregamos al buffer de recepción
                    self.recv_buffer += segment["data"]

                self.expected_seq_num += 1

            ack = {
                "ack": True,
                "syn": False,
                "fin": False,
                "seq": self.expected_seq_num,
                "data": b""
            }

            #enviamos el ACK correspondiente al segmento recibido
            self.udp_socket.sendto(self.create_segment(ack), self.dest_address)
