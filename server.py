# server.py
# (Corrigido bug de interação e adicionada loja de troféu)

import socket
import threading
import pickle
import random
import math
import sys
import time
import pygame
from queue import Queue

# --- Importa TODAS as constantes do config.py ---
from config import *

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
        return {"name": self.name, "rarity": self.rarity, "value": self.value,
                "income": self.income, "is_golden": self.is_golden, "color": self.color,
                "rect_data": (self.rect.x, self.rect.y, self.rect.w, self.rect.h),
                "owner_id": self.owner_id}


class Player:
    # (Não mudou)
    def __init__(self, x, y, color, base_rect_data, player_id, name):
        self.rect = pygame.Rect(x, y, 30, 30)
        self.color = color;
        self.id = player_id;
        self.money = 10.0
        self.name = name if name else f"Player {player_id + 1}"
        self.base_rect = pygame.Rect(base_rect_data)
        self.base_speed = 4;
        self.current_speed = self.base_speed
        self.theft_speed_multiplier = 1.5;
        self.carrying_bottle = None
        self.is_being_stolen_from = False;
        self.is_stunned = False;
        self.stun_timer = 0
        self.equipped_slots = [None, None, None];
        self.equipped_slot_positions_data = []
        self.has_weapon = {"Tênis": False, "Bateria Extra": False}
        self.consumables = {"Raio Orbital": 0}
        self.shield_active = False;
        self.shield_timer = 0;
        self.shield_cooldown = 0
        self.base_shield_duration_frames = 30 * FPS;
        self.bonus_shield_duration_frames = 0
        self.shield_button_rect = pygame.Rect(self.base_rect.x + 5, self.base_rect.y + 5, 20, 20)
        slot_width, slot_height, slot_padding = 40, 50, 20
        start_x = self.base_rect.centerx - (3 * slot_width + 2 * slot_padding) // 2
        start_y = self.base_rect.centery - slot_height // 2
        for i in range(3):
            self.equipped_slot_positions_data.append(
                (start_x + i * (slot_width + slot_padding), start_y, slot_width, slot_height))

    def to_dict(self):
        equipped = [b.to_dict() if b else None for b in self.equipped_slots]
        carrying = self.carrying_bottle.to_dict() if self.carrying_bottle else None
        return {"name": self.name, "rect_data": (self.rect.x, self.rect.y, self.rect.w, self.rect.h),
                "color": self.color, "id": self.id, "money": self.money,
                "base_rect_data": (self.base_rect.x, self.base_rect.y, self.base_rect.w, self.base_rect.h),
                "is_stunned": self.is_stunned, "carrying_bottle_data": carrying,
                "equipped_slots_data": equipped, "equipped_slot_positions_data": self.equipped_slot_positions_data,
                "has_weapon": self.has_weapon, "consumables": self.consumables,
                "shield_active": self.shield_active, "shield_timer_frames": self.shield_timer,
                "shield_cooldown_frames": self.shield_cooldown,
                "shield_button_rect_data": (
                self.shield_button_rect.x, self.shield_button_rect.y, self.shield_button_rect.w,
                self.shield_button_rect.h)}

    def move(self, keys_pressed):
        if self.is_stunned or game_over: return
        dx, dy = 0, 0
        if keys_pressed[pygame.K_w]: dy = -self.current_speed
        if keys_pressed[pygame.K_s]: dy = self.current_speed
        if keys_pressed[pygame.K_a]: dx = -self.current_speed
        if keys_pressed[pygame.K_d]: dx = self.current_speed
        self.rect.x += dx;
        self.rect.y += dy
        self.rect.clamp_ip(pygame.Rect(0, 0, SCREEN_WIDTH, SCREEN_HEIGHT))

    def update(self, all_players_list):
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
        return sum(b.income for b in self.equipped_slots if b)

    # --- handle_interaction (MODIFICADA E CORRIGIDA) ---
    def handle_interaction(self, conveyor_bottles, all_players_list):
        global game_over
        if self.is_stunned or game_over: return

        others = [p for p in all_players_list if p and p != self]

        # 1. Guardar Garrafa (Se está carregando)
        if self.carrying_bottle:
            if self.rect.colliderect(self.base_rect):
                for i in range(3):
                    if self.equipped_slots[i] is None:
                        self.equipped_slots[i] = self.carrying_bottle
                        self.equipped_slots[i].owner_id = self.id
                        slot = self.equipped_slot_positions_data[i]
                        self.equipped_slots[i].rect.center = (slot[0] + slot[2] // 2, slot[1] + slot[3] // 2)
                        self.carrying_bottle = None
                        return  # Ação concluída
            return  # Se está carregando, não pode fazer mais nada

        # --- Se NÃO está carregando, checa todas as outras ações ---

        # 2. Recuperar Garrafa
        for other in others:
            if other.carrying_bottle and other.carrying_bottle.owner_id == self.id and self.rect.colliderect(
                    other.rect):
                for i in range(3):
                    if self.equipped_slots[i] is None:
                        self.equipped_slots[i] = other.carrying_bottle
                        slot = self.equipped_slot_positions_data[i]
                        self.equipped_slots[i].rect.center = (slot[0] + slot[2] // 2, slot[1] + slot[3] // 2)
                        other.carrying_bottle = None
                        return  # Ação concluída

        # 3. Ativar Escudo
        if self.rect.colliderect(self.shield_button_rect):
            if self.shield_cooldown <= 0:
                self.shield_active = True
                duration = self.base_shield_duration_frames + self.bonus_shield_duration_frames
                self.shield_timer = duration
                self.shield_cooldown = (duration // FPS + 10) * FPS
                print(f"{self.name} ativou escudo ({duration // FPS}s)!")
            else:
                print(f"{self.name} escudo em CD ({self.shield_cooldown // FPS}s)")
            return  # Ação (ou tentativa) concluída

        # 4. Vender Itens da Base
        if self.rect.colliderect(self.base_rect):
            for i, slot_data in enumerate(self.equipped_slot_positions_data):
                if self.equipped_slots[i] and self.rect.colliderect(pygame.Rect(slot_data)):
                    self.money += self.equipped_slots[i].value
                    self.equipped_slots[i] = None
                    return  # Ação concluída

        # 5. Comprar Troféu (NOVA LÓGICA)
        trophy_rect = pygame.Rect(TROPHY_SHOP_RECT_DATA)
        if self.rect.colliderect(trophy_rect):
            if self.money >= TROPHY_SHOP_COST:
                self.money -= TROPHY_SHOP_COST
                print(f"JOGADOR {self.name} COMPROU O ITEM DE VITÓRIA!")
                game_over = True
                calculate_final_ranking(self)  # Calcula o placar
            else:
                print(f"{self.name} sem dinheiro para o Troféu.")
            return  # Ação (ou tentativa) concluída

        # 6. Comprar Upgrades (LÓGICA CORRIGIDA)
        for name, info in WEAPON_SHOP_ITEMS_DATA.items():
            if self.rect.colliderect(pygame.Rect(info["rect"])):
                # Colidiu com um item. Processa e para.
                if self.money >= info["cost"]:
                    if info["type"] == "passive" and self.has_weapon.get(name, False):
                        print(f"{self.name} já tem {name}.")
                        return  # Já tem, para

                    self.money -= info["cost"]
                    if info["type"] == "passive":
                        self.has_weapon[name] = True
                        if name == "Bateria Extra": self.bonus_shield_duration_frames = 15 * FPS
                    elif info["type"] == "consumable":
                        self.consumables[name] += 1

                    print(f"{self.name} comprou {name}.")
                    return  # Sucesso, para
                else:
                    print(f"{self.name} sem dinheiro para {name}.")
                    return  # Sem dinheiro, para

        # 7. Comprar Packs (LÓGICA CORRIGIDA)
        for rarity, info in SHOP_PACKS_DATA.items():
            if self.rect.colliderect(pygame.Rect(info["rect"])):
                # Colidiu com um pack. Processa e para.
                if self.money >= info["cost"]:
                    for i in range(3):
                        if self.equipped_slots[i] is None:
                            self.money -= info["cost"]
                            new_bottle = create_bottle_by_rarity(rarity)
                            self.equipped_slots[i] = new_bottle;
                            new_bottle.owner_id = self.id
                            slot = self.equipped_slot_positions_data[i]
                            new_bottle.rect.center = (slot[0] + slot[2] // 2, slot[1] + slot[3] // 2)
                            print(f"{self.name} comprou Pack {rarity}.")
                            return  # Sucesso, para
                    print(f"{self.name} sem slots para Pack {rarity}.")
                    return  # Slots cheios, para
                else:
                    print(f"{self.name} sem dinheiro para Pack {rarity}.")
                    return  # Sem dinheiro, para

        # 8. Roubar (Lógica movida para antes da esteira, pois é na base)
        for other in others:
            if other.shield_active and self.rect.colliderect(other.base_rect):
                print(f"Tentou roubar {other.name}, mas escudo ativo.")
                return  # Escudo bloqueia, para
            if self.rect.colliderect(other.base_rect):
                for i, slot_data in enumerate(other.equipped_slot_positions_data):
                    if other.equipped_slots[i] and self.rect.colliderect(pygame.Rect(slot_data)):
                        self.carrying_bottle = other.equipped_slots[i]
                        other.equipped_slots[i] = None
                        print(f"{self.name} roubou de {other.name}!")
                        return  # Sucesso, para

        # 9. Comprar da esteira (LÓGICA CORRIGIDA)
        for bottle in conveyor_bottles:
            if self.rect.colliderect(bottle.rect):
                # Colidiu com garrafa. Processa e para.
                if self.money >= bottle.value:
                    for i in range(3):
                        if self.equipped_slots[i] is None:
                            self.money -= bottle.value
                            self.equipped_slots[i] = bottle
                            bottle.owner_id = self.id
                            slot = self.equipped_slot_positions_data[i]
                            bottle.rect.center = (slot[0] + slot[2] // 2, slot[1] + slot[3] // 2)
                            conveyor_bottles.remove(bottle)
                            print(f"{self.name} comprou {bottle.name} da esteira.")
                            return  # Sucesso, para
                    print(f"{self.name} sem slots para {bottle.name}.")
                    return  # Slots cheios, para
                else:
                    print(f"{self.name} sem dinheiro para {bottle.name}.")
                    return  # Sem dinheiro, para

    def use_orbital_ray(self, all_players_list):
        # (Não mudou)
        if self.is_stunned or self.consumables["Raio Orbital"] <= 0 or game_over: return
        self.consumables["Raio Orbital"] -= 1
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
                            owner.equipped_slots[i] = bottle
                            slot = owner.equipped_slot_positions_data[i]
                            bottle.rect.center = (slot[0] + slot[2] // 2, slot[1] + slot[3] // 2)
                            return


# --- Funções Auxiliares do Servidor ---
def create_bottle_by_rarity(rarity):
    # (Não mudou)
    template = random.choice([t for t in BOTTLE_TEMPLATES if t["rarity"] == rarity])
    return Bottle(template, random.random() < 0.1)


def spawn_bottle():
    # (Não mudou)
    rarity = random.choices(RARITIES, weights=RARITY_WEIGHTS, k=1)[0]
    bottle = create_bottle_by_rarity(rarity)
    rect = pygame.Rect(conveyor_rect_data)
    bottle.rect.topleft = (-bottle.rect.width, rect.y + (rect.height // 2 - bottle.rect.height // 2))
    return bottle


# --- Lógica de Rede (Não mudou) ---
input_queue = Queue();
output_queues = {};
client_connections = {};
clients_lock = threading.Lock()


def client_listener_thread(conn, player_id):
    # (Não mudou)
    print(f"[Thread-{player_id}] Listener iniciada.")
    while True:
        try:
            header = conn.recv(HEADER_LENGTH)
            if not header: break
            length = int(header.decode('utf-8').strip())
            data = b'';
            while len(data) < length:
                part = conn.recv(min(4096, length - len(data)))
                if not part: raise ConnectionError("C2S Disconnect")
                data += part
            input_queue.put((player_id, pickle.loads(data)))
        except (ConnectionResetError, ConnectionAbortedError, EOFError, ConnectionError, ValueError):
            break
        except Exception as e:
            print(f"[Erro Listener P{player_id}]: {e}"); break
    print(f"[Thread-{player_id}] Listener encerrada.");
    input_queue.put((player_id, "disconnect"))


def client_sender_thread(conn, player_id):
    # (Não mudou)
    print(f"[Thread-{player_id}] Sender iniciada.")
    q = output_queues[player_id]
    while True:
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
        client_connections.pop(player_id, None);
        output_queues.pop(player_id, None)
    conn.close()


# --- Estado Global e Lógica Principal ---
players = [None] * MAX_PLAYERS;
conveyor_bottles = [];
game_over = False;
final_ranking = []


def calculate_final_ranking(winner_player):
    # (Não mudou)
    global final_ranking, players
    winner = winner_player
    others = [p for p in players if p and p.id != winner.id]
    others_sorted = sorted(others, key=lambda p: p.money, reverse=True)
    final_ranking = [winner] + others_sorted


def game_logic_thread():
    # (Não mudou)
    global players, conveyor_bottles, game_over, final_ranking
    clock = pygame.time.Clock();
    spawn_timer = 0;
    money_timer = 0
    print("[GameLogic] Thread de lógica iniciada.")
    while True:
        # 1. Processar Inputs
        while not input_queue.empty():
            p_id, data = input_queue.get()
            if game_over and data != "disconnect": continue
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
        if not game_over:
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
                 "conveyor_bottles": [b.to_dict() for b in conveyor_bottles],
                 "game_over": game_over,
                 "final_ranking": [p.to_dict() for p in final_ranking if p]}
        with clients_lock:
            for q in output_queues.values(): q.put(state)
        # 4. FPS
        clock.tick(FPS)


# --- Loop Principal (Aceita conexões) ---
def main():
    # (Não mudou)
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.bind(("0.0.0.0", PORT));
        s.listen(MAX_PLAYERS)
        print(f"Servidor iniciado em 0.0.0.0:{PORT}...")
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
                conn.send(pickle.dumps(new_player_id))
                player_name_bytes = conn.recv(1024)
                player_name = pickle.loads(player_name_bytes)
                print(f"Nome recebido: {player_name}")
                start_x, start_y = player_start_pos[new_player_id]
                color = player_colors[new_player_id]
                base_data = player_base_rects_data[new_player_id]
                players[new_player_id] = Player(start_x, start_y, color, base_data, new_player_id, player_name)
                with clients_lock:
                    output_queues[new_player_id] = Queue();
                    client_connections[new_player_id] = conn
                threading.Thread(target=client_listener_thread, args=(conn, new_player_id), daemon=True).start()
                threading.Thread(target=client_sender_thread, args=(conn, new_player_id), daemon=True).start()
                print(f"Jogador {new_player_id + 1} ({player_name}) conectado.")
            except Exception as e:
                print(f"Erro ao inicializar jogador {new_player_id}: {e}"); conn.close()
        else:
            print("Servidor cheio."); conn.close()


if __name__ == "__main__":
    main()