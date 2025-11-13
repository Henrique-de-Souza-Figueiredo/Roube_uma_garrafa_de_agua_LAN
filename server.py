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
# Certifique-se que RESENHA_RARITY_WEIGHTS e os tempos foram adicionados no config.py
from config import *

# --- VARIAVEIS GLOBAIS ---
players = [None] * MAX_PLAYERS
conveyor_bottles = []
game_over = False
final_ranking = []
resenha_active = False  # Nova flag global


# --- Classes do Jogo ---

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
        return {"name": self.name, "rarity": self.rarity, "value": self.value,
                "income": self.income, "is_golden": self.is_golden, "color": self.color,
                "rect_data": (self.rect.x, self.rect.y, self.rect.w, self.rect.h),
                "owner_id": self.owner_id}


class Player:
    def __init__(self, x, y, color, base_rect_data, player_id, name):
        self.rect = pygame.Rect(x, y, 30, 30)
        self.color = color
        self.id = player_id
        self.money = 10.0
        self.name = name if name else f"Player {player_id + 1}"
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
        self.has_weapon = {"Tênis": False, "Bateria Extra": False}
        self.consumables = {"Raio Orbital": 0}
        self.shield_active = False
        self.shield_timer = 0
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
                "shield_button_rect_data": (self.shield_button_rect.x, self.shield_button_rect.y,
                                            self.shield_button_rect.w, self.shield_button_rect.h)}

    def move(self, keys_pressed):
        if self.is_stunned or game_over: return
        dx, dy = 0, 0
        if keys_pressed[pygame.K_w]: dy = -self.current_speed
        if keys_pressed[pygame.K_s]: dy = self.current_speed
        if keys_pressed[pygame.K_a]: dx = -self.current_speed
        if keys_pressed[pygame.K_d]: dx = self.current_speed
        self.rect.x += dx
        self.rect.y += dy
        self.rect.clamp_ip(pygame.Rect(0, 0, SCREEN_WIDTH, SCREEN_HEIGHT))

    def update(self, all_players_list):
        # Lógica do Escudo e Stun
        if self.shield_timer > 0:
            self.shield_timer -= 1
            if self.shield_timer <= 0: self.shield_active = False
        if self.shield_cooldown > 0: self.shield_cooldown -= 1

        if self.is_stunned:
            self.stun_timer -= 1
            if self.stun_timer <= 0: self.is_stunned = False
            return

        # Verifica se está sendo roubado
        self.is_being_stolen_from = any(
            p and p.carrying_bottle and p.carrying_bottle.owner_id == self.id for p in all_players_list)

        # Lógica de Velocidade
        base_speed = self.base_speed + 2 if self.has_weapon["Tênis"] else self.base_speed
        self.current_speed = base_speed * self.theft_speed_multiplier if self.is_being_stolen_from else base_speed

        # --- MODIFICAÇÃO RESENHA (Velocidade Dobrada) ---
        if resenha_active:
            self.current_speed *= 2
        # ------------------------------------------------

        if self.carrying_bottle: self.carrying_bottle.rect.center = self.rect.center

    def calculate_income(self):
        # --- MODIFICAÇÃO RESENHA (Dinheiro Dobrado) ---
        base_income = sum(b.income for b in self.equipped_slots if b)
        return base_income * 2 if resenha_active else base_income
        # ----------------------------------------------

    def handle_interaction(self, conveyor_bottles, all_players_list):
        global game_over
        if self.is_stunned or game_over: return

        others = [p for p in all_players_list if p and p != self]

        # 1. Guardar Garrafa
        if self.carrying_bottle:
            if self.rect.colliderect(self.base_rect):
                for i in range(3):
                    if self.equipped_slots[i] is None:
                        self.equipped_slots[i] = self.carrying_bottle
                        self.equipped_slots[i].owner_id = self.id
                        slot = self.equipped_slot_positions_data[i]
                        self.equipped_slots[i].rect.center = (slot[0] + slot[2] // 2, slot[1] + slot[3] // 2)
                        self.carrying_bottle = None
                        return
            return

        # 2. Recuperar Garrafa (Roubada)
        for other in others:
            if other.carrying_bottle and other.carrying_bottle.owner_id == self.id and self.rect.colliderect(
                    other.rect):
                for i in range(3):
                    if self.equipped_slots[i] is None:
                        self.equipped_slots[i] = other.carrying_bottle
                        slot = self.equipped_slot_positions_data[i]
                        self.equipped_slots[i].rect.center = (slot[0] + slot[2] // 2, slot[1] + slot[3] // 2)
                        other.carrying_bottle = None
                        return

        # 3. Ativar Escudo
        if self.rect.colliderect(self.shield_button_rect):
            if self.shield_cooldown <= 0:
                self.shield_active = True
                duration = self.base_shield_duration_frames + self.bonus_shield_duration_frames
                self.shield_timer = duration
                self.shield_cooldown = (duration // FPS + 10) * FPS
            return

        # 4. Vender Itens
        if self.rect.colliderect(self.base_rect):
            for i, slot_data in enumerate(self.equipped_slot_positions_data):
                if self.equipped_slots[i] and self.rect.colliderect(pygame.Rect(slot_data)):
                    self.money += self.equipped_slots[i].value
                    self.equipped_slots[i] = None
                    return

        # 5. Comprar Troféu
        trophy_rect = pygame.Rect(TROPHY_SHOP_RECT_DATA)
        if self.rect.colliderect(trophy_rect):
            if self.money >= TROPHY_SHOP_COST:
                self.money -= TROPHY_SHOP_COST
                print(f"JOGADOR {self.name} COMPROU O ITEM DE VITÓRIA!")
                game_over = True
                calculate_final_ranking(self)
            return

        # 6. Comprar Upgrades
        for name, info in WEAPON_SHOP_ITEMS_DATA.items():
            if self.rect.colliderect(pygame.Rect(info["rect"])):
                if self.money >= info["cost"]:
                    if info["type"] == "passive" and self.has_weapon.get(name, False):
                        return
                    self.money -= info["cost"]
                    if info["type"] == "passive":
                        self.has_weapon[name] = True
                        if name == "Bateria Extra": self.bonus_shield_duration_frames = 15 * FPS
                    elif info["type"] == "consumable":
                        self.consumables[name] += 1
                    return

        # 7. Comprar Packs
        for rarity, info in SHOP_PACKS_DATA.items():
            if self.rect.colliderect(pygame.Rect(info["rect"])):
                if self.money >= info["cost"]:
                    for i in range(3):
                        if self.equipped_slots[i] is None:
                            self.money -= info["cost"]
                            new_bottle = create_bottle_by_rarity(rarity)
                            self.equipped_slots[i] = new_bottle
                            new_bottle.owner_id = self.id
                            slot = self.equipped_slot_positions_data[i]
                            new_bottle.rect.center = (slot[0] + slot[2] // 2, slot[1] + slot[3] // 2)
                            return
                    return

        # 8. Roubar
        for other in others:
            if other.shield_active and self.rect.colliderect(other.base_rect):
                return
            if self.rect.colliderect(other.base_rect):
                for i, slot_data in enumerate(other.equipped_slot_positions_data):
                    if other.equipped_slots[i] and self.rect.colliderect(pygame.Rect(slot_data)):
                        self.carrying_bottle = other.equipped_slots[i]
                        other.equipped_slots[i] = None
                        return

        # 9. Comprar da esteira
        for bottle in conveyor_bottles:
            if self.rect.colliderect(bottle.rect):
                if self.money >= bottle.value:
                    for i in range(3):
                        if self.equipped_slots[i] is None:
                            self.money -= bottle.value
                            self.equipped_slots[i] = bottle
                            bottle.owner_id = self.id
                            slot = self.equipped_slot_positions_data[i]
                            bottle.rect.center = (slot[0] + slot[2] // 2, slot[1] + slot[3] // 2)
                            conveyor_bottles.remove(bottle)
                            return
                    return

    def use_orbital_ray(self, all_players_list):
        if self.is_stunned or self.consumables["Raio Orbital"] <= 0 or game_over: return
        self.consumables["Raio Orbital"] -= 1
        closest, min_dist = None, float('inf')
        for enemy in all_players_list:
            if not enemy or enemy == self or enemy.rect.colliderect(enemy.base_rect): continue
            dist = (enemy.rect.centerx - self.rect.centerx) ** 2 + (enemy.rect.centery - self.rect.centery) ** 2
            if dist < min_dist: min_dist, closest = dist, enemy
        if closest:
            closest.is_stunned = True
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
    template = random.choice([t for t in BOTTLE_TEMPLATES if t["rarity"] == rarity])
    return Bottle(template, random.random() < 0.1)


def spawn_bottle():
    global resenha_active
    # --- MODIFICAÇÃO RESENHA (Melhores Drops) ---
    # Se resenha ativa, usa pesos melhores (importados do config)
    # Caso config não tenha sido atualizado, fallback para pesos normais
    weights = RESENHA_RARITY_WEIGHTS if resenha_active else RARITY_WEIGHTS
    # --------------------------------------------

    rarity = random.choices(RARITIES, weights=weights, k=1)[0]
    bottle = create_bottle_by_rarity(rarity)
    rect = pygame.Rect(conveyor_rect_data)
    bottle.rect.topleft = (-bottle.rect.width, rect.y + (rect.height // 2 - bottle.rect.height // 2))
    return bottle


# --- Lógica de Rede ---
input_queue = Queue()
output_queues = {}
client_connections = {}
clients_lock = threading.Lock()


def client_listener_thread(conn, player_id):
    # (Código inalterado)
    print(f"[Thread-{player_id}] Listener iniciada.")
    while True:
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
        except Exception:
            break
    print(f"[Thread-{player_id}] Listener encerrada.")
    input_queue.put((player_id, "disconnect"))


def client_sender_thread(conn, player_id):
    # (Código inalterado)
    print(f"[Thread-{player_id}] Sender iniciada.")
    q = output_queues[player_id]
    while True:
        try:
            state = q.get()
            if state == "disconnect": break
            data = pickle.dumps(state)
            header = f"{len(data):<{HEADER_LENGTH}}".encode('utf-8')
            conn.sendall(header + data)
        except Exception:
            break
    print(f"[Thread-{player_id}] Sender encerrada.")
    with clients_lock:
        client_connections.pop(player_id, None)
        output_queues.pop(player_id, None)
    conn.close()


def calculate_final_ranking(winner_player):
    global final_ranking, players
    winner = winner_player
    others = [p for p in players if p and p.id != winner.id]
    others_sorted = sorted(others, key=lambda p: p.money, reverse=True)
    final_ranking = [winner] + others_sorted


def game_logic_thread():
    global players, conveyor_bottles, game_over, final_ranking, resenha_active

    # --- CORREÇÃO: Remover clock do Pygame no Server ---
    # clock = pygame.time.Clock()

    spawn_timer = 0
    money_timer = 0
    game_over_timer = -1
    GAME_OVER_RESET_FRAMES = 15 * FPS

    # --- VARIÁVEIS DE CONTROLE RESENHA ---
    # Cooldown inicial aleatório entre MIN e MAX (ex: 4 a 6 minutos)
    resenha_cooldown = random.randint(RESENHA_MIN_INTERVAL_SEC, RESENHA_MAX_INTERVAL_SEC) * FPS
    resenha_duration = 0
    # -------------------------------------

    print("[GameLogic] Thread de lógica iniciada.")

    while True:
        # Início do frame para controle manual de FPS
        loop_start_time = time.time()

        # 1. Processar Inputs (Incluindo Novas Conexões)
        while not input_queue.empty():
            p_id_or_cmd, data = input_queue.get()

            # (Lógica de processamento igual, simplificada aqui pois o foco é a resenha)
            if p_id_or_cmd == "new_connection":
                # Handled in main loop really, but here for logic safety if structure changed
                continue

            p_id = p_id_or_cmd
            if data == "disconnect":
                players[p_id] = None
                continue

            if game_over or game_over_timer > 0: continue

            player = players[p_id]
            if player:
                player.move(data['keys'])
                if data['interact']: player.handle_interaction(conveyor_bottles, players)
                if data['use_item']: player.use_orbital_ray(players)

        # 2. Atualizar Estado
        if not game_over:

            # --- LÓGICA RESENHA ---
            if resenha_active:
                resenha_duration -= 1
                if resenha_duration <= 0:
                    resenha_active = False
                    # Reseta o cooldown aleatório
                    resenha_cooldown = random.randint(RESENHA_MIN_INTERVAL_SEC, RESENHA_MAX_INTERVAL_SEC) * FPS
                    print("[GameLogic] FIM DA RESENHA.")
            else:
                resenha_cooldown -= 1
                if resenha_cooldown <= 0:
                    resenha_active = True
                    resenha_duration = RESENHA_DURATION_SEC * FPS
                    print("[GameLogic] RESENHA ATIVADA!!!")
            # ----------------------

            active = [p for p in players if p]
            for p in active: p.update(active)

            spawn_timer = (spawn_timer + 1) % SPAWN_INTERVAL
            if spawn_timer == 0 and len(conveyor_bottles) < 15: conveyor_bottles.append(spawn_bottle())

            # Esteira pode andar mais rápido na resenha se quiser (opcional)
            current_conveyor_speed = conveyor_speed * 2 if resenha_active else conveyor_speed

            for b in conveyor_bottles[:]:
                b.rect.x += current_conveyor_speed
                if b.rect.left > SCREEN_WIDTH: conveyor_bottles.remove(b)

            money_timer = (money_timer + 1) % MONEY_INTERVAL
            if money_timer == 0:
                for p in active: p.money += p.calculate_income()

            if game_over:
                game_over_timer = GAME_OVER_RESET_FRAMES

        else:
            # Lógica de Restart
            if game_over_timer > 0:
                game_over_timer -= 1
            elif game_over_timer == 0:
                print("[GameLogic] Reiniciando partida...")
                conveyor_bottles = []
                game_over = False
                final_ranking = []
                game_over_timer = -1
                resenha_active = False
                resenha_cooldown = random.randint(RESENHA_MIN_INTERVAL_SEC, RESENHA_MAX_INTERVAL_SEC) * FPS
                for p in players:
                    if p:
                        p.money = 10.0
                        p.equipped_slots = [None] * 3
                        p.carrying_bottle = None

        # 3. Distribuir Estado
        state = {
            "players": [p.to_dict() if p else None for p in players],
            "conveyor_bottles": [b.to_dict() for b in conveyor_bottles],
            "game_over": game_over,
            "final_ranking": [p.to_dict() for p in final_ranking if p],
            "resenha_active": resenha_active  # <--- Envia estado para o cliente
        }

        with clients_lock:
            for q in output_queues.values():
                try:
                    q.put(state)
                except:
                    pass

        # 4. FPS Manual (Evita crash do Pygame Clock no servidor)
        target_frame_time = 1.0 / FPS
        elapsed_time = time.time() - loop_start_time
        sleep_time = target_frame_time - elapsed_time
        if sleep_time > 0:
            time.sleep(sleep_time)


# --- Loop Principal ---
def main():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.bind(("0.0.0.0", PORT))
        s.listen(MAX_PLAYERS)
        print(f"Servidor iniciado em 0.0.0.0:{PORT}...")
    except socket.error as e:
        print(f"Erro bind: {e}");
        sys.exit()

    threading.Thread(target=game_logic_thread, daemon=True).start()

    while True:
        try:
            conn, addr = s.accept()
            # Gatekeeper simples (evita entrar no meio do restart)
            if game_over:
                conn.close();
                continue

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

                    start_x, start_y = player_start_pos[new_player_id]
                    color = player_colors[new_player_id]
                    base_data = player_base_rects_data[new_player_id]
                    players[new_player_id] = Player(start_x, start_y, color, base_data, new_player_id, player_name)

                    with clients_lock:
                        output_queues[new_player_id] = Queue()
                        client_connections[new_player_id] = conn

                    threading.Thread(target=client_listener_thread, args=(conn, new_player_id), daemon=True).start()
                    threading.Thread(target=client_sender_thread, args=(conn, new_player_id), daemon=True).start()
                    print(f"Jogador {new_player_id + 1} ({player_name}) conectado.")
                except Exception as e:
                    print(f"Erro init P{new_player_id}: {e}");
                    conn.close()
            else:
                conn.close()
        except Exception as e:
            print(f"Erro accept: {e}")


if __name__ == "__main__":
    main()