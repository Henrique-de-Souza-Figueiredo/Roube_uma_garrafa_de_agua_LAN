import pygame

pygame.init()

# --- Constantes do Jogo ---
SCREEN_WIDTH = 1280
SCREEN_HEIGHT = 720
FPS = 60
HEADER_LENGTH = 10
MAX_PLAYERS = 4
SPAWN_INTERVAL = 120
MONEY_INTERVAL = 60
SERVER_IP = "127.0.0.1"
PORT = 5555
conveyor_speed = 2

# --- NOVO: Configurações do Imposto ---
TAX_INTERVAL = 460 * FPS
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

# --- Raridades ---
RARITIES = ["Descartável", "Reutilizável", "Colecionável", "Premium", "Artefato"]
RARITY_COLORS = {
    "Descartável": (150, 150, 150), "Reutilizável": (0, 200, 0), "Colecionável": (0, 100, 255),
    "Premium": (150, 0, 200), "Artefato": (255, 150, 0)
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

# --- Configurações de Posição ---
CONVEYOR_Y = SCREEN_HEIGHT // 2 - 30
conveyor_rect_data = (0, CONVEYOR_Y, SCREEN_WIDTH, 60)
base_width, base_height = 250, 100
player_base_rects_data = [
    (50, 50, base_width, base_height), (SCREEN_WIDTH - 300, 50, base_width, base_height),
    (50, CONVEYOR_Y + 70, base_width, base_height), (SCREEN_WIDTH - 300, CONVEYOR_Y + 70, base_width, base_height)
]
player_start_pos = [(100, 250), (SCREEN_WIDTH - 130, 250), (100, 470), (SCREEN_WIDTH - 130, 470)]
player_colors = [RED, BLUE, LIME_GREEN, MAGENTA]
CONTROLS_TEXT = "Use: WASD (Mover) | F (Interagir) | G (Usar Item)"

# --- Loja de Packs ---
PACK_WIDTH, PACK_HEIGHT, PACK_Y, PACK_PADDING = 180, 80, SCREEN_HEIGHT - 100, 20
SHOP_PACKS_DATA = {
    "Descartável": {"cost": 10, "rect": (SCREEN_WIDTH // 2 - (PACK_WIDTH * 1.5 + PACK_PADDING), PACK_Y, PACK_WIDTH, PACK_HEIGHT)},
    "Reutilizável": {"cost": 30, "rect": (SCREEN_WIDTH // 2 - (PACK_WIDTH * 0.5), PACK_Y, PACK_WIDTH, PACK_HEIGHT)},
    "Colecionável": {"cost": 100, "rect": (SCREEN_WIDTH // 2 + (PACK_WIDTH * 0.5 + PACK_PADDING), PACK_Y, PACK_WIDTH, PACK_HEIGHT)}
}

# --- Loja de Upgrades ---
WEAPON_WIDTH, WEAPON_HEIGHT, WEAPON_Y, WEAPON_PADDING = 180, 80, SCREEN_HEIGHT - 220, 10
WEAPON_START_X = (SCREEN_WIDTH - (WEAPON_WIDTH * 3 + WEAPON_PADDING * 2)) // 2
WEAPON_SHOP_ITEMS_DATA = {
    "Tênis": {"cost": 100, "desc": "Velocidade +2", "rect": (WEAPON_START_X, WEAPON_Y, WEAPON_WIDTH, WEAPON_HEIGHT), "type": "passive"},
    "Bateria Extra": {"cost": 250, "desc": "Escudo +15s", "rect": (WEAPON_START_X + (WEAPON_WIDTH + WEAPON_PADDING), WEAPON_Y, WEAPON_WIDTH, WEAPON_HEIGHT), "type": "passive"},
    "Raio Orbital": {"cost": 500, "desc": "Atordoa(3s)+Devolve", "rect": (WEAPON_START_X + (WEAPON_WIDTH + WEAPON_PADDING) * 2, WEAPON_Y, WEAPON_WIDTH, WEAPON_HEIGHT), "type": "consumable"}
}

TROPHY_SHOP_COST = 25000
TROPHY_SHOP_RECT_DATA = ((SCREEN_WIDTH // 2) - 75, 65, 150, 70)

RESENHA_DURATION_SEC = 90
RESENHA_MIN_INTERVAL_SEC = 240
RESENHA_MAX_INTERVAL_SEC = 360
RESENHA_RARITY_WEIGHTS = [10, 10, 25, 35, 20]