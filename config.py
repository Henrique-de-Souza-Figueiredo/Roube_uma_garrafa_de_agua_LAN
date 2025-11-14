import pygame
import socket
import struct

pygame.init()

# --- Constantes do Jogo ---
SCREEN_WIDTH = 1280
SCREEN_HEIGHT = 720
FPS = 60
HEADER_LENGTH = 10
MAX_PLAYERS = 4
SPAWN_INTERVAL = 120
MONEY_INTERVAL = 60
PORT = 5555
conveyor_speed = 2

# --- Configurações do Imposto ---
TAX_INTERVAL = 180 * FPS
TAX_RATE = 0.20
TAX_MIN_THRESHOLD = 100.0

# --- Cores ---
RED = (255, 0, 0)
BLUE = (0, 0, 255)
LIME_GREEN = (50, 255, 50)
MAGENTA = (255, 0, 255)
GOLD = (255, 215, 0)
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
GRAY = (100, 100, 100)
DARK_GRAY = (30, 30, 30)
YELLOW = (200, 200, 0)
SHOP_BLUE = (0, 70, 150)
WEAPON_SHOP_RED = (150, 0, 0)
SHIELD_BLUE = (100, 100, 255)
GREEN = (0, 200, 0)
INPUT_BOX_COLOR_INACTIVE = pygame.Color('lightskyblue3')
INPUT_BOX_COLOR_ACTIVE = pygame.Color('dodgerblue2')

# --- Raridades e Templates ---
RARITIES = ["Descartável", "Reutilizável", "Colecionável", "Premium", "Antiga", "Artefato", "Cósmica", "Bomba", "Misteriosa"]

RARITY_COLORS = {
    "Descartável": (150, 150, 150), "Reutilizável": (0, 200, 0), "Colecionável": (0, 100, 255),
    "Premium": (150, 0, 200), "Antiga": (139, 69, 19), "Artefato": (255, 140, 0),
    "Cósmica": (0, 255, 255), "Bomba": (139, 0, 0), "Misteriosa": (255, 0, 255)
}
RARITY_WEIGHTS = [40, 25, 15, 8, 4, 2, 1, 3, 2]
RESENHA_RARITY_WEIGHTS = [5, 10, 20, 25, 15, 10, 5, 5, 5]

BOTTLE_TEMPLATES = [
    # (Cole sua lista longa de garrafas aqui)
    {"name": "Copo Plástico", "rarity": "Descartável", "value": 2.0, "income": 0.1},
    {"name": "Água da Torneira", "rarity": "Descartável", "value": 5.0, "income": 0.15},
    {"name": "Garrafa de Vidro", "rarity": "Reutilizável", "value": 15.0, "income": 0.5},
    {"name": "Squeeze de Academia", "rarity": "Reutilizável", "value": 18.0, "income": 0.6},
    {"name": "Vinho Importado", "rarity": "Colecionável", "value": 50.0, "income": 1.5},
    {"name": "Vodka de Luxo", "rarity": "Colecionável", "value": 80.0, "income": 2.2},
    {"name": "Champagne Francês", "rarity": "Premium", "value": 150.0, "income": 5.0},
    {"name": "Whisky 18 Anos", "rarity": "Premium", "value": 180.0, "income": 6.0},
    {"name": "Ânfora Grega", "rarity": "Antiga", "value": 400.0, "income": 15.0},
    {"name": "Vaso Ming", "rarity": "Antiga", "value": 500.0, "income": 18.0},
    {"name": "Fonte da Juventude", "rarity": "Artefato", "value": 1000.0, "income": 40.0},
    {"name": "Cálice Sagrado", "rarity": "Artefato", "value": 1200.0, "income": 50.0},
    {"name": "Matéria Escura", "rarity": "Cósmica", "value": 5000.0, "income": 200.0},
    {"name": "Poeira Estelar", "rarity": "Cósmica", "value": 6000.0, "income": 250.0},
    {"name": "BOMBA!", "rarity": "Bomba", "value": 0, "income": 0},
    {"name": "????", "rarity": "Misteriosa", "value": 0, "income": 0}
]

# --- Posições e Lojas ---
CONVEYOR_Y = SCREEN_HEIGHT // 2 - 30
conveyor_rect_data = (0, CONVEYOR_Y, SCREEN_WIDTH, 60)
base_width, base_height = 250, 100
player_base_rects_data = [
    (50, 50, base_width, base_height), (SCREEN_WIDTH - 300, 50, base_width, base_height),
    (50, CONVEYOR_Y + 70, base_width, base_height), (SCREEN_WIDTH - 300, CONVEYOR_Y + 70, base_width, base_height)
]
player_start_pos = [(100, 250), (SCREEN_WIDTH - 130, 250), (100, 470), (SCREEN_WIDTH - 130, 470)]
player_colors = [RED, BLUE, LIME_GREEN, MAGENTA]
CONTROLS_TEXT = "Use: WASD (Mover) | F (Interagir) | G (Usar Item/Atacar)"

PACK_WIDTH, PACK_HEIGHT, PACK_Y, PACK_PADDING = 100, 60, SCREEN_HEIGHT - 120, 10
start_shop_x = (SCREEN_WIDTH - (5 * PACK_WIDTH + 4 * PACK_PADDING)) // 2
SHOP_PACKS_DATA = {
    "Descartável": {"cost": 10, "rect": (start_shop_x, PACK_Y, PACK_WIDTH, PACK_HEIGHT)},
    "Reutilizável": {"cost": 50, "rect": (start_shop_x + 110, PACK_Y, PACK_WIDTH, PACK_HEIGHT)},
    "Colecionável": {"cost": 150, "rect": (start_shop_x + 220, PACK_Y, PACK_WIDTH, PACK_HEIGHT)},
    "Premium": {"cost": 400, "rect": (start_shop_x + 330, PACK_Y, PACK_WIDTH, PACK_HEIGHT)},
    "Antiga": {"cost": 1000, "rect": (start_shop_x + 440, PACK_Y, PACK_WIDTH, PACK_HEIGHT)}
}

WEAPON_WIDTH, WEAPON_HEIGHT, WEAPON_Y, WEAPON_PADDING = 180, 80, SCREEN_HEIGHT - 220, 10
WEAPON_START_X = (SCREEN_WIDTH - (WEAPON_WIDTH * 3 + WEAPON_PADDING * 2)) // 2
WEAPON_SHOP_ITEMS_DATA = {
    "Tênis": {"cost": 100, "desc": "Velocidade +2", "rect": (WEAPON_START_X, WEAPON_Y, WEAPON_WIDTH, WEAPON_HEIGHT), "type": "passive"},
    "Bateria Extra": {"cost": 250, "desc": "Escudo +15s", "rect": (WEAPON_START_X + (WEAPON_WIDTH + WEAPON_PADDING), WEAPON_Y, WEAPON_WIDTH, WEAPON_HEIGHT), "type": "passive"},
    "Raio Orbital": {"cost": 500, "desc": "Atordoa(3s)+Devolve", "rect": (WEAPON_START_X + (WEAPON_WIDTH + WEAPON_PADDING) * 2, WEAPON_Y, WEAPON_WIDTH, WEAPON_HEIGHT), "type": "consumable"}
}

TROPHY_SHOP_COST = 100000
TROPHY_SHOP_RECT_DATA = ((SCREEN_WIDTH // 2) - 75, 65, 150, 70)

# --- Eventos ---
RESENHA_DURATION_SEC = 90
RESENHA_MIN_INTERVAL_SEC = 240
RESENHA_MAX_INTERVAL_SEC = 360

# Eventos Normais
EVENT_TYPES = ["WASSUUUP", "LA ELE"] # Lista de eventos comuns
EVENT_DURATION_FRAMES = 20 * FPS
EVENT_INTERVAL_FRAMES = 120 * FPS # Chance a cada 2 minutos

# Evento Raro: Boss Fight
BOSS_EVENT_MIN_INTERVAL_SEC = 300 # Chance a cada 5-10 minutos
BOSS_EVENT_MAX_INTERVAL_SEC = 600
BOSS_MAX_DURATION_FRAMES = 180 * FPS # 3 minutos para derrotar
BOSS_IMAGE_PATH = "boss.png"
BOSS_MUSIC_PATH = "boss_music.mp3"
BOSS_MAX_HEALTH = 200
BOSS_MOVE_SPEED = 2
BOSS_STOMP_COOLDOWN = 3 * FPS
BOSS_REWARD_MONEY = 5000

# --- Rede ---
def get_local_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except: return "127.0.0.1"
def ip_to_code(ip):
    try: return socket.inet_aton(ip).hex().upper()
    except: return "ERRO"
def code_to_ip(code):
    try: return socket.inet_ntoa(bytes.fromhex(code))
    except: return None