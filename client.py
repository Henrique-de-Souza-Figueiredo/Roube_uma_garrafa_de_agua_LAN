import pygame
import sys
import pickle
import random
import threading
from pathlib import Path
from network import Network
from config import *

try:
    import server

    HAS_SERVER_FILE = True
except ImportError:
    HAS_SERVER_FILE = False
    print("AVISO: server.py não encontrado. Modo 'Criar Partida' desabilitado.")

# --- Inicialização ---
pygame.init()
pygame.font.init()
AUDIO_ENABLED = True
try:
    pygame.mixer.init()
except pygame.error as e:
    AUDIO_ENABLED = False
    print(f"AVISO: audio desativado. Erro: {e}")
pygame.key.set_repeat(500, 30)


def resource_path(relative_path):
    base_path = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
    return str(base_path / relative_path)

screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
pygame.display.set_caption("Roube uma Garrafa de Agua")
clock = pygame.time.Clock()

font = pygame.font.SysFont("segoeui", 48)
small_font = pygame.font.SysFont("segoeui", 24)
price_font = pygame.font.SysFont("segoeui", 18)
title_font = pygame.font.SysFont("georgia", 72, bold=True)
resenha_font = pygame.font.SysFont("georgia", 100, bold=True)
event_font = pygame.font.SysFont("georgia", 120, bold=True)

BG_TOP = (18, 23, 34)
BG_BOTTOM = (43, 32, 24)
PANEL_BG = (24, 30, 44)
PANEL_BORDER = (91, 113, 145)
CONVEYOR_EDGE = (94, 96, 102)
CONVEYOR_STRIPE = (118, 120, 126)


def draw_vertical_gradient(surface, top_color=BG_TOP, bottom_color=BG_BOTTOM):
    height = surface.get_height()
    for y in range(height):
        ratio = y / max(height - 1, 1)
        color = tuple(int(top_color[i] * (1 - ratio) + bottom_color[i] * ratio) for i in range(3))
        pygame.draw.line(surface, color, (0, y), (surface.get_width(), y))


def draw_panel(surface, rect, fill=PANEL_BG, border=PANEL_BORDER, radius=14, alpha=230):
    fill_rgb = tuple(fill)[:3]
    border_rgb = tuple(border)[:3]
    panel = pygame.Surface((rect.w, rect.h), pygame.SRCALPHA)
    pygame.draw.rect(panel, (*fill_rgb, alpha), panel.get_rect(), border_radius=radius)
    pygame.draw.rect(panel, (*border_rgb, 210), panel.get_rect(), 2, border_radius=radius)
    surface.blit(panel, rect.topleft)


def draw_shadowed_text(surface, text_surf, center, shadow_color=BLACK, offset=(3, 3)):
    shadow = text_surf.copy()
    shadow.fill(shadow_color, special_flags=pygame.BLEND_RGB_MULT)
    surface.blit(shadow, shadow.get_rect(center=(center[0] + offset[0], center[1] + offset[1])))
    surface.blit(text_surf, text_surf.get_rect(center=center))

boss_image = None
try:
    boss_image = pygame.image.load(resource_path(BOSS_IMAGE_PATH)).convert_alpha()
    boss_image = pygame.transform.scale(boss_image, (100, 100))
except Exception as e:
    print(f"AVISO: Não foi possível carregar '{BOSS_IMAGE_PATH}'. Erro: {e}")
    boss_image = None

# Estado do Menu
game_mode_state = 0
player_name_input = ""
code_input = ""
connection_status = ""
is_host = False
my_lan_code = ""

last_event_pos_change = 0
current_event_pos = (0, 0)


# --- Componentes de UI ---
class Button:
    # (Código do Botão igual)
    def __init__(self, text, x, y, w, h, color, text_color=WHITE):
        self.rect = pygame.Rect(x, y, w, h)
        self.text = text
        self.color = color
        self.text_color = text_color

    def draw(self, surf):
        mouse_over = self.rect.collidepoint(pygame.mouse.get_pos())
        color = tuple(min(255, c + 28) for c in self.color) if mouse_over else self.color
        pygame.draw.rect(surf, (0, 0, 0), self.rect.move(0, 5), border_radius=14)
        pygame.draw.rect(surf, color, self.rect, border_radius=14)
        pygame.draw.rect(surf, WHITE, self.rect, 2, border_radius=14)
        txt_surf = font.render(self.text, True, self.text_color)
        surf.blit(txt_surf, txt_surf.get_rect(center=self.rect.center))

    def is_clicked(self, pos):
        return self.rect.collidepoint(pos)


def draw_text_centered(surf, text, y, f=font, color=WHITE):
    txt = f.render(text, True, color)
    surf.blit(txt, txt.get_rect(center=(SCREEN_WIDTH // 2, y)))


# --- Funções de Desenho (draw_bottle, draw_player, draw_base, etc.) ---
# (Todas as funções de desenho permanecem EXATAMENTE IGUAIS ao código anterior)
# (Vamos pular para a função 'main' onde a lógica da música entra)

def draw_bottle(surface, bottle_data):
    if not bottle_data: return
    rect = pygame.Rect(bottle_data["rect_data"])
    rarity = bottle_data.get("rarity", "")
    b_type = bottle_data.get("type", "normal")
    rarity_color = bottle_data["color"]
    tick = pygame.time.get_ticks()

    def mix(a, b, t):
        return tuple(int(a[i] * (1 - t) + b[i] * t) for i in range(3))

    profiles = {
        "Descart": {"glass": (150, 154, 158), "water": (130, 145, 155), "cap": (92, 96, 100), "shape": "plastic"},
        "Reutil": {"glass": (110, 205, 130), "water": (70, 170, 120), "cap": (25, 110, 55), "shape": "sport"},
        "Colecion": {"glass": (88, 150, 235), "water": (55, 120, 210), "cap": (20, 70, 155), "shape": "glass"},
        "Premium": {"glass": (145, 76, 195), "water": (100, 45, 150), "cap": (225, 205, 90), "shape": "tall"},
        "Antiga": {"glass": (154, 95, 52), "water": (110, 65, 35), "cap": (88, 54, 32), "shape": "amphora"},
        "Artefato": {"glass": (230, 175, 55), "water": (255, 215, 80), "cap": (255, 245, 170), "shape": "relic"},
        "C": {"glass": (40, 240, 255), "water": (35, 100, 255), "cap": (255, 255, 255), "shape": "cosmic"},
    }
    profile = next((data for key, data in profiles.items() if rarity.startswith(key)), profiles["Descart"])

    if b_type == "bomb" or rarity.startswith("Bomba"):
        profile = {"glass": (95, 20, 20), "water": (185, 30, 30), "cap": (35, 35, 35), "shape": "bomb"}
    elif b_type == "mystery" or rarity.startswith("Misteriosa"):
        phase = 0.5 + 0.5 * ((tick // 180) % 2)
        pulse = mix((255, 40, 220), (80, 220, 255), phase)
        profile = {"glass": pulse, "water": mix(pulse, WHITE, 0.25), "cap": WHITE, "shape": "mystery"}

    glass = profile["glass"]
    water_color = mix(profile["water"], rarity_color, 0.25)
    cap_color = profile["cap"]
    outline = mix(glass, BLACK, 0.55)
    body = pygame.Rect(rect.x + rect.w * 0.18, rect.y + rect.h * 0.30, rect.w * 0.64, rect.h * 0.66)
    neck = pygame.Rect(rect.x + rect.w * 0.37, rect.y + rect.h * 0.08, rect.w * 0.26, rect.h * 0.22)
    cap = pygame.Rect(rect.x + rect.w * 0.32, rect.y, rect.w * 0.36, rect.h * 0.12)
    label = pygame.Rect(body.x + 2, body.y + body.h * 0.38, body.w - 4, max(5, int(body.h * 0.22)))
    water = pygame.Rect(body.x + 3, body.y + body.h * 0.20, body.w - 6, body.h * 0.68)

    pygame.draw.ellipse(surface, (0, 0, 0), rect.move(3, 5))

    shape = profile["shape"]
    if shape == "plastic":
        pygame.draw.rect(surface, glass, body, border_radius=5)
        pygame.draw.rect(surface, glass, neck, border_radius=3)
    elif shape == "sport":
        body.inflate_ip(4, 0)
        pygame.draw.rect(surface, glass, body, border_radius=10)
        pygame.draw.polygon(surface, glass, [(body.left, body.top + 7), (body.centerx, neck.bottom), (body.right, body.top + 7)])
        pygame.draw.rect(surface, glass, neck, border_radius=4)
    elif shape == "glass":
        pygame.draw.ellipse(surface, glass, pygame.Rect(body.x, body.y - 3, body.w, 12))
        pygame.draw.rect(surface, glass, body, border_radius=9)
        pygame.draw.rect(surface, glass, neck, border_radius=4)
    elif shape == "tall":
        body = pygame.Rect(rect.x + rect.w * 0.26, rect.y + rect.h * 0.26, rect.w * 0.48, rect.h * 0.70)
        water = pygame.Rect(body.x + 3, body.y + body.h * 0.25, body.w - 6, body.h * 0.65)
        label = pygame.Rect(body.x + 1, body.y + body.h * 0.48, body.w - 2, max(5, int(body.h * 0.20)))
        pygame.draw.rect(surface, glass, body, border_radius=10)
        pygame.draw.rect(surface, glass, neck, border_radius=3)
    elif shape == "amphora":
        points = [(rect.centerx, rect.y + 4), (rect.x + rect.w * 0.70, rect.y + rect.h * 0.35),
                  (rect.x + rect.w * 0.78, rect.y + rect.h * 0.85), (rect.centerx, rect.bottom),
                  (rect.x + rect.w * 0.22, rect.y + rect.h * 0.85), (rect.x + rect.w * 0.30, rect.y + rect.h * 0.35)]
        pygame.draw.polygon(surface, glass, points)
        pygame.draw.line(surface, outline, (rect.x + 3, rect.y + rect.h * 0.45), (rect.x + rect.w * 0.22, rect.y + rect.h * 0.58), 3)
        pygame.draw.line(surface, outline, (rect.right - 3, rect.y + rect.h * 0.45), (rect.x + rect.w * 0.78, rect.y + rect.h * 0.58), 3)
    elif shape == "relic":
        pygame.draw.polygon(surface, glass, [(rect.centerx, rect.y + 2), (rect.right - 4, rect.centery),
                                             (rect.centerx, rect.bottom - 2), (rect.x + 4, rect.centery)])
        pygame.draw.circle(surface, water_color, rect.center, max(4, rect.w // 5))
    elif shape == "cosmic":
        glow = pygame.Surface(rect.size, pygame.SRCALPHA)
        pygame.draw.ellipse(glow, (*glass, 80), glow.get_rect())
        surface.blit(glow, rect.topleft)
        pygame.draw.polygon(surface, glass, [(rect.centerx, rect.y), (rect.right - 5, rect.y + rect.h * 0.35),
                                             (rect.right - 8, rect.bottom - 4), (rect.x + 8, rect.bottom - 4),
                                             (rect.x + 5, rect.y + rect.h * 0.35)])
    elif shape == "bomb":
        pygame.draw.circle(surface, glass, rect.center, max(rect.w, rect.h) // 3)
        pygame.draw.rect(surface, cap_color, cap, border_radius=2)
        pygame.draw.line(surface, YELLOW, cap.midtop, (cap.centerx + 8, cap.y - 8), 2)
    elif shape == "mystery":
        pygame.draw.polygon(surface, glass, [(rect.centerx, rect.y), (rect.right - 3, rect.centery),
                                             (rect.centerx, rect.bottom), (rect.x + 3, rect.centery)])

    if shape not in ["amphora", "relic", "cosmic", "bomb", "mystery"]:
        pygame.draw.rect(surface, water_color, water, border_radius=7)
        pygame.draw.rect(surface, cap_color, cap, border_radius=3)
        pygame.draw.rect(surface, (235, 240, 245), label, border_radius=4)
        pygame.draw.rect(surface, rarity_color, label.inflate(-4, -3), border_radius=3)
        pygame.draw.line(surface, WHITE, (body.x + body.w * 0.28, body.y + 4), (body.x + body.w * 0.28, body.bottom - 6), 2)
        pygame.draw.rect(surface, outline, body, 2, border_radius=8)
        pygame.draw.rect(surface, outline, neck, 1, border_radius=4)
    elif shape not in ["bomb", "mystery"]:
        pygame.draw.polygon(surface, outline, [(rect.centerx, rect.y + 2), (rect.right - 4, rect.centery),
                                               (rect.centerx, rect.bottom - 2), (rect.x + 4, rect.centery)], 2)

    if bottle_data.get("is_golden", False):
        pygame.draw.rect(surface, GOLD, body.inflate(6, 6), 3, border_radius=10)

    if b_type == "bomb":
        if (pygame.time.get_ticks() // 200) % 2 == 0:
            pygame.draw.rect(surface, RED, body.inflate(7, 7), 3, border_radius=10)
        timer_frames = bottle_data.get("explode_timer", 0)
        if timer_frames > 0:
            timer_sec = (timer_frames // FPS) + 1
            timer_surf = font.render(str(timer_sec), True, RED)
            surface.blit(timer_surf, timer_surf.get_rect(center=rect.center))
    elif b_type == "mystery":
        if (pygame.time.get_ticks() // 300) % 2 == 0:
            q_surf = font.render("?", True, WHITE)
            surface.blit(q_surf, q_surf.get_rect(center=rect.center))


def draw_player(surface, player_data, game_state):
    if not player_data: return
    rect = pygame.Rect(player_data["rect_data"])
    color = player_data["color"]
    pygame.draw.ellipse(surface, (0, 0, 0), rect.move(3, 5))
    pygame.draw.rect(surface, color, rect, border_radius=8)
    pygame.draw.rect(surface, tuple(min(255, c + 65) for c in color), rect.inflate(-10, -12), border_radius=6)
    pygame.draw.rect(surface, WHITE, rect, 2, border_radius=8)
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
    if player_data.get("tax_visual_timer", 0) > 0:
        tax_amount = player_data.get("last_tax_amount", 0)
        msg = small_font.render(f"-${tax_amount:.2f} IMPOSTO!", True, RED)
        offset_y = (FPS * 3 - player_data["tax_visual_timer"]) * 0.5
        surface.blit(msg, msg.get_rect(center=(rect.centerx, rect.top - 25 - offset_y)))
    if game_state.get("active_event") == "LA ELE" and game_state.get("la_ele_player_id") == player_data["id"]:
        if (pygame.time.get_ticks() // 150) % 2 == 0:
            pygame.draw.line(surface, BLACK, rect.topleft, rect.bottomright, 7)
            pygame.draw.line(surface, BLACK, rect.topright, rect.bottomleft, 7)
            pygame.draw.line(surface, WHITE, rect.topleft, rect.bottomright, 3)
            pygame.draw.line(surface, WHITE, rect.topright, rect.bottomleft, 3)


def draw_base(surface, player_data, game_state):
    if game_state.get("active_event") == "BOSS FIGHT": return
    if not player_data: return
    base_rect = pygame.Rect(player_data["base_rect_data"])
    color = player_data["color"]
    draw_panel(surface, base_rect, fill=(18, 22, 30), border=color, radius=12, alpha=210)
    button_rect = pygame.Rect(player_data["shield_button_rect_data"])
    cooldown = player_data["shield_cooldown_frames"]
    btn_color = GREEN if cooldown <= 0 else RED
    pygame.draw.rect(surface, btn_color, button_rect, border_radius=6)
    pygame.draw.rect(surface, WHITE, button_rect, 1, border_radius=6)
    if game_state.get("active_event") == "WASSUUUP":
        phone_rect = pygame.Rect(player_data["phone_rect_data"])
        phone_color = YELLOW if (pygame.time.get_ticks() // 200) % 2 == 0 else BLACK
        pygame.draw.rect(surface, phone_color, phone_rect, border_radius=6)
        pygame.draw.rect(surface, WHITE, phone_rect, 1, border_radius=6)
        if player_data.get("controls_reversed", False):
            f_surf = small_font.render("F", True, WHITE)
            surface.blit(f_surf, f_surf.get_rect(center=phone_rect.center))
    if player_data["shield_active"]:
        shield_surf = pygame.Surface(base_rect.size, pygame.SRCALPHA)
        alpha = 100 + (player_data['shield_timer_frames'] % 15) * 2
        shield_surf.fill((*SHIELD_BLUE, alpha))
        surface.blit(shield_surf, base_rect.topleft)
    for slot_data in player_data["equipped_slot_positions_data"]:
        pygame.draw.rect(surface, (42, 47, 58), pygame.Rect(slot_data), border_radius=5)
        pygame.draw.rect(surface, (95, 104, 120), pygame.Rect(slot_data), 1, border_radius=5)
    for bottle_data in player_data["equipped_slots_data"]:
        draw_bottle(surface, bottle_data)


def draw_tooltip(surface, bottle_data, mouse_pos):
    color = RARITY_COLORS.get(bottle_data["rarity"], WHITE)
    gold = " (Dourada)" if bottle_data.get("is_golden") else ""
    name_display = bottle_data['name']
    if bottle_data['rarity'] == "Bomba":
        name_display = "BATATA QUENTE!"
    elif bottle_data['rarity'] == "Misteriosa":
        name_display = "GARRAFA MISTERIOSA"
    lines = [
        (f"{name_display}{gold}", color),
        (f"Raridade: {bottle_data['rarity']}", WHITE),
        (f"Valor: ${bottle_data['value']:.2f}", YELLOW),
        (f"Renda: ${bottle_data['income']:.2f}/s", GREEN)
    ]
    surfs = [small_font.render(text, True, t_color) for text, t_color in lines]
    pad = 5
    w = max(s.get_width() for s in surfs) + pad * 2
    h = sum(s.get_height() for s in surfs) + pad * (len(lines) + 1)
    rect = pygame.Rect(mouse_pos[0] + 10, mouse_pos[1] + 10, w, h)
    rect.clamp_ip(screen.get_rect())
    draw_panel(surface, rect, fill=(16, 18, 22), border=WHITE, radius=8, alpha=240)
    y = rect.y + pad
    for s in surfs:
        surface.blit(s, (rect.x + pad, y))
        y += s.get_height() + pad


def draw_shop(surface):
    title = font.render("Loja de Packs (Interaja)", True, WHITE)
    surface.blit(title, title.get_rect(center=(SCREEN_WIDTH // 2, PACK_Y - 30)))
    for rarity, info in SHOP_PACKS_DATA.items():
        rect, cost = pygame.Rect(info["rect"]), info["cost"]
        color = RARITY_COLORS.get(rarity, GRAY)
        pygame.draw.rect(surface, (0, 0, 0), rect.move(3, 4), border_radius=10)
        pygame.draw.rect(surface, SHOP_BLUE, rect, border_radius=10)
        pygame.draw.rect(surface, color, rect, 3, border_radius=10)
        r_text = small_font.render(f"{rarity}", True, WHITE)
        c_text = small_font.render(f"${cost}", True, YELLOW)
        surface.blit(r_text, r_text.get_rect(center=(rect.centerx, rect.centery - 10)))
        surface.blit(c_text, c_text.get_rect(center=(rect.centerx, rect.centery + 10)))


def draw_trophy_shop(surface):
    rect = pygame.Rect(TROPHY_SHOP_RECT_DATA)
    pygame.draw.rect(surface, (0, 0, 0), rect.move(4, 5), border_radius=12)
    pygame.draw.rect(surface, GOLD, rect, border_radius=12)
    pygame.draw.rect(surface, WHITE, rect, 4, border_radius=12)
    title = small_font.render("TROFÉU", True, BLACK)
    cost = small_font.render(f"${TROPHY_SHOP_COST:,}", True, BLACK)
    surface.blit(title, title.get_rect(center=(rect.centerx, rect.centery - 15)))
    surface.blit(cost, cost.get_rect(center=(rect.centerx, rect.centery + 15)))


def draw_weapon_shop(surface):
    title = font.render("Loja de Upgrades", True, WHITE)
    surface.blit(title, title.get_rect(center=(SCREEN_WIDTH // 2, WEAPON_Y - 20)))
    for name, info in WEAPON_SHOP_ITEMS_DATA.items():
        rect, cost, desc = pygame.Rect(info["rect"]), info["cost"], info["desc"]
        pygame.draw.rect(surface, (0, 0, 0), rect.move(3, 4), border_radius=10)
        pygame.draw.rect(surface, WEAPON_SHOP_RED, rect, border_radius=10)
        pygame.draw.rect(surface, WHITE, rect, 3, border_radius=10)
        n_text = small_font.render(name, True, WHITE)
        c_text = small_font.render(f"Custo: ${cost:,}", True, YELLOW)
        d_text = small_font.render(desc, True, WHITE)
        surface.blit(n_text, n_text.get_rect(center=(rect.centerx, rect.centery - 25)))
        surface.blit(c_text, c_text.get_rect(center=(rect.centerx, rect.centery)))
        surface.blit(d_text, d_text.get_rect(center=(rect.centerx, rect.centery + 25)))


def draw_ui(surface, players_data_list, my_id):
    if my_id is None: return
    if players_data_list[my_id]:
        p = players_data_list[my_id]
        controls = small_font.render(CONTROLS_TEXT, True, p['color'])
        base = pygame.Rect(p["base_rect_data"])
        pos_x = base.left if my_id in [0, 2] else base.right - controls.get_width()
        surface.blit(controls, (pos_x, base.bottom + 5))
        if p.get("controls_reversed", False):
            warn_surf = font.render("CONTROLES INVERTIDOS!", True, RED)
            surface.blit(warn_surf, warn_surf.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT - 30)))

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
        money_txt = font.render(f"{name}: ${p['money']:.2f}", True, WHITE)
        rays_txt = small_font.render(f"Raios: {p['consumables'].get('Raio Orbital', 0)}", True, WHITE)
        shield_txt = get_shield_txt(p)
        x, y = positions[i]
        if i == 1:
            x -= money_txt.get_width()
        elif i == 2:
            base_rect = pygame.Rect(p["base_rect_data"])
            y = base_rect.top - 80
        elif i == 3:
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
    global last_event_pos_change, current_event_pos
    now = pygame.time.get_ticks()
    if now - last_event_pos_change > 500:
        x = random.randint(50, SCREEN_WIDTH - 300)
        y = random.randint(50, SCREEN_HEIGHT - 100)
        current_event_pos = (x, y)
        last_event_pos_change = now
    text = "RESENHA!!!"
    color = random.choice([YELLOW, (0, 255, 255), MAGENTA, GOLD])
    surf_border = resenha_font.render(text, True, BLACK)
    surf = resenha_font.render(text, True, color)
    surface.blit(surf_border, (current_event_pos[0] + 4, current_event_pos[1] + 4))
    surface.blit(surf, current_event_pos)
    info_text = "MODO RESENHA: 2x Grana | 2x Speed | Drops Raros!"
    info_surf = small_font.render(info_text, True, GOLD)
    info_rect = info_surf.get_rect(center=(SCREEN_WIDTH // 2, 135))
    bg_rect = info_rect.inflate(20, 10)
    s = pygame.Surface((bg_rect.width, bg_rect.height))
    s.set_alpha(200)
    s.fill(BLACK)
    surface.blit(s, bg_rect.topleft)
    surface.blit(info_surf, info_rect)


def draw_event_overlay(surface, game_state):
    active_event = game_state.get("active_event")
    if not active_event: return

    global last_event_pos_change, current_event_pos
    now = pygame.time.get_ticks()

    if now - last_event_pos_change > 300:
        x = random.randint(50, SCREEN_WIDTH - 400)
        y = random.randint(50, SCREEN_HEIGHT - 200)
        current_event_pos = (x, y)
        last_event_pos_change = now

    if active_event == "WASSUUUP":
        text = "WASSUUUP?!"
        color = random.choice([WHITE, LIME_GREEN, YELLOW])
        surf = event_font.render(text, True, color)
        surf_border = event_font.render(text, True, BLACK)
        surface.blit(surf_border, (current_event_pos[0] + 5, current_event_pos[1] + 5))
        surface.blit(surf, current_event_pos)

    elif active_event == "LA ELE":
        text = "LA ELE?!"
        color = random.choice([WHITE, RED, MAGENTA])
        surf = event_font.render(text, True, color)
        surf_border = event_font.render(text, True, BLACK)
        surface.blit(surf_border, (current_event_pos[0] + 5, current_event_pos[1] + 5))
        surface.blit(surf, current_event_pos)
        timer_sec = game_state.get("event_duration", 0) // FPS
        timer_surf = font.render(f"Tempo: {timer_sec}s", True, RED)
        surface.blit(timer_surf, timer_surf.get_rect(center=(SCREEN_WIDTH // 2, 100)))


def draw_boss(surface, boss_data):
    if not boss_data: return
    rect = pygame.Rect(boss_data["rect_data"])
    if boss_image:
        surface.blit(boss_image, rect.topleft)
    else:
        pygame.draw.rect(surface, MAGENTA, rect)
    health_perc = boss_data["current_health"] / boss_data["max_health"]
    bar_width = 300
    bar_height = 20
    bg_bar = pygame.Rect((SCREEN_WIDTH - bar_width) // 2, 20, bar_width, bar_height)
    hp_bar = pygame.Rect((SCREEN_WIDTH - bar_width) // 2, 20, bar_width * health_perc, bar_height)
    pygame.draw.rect(surface, RED, bg_bar)
    pygame.draw.rect(surface, GREEN, hp_bar)
    pygame.draw.rect(surface, WHITE, bg_bar, 2)
    boss_text = font.render("Earthmover", True, RED)
    surface.blit(boss_text, boss_text.get_rect(center=(SCREEN_WIDTH // 2, 60)))


def redraw_window(surface, game_state, my_id):
    draw_vertical_gradient(surface)

    boss_data = game_state.get("boss_data")

    if boss_data:
        pass  # Esconde lojas e esteira
    else:
        conveyor = pygame.Rect(conveyor_rect_data)
        pygame.draw.rect(surface, CONVEYOR_EDGE, conveyor.inflate(0, 16), border_radius=18)
        pygame.draw.rect(surface, GRAY, conveyor, border_radius=12)
        for x in range(-80, SCREEN_WIDTH + 80, 80):
            pygame.draw.line(surface, CONVEYOR_STRIPE, (x, conveyor.top), (x + 45, conveyor.bottom), 4)
        draw_shop(surface)
        draw_weapon_shop(surface)
        draw_trophy_shop(surface)

    if not game_state: return

    players = game_state.get("players", [])
    bottles = game_state.get("conveyor_bottles", [])

    if not boss_data:
        for b_data in bottles:
            draw_bottle(surface, b_data)
            b_rect = pygame.Rect(b_data["rect_data"])
            price = price_font.render(f"${b_data['value']:.2f}", True, YELLOW)
            price_rect = price.get_rect(centerx=b_rect.centerx, bottom=b_rect.top - 2)
            surface.blit(price, price_rect)

    for p_data in players:
        draw_base(surface, p_data, game_state)
        draw_player(surface, p_data, game_state)

    draw_ui(surface, players, my_id)
    draw_boss(surface, boss_data)

    if game_state.get("resenha_active", False):
        draw_resenha_overlay(surface)

    draw_event_overlay(surface, game_state)

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

    if hover and not boss_data:
        draw_tooltip(surface, hover, mouse)

    pygame.display.flip()


def draw_game_over_screen(surface, ranking_data_list):
    draw_vertical_gradient(surface)
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


# --- LOOP PRINCIPAL ---
def main():
    global game_mode_state, player_name_input, code_input, is_host, my_lan_code, connection_status, boss_image

    # Carrega a imagem do boss
    try:
        boss_image = pygame.image.load(resource_path(BOSS_IMAGE_PATH)).convert_alpha()
        boss_image = pygame.transform.scale(boss_image, (100, 100))
    except Exception as e:
        print(f"AVISO: Não foi possível carregar '{BOSS_IMAGE_PATH}'. Usando um quadrado. Erro: {e}")
        boss_image = None

    # --- NOVO: Carrega a Musica do Boss ---
    if AUDIO_ENABLED:
        try:
            pygame.mixer.music.load(resource_path(BOSS_MUSIC_PATH))
            pygame.mixer.music.set_volume(0.5)
        except Exception as e:
            print(f"AVISO: nao foi possivel carregar '{BOSS_MUSIC_PATH}'. Sem musica. Erro: {e}")
    running = True
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

    boss_music_playing = False  # Flag de controle

    while running:
        clock.tick(FPS)

        events = pygame.event.get()
        for event in events:
            if event.type == pygame.QUIT:
                running = False
                if is_host and server:
                    server.server_running = False

        # --- ESTADO 0: MENU ---
        if game_mode_state == 0:
            draw_vertical_gradient(screen)
            title = title_font.render("ROUBE UMA GARRAFA DE AGUA", True, GOLD)
            draw_shadowed_text(screen, title, (SCREEN_WIDTH // 2, 150))
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

        # --- ESTADO 1: NOME ---
        elif game_mode_state == 1:
            draw_vertical_gradient(screen)
            draw_text_centered(screen, "Digite seu Nome (Max 10):", 200)
            draw_panel(screen, input_rect.inflate(18, 10), fill=(12, 16, 24), border=INPUT_BOX_COLOR_ACTIVE, radius=10)
            txt_surf = font.render(player_name_input, True, WHITE)
            screen.blit(txt_surf, (input_rect.x + 5, input_rect.y + 10))

            for event in events:
                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_RETURN and player_name_input.strip():
                        if is_host:
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
                            except:
                                print("Erro ao conectar no host local")
                                running = False
                        else:
                            game_mode_state = 2
                    elif event.key == pygame.K_BACKSPACE:
                        player_name_input = player_name_input[:-1]
                    elif len(player_name_input) < 10 and event.unicode.isprintable():
                        player_name_input += event.unicode
            pygame.display.flip()

        # --- ESTADO 2: CÓDIGO ---
        elif game_mode_state == 2:
            draw_vertical_gradient(screen)
            draw_text_centered(screen, "Digite o CÓDIGO da Sala:", 200)
            draw_text_centered(screen, "(Ex: C0A80105)", 500, small_font, GRAY)

            draw_panel(screen, input_rect.inflate(18, 10), fill=(12, 16, 24), border=INPUT_BOX_COLOR_ACTIVE, radius=10)
            txt_surf = font.render(code_input, True, WHITE)
            screen.blit(txt_surf, (input_rect.x + 5, input_rect.y + 10))

            if connection_status:
                draw_text_centered(screen, connection_status, 400, small_font, RED)

            for event in events:
                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_RETURN and code_input:
                        target_ip = code_to_ip(code_input)
                        if target_ip:
                            try:
                                connection_status = "Conectando..."
                                pygame.display.flip()
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

                        # --- LÓGICA DA MÚSICA DO BOSS ---
                        is_boss_fight = game_state.get("active_event") == "BOSS FIGHT"
                        if AUDIO_ENABLED and is_boss_fight and not boss_music_playing:
                            pygame.mixer.music.play(-1)  # Toca em loop
                            boss_music_playing = True
                        elif AUDIO_ENABLED and not is_boss_fight and boss_music_playing:
                            pygame.mixer.music.stop()
                            boss_music_playing = False
                        # --- FIM DA LÓGICA DA MÚSICA ---

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
                if n:
                    if not n.send({'keys': keys, 'interact': interact, 'use_item': use_item}):
                        print("Falha ao enviar dados.")
                        running = False
            except:
                running = False

            if game_state:
                redraw_window(screen, game_state, my_id)
            else:
                draw_vertical_gradient(screen)
                draw_text_centered(screen, "Sincronizando...", SCREEN_HEIGHT // 2)
                pygame.display.flip()

    if AUDIO_ENABLED:
        pygame.mixer.music.stop()
    if n:
        n.client.close()

    pygame.quit()
    sys.exit()


if __name__ == "__main__":
    main()
