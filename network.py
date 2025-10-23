import socket
import pickle

HEADER_LENGTH = 10  # Tamanho fixo para o header


class Network:
    def __init__(self, server_ip, port=5555):
        self.client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server = server_ip
        self.port = port
        self.addr = (self.server, self.port)

        try:
            self.player_id = self.connect()
        except Exception as e:
            print(f"[Network] Erro ao conectar: {e}")
            raise

    def get_player_id(self):
        return self.player_id

    def connect(self):
        try:
            self.client.connect(self.addr)
            return pickle.loads(self.client.recv(2048))  # Receber ID é simples
        except socket.error as e:
            print(f"[Network] Erro de socket: {e}")
            return None

    def send(self, data):
        """Apenas envia dados C2S com header."""
        try:
            pickled_data = pickle.dumps(data)
            header = f"{len(pickled_data):<{HEADER_LENGTH}}".encode('utf-8')
            self.client.sendall(header + pickled_data)
            return True
        except socket.error as e:
            print(f"[Network] Erro ao enviar: {e}")
            return False

    def recv(self):
        """Apenas recebe dados S2C com header."""
        try:
            # 1. Recebe o header
            header = self.client.recv(HEADER_LENGTH)
            if not header:
                print("[Network] Conexão fechada ao esperar header S2C.")
                return None

            message_length = int(header.decode('utf-8').strip())

            # 2. Recebe a mensagem
            all_data = b''
            while len(all_data) < message_length:
                remaining_bytes = message_length - len(all_data)
                bytes_to_read = min(8192, remaining_bytes)
                part = self.client.recv(bytes_to_read)
                if not part:
                    print("[Network] Conexão perdida no meio da mensagem S2C.")
                    return None
                all_data += part

            return pickle.loads(all_data)

        except socket.error as e:
            # Captura erros comuns de desconexão sem poluir o console
            if e.errno != 10054 and e.errno != 10053:  # Connection reset/aborted
                print(f"[Network] Erro ao receber: {e}")
            return None
        except Exception as e:
            print(f"[Network] Erro geral ao receber: {e}")
            return None