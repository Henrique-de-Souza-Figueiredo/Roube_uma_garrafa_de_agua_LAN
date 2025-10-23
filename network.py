import socket
import pickle

HEADER_LENGTH = 10  # Tamanho fixo para o header


class Network:
    # (NOVO) Aceita player_name no construtor
    def __init__(self, server_ip, player_name, port=5555):
        self.client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server = server_ip
        self.port = port
        self.addr = (self.server, self.port)
        self.player_name = player_name  # Armazena o nome

        try:
            # (NOVO) Passa o nome para o método connect
            self.player_id = self.connect(self.player_name)
        except Exception as e:
            print(f"[Network] Erro ao conectar: {e}")
            raise

    def get_player_id(self):
        return self.player_id

    # (NOVO) Aceita player_name como argumento
    def connect(self, player_name_to_send):
        """Conecta, recebe ID, envia nome e retorna ID."""
        try:
            # 1. Conecta
            self.client.connect(self.addr)

            # 2. Recebe ID do servidor
            player_id = pickle.loads(self.client.recv(2048))

            # 3. (NOVO) Envia o nome para o servidor
            #    (Usamos send simples aqui, nomes são curtos)
            self.client.send(pickle.dumps(player_name_to_send))

            # 4. Retorna o ID recebido
            return player_id

        except socket.error as e:
            print(f"[Network] Erro de socket na conexão: {e}")
            return None

    def send(self, data):
        """Apenas envia dados C2S com header."""
        try:
            pickled_data = pickle.dumps(data)
            header = f"{len(pickled_data):<{HEADER_LENGTH}}".encode('utf-8')
            self.client.sendall(header + pickled_data)
            return True
        except socket.error as e:
            # Minimiza spam de erros de desconexão comum
            if e.errno != 10053 and e.errno != 10054:  # Software caused connection abort / Connection reset by peer
                print(f"[Network] Erro ao enviar: {e}")
            return False

    def recv(self):
        """Apenas recebe dados S2C com header."""
        try:
            header = self.client.recv(HEADER_LENGTH)
            if not header: return None  # Conexão fechada
            message_length = int(header.decode('utf-8').strip())

            all_data = b''
            while len(all_data) < message_length:
                part = self.client.recv(min(8192, message_length - len(all_data)))
                if not part: return None  # Conexão perdida
                all_data += part

            return pickle.loads(all_data)

        except socket.error as e:
            if e.errno != 10054 and e.errno != 10053:
                print(f"[Network] Erro ao receber: {e}")
            return None
        except ValueError:  # Erro se o header for inválido
            print(f"[Network] Header S2C inválido recebido.")
            return None
        except Exception as e:
            print(f"[Network] Erro geral ao receber: {e}")
            return None