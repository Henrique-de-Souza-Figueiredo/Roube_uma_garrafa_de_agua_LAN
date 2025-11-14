import socket
import threading
import pickle
import random
import sys
import time
import pygame
from queue import Queue
from config import *

# --- VARIAVEIS GLOBAIS ---
players = [None] * MAX_PLAYERS
conveyor_bottles = []
game_over = False
final_ranking = []
resenha_active = False
server_running = False

active_event = None  # (WASSUUUP, etc)
event_duration = 0  # Timer do evento


# --- Classes do Jogo (Bottle e Player) ---
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

        self.type = "normal"
        if self.rarity == "Bomba":
            self.type = "bomb"
            self.explode_timer = 0
        elif self.rarity == "Misteriosa":
            self.type = "mystery"
            possible = [t for t in BOTTLE_TEMPLATES if t["rarity"] in ["Colecionável", "Premium", "Antiga", "Artefato"]]
            self.real_template = random.choice(possible) if possible else BOTTLE_TEMPLATES[0]

    def update(self):
        if self.type == "bomb" and self.explode_timer > 0:
            self.explode_timer -= 1

    def to_dict(self):
        return {
            "name": self.name, "rarity": self.rarity, "value": self.value, "income": self.income,
            "is_golden": self.is_golden, "color": self.color,
            "rect_data": (self.rect.x, self.rect.y, self.rect.w, self.rect.h),
            "owner_id": self.owner_id, "type": self.type,
            "explode_timer": getattr(self, "explode_timer", 0)
        }


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
        self.last_tax_amount = 0
        self.tax_visual_timer = 0

        # NOVO: Controle do WASSUP
        self.controls_reversed = False
        self.phone_rect = pygame.Rect(self.base_rect.x + 30, self.base_rect.y + 5, 20, 20)  # Posição do telefone

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
                "is_stunned": self.is_stunned, "carrying_bottle_data": carrying, "equipped_slots_data": equipped,
                "equipped_slot_positions_data": self.equipped_slot_positions_data, "has_weapon": self.has_weapon,
                "consumables": self.consumables, "shield_active": self.shield_active,
                "shield_timer_frames": self.shield_timer, "shield_cooldown_frames": self.shield_cooldown,
                "shield_button_rect_data": (
                self.shield_button_rect.x, self.shield_button_rect.y, self.shield_button_rect.w,
                self.shield_button_rect.h),
                "last_tax_amount": self.last_tax_amount,
                "tax_visual_timer": self.tax_visual_timer,
                "controls_reversed": self.controls_reversed,  # Envia estado dos controles
                "phone_rect_data": (self.phone_rect.x, self.phone_rect.y, self.phone_rect.w, self.phone_rect.h)
                # Envia pos do telefone
                }

    def move(self, keys_pressed):
        if self.is_stunned or game_over: return

        dx, dy = 0, 0

        # --- LÓGICA WASSUUUP (Controles Invertidos) ---
        if self.controls_reversed:
            if keys_pressed[pygame.K_w]: dy = self.current_speed  # Invertido
            if keys_pressed[pygame.K_s]: dy = -self.current_speed  # Invertido
            if keys_pressed[pygame.K_a]: dx = self.current_speed  # Invertido
            if keys_pressed[pygame.K_d]: dx = -self.current_speed  # Invertido
        else:
            if keys_pressed[pygame.K_w]: dy = -self.current_speed
            if keys_pressed[pygame.K_s]: dy = self.current_speed
            if keys_pressed[pygame.K_a]: dx = -self.current_speed
            if keys_pressed[pygame.K_d]: dx = self.current_speed

        self.rect.x += dx
        self.rect.y += dy
        self.rect.clamp_ip(pygame.Rect(0, 0, SCREEN_WIDTH, SCREEN_HEIGHT))

    def update(self, all_players_list):
        if self.shield_timer > 0: self.shield_timer -= 1
        if self.shield_cooldown > 0: self.shield_cooldown -= 1
        if self.tax_visual_timer > 0: self.tax_visual_timer -= 1

        if self.is_stunned:
            self.stun_timer -= 1
            if self.stun_timer <= 0: self.is_stunned = False
            return

        if self.carrying_bottle and self.carrying_bottle.type == "bomb":
            self.carrying_bottle.update()
            if self.carrying_bottle.explode_timer <= 0:
                self.is_stunned = True
                self.stun_timer = 5 * FPS
                self.carrying_bottle = None
                slots_cheios = [i for i, slot in enumerate(self.equipped_slots) if slot]
                if slots_cheios:
                    self.equipped_slots[random.choice(slots_cheios)] = None

        self.is_being_stolen_from = any(
            p and p.carrying_bottle and p.carrying_bottle.owner_id == self.id for p in all_players_list)
        base_speed = self.base_speed + 2 if self.has_weapon["Tênis"] else self.base_speed
        self.current_speed = base_speed * self.theft_speed_multiplier if self.is_being_stolen_from else base_speed
        if resenha_active: self.current_speed *= 2

        if self.carrying_bottle: self.carrying_bottle.rect.center = self.rect.center

    def calculate_income(self):
        base_income = sum(b.income for b in self.equipped_slots if b)
        return base_income * 2 if resenha_active else base_income

    def handle_interaction(self, conveyor_bottles, all_players_list):
        global game_over, active_event
        if self.is_stunned or game_over: return

        others = [p for p in all_players_list if p and p != self]

        # --- 1. LÓGICA DO TELEFONE (WASSUUUP) ---
        if active_event == "WASSUUUP" and self.controls_reversed:
            if self.rect.colliderect(self.phone_rect):
                self.controls_reversed = False  # Cura
                print(f"{self.name} atendeu o WASSUUUP!")
                return  # Ação de atender o telefone

        # --- 2. LÓGICA DA BATATA QUENTE ---
        if self.carrying_bottle and self.carrying_bottle.type == "bomb":
            for other in others:
                if self.rect.colliderect(other.rect) and not other.is_stunned and not other.shield_active:
                    other_bottle = other.carrying_bottle
                    other.carrying_bottle = self.carrying_bottle
                    self.carrying_bottle = other_bottle
                    if self.carrying_bottle and self.carrying_bottle.type == "bomb" and self.carrying_bottle.explode_timer == 0:
                        self.carrying_bottle.explode_timer = 10 * FPS
                    return
            return  # Não pode guardar bomba

        # --- 3. Guardar Garrafa (Normal ou Mistério) ---
        if self.carrying_bottle:
            if self.rect.colliderect(self.base_rect):
                if self.carrying_bottle.type == "mystery":
                    template = self.carrying_bottle.real_template
                    is_gold = self.carrying_bottle.is_golden
                    self.carrying_bottle = Bottle(template, is_gold)
                    self.carrying_bottle.owner_id = self.id

                for i in range(3):
                    if self.equipped_slots[i] is None:
                        self.equipped_slots[i] = self.carrying_bottle
                        self.equipped_slots[i].owner_id = self.id
                        slot = self.equipped_slot_positions_data[i]
                        self.equipped_slots[i].rect.center = (slot[0] + slot[2] // 2, slot[1] + slot[3] // 2)
                        self.carrying_bottle = None
                        return
            return

            # --- 4. Interações (Mão Vazia) ---
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

        if self.rect.colliderect(self.shield_button_rect):
            if self.shield_cooldown <= 0:
                self.shield_active = True
                duration = self.base_shield_duration_frames + self.bonus_shield_duration_frames
                self.shield_timer = duration
                self.shield_cooldown = (duration // FPS + 10) * FPS
            return

        if self.rect.colliderect(self.base_rect):
            for i, slot_data in enumerate(self.equipped_slot_positions_data):
                if self.equipped_slots[i] and self.rect.colliderect(pygame.Rect(slot_data)):
                    self.money += self.equipped_slots[i].value
                    self.equipped_slots[i] = None
                    return

        trophy_rect = pygame.Rect(TROPHY_SHOP_RECT_DATA)
        if self.rect.colliderect(trophy_rect):
            if self.money >= TROPHY_SHOP_COST:
                self.money -= TROPHY_SHOP_COST
                game_over = True
                calculate_final_ranking(self)
            return

        for name, info in WEAPON_SHOP_ITEMS_DATA.items():
            if self.rect.colliderect(pygame.Rect(info["rect"])):
                if self.money >= info["cost"]:
                    if info["type"] == "passive" and self.has_weapon.get(name, False): return
                    self.money -= info["cost"]
                    if info["type"] == "passive":
                        self.has_weapon[name] = True
                        if name == "Bateria Extra": self.bonus_shield_duration_frames = 15 * FPS
                    elif info["type"] == "consumable":
                        self.consumables[name] += 1
                    return
                else:
                    return

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
                else:
                    return

        for other in others:
            if other.shield_active and self.rect.colliderect(other.base_rect): return
            if self.rect.colliderect(other.base_rect):
                for i, slot_data in enumerate(other.equipped_slot_positions_data):
                    if other.equipped_slots[i] and self.rect.colliderect(pygame.Rect(slot_data)):
                        self.carrying_bottle = other.equipped_slots[i]
                        other.equipped_slots[i] = None
                        if self.carrying_bottle.type == "bomb":
                            self.carrying_bottle.explode_timer = 10 * FPS
                        return

        for bottle in conveyor_bottles:
            if self.rect.colliderect(bottle.rect):
                is_special = bottle.rarity in ["Bomba", "Misteriosa"]
                if is_special and self.carrying_bottle is None:
                    if self.money >= bottle.value:
                        self.money -= bottle.value
                        self.carrying_bottle = bottle
                        bottle.owner_id = self.id
                        if bottle.type == "bomb":
                            bottle.explode_timer = 10 * FPS
                        conveyor_bottles.remove(bottle)
                        return
                    else:
                        return

                if self.money >= bottle.value and not is_special:
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


def create_bottle_by_rarity(rarity):
    possible_templates = [t for t in BOTTLE_TEMPLATES if t["rarity"] == rarity]
    if not possible_templates:
        template = BOTTLE_TEMPLATES[0]
    else:
        template = random.choice(possible_templates)
    return Bottle(template, random.random() < 0.1)


def spawn_bottle():
    global resenha_active
    weights = RESENHA_RARITY_WEIGHTS if resenha_active else RARITY_WEIGHTS

    rarity_list = RARITIES
    if len(rarity_list) != len(weights):
        print(f"ERRO: Config! {len(rarity_list)} raridades, {len(weights)} pesos.")
        weights = weights[:len(rarity_list)]
        if len(rarity_list) > len(weights):
            weights.extend([1] * (len(rarity_list) - len(weights)))

    rarity = random.choices(rarity_list, weights=weights, k=1)[0]

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
    while True:
        try:
            header = conn.recv(HEADER_LENGTH)
            if not header: break
            length = int(header.decode('utf-8').strip())
            data = b''
            while len(data) < length:
                part = conn.recv(min(4096, length - len(data)))
                if not part: raise ConnectionError
                data += part
            input_queue.put((player_id, pickle.loads(data)))
        except:
            break
    input_queue.put((player_id, "disconnect"))


def client_sender_thread(conn, player_id):
    try:
        q = output_queues[player_id]
        while True:
            try:
                state = q.get()
                if state == "disconnect": break
                data = pickle.dumps(state)
                header = f"{len(data):<{HEADER_LENGTH}}".encode('utf-8')
                conn.sendall(header + data)
            except:
                break
    except KeyError:
        pass

    with clients_lock:
        client_connections.pop(player_id, None)
        output_queues.pop(player_id, None)
    try:
        conn.close()
    except:
        pass


def calculate_final_ranking(winner_player):
    global final_ranking, players
    winner = winner_player
    others = [p for p in players if p and p.id != winner.id]
    others_sorted = sorted(others, key=lambda p: p.money, reverse=True)
    final_ranking = [winner] + others_sorted


def game_logic_thread():
    global players, conveyor_bottles, game_over, final_ranking, resenha_active, server_running
    global active_event, event_duration

    spawn_timer = 0
    money_timer = 0
    tax_timer = 0
    game_over_timer = -1

    resenha_cooldown = random.randint(RESENHA_MIN_INTERVAL_SEC, RESENHA_MAX_INTERVAL_SEC) * FPS
    resenha_duration = 0

    event_cooldown = EVENT_INTERVAL_FRAMES
    event_duration = 0

    print("[ServerLogic] Loop iniciado.")
    while server_running:
        loop_start_time = time.time()

        while not input_queue.empty():
            p_id_or_cmd, data = input_queue.get()
            if p_id_or_cmd == "new_connection": continue
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

        if not game_over:

            # --- LÓGICA DE EVENTOS (WASSUUUP) ---
            if active_event:
                event_duration -= 1
                if event_duration <= 0:
                    active_event = None
                    event_cooldown = EVENT_INTERVAL_FRAMES
                    # Reseta controles de quem não atendeu
                    for p in players:
                        if p: p.controls_reversed = False
                    print("[Evento] Evento finalizado.")
            elif not resenha_active:  # Não ativa evento durante resenha
                event_cooldown -= 1
                if event_cooldown <= 0:
                    active_event = random.choice(EVENT_TYPES)
                    event_duration = EVENT_DURATION_FRAMES
                    print(f"[Evento] {active_event} ativado!")

                    if active_event == "WASSUUUP":
                        for p in players:
                            if p: p.controls_reversed = True

            # Lógica da Resenha
            if resenha_active:
                resenha_duration -= 1
                if resenha_duration <= 0:
                    resenha_active = False
                    resenha_cooldown = random.randint(RESENHA_MIN_INTERVAL_SEC, RESENHA_MAX_INTERVAL_SEC) * FPS
            elif not active_event:  # Não conta timer da resenha durante outro evento
                resenha_cooldown -= 1
                if resenha_cooldown <= 0:
                    resenha_active = True
                    resenha_duration = RESENHA_DURATION_SEC * FPS

            active = [p for p in players if p]
            for p in active: p.update(active)

            spawn_timer = (spawn_timer + 1) % SPAWN_INTERVAL
            if spawn_timer == 0 and len(conveyor_bottles) < 15: conveyor_bottles.append(spawn_bottle())

            current_conveyor_speed = conveyor_speed * 2 if resenha_active else conveyor_speed
            for b in conveyor_bottles[:]:
                b.rect.x += current_conveyor_speed
                if b.rect.left > SCREEN_WIDTH: conveyor_bottles.remove(b)

            money_timer = (money_timer + 1) % MONEY_INTERVAL
            if money_timer == 0:
                for p in active: p.money += p.calculate_income()

            tax_timer += 1
            if tax_timer >= TAX_INTERVAL:
                tax_timer = 0
                for p in active:
                    if p.money > TAX_MIN_THRESHOLD:
                        tax_amount = p.money * TAX_RATE
                        p.money -= tax_amount
                        p.last_tax_amount = tax_amount
                        p.tax_visual_timer = FPS * 3

            if game_over: game_over_timer = 15 * FPS

        else:
            if game_over_timer > 0:
                game_over_timer -= 1
            elif game_over_timer == 0:
                conveyor_bottles = []
                game_over = False
                final_ranking = []
                game_over_timer = -1
                resenha_active = False
                active_event = None
                tax_timer = 0
                for p in players:
                    if p:
                        p.money = 10.0
                        p.equipped_slots = [None] * 3
                        p.carrying_bottle = None
                        p.last_tax_amount = 0

        state = {
            "players": [p.to_dict() if p else None for p in players],
            "conveyor_bottles": [b.to_dict() for b in conveyor_bottles],
            "game_over": game_over,
            "final_ranking": [p.to_dict() for p in final_ranking if p],
            "resenha_active": resenha_active,
            "active_event": active_event
        }

        with clients_lock:
            for q in output_queues.values():
                try:
                    q.put(state)
                except:
                    pass

        elapsed_time = time.time() - loop_start_time
        sleep_duration = (1.0 / FPS) - elapsed_time
        if sleep_duration > 0:
            time.sleep(sleep_duration)


def start_server_logic():
    global server_running
    server_running = True

    ip = get_local_ip()
    code = ip_to_code(ip)
    print(f"--- SERVIDOR INICIADO ---")
    print(f"IP Local: {ip}")
    print(f"CÓDIGO DA SALA: {code}")
    print(f"-------------------------")

    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.bind(("0.0.0.0", PORT))
        s.listen(MAX_PLAYERS)
    except socket.error as e:
        print(f"Erro bind: {e}")
        return

    threading.Thread(target=game_logic_thread, daemon=True).start()

    while server_running:
        try:
            conn, addr = s.accept()
            if game_over:
                conn.close()
                continue

            new_player_id = -1
            with clients_lock:
                for i in range(MAX_PLAYERS):
                    if players[i] is None and i not in client_connections:
                        new_player_id = i
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
                except:
                    conn.close()
            else:
                conn.close()
        except:
            pass


if __name__ == "__main__":
    start_server_logic()