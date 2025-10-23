import pygame
import sys
import pickle
from network import Network  # Importa o network.py (v4)

# --- Inicialização do Pygame (Apenas no Cliente) ---
pygame.init()
pygame.font.init()

# --- Constantes do Jogo (Apenas Visuais) ---
SCREEN_WIDTH = 1280
SCREEN_HEIGHT = 720
FPS = 60

# --- Cores ---
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
GRAY = (100, 100, 100)
DARK_GRAY = (30, 30, 30)
GREEN = (0, 200, 0)
YELLOW = (200, 200, 0)
GOLD = (255, 215, 0)
SHOP_BLUE = (0, 70, 150)
WEAPON_SHOP_RED = (150, 0, 0)

# --- Configuração da Tela e Fontes ---
screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
pygame.display.set_caption("Guerra das Garrafas 20XX - Cliente")
clock = pygame.time.Clock()
font = pygame.font.SysFont(None, 24)
small_font = pygame.font.SysFont(None, 20)

# --- Configuração do Servidor ---
# !!! MUDE "SEU_IP_AQUI" PARA O IP DO COMPUTADOR HOST !!!
SERVER_IP = "127.0.0.1"  # Mude isso! (127.0.0.1 = localhost, para testar sozinho)
PORT = 5555

# --- (MUDANÇA) Definições de Controles Padronizadas ---
CONTROLS_TEXT = "Use: WASD (Mover) | F (Interagir) | G (Usar Item)"

PLAYER_COLORS = [
    (255, 0, 0),  # P1
    (0, 0, 255),  # P2
    (50, 255, 50),  # P3
    (255, 0, 255)  # P4
]

# --- Raridades (Apenas para Cores) ---
RARITY_COLORS = {
    "Descartável": (150, 150, 150),
    "Reutilizável": (0, 200, 0),
    "Colecionável": (0, 100, 255),
    "Premium": (150, 0, 200),
    "Artefato": (255, 150, 0)
}

# --- Dados das Lojas (Estáticos para desenhar) ---
CONVEYOR_Y = SCREEN_HEIGHT // 2 - 30
conveyor_rect_data = (0, CONVEYOR_Y, SCREEN_WIDTH, 60)
player_base_rects_data = [
    (50, 50, 250, 100),  # P1
    (SCREEN_WIDTH - 300, 50, 250, 100),  # P2
    (50, CONVEYOR_Y + 70, 250, 100),  # P3
    (SCREEN_WIDTH - 300, CONVEYOR_Y + 70, 250, 100)  # P4
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


# --- Funções de Desenho ---

def draw_bottle(surface, bottle_data):
    if not bottle_data: return
    rect = pygame.Rect(bottle_data["rect_data"])
    color = bottle_data["color"]
    pygame.draw.rect(surface, color, rect)
    if bottle_data["is_golden"]:
        pygame.draw.rect(surface, GOLD, rect, 3)


def draw_player(surface, player_data):
    if not player_data: return
    rect = pygame.Rect(player_data["rect_data"])
    color = player_data["color"]
    pygame.draw.rect(surface, color, rect)

    if player_data["carrying_bottle_data"]:
        bottle_data = player_data["carrying_bottle_data"]
        bottle_rect = pygame.Rect(bottle_data["rect_data"])
        bottle_rect.center = rect.center
        temp_bottle_draw_data = bottle_data.copy()
        temp_bottle_draw_data["rect_data"] = (bottle_rect.x, bottle_rect.y, bottle_rect.w, bottle_rect.h)
        draw_bottle(surface, temp_bottle_draw_data)

    if player_data["is_stunned"]:
        stun_text = small_font.render("STUNNED", True, YELLOW)
        stun_rect = stun_text.get_rect(center=(rect.centerx, rect.top - 10))
        surface.blit(stun_text, stun_rect)


def draw_base(surface, player_data):
    if not player_data: return
    base_rect = pygame.Rect(player_data["base_rect_data"])
    color = player_data["color"]
    pygame.draw.rect(surface, color, base_rect, 3)

    for slot_data in player_data["equipped_slot_positions_data"]:
        pygame.draw.rect(surface, (50, 50, 50), pygame.Rect(slot_data))

    for bottle_data in player_data["equipped_slots_data"]:
        draw_bottle(surface, bottle_data)


def draw_tooltip(surface, bottle_data, mouse_pos):
    rarity_color = RARITY_COLORS[bottle_data["rarity"]]
    golden_text = " (Dourada)" if bottle_data["is_golden"] else ""
    lines = [
        (f"{bottle_data['name']}{golden_text}", rarity_color),
        (f"Raridade: {bottle_data['rarity']}", WHITE),
        (f"Custo: ${bottle_data['value']:.2f}", YELLOW),
        (f"Renda: ${bottle_data['income']:.2f}/s", GREEN)
    ]
    surfaces = [font.render(text, True, color) for text, color in lines]
    padding = 5
    box_width = max(s.get_width() for s in surfaces) + padding * 2
    box_height = sum(s.get_height() for s in surfaces) + padding * (len(lines) + 1)
    box_rect = pygame.Rect(mouse_pos[0] + 10, mouse_pos[1] + 10, box_width, box_height)
    box_rect.clamp_ip(screen.get_rect())
    pygame.draw.rect(surface, (20, 20, 20), box_rect)
    pygame.draw.rect(surface, WHITE, box_rect, 1)
    current_y = box_rect.y + padding
    for s in surfaces:
        surface.blit(s, (box_rect.x + padding, current_y))
        current_y += s.get_height() + padding


def draw_shop(surface):
    shop_title = font.render("Loja de Packs (Interaja para comprar)", True, WHITE)
    title_rect = shop_title.get_rect(center=(SCREEN_WIDTH // 2, PACK_Y - 20))
    surface.blit(shop_title, title_rect)
    for rarity, pack_info in SHOP_PACKS_DATA.items():
        rect, cost = pygame.Rect(pack_info["rect"]), pack_info["cost"]
        color = RARITY_COLORS[rarity]
        pygame.draw.rect(surface, SHOP_BLUE, rect)
        pygame.draw.rect(surface, color, rect, 3)
        rarity_text = small_font.render(f"Pack {rarity}", True, WHITE)
        cost_text = small_font.render(f"Custo: ${cost}", True, YELLOW)
        rarity_rect = rarity_text.get_rect(center=(rect.centerx, rect.centery - 15))
        cost_rect = cost_text.get_rect(center=(rect.centerx, rect.centery + 15))
        surface.blit(rarity_text, rarity_rect)
        surface.blit(cost_text, cost_rect)


def draw_weapon_shop(surface):
    shop_title = font.render("Loja de Upgrades", True, WHITE)
    title_rect = shop_title.get_rect(center=(SCREEN_WIDTH // 2, WEAPON_Y - 20))
    surface.blit(shop_title, title_rect)
    for weapon_name, info in WEAPON_SHOP_ITEMS_DATA.items():
        rect, cost, desc = pygame.Rect(info["rect"]), info["cost"], info["desc"]
        pygame.draw.rect(surface, WEAPON_SHOP_RED, rect)
        pygame.draw.rect(surface, WHITE, rect, 3)
        name_text = small_font.render(weapon_name, True, WHITE)
        cost_text = small_font.render(f"Custo: ${cost}", True, YELLOW)
        desc_text = small_font.render(desc, True, WHITE)
        name_rect = name_text.get_rect(center=(rect.centerx, rect.centery - 25))
        cost_rect = cost_text.get_rect(center=(rect.centerx, rect.centery))
        desc_rect = desc_text.get_rect(center=(rect.centerx, rect.centery + 25))
        surface.blit(name_text, name_rect)
        surface.blit(cost_text, cost_rect)
        surface.blit(desc_text, desc_rect)


def draw_ui(surface, players_data_list, my_id):
    # Mostra os controles padronizados para o jogador local
    if players_data_list[my_id]:
        p_data = players_data_list[my_id]
        color = p_data['color']
        controls_text = small_font.render(CONTROLS_TEXT, True, color)

        base_rect = pygame.Rect(p_data["base_rect_data"])
        if my_id == 0:  # Top-Left
            surface.blit(controls_text, (base_rect.left, base_rect.bottom + 5))
        elif my_id == 1:  # Top-Right
            surface.blit(controls_text, (base_rect.right - controls_text.get_width(), base_rect.bottom + 5))
        elif my_id == 2:  # Bottom-Left
            surface.blit(controls_text, (base_rect.left, base_rect.bottom + 5))
        elif my_id == 3:  # Bottom-Right
            surface.blit(controls_text, (base_rect.right - controls_text.get_width(), base_rect.bottom + 5))

    # Desenha as informações dos jogadores (Dinheiro, Raios)
    if players_data_list[0]:
        p_data = players_data_list[0]
        money_text = font.render(f"P1 Dinheiro: ${p_data['money']:.2f}", True, WHITE)
        ray_text = small_font.render(f"Raios: {p_data['consumables']['Raio Orbital']}", True, WHITE)
        surface.blit(money_text, (10, 10));
        surface.blit(ray_text, (10, 30))

    if players_data_list[1]:
        p_data = players_data_list[1]
        money_surf = font.render(f"P2 Dinheiro: ${p_data['money']:.2f}", True, WHITE)
        ray_surf = small_font.render(f"Raios: {p_data['consumables']['Raio Orbital']}", True, WHITE)
        surface.blit(money_surf, (SCREEN_WIDTH - money_surf.get_width() - 10, 10))
        surface.blit(ray_surf, (SCREEN_WIDTH - ray_surf.get_width() - 10, 30))

    if players_data_list[2]:
        p_data = players_data_list[2]
        base_rect = pygame.Rect(p_data["base_rect_data"])
        money_text = font.render(f"P3 Dinheiro: ${p_data['money']:.2f}", True, WHITE)
        ray_text = small_font.render(f"Raios: {p_data['consumables']['Raio Orbital']}", True, WHITE)
        surface.blit(money_text, (10, base_rect.top - 40))
        surface.blit(ray_text, (10, base_rect.top - 20))

    if players_data_list[3]:
        p_data = players_data_list[3]
        base_rect = pygame.Rect(p_data["base_rect_data"])
        money_surf = font.render(f"P4 Dinheiro: ${p_data['money']:.2f}", True, WHITE)
        ray_surf = small_font.render(f"Raios: {p_data['consumables']['Raio Orbital']}", True, WHITE)
        surface.blit(money_surf, (SCREEN_WIDTH - money_surf.get_width() - 10, base_rect.top - 40))
        surface.blit(ray_surf, (SCREEN_WIDTH - ray_surf.get_width() - 10, base_rect.top - 20))


def redraw_window(surface, game_state, my_id):
    surface.fill(DARK_GRAY)
    pygame.draw.rect(surface, GRAY, pygame.Rect(conveyor_rect_data))
    draw_shop(surface)
    draw_weapon_shop(surface)

    if not game_state: return

    players_data_list = game_state.get("players", [])
    conveyor_bottles_data = game_state.get("conveyor_bottles", [])

    for bottle_data in conveyor_bottles_data:
        draw_bottle(surface, bottle_data)

    for player_data in players_data_list:
        draw_base(surface, player_data)
        draw_player(surface, player_data)

    draw_ui(surface, players_data_list, my_id)

    # Tooltip
    mouse_pos = pygame.mouse.get_pos()
    hover_bottle_data = None
    all_bottles_to_check = list(conveyor_bottles_data)
    for p_data in players_data_list:
        if p_data:
            if p_data["carrying_bottle_data"]:
                bottle_data = p_data["carrying_bottle_data"]
                player_rect = pygame.Rect(p_data["rect_data"])
                bottle_rect = pygame.Rect(bottle_data["rect_data"])
                bottle_rect.center = player_rect.center
                temp_bottle_data = bottle_data.copy()
                temp_bottle_data["rect_data"] = (bottle_rect.x, bottle_rect.y, bottle_rect.w, bottle_rect.h)
                all_bottles_to_check.append(temp_bottle_data)
            for b_data in p_data["equipped_slots_data"]:
                if b_data:
                    all_bottles_to_check.append(b_data)

    for bottle_data in all_bottles_to_check:
        if pygame.Rect(bottle_data["rect_data"]).collidepoint(mouse_pos):
            hover_bottle_data = bottle_data
            break

    if hover_bottle_data:
        draw_tooltip(surface, hover_bottle_data, mouse_pos)

    pygame.display.flip()


# --- Loop Principal do Cliente ---
def main():
    running = True

    try:
        n = Network(SERVER_IP, PORT)
        my_id = n.get_player_id()
        if my_id is None: raise Exception("ID do jogador é None")
        print(f"Você é o Jogador {my_id + 1}")
    except Exception as e:
        print(f"Não foi possível conectar ao servidor {SERVER_IP}:{PORT}")
        print(f"Erro: {e}")
        print("Verifique se o 'server.py' está rodando e se o IP no 'client.py' está correto.")
        running = False
        pygame.time.wait(3000)
        return

    game_state = None

    while running:
        clock.tick(FPS)

        # 1. Recebe o estado mais recente do servidor
        new_game_state = n.recv()
        if new_game_state:
            game_state = new_game_state
        elif new_game_state is None and game_state is None:
            print("Falha ao receber o estado inicial do jogo. Desconectando.")
            running = False
            break
        elif new_game_state is None:
            print("Servidor desconectado.")
            running = False
            break

        # 2. Coleta os inputs locais
        interact_pressed = False
        use_item_pressed = False

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False

            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_f:
                    interact_pressed = True
                if event.key == pygame.K_g:
                    use_item_pressed = True

        keys_pressed = pygame.key.get_pressed()

        input_data = {
            'keys': keys_pressed,
            'interact': interact_pressed,
            'use_item': use_item_pressed
        }

        # 3. Envia os inputs para o servidor
        if not n.send(input_data):
            print("Não foi possível enviar dados para o servidor. Desconectando.")
            running = False
            break

        # 4. Desenha o último estado recebido
        if game_state:
            redraw_window(screen, game_state, my_id)
        else:
            screen.fill(DARK_GRAY)
            text = font.render("Conectado. Aguardando estado do jogo...", True, WHITE)
            screen.blit(text, (20, 20))
            pygame.display.flip()

    pygame.quit()
    sys.exit()


if __name__ == "__main__":
    main()