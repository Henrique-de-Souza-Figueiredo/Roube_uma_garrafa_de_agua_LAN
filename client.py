import pygame
import sys
import pickle
import random
import threading
from network import Network
from config import *

# Tenta importar o servidor para o modo Host
try:
    import server

    HAS_SERVER_FILE = True
except ImportError:
    HAS_SERVER_FILE = False
    print("Aviso: 'server.py' não encontrado. Modo 'Criar Partida' desativado.")

# --- Inicialização ---
pygame.init()
pygame.font.init()
pygame.key.set_repeat(500, 30)  # Permite segurar backspace

screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
pygame.display.set_caption("Guerra das Garrafas - Cliente")
clock = pygame.time.Clock()

# Fontes
font = pygame.font.SysFont(None, 48)
small_font = pygame.font.SysFont(None, 24)
price_font = pygame.font.SysFont(None, 18)
title_font = pygame.font.SysFont(None, 72)
resenha_font = pygame.font.SysFont(None, 100, bold=True)

# Estado do Menu: 0=Menu, 1=Nome, 2=EntrarCodigo, 3=Jogo
game_mode_state = 0
player_name_input = ""
code_input = ""
connection_status = ""  # Feedback para o usuário
is_host = False
my_lan_code = ""

last_resenha_pos_change = 0
current_resenha_pos = (0, 0)


# --- Componentes de UI ---
class Button:
    def __init__(self, text, x, y, w, h, color, text_color=WHITE):
        self.rect = pygame.Rect(x, y, w, h)
        self.text = text
        self.color = color
        self.text_color = text_color

    def draw(self, surf):
        pygame.draw.rect(surf, self.color, self.rect)
        pygame.draw.rect(surf, WHITE, self.rect, 2)
        txt_surf = font.render(self.text, True, self.text_color)
        surf.blit(txt_surf, txt_surf.get_rect(center=self.rect.center))

    def is_clicked(self, pos):
        return self.rect.collidepoint(pos)


def draw_text_centered(surf, text, y, f=font, color=WHITE):
    txt = f.render(text, True, color)
    surf.blit(txt, txt.get_rect(center=(SCREEN_WIDTH // 2, y)))


# --- Funções de Desenho do Jogo ---

def draw_bottle(surface, bottle_data):
    if not bottle_data: return
    rect = pygame.Rect(bottle_data["rect_data"])
    color = bottle_data["color"]

    pygame.draw.rect(surface, color, rect)

    if bottle_data["is_golden"]:
        pygame.draw.rect(surface, GOLD, rect, 3)

    # --- NOVO: Visual do Caos ---
    b_type = bottle_data.get("type", "normal")

    if b_type == "bomb":
        # Pisca em vermelho
        if (pygame.time.get_ticks() // 200) % 2 == 0:
            pygame.draw.rect(surface, RED, rect, 3)

        # Mostra o timer
        timer_sec = bottle_data.get("explode_timer", 0) // FPS
        if timer_sec > 0:
            timer_surf = font.render(str(timer_sec), True, RED)
            surface.blit(timer_surf, timer_surf.get_rect(center=rect.center))

    elif b_type == "mystery":
        # Mostra "?" piscando
        if (pygame.time.get_ticks() // 300) % 2 == 0:
            q_surf = font.render("?", True, WHITE)
            surface.blit(q_surf, q_surf.get_rect(center=rect.center))


def draw_player(surface, player_data):
    if not player_data: return
    rect = pygame.Rect(player_data["rect_data"])
    color = player_data["color"]
    pygame.draw.rect(surface, color, rect)

    if player_data["carrying_bottle_data"]:
        b_data = player_data["carrying_bottle_data"]
        b_rect = pygame.Rect(b_data["rect_data"])
        b_rect.center = rect.center
        temp_b_data = b_data.copy()
        temp_b_data["rect_data"] = (b_rect.x, b_rect.y, b_rect.w, b_rect.h)
        draw_bottle(surface, temp_b_data)  # Desenha garrafa (com lógica da bomba)

    if player_data["is_stunned"]:
        stun = small_font.render("STUNNED", True, YELLOW)
        surface.blit(stun, stun.get_rect(center=(rect.centerx, rect.top - 10)))

    if player_data.get("tax_visual_timer", 0) > 0:
        tax_amount = player_data.get("last_tax_amount", 0)
        msg = small_font.render(f"-${tax_amount:.0f} IMPOSTO!", True, RED)
        offset_y = (FPS * 3 - player_data["tax_visual_timer"]) * 0.5
        surface.blit(msg, msg.get_rect(center=(rect.centerx, rect.top - 25 - offset_y)))


def draw_base(surface, player_data):
    if not player_data: return
    base_rect = pygame.Rect(player_data["base_rect_data"])
    color = player_data["color"]
    pygame.draw.rect(surface, color, base_rect, 3)

    button_rect = pygame.Rect(player_data["shield_button_rect_data"])
    cooldown = player_data["shield_cooldown_frames"]
    btn_color = GREEN if cooldown <= 0 else RED
    pygame.draw.rect(surface, btn_color, button_rect)
    pygame.draw.rect(surface, WHITE, button_rect, 1)

    if player_data["shield_active"]:
        shield_surf = pygame.Surface(base_rect.size, pygame.SRCALPHA)
        alpha = 100 + (player_data['shield_timer_frames'] % 15) * 2
        shield_surf.fill((*SHIELD_BLUE, alpha))
        surface.blit(shield_surf, base_rect.topleft)

    for slot_data in player_data["equipped_slot_positions_data"]:
        pygame.draw.rect(surface, (50, 50, 50), pygame.Rect(slot_data))
    for bottle_data in player_data["equipped_slots_data"]:
        draw_bottle(surface, bottle_data)


def draw_tooltip(surface, bottle_data, mouse_pos):
    # CORRIGIDO: Proteção contra KeyError se a raridade não estiver no dict
    color = RARITY_COLORS.get(bottle_data["rarity"], WHITE)
    gold = " (Dourada)" if bottle_data.get("is_golden", False) else ""

    # CORRIGIDO: Usa fonte pequena
    lines = [
        (f"{bottle_data['name']}{gold}", color),
        (f"Raridade: {bottle_data['rarity']}", WHITE),
        (f"Valor: ${bottle_data['value']:.2f}", YELLOW),
        (f"Renda: ${bottle_data['income']:.2f}/s", GREEN)
    ]
    surfs = [small_font.render(text, True, color) for text, color in lines]

    pad = 5
    w = max(s.get_width() for s in surfs) + pad * 2
    h = sum(s.get_height() for s in surfs) + pad * (len(lines) + 1)
    rect = pygame.Rect(mouse_pos[0] + 10, mouse_pos[1] + 10, w, h)
    rect.clamp_ip(screen.get_rect())

    pygame.draw.rect(surface, (20, 20, 20), rect)
    pygame.draw.rect(surface, WHITE, rect, 1)

    y = rect.y + pad
    for s in surfs:
        surface.blit(s, (rect.x + pad, y))
        y += s.get_height() + pad


def draw_shop(surface):
    title = font.render("Loja de Packs (Interaja)", True, WHITE)
    surface.blit(title, title.get_rect(center=(SCREEN_WIDTH // 2, PACK_Y - 30)))

    for rarity, info in SHOP_PACKS_DATA.items():
        rect, cost = pygame.Rect(info["rect"]), info["cost"]
        # Proteção (assim como no tooltip)
        color = RARITY_COLORS.get(rarity, GRAY)

        pygame.draw.rect(surface, SHOP_BLUE, rect)
        pygame.draw.rect(surface, color, rect, 3)

        r_text = small_font.render(f"{rarity}", True, WHITE)
        c_text = small_font.render(f"${cost}", True, YELLOW)

        surface.blit(r_text, r_text.get_rect(center=(rect.centerx, rect.centery - 10)))
        surface.blit(c_text, c_text.get_rect(center=(rect.centerx, rect.centery + 10)))


def draw_trophy_shop(surface):
    rect = pygame.Rect(TROPHY_SHOP_RECT_DATA)
    pygame.draw.rect(surface, GOLD, rect)
    pygame.draw.rect(surface, WHITE, rect, 4)
    title = small_font.render("TROFÉU", True, BLACK)
    cost = small_font.render(f"${TROPHY_SHOP_COST:,}", True, BLACK)
    desc = small_font.render("COMPRE P/ VENCER!", True, BLACK)
    surface.blit(title, title.get_rect(center=(rect.centerx, rect.centery - 20)))
    surface.blit(cost, cost.get_rect(center=(rect.centerx, rect.centery)))
    surface.blit(desc, desc.get_rect(center=(rect.centerx, rect.centery + 20)))


def draw_weapon_shop(surface):
    title = font.render("Loja de Upgrades", True, WHITE)
    surface.blit(title, title.get_rect(center=(SCREEN_WIDTH // 2, WEAPON_Y - 20)))
    for name, info in WEAPON_SHOP_ITEMS_DATA.items():
        rect, cost, desc = pygame.Rect(info["rect"]), info["cost"], info["desc"]
        pygame.draw.rect(surface, WEAPON_SHOP_RED, rect)
        pygame.draw.rect(surface, WHITE, rect, 3)
        n_text = small_font.render(name, True, WHITE)
        c_text = small_font.render(f"Custo: ${cost:,}", True, YELLOW)
        d_text = small_font.render(desc, True, WHITE)
        surface.blit(n_text, n_text.get_rect(center=(rect.centerx, rect.centery - 25)))
        surface.blit(c_text, c_text.get_rect(center=(rect.centerx, rect.centery)))
        surface.blit(d_text, d_text.get_rect(center=(rect.centerx, rect.centery + 25)))


def draw_ui(surface, players_data_list, my_id):
    if my_id is None: return  # Guarda de segurança

    if players_data_list[my_id]:
        p = players_data_list[my_id]
        controls = small_font.render(CONTROLS_TEXT, True, p['color'])
        base = pygame.Rect(p["base_rect_data"])
        pos_x = base.left if my_id in [0, 2] else base.right - controls.get_width()
        surface.blit(controls, (pos_x, base.bottom + 5))

    def get_shield_txt(p):
        txt = ""
        if p["shield_active"]:
            txt = f"Escudo: {p['shield_timer_frames'] // FPS}s"
        elif p["shield_cooldown_frames"] > 0:
            txt = f"Escudo CD: {(p['shield_cooldown_frames'] // FPS) + 1}s"
        return small_font.render(txt, True, SHIELD_BLUE if txt else WHITE)

    positions = [(10, 10), (SCREEN_WIDTH - 10, 10), (10, 0), (SCREEN_WIDTH - 10, 0)]
    for i, p in enumerate(players_data_list):
        if not p: continue
        name = p['name'][:10]
        money_txt = font.render(f"{name}: ${p['money']:.0f}", True, WHITE)
        # Proteção caso 'Raio Orbital' não esteja definido
        rays = p['consumables'].get('Raio Orbital', 0)
        rays_txt = small_font.render(f"Raios: {rays}", True, WHITE)

        shield_txt = get_shield_txt(p)
        x, y = positions[i]

        if i == 1:  # Canto Sup Direito
            x -= money_txt.get_width()
        elif i == 2:  # Canto Inf Esquerdo
            base_rect = pygame.Rect(p["base_rect_data"])
            y = base_rect.top - 80
        elif i == 3:  # Canto Inf Direito
            base_rect = pygame.Rect(p["base_rect_data"])
            x -= money_txt.get_width()
            y = base_rect.top - 80

        surface.blit(money_txt, (x, y))
        surface.blit(rays_txt, (x, y + 40 if i < 2 else y + 35))
        surface.blit(shield_txt, (x, y + 60 if i < 2 else y + 55))

    if is_host:
        lbl = small_font.render(f"SALA: {my_lan_code}", True, LIME_GREEN)
        surface.blit(lbl, (SCREEN_WIDTH // 2 - lbl.get_width() // 2, 10))


def draw_resenha_overlay(surface):
    global last_resenha_pos_change, current_resenha_pos
    now = pygame.time.get_ticks()
    if now - last_resenha_pos_change > 500:
        x = random.randint(50, SCREEN_WIDTH - 300)
        y = random.randint(50, SCREEN_HEIGHT - 100)
        current_resenha_pos = (x, y)
        last_resenha_pos_change = now

    text = "RESENHA!!!"
    color = random.choice([YELLOW, (0, 255, 255), MAGENTA, GOLD])
    surf_border = resenha_font.render(text, True, BLACK)
    surf = resenha_font.render(text, True, color)
    surface.blit(surf_border, (current_resenha_pos[0] + 4, current_resenha_pos[1] + 4))
    surface.blit(surf, current_resenha_pos)

    info_text = "MODO RESENHA: 2x Grana | 2x Speed | Drops Raros!"
    info_surf = small_font.render(info_text, True, GOLD)
    info_rect = info_surf.get_rect(center=(SCREEN_WIDTH // 2, 135))
    bg_rect = info_rect.inflate(20, 10)
    s = pygame.Surface((bg_rect.width, bg_rect.height))
    s.set_alpha(200)
    s.fill(BLACK)
    surface.blit(s, bg_rect.topleft)
    surface.blit(info_surf, info_rect)


def redraw_window(surface, game_state, my_id):
    surface.fill(DARK_GRAY)
    pygame.draw.rect(surface, GRAY, pygame.Rect(conveyor_rect_data))

    draw_shop(surface)
    draw_weapon_shop(surface)
    draw_trophy_shop(surface)

    if not game_state: return

    players = game_state.get("players", [])
    bottles = game_state.get("conveyor_bottles", [])

    for b_data in bottles:
        draw_bottle(surface, b_data)
        b_rect = pygame.Rect(b_data["rect_data"])
        price = price_font.render(f"${b_data['value']:.0f}", True, YELLOW)
        price_rect = price.get_rect(centerx=b_rect.centerx, bottom=b_rect.top - 2)
        surface.blit(price, price_rect)

    for p_data in players:
        draw_base(surface, p_data)
        draw_player(surface, p_data)

    draw_ui(surface, players, my_id)

    if game_state.get("resenha_active", False):
        draw_resenha_overlay(surface)

    mouse = pygame.mouse.get_pos()
    hover = None
    all_visible_bottles = list(bottles)
    for p in players:
        if p:
            if p["carrying_bottle_data"]:
                b = p["carrying_bottle_data"].copy()
                p_rect = pygame.Rect(p["rect_data"])
                b_rect = pygame.Rect(b["rect_data"])
                b_rect.center = p_rect.center
                b["rect_data"] = (b_rect.x, b_rect.y, b_rect.w, b_rect.h)
                all_visible_bottles.append(b)
            all_visible_bottles.extend([b for b in p["equipped_slots_data"] if b])

    for b_data in all_visible_bottles:
        if pygame.Rect(b_data["rect_data"]).collidepoint(mouse):
            hover = b_data
            break

    if hover:
        draw_tooltip(surface, hover, mouse)

    pygame.display.flip()


def draw_game_over_screen(surface, ranking_data_list):
    surface.fill(DARK_GRAY)
    title = title_font.render("FIM DE JOGO!", True, GOLD)
    surface.blit(title, title.get_rect(center=(SCREEN_WIDTH // 2, 100)))
    places = ["1º LUGAR", "2º LUGAR", "3º LUGAR", "4º LUGAR"]
    start_y = 250
    for i, player_data in enumerate(ranking_data_list):
        if not player_data: continue
        name = player_data["name"]
        money = player_data["money"]
        color = player_data["color"]
        text_color = GOLD if i == 0 else (200, 200, 200) if i == 1 else (205, 127, 50) if i == 2 else WHITE
        place_text = font.render(places[i], True, text_color)
        player_text = font.render(f"{name} - ${money:,.2f}", True, color)
        y_pos = start_y + i * 80
        surface.blit(place_text, place_text.get_rect(center=(SCREEN_WIDTH // 2, y_pos)))
        surface.blit(player_text, player_text.get_rect(center=(SCREEN_WIDTH // 2, y_pos + 40)))
    pygame.display.flip()


# --- LOOP PRINCIPAL COM MENU ---
def main():
    global game_mode_state, player_name_input, code_input, is_host, my_lan_code, connection_status

    running = True

    # Botões do Menu
    btn_join_game = Button("ENTRAR (CODIGO)", SCREEN_WIDTH // 2 - 200, 400, 400, 60, BLUE)
    btn_create_game = Button("CRIAR PARTIDA", SCREEN_WIDTH // 2 - 200, 500, 400, 60, GREEN)

    if not HAS_SERVER_FILE:
        btn_create_game.color = GRAY
        btn_create_game.text = "CRIAR (server.py ausente)"

    input_rect = pygame.Rect(SCREEN_WIDTH // 2 - 150, SCREEN_HEIGHT // 2 - 25, 300, 50)

    n = None
    my_id = None
    game_state = None
    game_over = False
    final_ranking = []

    # --- LOOP DE ESTADOS ---
    while running:
        clock.tick(FPS)

        # Pega eventos uma vez por frame
        events = pygame.event.get()
        for event in events:
            if event.type == pygame.QUIT:
                running = False

        # --- ESTADO 0: MENU PRINCIPAL ---
        if game_mode_state == 0:
            screen.fill(DARK_GRAY)
            draw_text_centered(screen, "GUERRA DAS GARRAFAS", 150, title_font, GOLD)
            draw_text_centered(screen, "Menu Principal", 250)

            btn_join_game.draw(screen)
            btn_create_game.draw(screen)

            for event in events:
                if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    pos = pygame.mouse.get_pos()
                    if btn_join_game.is_clicked(pos):
                        is_host = False
                        game_mode_state = 1
                    elif btn_create_game.is_clicked(pos) and HAS_SERVER_FILE:
                        is_host = True
                        game_mode_state = 1

            pygame.display.flip()

        # --- ESTADO 1: INPUT NOME ---
        elif game_mode_state == 1:
            screen.fill(DARK_GRAY)
            draw_text_centered(screen, "Digite seu Nome (Max 10):", 200)

            pygame.draw.rect(screen, INPUT_BOX_COLOR_ACTIVE, input_rect, 2)
            txt_surf = font.render(player_name_input, True, WHITE)
            screen.blit(txt_surf, (input_rect.x + 5, input_rect.y + 10))

            for event in events:
                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_RETURN and player_name_input.strip():
                        if is_host:
                            # Inicia servidor e conecta
                            t = threading.Thread(target=server.start_server_logic, daemon=True)
                            t.start()
                            pygame.time.wait(1000)

                            ip = get_local_ip()
                            my_lan_code = ip_to_code(ip)

                            try:
                                n = Network("127.0.0.1", player_name_input, PORT)
                                my_id = n.get_player_id()
                                if my_id is None: raise Exception("ID Nulo")
                                game_mode_state = 3
                            except Exception as e:
                                print(f"Erro ao conectar no host local: {e}")
                                running = False
                        else:
                            game_mode_state = 2
                    elif event.key == pygame.K_BACKSPACE:
                        player_name_input = player_name_input[:-1]
                    elif len(player_name_input) < 10 and event.unicode.isprintable():
                        player_name_input += event.unicode
            pygame.display.flip()

        # --- ESTADO 2: INPUT CÓDIGO (CLIENTE) ---
        elif game_mode_state == 2:
            screen.fill(DARK_GRAY)
            draw_text_centered(screen, "Digite o CÓDIGO da Sala:", 200)
            draw_text_centered(screen, "(Ex: C0A80105)", 500, small_font, GRAY)

            pygame.draw.rect(screen, INPUT_BOX_COLOR_ACTIVE, input_rect, 2)
            txt_surf = font.render(code_input, True, WHITE)
            screen.blit(txt_surf, (input_rect.x + 5, input_rect.y + 10))

            # Mostra status de conexão/erro
            if connection_status:
                draw_text_centered(screen, connection_status, 400, small_font, RED)

            for event in events:
                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_RETURN and code_input:
                        target_ip = code_to_ip(code_input)
                        if target_ip:
                            try:
                                connection_status = "Conectando..."
                                pygame.display.flip()  # Mostra "Conectando"

                                n = Network(target_ip, player_name_input, PORT)
                                my_id = n.get_player_id()
                                if my_id is None:
                                    connection_status = "Sala Cheia ou Recusada"
                                    code_input = ""
                                else:
                                    game_mode_state = 3
                            except:
                                connection_status = "Falha na Conexão (Servidor Offline?)"
                                code_input = ""
                        else:
                            connection_status = "Código Inválido"
                            code_input = ""
                    elif event.key == pygame.K_BACKSPACE:
                        code_input = code_input[:-1]
                    elif len(code_input) < 8 and event.unicode.isalnum():
                        code_input += event.unicode.upper()
            pygame.display.flip()

        # --- ESTADO 3: JOGO ---
        elif game_mode_state == 3:
            if not game_over:
                try:
                    new_state = n.recv()
                    if new_state:
                        game_state = new_state
                        if new_state.get("game_over"):
                            game_over = True
                            final_ranking = new_state.get("final_ranking", [])
                    elif new_state is None:
                        print("Desconectado do servidor.")
                        running = False
                except Exception as e:
                    print(f"Erro de rede: {e}")
                    running = False

            if game_over:
                draw_game_over_screen(screen, final_ranking)
                continue

            interact, use_item = False, False
            for event in events:
                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_f: interact = True
                    if event.key == pygame.K_g: use_item = True

            keys = pygame.key.get_pressed()

            try:
                if not n.send({'keys': keys, 'interact': interact, 'use_item': use_item}):
                    print("Falha ao enviar dados.")
                    running = False
            except:
                running = False

            if game_state:
                redraw_window(screen, game_state, my_id)
            else:
                screen.fill(DARK_GRAY)
                draw_text_centered(screen, "Conectando...", SCREEN_HEIGHT // 2)
                pygame.display.flip()

    pygame.quit()
    sys.exit()


if __name__ == "__main__":
    main()