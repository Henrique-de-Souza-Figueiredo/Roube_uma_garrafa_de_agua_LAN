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
SCREEN_WIDTH = 1280;
SCREEN_HEIGHT = 720;
FPS = 60
HEADER_LENGTH = 10;
MAX_PLAYERS = 4
SPAWN_INTERVAL = 120;
MONEY_INTERVAL = 60

# --- Cores ---
RED = (255, 0, 0);
BLUE = (0, 0, 255);
LIME_GREEN = (50, 255, 50)
MAGENTA = (255, 0, 255);
GOLD = (255, 215, 0)

# --- Raridades ---
RARITIES = ["Descartável", "Reutilizável", "Colecionável", "Premium", "Artefato"]
RARITY_COLORS = {
    "Descartável": (150, 150, 150), "Reutilizável": (0, 200, 0), "Colecionável": (0, 100, 255),
    "Premium": (150, 0, 200), "Artefato": (255, 150, 0)
}
RARITY_WEIGHTS = [50, 30, 15, 4, 1]

# --- Templates das Garrafas ---
# (Omitido - igual antes)
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

# --- Configurações ---
CONVEYOR_Y = SCREEN_HEIGHT // 2 - 30
conveyor_rect_data = (0, CONVEYOR_Y, SCREEN_WIDTH, 60);
conveyor_speed = 2
base_width, base_height = 250, 100
player_base_rects_data = [
    (50, 50, base_width, base_height), (SCREEN_WIDTH - 300, 50, base_width, base_height),
    (50, CONVEYOR_Y + 70, base_width, base_height), (SCREEN_WIDTH - 300, CONVEYOR_Y + 70, base_width, base_height)
]
player_start_pos = [(100, 250), (SCREEN_WIDTH - 130, 250), (100, 470), (SCREEN_WIDTH - 130, 470)]
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
WEAPON_START_X = (SCREEN_WIDTH - (WEAPON_WIDTH * 3 + WEAPON_PADDING * 2)) // 2
WEAPON_SHOP_ITEMS_DATA = {
    "Tênis": {"cost": 100, "desc": "Velocidade +2", "rect": (WEAPON_START_X, WEAPON_Y, WEAPON_WIDTH, WEAPON_HEIGHT),
              "type": "passive"},
    "Bateria Extra": {"cost": 250, "desc": "Escudo +15s",
                      "rect": (WEAPON_START_X + WEAPON_WIDTH + WEAPON_PADDING, WEAPON_Y, WEAPON_WIDTH, WEAPON_HEIGHT),
                      "type": "passive"},
    "Raio Orbital": {"cost": 500, "desc": "Atordoa(3s)+Devolve", "rect": (
    WEAPON_START_X + (WEAPON_WIDTH + WEAPON_PADDING) * 2, WEAPON_Y, WEAPON_WIDTH, WEAPON_HEIGHT), "type": "consumable"}
}

# --- Classes do Jogo ---
pygame.init()


class Bottle:
    # (Não mudou)
    def __init__(self, template, is_golden=False):
        self.name = template["name"];
        self.rarity = template["rarity"]
        self.base_value = template["value"];
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
    # (NOVO) Aceita 'name' no construtor
    def __init__(self, x, y, color, base_rect_data, player_id, name):
        self.rect = pygame.Rect(x, y, 30, 30)
        self.color = color;
        self.id = player_id;
        self.money = 10.0
        self.name = name if name else f"Player {player_id + 1}"  # Nome default se vazio
        self.base_rect = pygame.Rect(base_rect_data)
        self.base_speed = 4;
        self.current_speed = self.base_speed
        self.theft_speed_multiplier = 1.5
        self.carrying_bottle = None
        self.is_being_stolen_from = False
        self.is_stunned = False;
        self.stun_timer = 0
        self.equipped_slots = [None, None, None]
        self.equipped_slot_positions_data = []
        self.has_weapon = {"Tênis": False, "Bateria Extra": False}
        self.consumables = {"Raio Orbital": 0}
        self.shield_active = False;
        self.shield_timer = 0;
        self.shield_cooldown = 0
        self.base_shield_duration_frames = 30 * FPS
        self.bonus_shield_duration_frames = 0
        self.shield_button_rect = pygame.Rect(self.base_rect.x + 5, self.base_rect.y + 5, 20, 20)

        slot_width, slot_height, slot_padding = 40, 50, 20
        start_x = self.base_rect.centerx - (3 * slot_width + 2 * slot_padding) // 2
        start_y = self.base_rect.centery - slot_height // 2
        for i in range(3):
            self.equipped_slot_positions_data.append(
                (start_x + i * (slot_width + slot_padding), start_y, slot_width, slot_height))

    def to_dict(self):
        # (NOVO) Inclui 'name'
        equipped = [b.to_dict() if b else None for b in self.equipped_slots]
        carrying = self.carrying_bottle.to_dict() if self.carrying_bottle else None
        return {
            "name": self.name,  # <-- Incluído
            "rect_data": (self.rect.x, self.rect.y, self.rect.w, self.rect.h),
            "color": self.color, "id": self.id, "money": self.money,
            "base_rect_data": (self.base_rect.x, self.base_rect.y, self.base_rect.w, self.base_rect.h),
            "is_stunned": self.is_stunned, "carrying_bottle_data": carrying,
            "equipped_slots_data": equipped, "equipped_slot_positions_data": self.equipped_slot_positions_data,
            "has_weapon": self.has_weapon, "consumables": self.consumables,
            "shield_active": self.shield_active, "shield_timer_frames": self.shield_timer,
            "shield_cooldown_frames": self.shield_cooldown,
            "shield_button_rect_data": (
            self.shield_button_rect.x, self.shield_button_rect.y, self.shield_button_rect.w, self.shield_button_rect.h)
        }

    def move(self, keys_pressed):
        # (Não mudou - já usa WASD)
        if self.is_stunned: return
        dx, dy = 0, 0
        if keys_pressed[pygame.K_w]: dy = -self.current_speed
        if keys_pressed[pygame.K_s]: dy = self.current_speed
        if keys_pressed[pygame.K_a]: dx = -self.current_speed
        if keys_pressed[pygame.K_d]: dx = self.current_speed
        self.rect.x += dx;
        self.rect.y += dy
        self.rect.clamp_ip(pygame.Rect(0, 0, SCREEN_WIDTH, SCREEN_HEIGHT))

    def update(self, all_players_list):
        # (Não mudou - escudo e velocidade)
        if self.shield_timer > 0:
            self.shield_timer -= 1
            if self.shield_timer <= 0: self.shield_active = False
        if self.shield_cooldown > 0: self.shield_cooldown -= 1
        if self.is_stunned:
            self.stun_timer -= 1
            if self.stun_timer <= 0: self.is_stunned = False
            return
        self.is_being_stolen_from = any(
            p and p.carrying_bottle and p.carrying_bottle.owner_id == self.id for p in all_players_list)
        base_speed = self.base_speed + 2 if self.has_weapon["Tênis"] else self.base_speed
        self.current_speed = base_speed * self.theft_speed_multiplier if self.is_being_stolen_from else base_speed
        if self.carrying_bottle: self.carrying_bottle.rect.center = self.rect.center

    def calculate_income(self):
        # (Não mudou)
        return sum(b.income for b in self.equipped_slots if b)

    def handle_interaction(self, conveyor_bottles, all_players_list):
        # (Não mudou - lógica de interação, compra de Bateria Extra já estava correta)
        if self.is_stunned: return
        others = [p for p in all_players_list if p and p != self]

        # 1. Guardar
        if self.carrying_bottle and self.rect.colliderect(self.base_rect):
            for i in range(3):
                if self.equipped_slots[i] is None:
                    self.equipped_slots[i] = self.carrying_bottle;
                    self.equipped_slots[i].owner_id = self.id
                    slot = self.equipped_slot_positions_data[i]
                    self.equipped_slots[i].rect.center = (slot[0] + slot[2] // 2, slot[1] + slot[3] // 2)
                    self.carrying_bottle = None;
                    return
        # 2. Recuperar
        for other in others:
            if other.carrying_bottle and other.carrying_bottle.owner_id == self.id and self.rect.colliderect(
                    other.rect):
                for i in range(3):
                    if self.equipped_slots[i] is None:
                        self.equipped_slots[i] = other.carrying_bottle
                        slot = self.equipped_slot_positions_data[i]
                        self.equipped_slots[i].rect.center = (slot[0] + slot[2] // 2, slot[1] + slot[3] // 2)
                        other.carrying_bottle = None;
                        return
        # 3. Escudo
        if not self.carrying_bottle and self.rect.colliderect(self.shield_button_rect):
            if self.shield_cooldown <= 0:
                self.shield_active = True
                duration = self.base_shield_duration_frames + self.bonus_shield_duration_frames
                self.shield_timer = duration
                self.shield_cooldown = (duration // FPS + 10) * FPS
                print(f"{self.name} ativou escudo ({duration // FPS}s)!");
                return
            else:
                print(f"{self.name} escudo em CD ({self.shield_cooldown // FPS}s)"); return
            # 4. Vender
        if not self.carrying_bottle and self.rect.colliderect(self.base_rect):
            for i, slot_data in enumerate(self.equipped_slot_positions_data):
                if self.equipped_slots[i] and self.rect.colliderect(pygame.Rect(slot_data)):
                    self.money += self.equipped_slots[i].value;
                    self.equipped_slots[i] = None;
                    return
        # 5. Comprar Upgrades
        if not self.carrying_bottle:
            for name, info in WEAPON_SHOP_ITEMS_DATA.items():
                if self.rect.colliderect(pygame.Rect(info["rect"])):
                    if self.money < info["cost"]: return
                    if info["type"] == "passive" and self.has_weapon.get(name, False): return
                    self.money -= info["cost"]
                    if info["type"] == "passive":
                        self.has_weapon[name] = True
                        if name == "Bateria Extra": self.bonus_shield_duration_frames = 15 * FPS
                    elif info["type"] == "consumable":
                        self.consumables[name] += 1
                    return
        # 6. Comprar Packs
        if not self.carrying_bottle:
            for rarity, info in SHOP_PACKS_DATA.items():
                if self.rect.colliderect(pygame.Rect(info["rect"])):
                    if self.money >= info["cost"]:
                        for i in range(3):
                            if self.equipped_slots[i] is None:
                                self.money -= info["cost"];
                                new_bottle = create_bottle_by_rarity(rarity)
                                self.equipped_slots[i] = new_bottle;
                                new_bottle.owner_id = self.id
                                slot = self.equipped_slot_positions_data[i]
                                new_bottle.rect.center = (slot[0] + slot[2] // 2, slot[1] + slot[3] // 2);
                                return
                    return
        # 7. Roubar
        if not self.carrying_bottle:
            for other in others:
                if other.shield_active and self.rect.colliderect(other.base_rect): return
                if self.rect.colliderect(other.base_rect):
                    for i, slot_data in enumerate(other.equipped_slot_positions_data):
                        if other.equipped_slots[i] and self.rect.colliderect(pygame.Rect(slot_data)):
                            self.carrying_bottle = other.equipped_slots[i];
                            other.equipped_slots[i] = None;
                            return
        # 8. Comprar da esteira
        if not self.carrying_bottle:
            for bottle in conveyor_bottles:
                if self.rect.colliderect(bottle.rect):
                    if self.money >= bottle.value:
                        for i in range(3):
                            if self.equipped_slots[i] is None:
                                self.money -= bottle.value;
                                self.equipped_slots[i] = bottle
                                bottle.owner_id = self.id;
                                slot = self.equipped_slot_positions_data[i]
                                bottle.rect.center = (slot[0] + slot[2] // 2, slot[1] + slot[3] // 2)
                                conveyor_bottles.remove(bottle);
                                return
                    return

    def use_orbital_ray(self, all_players_list):
        # (Não mudou)
        if self.is_stunned or self.consumables["Raio Orbital"] <= 0: return
        self.consumables["Raio Orbital"] -= 1;
        closest, min_dist = None, float('inf')
        for enemy in all_players_list:
            if not enemy or enemy == self or enemy.rect.colliderect(enemy.base_rect): continue
            dist = (enemy.rect.centerx - self.rect.centerx) ** 2 + (enemy.rect.centery - self.rect.centery) ** 2
            if dist < min_dist: min_dist, closest = dist, enemy
        if closest:
            closest.is_stunned = True;
            closest.stun_timer = FPS * 3
            if closest.carrying_bottle:
                bottle, owner_id = closest.carrying_bottle, closest.carrying_bottle.owner_id
                closest.carrying_bottle = None
                owner = next((p for p in all_players_list if p and p.id == owner_id), None)
                if owner:
                    for i in range(3):
                        if owner.equipped_slots[i] is None:
                            owner.equipped_slots[i] = bottle;
                            slot = owner.equipped_slot_positions_data[i]
                            bottle.rect.center = (slot[0] + slot[2] // 2, slot[1] + slot[3] // 2);
                            return


# --- Funções Auxiliares do Servidor ---
def create_bottle_by_rarity(rarity):
    template = random.choice([t for t in BOTTLE_TEMPLATES if t["rarity"] == rarity])
    return Bottle(template, random.random() < 0.1)


def spawn_bottle():
    rarity = random.choices(RARITIES, weights=RARITY_WEIGHTS, k=1)[0]
    bottle = create_bottle_by_rarity(rarity)
    rect = pygame.Rect(conveyor_rect_data)
    bottle.rect.topleft = (-bottle.rect.width, rect.y + (rect.height // 2 - bottle.rect.height // 2))
    return bottle


# --- Lógica de Rede (Filas - Não mudou) ---
input_queue = Queue();
output_queues = {};
client_connections = {};
clients_lock = threading.Lock()


def client_listener_thread(conn, player_id):
    print(f"[Thread-{player_id}] Listener iniciada.")
    while True:  # Loop para receber dados C2S
        try:
            header = conn.recv(HEADER_LENGTH)
            if not header: break
            length = int(header.decode('utf-8').strip())
            data = b''
            while len(data) < length:
                part = conn.recv(min(4096, length - len(data)))
                if not part: raise ConnectionError("C2S Disconnect")
                data += part
            input_queue.put((player_id, pickle.loads(data)))
        except (ConnectionResetError, ConnectionAbortedError, EOFError, ConnectionError, ValueError):
            break
        except Exception as e:
            print(f"[Erro Listener P{player_id}]: {e}"); break
    print(f"[Thread-{player_id}] Listener encerrada.")
    input_queue.put((player_id, "disconnect"))


def client_sender_thread(conn, player_id):
    print(f"[Thread-{player_id}] Sender iniciada.")
    q = output_queues[player_id]
    while True:  # Loop para enviar dados S2C
        try:
            state = q.get();
            if state == "disconnect": break
            data = pickle.dumps(state)
            header = f"{len(data):<{HEADER_LENGTH}}".encode('utf-8')
            conn.sendall(header + data)
        except (ConnectionResetError, ConnectionAbortedError, EOFError):
            break
        except Exception as e:
            print(f"[Erro Sender P{player_id}]: {e}"); break
    print(f"[Thread-{player_id}] Sender encerrada.")
    with clients_lock:
        client_connections.pop(player_id, None); output_queues.pop(player_id, None)
    conn.close()


# --- Estado Global e Lógica Principal ---
players = [None] * MAX_PLAYERS
conveyor_bottles = []


def game_logic_thread():
    global players, conveyor_bottles
    clock = pygame.time.Clock();
    spawn_timer = 0;
    money_timer = 0
    print("[GameLogic] Thread de lógica iniciada.")
    while True:
        # 1. Processar Inputs
        while not input_queue.empty():
            p_id, data = input_queue.get()
            if data == "disconnect":
                print(f"[GameLogic] Desconexão P{p_id + 1}")
                players[p_id] = None
                with clients_lock:
                    if p_id in output_queues: output_queues[p_id].put("disconnect")
                continue
            player = players[p_id]
            if player:
                player.move(data['keys'])
                if data['interact']: player.handle_interaction(conveyor_bottles, players)
                if data['use_item']: player.use_orbital_ray(players)
        # 2. Atualizar Estado
        active = [p for p in players if p]
        for p in active: p.update(active)
        spawn_timer = (spawn_timer + 1) % SPAWN_INTERVAL
        if spawn_timer == 0 and len(conveyor_bottles) < 15: conveyor_bottles.append(spawn_bottle())
        for b in conveyor_bottles[:]:
            b.rect.x += conveyor_speed
            if b.rect.left > SCREEN_WIDTH: conveyor_bottles.remove(b)
        money_timer = (money_timer + 1) % MONEY_INTERVAL
        if money_timer == 0:
            for p in active: p.money += p.calculate_income()
        # 3. Distribuir Estado
        state = {"players": [p.to_dict() if p else None for p in players],
                 "conveyor_bottles": [b.to_dict() for b in conveyor_bottles]}
        with clients_lock:
            for q in output_queues.values(): q.put(state)
            # 4. FPS
        clock.tick(FPS)


# --- Loop Principal (Aceita conexões) ---
def main():
    SERVER_IP = "0.0.0.0";
    PORT = 5555
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.bind((SERVER_IP, PORT));
        s.listen(MAX_PLAYERS)
        print(f"Servidor iniciado em {SERVER_IP}:{PORT}...")
    except socket.error as e:
        print(f"Erro bind: {e}"); sys.exit()

    threading.Thread(target=game_logic_thread, daemon=True).start()

    while True:
        conn, addr = s.accept();
        print(f"Conexão de: {addr}")
        new_player_id = -1
        with clients_lock:
            for i in range(MAX_PLAYERS):
                if players[i] is None and i not in client_connections:
                    new_player_id = i;
                    break

        if new_player_id != -1:
            try:
                # --- (NOVO) Recebe nome APÓS enviar ID ---
                conn.send(pickle.dumps(new_player_id))  # Envia ID
                player_name_bytes = conn.recv(1024)  # Espera nome (buffer razoável)
                player_name = pickle.loads(player_name_bytes)
                print(f"Nome recebido: {player_name}")

                # Cria o jogador COM o nome
                start_x, start_y = player_start_pos[new_player_id]
                color = player_colors[new_player_id]
                base_data = player_base_rects_data[new_player_id]
                players[new_player_id] = Player(start_x, start_y, color, base_data, new_player_id, player_name)

                # Inicia threads de rede
                with clients_lock:
                    output_queues[new_player_id] = Queue()
                    client_connections[new_player_id] = conn
                threading.Thread(target=client_listener_thread, args=(conn, new_player_id), daemon=True).start()
                threading.Thread(target=client_sender_thread, args=(conn, new_player_id), daemon=True).start()
                print(f"Jogador {new_player_id + 1} ({player_name}) conectado.")

            except Exception as e:
                print(f"Erro ao inicializar jogador {new_player_id}: {e}")
                conn.close()  # Fecha a conexão se algo deu errado
        else:
            print("Servidor cheio.");
            conn.close()


if __name__ == "__main__":
    main()