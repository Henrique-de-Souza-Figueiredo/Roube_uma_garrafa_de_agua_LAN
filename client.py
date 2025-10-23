import pygame
import sys
import pickle
from network import Network

# --- Inicialização ---
pygame.init()
pygame.font.init()

# --- Constantes ---
SCREEN_WIDTH = 1280
SCREEN_HEIGHT = 720
FPS = 60

# --- Cores ---
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
GRAY = (100, 100, 100)
DARK_GRAY = (30, 30, 30)
YELLOW = (200, 200, 0)
GOLD = (255, 215, 0)
SHOP_BLUE = (0, 70, 150)
WEAPON_SHOP_RED = (150, 0, 0)
SHIELD_BLUE = (100, 100, 255)
RED = (255, 0, 0)
GREEN = (0, 200, 0)
INPUT_BOX_COLOR_INACTIVE = pygame.Color('lightskyblue3')
INPUT_BOX_COLOR_ACTIVE = pygame.Color('dodgerblue2')

# --- Tela e Fontes ---
screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
pygame.display.set_caption("Guerra das Garrafas 20XX - Cliente")
clock = pygame.time.Clock()
font = pygame.font.SysFont(None, 32)
small_font = pygame.font.SysFont(None, 20)
price_font = pygame.font.SysFont(None, 18)

# --- Configuração ---
PORT = 5555
CONTROLS_TEXT = "Use: WASD (Mover) | F (Interagir) | G (Usar Item)"
PLAYER_COLORS = [(255, 0, 0), (0, 0, 255), (50, 255, 50), (255, 0, 255)]
RARITY_COLORS = {
    "Descartável": (150, 150, 150), "Reutilizável": (0, 200, 0),
    "Colecionável": (0, 100, 255), "Premium": (150, 0, 200), "Artefato": (255, 150, 0)
}

# --- Dados Estáticos Lojas ---
CONVEYOR_Y = SCREEN_HEIGHT // 2 - 30
conveyor_rect_data = (0, CONVEYOR_Y, SCREEN_WIDTH, 60)
player_base_rects_data = [
    (50, 50, 250, 100), (SCREEN_WIDTH - 300, 50, 250, 100),
    (50, CONVEYOR_Y + 70, 250, 100), (SCREEN_WIDTH - 300, CONVEYOR_Y + 70, 250, 100)
]
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


# --- Função Input Genérica ---
def get_text_input(surface, prompt):
    input_text = ''
    input_box = pygame.Rect(SCREEN_WIDTH // 2 - 150, SCREEN_HEIGHT // 2 - 25, 300, 50)
    color = INPUT_BOX_COLOR_ACTIVE
    active = True
    prompt_surf = font.render(prompt, True, WHITE)
    prompt_rect = prompt_surf.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2 - 60))
    while active:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_RETURN:
                    if input_text or "IP" in prompt:
                        active = False
                elif event.key == pygame.K_BACKSPACE:
                    input_text = input_text[:-1]
                elif len(input_text) < 30:
                    input_text += event.unicode
        surface.fill(DARK_GRAY)
        surface.blit(prompt_surf, prompt_rect)
        txt_surf = font.render(input_text, True, WHITE)
        pygame.draw.rect(surface, color, input_box, 2)
        surface.blit(txt_surf, (input_box.x + 5, input_box.y + 5))
        pygame.display.flip()
        clock.tick(FPS)
    return input_text if input_text else ("127.0.0.1" if "IP" in prompt else None)


# --- Funções de Desenho ---
def draw_bottle(surface, bottle_data):
    if not bottle_data: return
    rect = pygame.Rect(bottle_data["rect_data"])
    color = bottle_data["color"]
    pygame.draw.rect(surface, color, rect)
    if bottle_data["is_golden"]: pygame.draw.rect(surface, GOLD, rect, 3)


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
        draw_bottle(surface, temp_b_data)
    if player_data["is_stunned"]:
        stun = small_font.render("STUNNED", True, YELLOW)
        surface.blit(stun, stun.get_rect(center=(rect.centerx, rect.top - 10)))


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
    color = RARITY_COLORS[bottle_data["rarity"]]
    gold = " (Dourada)" if bottle_data["is_golden"] else ""
    lines = [
        (f"{bottle_data['name']}{gold}", color),
        (f"Raridade: {bottle_data['rarity']}", WHITE),
        (f"Custo: ${bottle_data['value']:.2f}", YELLOW),
        (f"Renda: ${bottle_data['income']:.2f}/s", GREEN)
    ]
    surfs = [font.render(text, True, color) for text, color in lines]
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
    surface.blit(title, title.get_rect(center=(SCREEN_WIDTH // 2, PACK_Y - 20)))
    for rarity, info in SHOP_PACKS_DATA.items():
        rect, cost = pygame.Rect(info["rect"]), info["cost"]
        color = RARITY_COLORS[rarity]
        pygame.draw.rect(surface, SHOP_BLUE, rect)
        pygame.draw.rect(surface, color, rect, 3)
        r_text = small_font.render(f"Pack {rarity}", True, WHITE)
        c_text = small_font.render(f"Custo: ${cost}", True, YELLOW)
        surface.blit(r_text, r_text.get_rect(center=(rect.centerx, rect.centery - 15)))
        surface.blit(c_text, c_text.get_rect(center=(rect.centerx, rect.centery + 15)))


def draw_weapon_shop(surface):
    title = font.render("Loja de Upgrades", True, WHITE)
    surface.blit(title, title.get_rect(center=(SCREEN_WIDTH // 2, WEAPON_Y - 20)))
    for name, info in WEAPON_SHOP_ITEMS_DATA.items():
        rect, cost, desc = pygame.Rect(info["rect"]), info["cost"], info["desc"]
        pygame.draw.rect(surface, WEAPON_SHOP_RED, rect)
        pygame.draw.rect(surface, WHITE, rect, 3)
        n_text = small_font.render(name, True, WHITE)
        c_text = small_font.render(f"Custo: ${cost}", True, YELLOW)
        d_text = small_font.render(desc, True, WHITE)
        surface.blit(n_text, n_text.get_rect(center=(rect.centerx, rect.centery - 25)))
        surface.blit(c_text, c_text.get_rect(center=(rect.centerx, rect.centery)))
        surface.blit(d_text, d_text.get_rect(center=(rect.centerx, rect.centery + 25)))


def draw_ui(surface, players_data_list, my_id):
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

    if players_data_list[0]:
        p = players_data_list[0]
        name = p['name'][:10]
        money = font.render(f"{name}: ${p['money']:.2f}", True, WHITE)
        rays = small_font.render(f"Raios: {p['consumables']['Raio Orbital']}", True, WHITE)
        shield = get_shield_txt(p)
        surface.blit(money, (10, 10))
        surface.blit(rays, (10, 40))
        surface.blit(shield, (10, 60))
    if players_data_list[1]:
        p = players_data_list[1]
        name = p['name'][:10]
        money = font.render(f"{name}: ${p['money']:.2f}", True, WHITE)
        rays = small_font.render(f"Raios: {p['consumables']['Raio Orbital']}", True, WHITE)
        shield = get_shield_txt(p)
        surface.blit(money, (SCREEN_WIDTH - money.get_width() - 10, 10))
        surface.blit(rays, (SCREEN_WIDTH - rays.get_width() - 10, 40))
        surface.blit(shield, (SCREEN_WIDTH - shield.get_width() - 10, 60))
    if players_data_list[2]:
        p = players_data_list[2]
        name = p['name'][:10]
        base = pygame.Rect(p["base_rect_data"])
        money = font.render(f"{name}: ${p['money']:.2f}", True, WHITE)
        rays = small_font.render(f"Raios: {p['consumables']['Raio Orbital']}", True, WHITE)
        shield = get_shield_txt(p)
        surface.blit(money, (10, base.top - 70))
        surface.blit(rays, (10, base.top - 45))
        surface.blit(shield, (10, base.top - 25))
    if players_data_list[3]:
        p = players_data_list[3]
        name = p['name'][:10]
        base = pygame.Rect(p["base_rect_data"])
        money = font.render(f"{name}: ${p['money']:.2f}", True, WHITE)
        rays = small_font.render(f"Raios: {p['consumables']['Raio Orbital']}", True, WHITE)
        shield = get_shield_txt(p)
        surface.blit(money, (SCREEN_WIDTH - money.get_width() - 10, base.top - 70))
        surface.blit(rays, (SCREEN_WIDTH - rays.get_width() - 10, base.top - 45))
        surface.blit(shield, (SCREEN_WIDTH - shield.get_width() - 10, base.top - 25))


def redraw_window(surface, game_state, my_id):
    surface.fill(DARK_GRAY)
    pygame.draw.rect(surface, GRAY, pygame.Rect(conveyor_rect_data))
    draw_shop(surface)
    draw_weapon_shop(surface)
    if not game_state: return
    players = game_state.get("players", [])
    bottles = game_state.get("conveyor_bottles", [])

    # Garrafas na esteira + Preços
    for b_data in bottles:
        draw_bottle(surface, b_data)
        b_rect = pygame.Rect(b_data["rect_data"])
        price = price_font.render(f"${b_data['value']:.0f}", True, YELLOW)

        # --- (MUDANÇA AQUI) Ajusta o posicionamento do texto do preço ---
        # Posiciona o preço centralizado horizontalmente acima da garrafa.
        # Ajustamos o 'y' para garantir que ele esteja FORA da garrafa.
        price_rect = price.get_rect(centerx=b_rect.centerx, bottom=b_rect.top - 2)  # 2 pixels acima do topo da garrafa
        surface.blit(price, price_rect)
        # --- FIM DA MUDANÇA ---

    # Bases e Jogadores
    for p_data in players:
        draw_base(surface, p_data)
        draw_player(surface, p_data)
    draw_ui(surface, players, my_id)

    # Tooltip agora verifica TODAS as garrafas
    mouse = pygame.mouse.get_pos()
    hover = None

    all_visible_bottles = list(bottles)
    for p in players:
        if p:
            if p["carrying_bottle_data"]:
                b = p["carrying_bottle_data"]
                p_rect = pygame.Rect(p["rect_data"])
                b_rect = pygame.Rect(b["rect_data"])
                b_rect.center = p_rect.center
                temp = b.copy()
                temp["rect_data"] = (b_rect.x, b_rect.y, b_rect.w, b_rect.h)
                all_visible_bottles.append(temp)
            all_visible_bottles.extend([b for b in p["equipped_slots_data"] if b])

    for b_data in all_visible_bottles:
        if pygame.Rect(b_data["rect_data"]).collidepoint(mouse):
            hover = b_data
            break

    if hover: draw_tooltip(surface, hover, mouse)

    pygame.display.flip()


# --- Loop Principal ---
def main():
    running = True

    player_name = get_text_input(screen, "Digite seu Nome (max 10 chars) e Enter:")
    player_name = (player_name if player_name else "Jogador")[:10]
    server_ip = get_text_input(screen, "Digite o IP do Servidor (Enter para localhost):")
    server_ip = server_ip if server_ip else "127.0.0.1"

    try:
        n = Network(server_ip, player_name, PORT)
        my_id = n.get_player_id()
        if my_id is None: raise ConnectionRefusedError("ID None")
        print(f"ID: {my_id + 1} ({player_name})")
    except Exception as e:
        print(f"Conexão falhou para {server_ip}:{PORT}. Erro: {e}")
        running = False
        pygame.time.wait(4000)
        pygame.quit()
        sys.exit()

    game_state = None
    while running:
        clock.tick(FPS)

        new_state = n.recv()
        if new_state:
            game_state = new_state
        elif new_state is None and game_state is None:
            print("Falha inicial.")
            running = False
            break
        elif new_state is None:
            print("Servidor desconectado.")
            running = False
            break

        interact, use_item = False, False
        for event in pygame.event.get():
            if event.type == pygame.QUIT: running = False
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_f: interact = True
                if event.key == pygame.K_g: use_item = True
        keys = pygame.key.get_pressed()
        inputs = {'keys': keys, 'interact': interact, 'use_item': use_item}

        if not n.send(inputs):
            print("Falha envio. Desconectando.")
            running = False
            break

        if game_state:
            redraw_window(screen, game_state, my_id)
        else:
            screen.fill(DARK_GRAY)
            text = font.render("Aguardando estado...", True, WHITE)
            screen.blit(text, (20, 20))
            pygame.display.flip()

    pygame.quit()
    sys.exit()


if __name__ == "__main__":
    main()