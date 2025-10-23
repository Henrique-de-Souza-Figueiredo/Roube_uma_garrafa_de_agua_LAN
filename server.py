import socket
import threading
import pickle
import random
import math
import sys
import time
import pygame
from queue import Queue  # Fila para comunicação entre threads

# --- Constantes do Jogo ---
SCREEN_WIDTH = 1280
SCREEN_HEIGHT = 720
FPS = 60
HEADER_LENGTH = 10
MAX_PLAYERS = 4
SPAWN_INTERVAL = 120  # 2 segundos (a 60 FPS)
MONEY_INTERVAL = 60  # 1 segundo (a 60 FPS)

# --- Cores ---
RED = (255, 0, 0)
BLUE = (0, 0, 255)
LIME_GREEN = (50, 255, 50)
MAGENTA = (255, 0, 255)
GOLD = (255, 215, 0)

# --- Raridades ---
RARITIES = ["Descartável", "Reutilizável", "Colecionável", "Premium", "Artefato"]
RARITY_COLORS = {
    "Descartável": (150, 150, 150),
    "Reutilizável": (0, 200, 0),
    "Colecionável": (0, 100, 255),
    "Premium": (150, 0, 200),
    "Artefato": (255, 150, 0)
}
RARITY_WEIGHTS = [50, 30, 15, 4, 1]

# --- Templates das Garrafas ---
BOTTLE_TEMPLATES = [
    {"name": "Água de Torneira", "rarity": "Descartável", "value": 5, "income": 0.1},
    {"name": "Garrafinha Comum", "rarity": "Descartável", "value": 7, "income": 0.15},
    {"name": "Marca Duvidosa", "rarity": "Descartável", "value": 6, "income": 0.12},
    {"name": "Água Filtrada", "rarity": "Descartável", "value": 8, "income": 0.18},
    {"name": "Água Mineral", "rarity": "Reutilizável", "value": 15, "income": 0.5},
    {"name": "Garrafa Esportiva", "rarity": "Reutilizável", "value": 20, "income": 0.7},
    {"name": "Squeeze Básico", "rarity": "Reutilizável", "value": 18, "income": 0.6},
    {"name": "Garrafa de Plástico Duro", "rarity": "Reutilizável", "value": 22, "income": 0.8},
    {"name": "Água de Nascente", "rarity": "Colecionável", "value": 50, "income": 1.5},
    {"name": "Garrafa de Vidro", "rarity": "Colecionável", "value": 60, "income": 1.8},
    {"name": "Edição Limitada", "rarity": "Colecionável", "value": 55, "income": 1.6},
    {"name": "Água Vulcânica", "rarity": "Colecionável", "value": 65, "income": 2.0},
    {"name": "Água de Geleira", "rarity": "Premium", "value": 150, "income": 5.0},
    {"name": "Garrafa Térmica", "rarity": "Premium", "value": 180, "income": 6.0},
    {"name": "Design Italiano", "rarity": "Premium", "value": 160, "income": 5.5},
    {"name": "Água Alcalina", "rarity": "Premium", "value": 200, "income": 7.0},
    {"name": "Fonte da Juventude", "rarity": "Artefato", "value": 500, "income": 20.0},
    {"name": "Elixir Místico", "rarity": "Artefato", "value": 600, "income": 25.0},
    {"name": "Água Lunar", "rarity": "Artefato", "value": 550, "income": 22.0},
    {"name": "Hidromel dos Deuses", "rarity": "Artefato", "value": 700, "income": 30.0}
]

# --- Configuração das Lojas (Apenas dados, sem Pygame Rects) ---
CONVEYOR_Y = SCREEN_HEIGHT // 2 - 30
conveyor_rect_data = (0, CONVEYOR_Y, SCREEN_WIDTH, 60)
conveyor_speed = 2

# Bases
base_width, base_height = 250, 100
player_base_rects_data = [
    (50, 50, base_width, base_height),  # P1
    (SCREEN_WIDTH - 300, 50, base_width, base_height),  # P2
    (50, CONVEYOR_Y + 70, base_width, base_height),  # P3
    (SCREEN_WIDTH - 300, CONVEYOR_Y + 70, base_width, base_height)  # P4
]

# Posições Iniciais
player_start_pos = [
    (100, 250),  # P1
    (SCREEN_WIDTH - 130, 250),  # P2
    (100, 470),  # P3
    (SCREEN_WIDTH - 130, 470)  # P4
]

# Cores
player_colors = [RED, BLUE, LIME_GREEN, MAGENTA]

# Lojas
PACK_WIDTH, PACK_HEIGHT, PACK_Y, PACK_PADDING = 180, 80, SCREEN_HEIGHT - 100, 20
SHOP_PACKS_DATA = {
    "Descartável": {"cost": 10,
                    "rect": (SCREEN_WIDTH // 2 - (PACK_WIDTH * 1.5 + PACK_PADDING), PACK_Y, PACK_WIDTH, PACK_HEIGHT)},
    "Reutilizável": {"cost": 30, "rect": (SCREEN_WIDTH // 2 - (PACK_WIDTH * 0.5), PACK_Y, PACK_WIDTH, PACK_HEIGHT)},
    "Colecionável": {"cost": 100,
                     "rect": (SCREEN_WIDTH // 2 + (PACK_WIDTH * 0.5 + PACK_PADDING), PACK_Y, PACK_WIDTH, PACK_HEIGHT)}
}

WEAPON_WIDTH, WEAPON_HEIGHT, WEAPON_Y, WEAPON_PADDING = 180, 80, SCREEN_HEIGHT - 220, 10
TOTAL_WEAPON_WIDTH = (WEAPON_WIDTH * 3) + (WEAPON_PADDING * 2)
WEAPON_START_X = (SCREEN_WIDTH - TOTAL_WEAPON_WIDTH) // 2
WEAPON_SHOP_ITEMS_DATA = {
    "Tênis": {"cost": 100, "desc": "Velocidade +2", "rect": (WEAPON_START_X, WEAPON_Y, WEAPON_WIDTH, WEAPON_HEIGHT),
              "type": "passive"},
    "Defesa": {"cost": 250, "desc": "Defesa Speed x2.0",
               "rect": (WEAPON_START_X + WEAPON_WIDTH + WEAPON_PADDING, WEAPON_Y, WEAPON_WIDTH, WEAPON_HEIGHT),
               "type": "passive"},
    "Raio Orbital": {"cost": 500, "desc": "Atordoa (3s) + Devolve Item", "rect": (
    WEAPON_START_X + (WEAPON_WIDTH + WEAPON_PADDING) * 2, WEAPON_Y, WEAPON_WIDTH, WEAPON_HEIGHT), "type": "consumable"}
}

# --- Classes do Jogo (Lógica do Servidor) ---
pygame.init()


class Bottle:
    def __init__(self, template, is_golden=False):
        self.name = template["name"]
        self.rarity = template["rarity"]
        self.base_value = template["value"]
        self.base_income = template["income"]
        self.is_golden = is_golden
        self.value = self.base_value * 3 if self.is_golden else self.base_value
        self.income = self.base_income * 3 if self.is_golden else self.base_income
        self.color = RARITY_COLORS[self.rarity]
        self.rect = pygame.Rect(0, 0, 20, 40)
        self.owner_id = None

    def to_dict(self):
        return {
            "name": self.name, "rarity": self.rarity, "value": self.value,
            "income": self.income, "is_golden": self.is_golden, "color": self.color,
            "rect_data": (self.rect.x, self.rect.y, self.rect.w, self.rect.h),
            "owner_id": self.owner_id
        }


class Player:
    def __init__(self, x, y, color, base_rect_data, player_id):
        self.rect = pygame.Rect(x, y, 30, 30)
        self.color = color
        self.id = player_id
        self.money = 10.0
        self.base_rect = pygame.Rect(base_rect_data)
        self.base_speed = 4
        self.current_speed = self.base_speed
        self.theft_speed_multiplier = 1.5
        self.carrying_bottle = None
        self.is_being_stolen_from = False
        self.is_stunned = False
        self.stun_timer = 0
        self.equipped_slots = [None, None, None]
        self.equipped_slot_positions_data = []
        self.has_weapon = {"Tênis": False, "Defesa": False}
        self.consumables = {"Raio Orbital": 0}

        slot_width, slot_height, slot_padding = 40, 50, 20
        total_width = (3 * slot_width) + (2 * slot_padding)
        start_x = self.base_rect.centerx - total_width // 2
        start_y = self.base_rect.centery - slot_height // 2
        for i in range(3):
            slot_x = start_x + i * (slot_width + slot_padding)
            rect_data = (slot_x, start_y, slot_width, slot_height)
            self.equipped_slot_positions_data.append(rect_data)

    def to_dict(self):
        equipped_slots_data = [b.to_dict() if b else None for b in self.equipped_slots]
        carrying_bottle_data = self.carrying_bottle.to_dict() if self.carrying_bottle else None
        return {
            "rect_data": (self.rect.x, self.rect.y, self.rect.w, self.rect.h),
            "color": self.color, "id": self.id, "money": self.money,
            "base_rect_data": (self.base_rect.x, self.base_rect.y, self.base_rect.w, self.base_rect.h),
            "is_stunned": self.is_stunned,
            "carrying_bottle_data": carrying_bottle_data,
            "equipped_slots_data": equipped_slots_data,
            "equipped_slot_positions_data": self.equipped_slot_positions_data,
            "has_weapon": self.has_weapon, "consumables": self.consumables
        }

    def move(self, keys_pressed):
        """(MUDANÇA) Move o jogador usando WASD, independente do ID."""
        if self.is_stunned: return

        dx, dy = 0, 0

        # Padroniza para WASD para todos
        if keys_pressed[pygame.K_w]: dy = -self.current_speed
        if keys_pressed[pygame.K_s]: dy = self.current_speed
        if keys_pressed[pygame.K_a]: dx = -self.current_speed
        if keys_pressed[pygame.K_d]: dx = self.current_speed

        self.rect.x += dx
        self.rect.y += dy
        screen_rect = pygame.Rect(0, 0, SCREEN_WIDTH, SCREEN_HEIGHT)
        self.rect.clamp_ip(screen_rect)

    def update(self, all_players_list):
        if self.is_stunned:
            self.stun_timer -= 1
            if self.stun_timer <= 0: self.is_stunned = False
            return
        self.is_being_stolen_from = False
        for p in all_players_list:
            if p and p.carrying_bottle and p.carrying_bottle.owner_id == self.id:
                self.is_being_stolen_from = True;
                break
        current_base_speed = self.base_speed + 2 if self.has_weapon["Tênis"] else self.base_speed
        current_multiplier = 2.0 if self.has_weapon["Defesa"] else self.theft_speed_multiplier
        self.current_speed = current_base_speed * current_multiplier if self.is_being_stolen_from else current_base_speed
        if self.carrying_bottle:
            self.carrying_bottle.rect.center = self.rect.center

    def calculate_income(self):
        return sum(b.income for b in self.equipped_slots if b)

    def handle_interaction(self, conveyor_bottles, all_players_list):
        if self.is_stunned: return
        all_other_players = [p for p in all_players_list if p and p != self]

        # 1. Guardar garrafa
        if self.carrying_bottle and self.rect.colliderect(self.base_rect):
            for i in range(len(self.equipped_slots)):
                if self.equipped_slots[i] is None:
                    self.equipped_slots[i] = self.carrying_bottle
                    self.equipped_slots[i].owner_id = self.id
                    slot_rect_data = self.equipped_slot_positions_data[i]
                    self.equipped_slots[i].rect.center = (
                    slot_rect_data[0] + slot_rect_data[2] // 2, slot_rect_data[1] + slot_rect_data[3] // 2)
                    self.carrying_bottle = None;
                    return
        # 2. Recuperar garrafa
        for other_player in all_other_players:
            if other_player.carrying_bottle and other_player.carrying_bottle.owner_id == self.id and self.rect.colliderect(
                    other_player.rect):
                for i in range(len(self.equipped_slots)):
                    if self.equipped_slots[i] is None:
                        self.equipped_slots[i] = other_player.carrying_bottle
                        slot_rect_data = self.equipped_slot_positions_data[i]
                        self.equipped_slots[i].rect.center = (
                        slot_rect_data[0] + slot_rect_data[2] // 2, slot_rect_data[1] + slot_rect_data[3] // 2)
                        other_player.carrying_bottle = None;
                        return
        # 3. Vender garrafa
        if self.carrying_bottle is None and self.rect.colliderect(self.base_rect):
            for i, slot_data in enumerate(self.equipped_slot_positions_data):
                if self.equipped_slots[i] and self.rect.colliderect(pygame.Rect(slot_data)):
                    self.money += self.equipped_slots[i].value
                    self.equipped_slots[i] = None;
                    return
        # 4. Comprar Upgrades
        if self.carrying_bottle is None:
            for weapon_name, info in WEAPON_SHOP_ITEMS_DATA.items():
                if self.rect.colliderect(pygame.Rect(info["rect"])):
                    if self.money < info["cost"]: return
                    self.money -= info["cost"]
                    if info["type"] == "passive":
                        if not self.has_weapon[weapon_name]:
                            self.has_weapon[weapon_name] = True
                        else:
                            self.money += info["cost"]  # Devolve
                    elif info["type"] == "consumable":
                        self.consumables[weapon_name] += 1
                    return
        # 5. Comprar Packs
        if self.carrying_bottle is None:
            for rarity, pack_info in SHOP_PACKS_DATA.items():
                if self.rect.colliderect(pygame.Rect(pack_info["rect"])):
                    if self.money >= pack_info["cost"]:
                        for i in range(len(self.equipped_slots)):
                            if self.equipped_slots[i] is None:
                                self.money -= pack_info["cost"]
                                new_bottle = create_bottle_by_rarity(rarity)
                                self.equipped_slots[i] = new_bottle
                                new_bottle.owner_id = self.id
                                slot_rect_data = self.equipped_slot_positions_data[i]
                                new_bottle.rect.center = (
                                slot_rect_data[0] + slot_rect_data[2] // 2, slot_rect_data[1] + slot_rect_data[3] // 2)
                                return
                    return
        # 6. Roubar
        if self.carrying_bottle is None:
            for other_player in all_other_players:
                if self.rect.colliderect(other_player.base_rect):
                    for i, slot_data in enumerate(other_player.equipped_slot_positions_data):
                        if other_player.equipped_slots[i] and self.rect.colliderect(pygame.Rect(slot_data)):
                            self.carrying_bottle = other_player.equipped_slots[i]
                            other_player.equipped_slots[i] = None;
                            return
        # 7. Comprar da esteira
        if self.carrying_bottle is None:
            for bottle in conveyor_bottles:
                if self.rect.colliderect(bottle.rect):
                    if self.money >= bottle.value:
                        for i in range(len(self.equipped_slots)):
                            if self.equipped_slots[i] is None:
                                self.money -= bottle.value
                                self.equipped_slots[i] = bottle
                                bottle.owner_id = self.id
                                slot_rect_data = self.equipped_slot_positions_data[i]
                                bottle.rect.center = (
                                slot_rect_data[0] + slot_rect_data[2] // 2, slot_rect_data[1] + slot_rect_data[3] // 2)
                                conveyor_bottles.remove(bottle);
                                return
                    return

    def use_orbital_ray(self, all_players_list):
        if self.is_stunned or self.consumables["Raio Orbital"] <= 0: return
        self.consumables["Raio Orbital"] -= 1
        closest_enemy, min_dist_sq = None, float('inf')
        for enemy in all_players_list:
            if not enemy or enemy == self or enemy.rect.colliderect(enemy.base_rect): continue
            dist_sq = (enemy.rect.centerx - self.rect.centerx) ** 2 + (enemy.rect.centery - self.rect.centery) ** 2
            if dist_sq < min_dist_sq: min_dist_sq, closest_enemy = dist_sq, enemy
        if closest_enemy:
            closest_enemy.is_stunned = True
            closest_enemy.stun_timer = FPS * 3
            if closest_enemy.carrying_bottle:
                bottle, owner_id = closest_enemy.carrying_bottle, closest_enemy.carrying_bottle.owner_id
                closest_enemy.carrying_bottle = None
                owner = next((p for p in all_players_list if p and p.id == owner_id), None)
                if owner:
                    for i in range(len(owner.equipped_slots)):
                        if owner.equipped_slots[i] is None:
                            owner.equipped_slots[i] = bottle
                            slot_rect_data = owner.equipped_slot_positions_data[i]
                            bottle.rect.center = (
                            slot_rect_data[0] + slot_rect_data[2] // 2, slot_rect_data[1] + slot_rect_data[3] // 2)
                            return


# --- Funções Auxiliares do Servidor ---
def create_bottle_by_rarity(rarity):
    possible_templates = [t for t in BOTTLE_TEMPLATES if t["rarity"] == rarity]
    template = random.choice(possible_templates)
    return Bottle(template, random.random() < 0.1)


def spawn_bottle():
    rarity_choice = random.choices(RARITIES, weights=RARITY_WEIGHTS, k=1)[0]
    new_bottle = create_bottle_by_rarity(rarity_choice)
    conveyor_rect = pygame.Rect(conveyor_rect_data)
    new_bottle.rect.topleft = (
    -new_bottle.rect.width, conveyor_rect.y + (conveyor_rect.height // 2 - new_bottle.rect.height // 2))
    return new_bottle


# --- Lógica de Rede (Arquitetura de Filas) ---

input_queue = Queue()
output_queues = {}
client_connections = {}
clients_lock = threading.Lock()


def client_listener_thread(conn, player_id):
    """Thread dedicada a *apenas* OUVIR um cliente."""
    conn.send(pickle.dumps(player_id))  # Envia o ID (simples)
    print(f"[Thread-{player_id}] Listener iniciada.")
    while True:
        try:
            # 1. Recebe C2S (inputs) com header
            header = conn.recv(HEADER_LENGTH)
            if not header:
                break

            message_length = int(header.decode('utf-8').strip())

            data = b''
            while len(data) < message_length:
                remaining = message_length - len(data)
                part = conn.recv(min(4096, remaining))
                if not part:
                    raise ConnectionError("Cliente desconectou no meio da mensagem C2S")
                data += part

            input_queue.put((player_id, pickle.loads(data)))

        except (ConnectionResetError, ConnectionAbortedError, EOFError):
            break
        except Exception as e:
            print(f"[Erro Listener P{player_id}]: {e}")
            break

    print(f"[Thread-{player_id}] Listener encerrada.")
    input_queue.put((player_id, "disconnect"))  # Sinaliza desconexão


def client_sender_thread(conn, player_id):
    """Thread dedicada a *apenas* ENVIAR para um cliente."""
    print(f"[Thread-{player_id}] Sender iniciada.")
    q = output_queues[player_id]
    while True:
        try:
            game_state = q.get()
            if game_state == "disconnect":
                break

            pickled_state = pickle.dumps(game_state)
            header = f"{len(pickled_state):<{HEADER_LENGTH}}".encode('utf-8')

            conn.sendall(header + pickled_state)

        except (ConnectionResetError, ConnectionAbortedError, EOFError):
            break
        except Exception as e:
            print(f"[Erro Sender P{player_id}]: {e}")
            break

    print(f"[Thread-{player_id}] Sender encerrada.")
    with clients_lock:
        client_connections.pop(player_id, None)
        output_queues.pop(player_id, None)
    conn.close()


# --- Estado Global do Jogo (Controlado pela Lógica Principal) ---
players = [None] * MAX_PLAYERS
conveyor_bottles = []


def game_logic_thread():
    """Thread única que roda a lógica do jogo (sem travas de rede)."""
    global players, conveyor_bottles

    clock = pygame.time.Clock()
    spawn_timer = 0
    money_timer = 0

    print("[GameLogic] Thread de lógica iniciada.")

    while True:
        # 1. Processar todos os inputs da fila (C2S)
        while not input_queue.empty():
            player_id, data = input_queue.get()

            if data == "disconnect":
                print(f"[GameLogic] Processando desconexão de P{player_id + 1}")
                players[player_id] = None
                with clients_lock:
                    if player_id in output_queues:
                        output_queues[player_id].put("disconnect")
                continue

            player = players[player_id]
            if not player:
                continue

            # Processa os inputs
            player.move(data['keys'])
            if data['interact']:
                player.handle_interaction(conveyor_bottles, players)
            if data['use_item']:
                player.use_orbital_ray(players)

        # 2. Atualizar Estado do Jogo (Lógica de Ticks)
        active_players = [p for p in players if p]

        for player in active_players:
            player.update(active_players)

        # Spawner
        spawn_timer += 1
        if spawn_timer >= SPAWN_INTERVAL:
            spawn_timer = 0
            if len(conveyor_bottles) < 15:
                conveyor_bottles.append(spawn_bottle())

        # Esteira
        for bottle in conveyor_bottles[:]:
            bottle.rect.x += conveyor_speed
            if bottle.rect.left > SCREEN_WIDTH:
                conveyor_bottles.remove(bottle)

        # Dinheiro
        money_timer += 1
        if money_timer >= MONEY_INTERVAL:
            money_timer = 0
            for player in active_players:
                player.money += player.calculate_income()

        # 3. Preparar e Distribuir o novo Estado (S2C)
        players_data = [p.to_dict() if p else None for p in players]
        bottles_data = [b.to_dict() for b in conveyor_bottles]

        game_state = {
            "players": players_data,
            "conveyor_bottles": bottles_data
        }

        with clients_lock:
            for q in output_queues.values():
                q.put(game_state)

                # 4. Controla o FPS
        clock.tick(FPS)


# --- Loop Principal (Apenas aceita conexões) ---
def main():
    SERVER_IP = "0.0.0.0"
    PORT = 5555

    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.bind((SERVER_IP, PORT))
        s.listen(MAX_PLAYERS)
        print(f"Servidor iniciado em {SERVER_IP}:{PORT}. Aguardando conexões...")
    except socket.error as e:
        print(f"Erro ao iniciar o servidor: {str(e)}")
        sys.exit()

    threading.Thread(target=game_logic_thread, daemon=True).start()

    while True:
        conn, addr = s.accept()
        print(f"Nova conexão de: {addr}")

        new_player_id = -1
        with clients_lock:
            for i in range(MAX_PLAYERS):
                if players[i] is None and i not in client_connections:
                    new_player_id = i
                    break

        if new_player_id != -1:
            start_x, start_y = player_start_pos[new_player_id]
            color = player_colors[new_player_id]
            base_data = player_base_rects_data[new_player_id]
            players[new_player_id] = Player(start_x, start_y, color, base_data, new_player_id)

            with clients_lock:
                output_queues[new_player_id] = Queue()
                client_connections[new_player_id] = conn

            threading.Thread(target=client_listener_thread, args=(conn, new_player_id), daemon=True).start()
            threading.Thread(target=client_sender_thread, args=(conn, new_player_id), daemon=True).start()

            print(f"Jogador {new_player_id + 1} (P{new_player_id + 1}) conectado.")
        else:
            print("Servidor cheio. Conexão recusada.")
            conn.close()


if __name__ == "__main__":
    main()