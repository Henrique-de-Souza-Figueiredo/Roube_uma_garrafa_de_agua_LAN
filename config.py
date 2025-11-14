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
    "Descartável": (150, 150, 150), # Cinza
    "Reutilizável": (0, 200, 0),    # Verde
    "Colecionável": (0, 100, 255),  # Azul
    "Premium": (150, 0, 200),       # Roxo
    "Antiga": (139, 69, 19),        # Marrom/Bronze
    "Artefato": (255, 140, 0),      # Laranja Escuro
    "Cósmica": (0, 255, 255),       # Ciano Neon
    "Bomba": (139, 0, 0),           # Vermelho Sangue
    "Misteriosa": (255, 0, 255)     # Magenta
}

# Pesos para spawn na esteira (Normal) - 9 itens
RARITY_WEIGHTS = [40, 25, 15, 8, 4, 2, 1, 3, 2]

# Pesos para o Modo Resenha (Muito mais caos e itens caros) - 9 itens
RESENHA_RARITY_WEIGHTS = [5, 10, 20, 25, 15, 10, 5, 5, 5]

# --- Templates das Garrafas (LISTA EXPANDIDA) ---
BOTTLE_TEMPLATES = [
    # --- Descartável (Valor: $2-$8 | Renda: $0.1-$0.3) ---
    {"name": "Copo Plástico", "rarity": "Descartável", "value": 2.0, "income": 0.1},
    {"name": "Lata Amassada", "rarity": "Descartável", "value": 3.0, "income": 0.1},
    {"name": "Água da Torneira", "rarity": "Descartável", "value": 5.0, "income": 0.15},
    {"name": "Garrafa Pet", "rarity": "Descartável", "value": 6.0, "income": 0.2},
    {"name": "Saco de Leite", "rarity": "Descartável", "value": 4.0, "income": 0.1},
    {"name": "Caixa de Suco", "rarity": "Descartável", "value": 7.0, "income": 0.25},
    {"name": "Refrigerante Genérico", "rarity": "Descartável", "value": 8.0, "income": 0.3},

    # --- Reutilizável (Valor: $15-$30 | Renda: $0.5-$1.0) ---
    {"name": "Garrafa de Vidro", "rarity": "Reutilizável", "value": 15.0, "income": 0.5},
    {"name": "Squeeze de Academia", "rarity": "Reutilizável", "value": 18.0, "income": 0.6},
    {"name": "Cantil de Escoteiro", "rarity": "Reutilizável", "value": 22.0, "income": 0.7},
    {"name": "Garrafa de Alumínio", "rarity": "Reutilizável", "value": 25.0, "income": 0.8},
    {"name": "Growler de Cerveja", "rarity": "Reutilizável", "value": 28.0, "income": 0.9},
    {"name": "Jarra de Suco", "rarity": "Reutilizável", "value": 20.0, "income": 0.6},
    {"name": "Garrafa Térmica Velha", "rarity": "Reutilizável", "value": 30.0, "income": 1.0},

    # --- Colecionável (Valor: $50-$100 | Renda: $1.5-$3.0) ---
    {"name": "Vinho Importado", "rarity": "Colecionável", "value": 50.0, "income": 1.5},
    {"name": "Licor Fino", "rarity": "Colecionável", "value": 60.0, "income": 1.8},
    {"name": "Garrafa de Perfume", "rarity": "Colecionável", "value": 70.0, "income": 2.0},
    {"name": "Vodka de Luxo", "rarity": "Colecionável", "value": 80.0, "income": 2.2},
    {"name": "Azeite Trufado", "rarity": "Colecionável", "value": 90.0, "income": 2.5},
    {"name": "Poção Decorativa", "rarity": "Colecionável", "value": 55.0, "income": 1.6},
    {"name": "Garrafa de Coca 1950", "rarity": "Colecionável", "value": 100.0, "income": 3.0},

    # --- Premium (Valor: $150-$300 | Renda: $5.0-$10.0) ---
    {"name": "Champagne Francês", "rarity": "Premium", "value": 150.0, "income": 5.0},
    {"name": "Whisky 18 Anos", "rarity": "Premium", "value": 180.0, "income": 6.0},
    {"name": "Água dos Alpes", "rarity": "Premium", "value": 200.0, "income": 7.0},
    {"name": "Decanter de Cristal", "rarity": "Premium", "value": 250.0, "income": 8.5},
    {"name": "Garrafa de Ouro Líquido", "rarity": "Premium", "value": 300.0, "income": 10.0},
    {"name": "Vinho do Porto Real", "rarity": "Premium", "value": 220.0, "income": 7.5},

    # --- Antiga (Valor: $400-$800 | Renda: $15.0-$25.0) ---
    {"name": "Ânfora Grega", "rarity": "Antiga", "value": 400.0, "income": 15.0},
    {"name": "Vaso Ming", "rarity": "Antiga", "value": 500.0, "income": 18.0},
    {"name": "Cantil da 1ª Guerra", "rarity": "Antiga", "value": 450.0, "income": 16.0},
    {"name": "Frasco Egípcio", "rarity": "Antiga", "value": 600.0, "income": 20.0},
    {"name": "Garrafa Viking", "rarity": "Antiga", "value": 700.0, "income": 22.0},
    {"name": "Cabaça Indígena", "rarity": "Antiga", "value": 800.0, "income": 25.0},

    # --- Artefato (Valor: $1000-$2000 | Renda: $40.0-$80.0) ---
    {"name": "Fonte da Juventude", "rarity": "Artefato", "value": 1000.0, "income": 40.0},
    {"name": "Cálice Sagrado", "rarity": "Artefato", "value": 1200.0, "income": 50.0},
    {"name": "Lágrima de Fênix", "rarity": "Artefato", "value": 1500.0, "income": 60.0},
    {"name": "Hidromel de Odin", "rarity": "Artefato", "value": 1800.0, "income": 70.0},
    {"name": "Sangue de Dragão", "rarity": "Artefato", "value": 2000.0, "income": 80.0},

    # --- Cósmica (Valor: $5000-$10000 | Renda: $200.0-$500.0) ---
    {"name": "Matéria Escura", "rarity": "Cósmica", "value": 5000.0, "income": 200.0},
    {"name": "Poeira Estelar", "rarity": "Cósmica", "value": 6000.0, "income": 250.0},
    {"name": "Buraco Negro Portátil", "rarity": "Cósmica", "value": 8000.0, "income": 350.0},
    {"name": "Via Láctea Engarrafada", "rarity": "Cósmica", "value": 10000.0, "income": 500.0},

    # --- Especiais ---
    {"name": "BOMBA!", "rarity": "Bomba", "value": 0, "income": 0},
    {"name": "????", "rarity": "Misteriosa", "value": 0, "income": 0}
]

# --- Posições (VARIÁVEIS QUE FALTAVAM) ---
CONVEYOR_Y = SCREEN_HEIGHT // 2 - 30
conveyor_rect_data = (0, CONVEYOR_Y, SCREEN_WIDTH, 60)
base_width, base_height = 250, 100

player_base_rects_data = [
    (50, 50, base_width, base_height),
    (SCREEN_WIDTH - 300, 50, base_width, base_height),
    (50, CONVEYOR_Y + 70, base_width, base_height),
    (SCREEN_WIDTH - 300, CONVEYOR_Y + 70, base_width, base_height)
]
player_start_pos = [(100, 250), (SCREEN_WIDTH - 130, 250), (100, 470), (SCREEN_WIDTH - 130, 470)]
player_colors = [RED, BLUE, LIME_GREEN, MAGENTA]
CONTROLS_TEXT = "Use: WASD (Mover) | F (Interagir) | G (Usar Item)"

# --- Lojas (CORRIGIDO) ---
PACK_WIDTH, PACK_HEIGHT, PACK_Y, PACK_PADDING = 100, 60, SCREEN_HEIGHT - 120, 10
start_shop_x = (SCREEN_WIDTH - (5 * PACK_WIDTH + 4 * PACK_PADDING)) // 2

# CORRIGIDO: Chaves ("Descartável") batem com a lista RARITIES agora
SHOP_PACKS_DATA = {
    "Descartável":  {"cost": 10, "rect": (start_shop_x + (PACK_WIDTH + PACK_PADDING) * 0, PACK_Y, PACK_WIDTH, PACK_HEIGHT)},
    "Reutilizável": {"cost": 50, "rect": (start_shop_x + (PACK_WIDTH + PACK_PADDING) * 1, PACK_Y, PACK_WIDTH, PACK_HEIGHT)},
    "Colecionável": {"cost": 150, "rect": (start_shop_x + (PACK_WIDTH + PACK_PADDING) * 2, PACK_Y, PACK_WIDTH, PACK_HEIGHT)},
    "Premium":      {"cost": 400, "rect": (start_shop_x + (PACK_WIDTH + PACK_PADDING) * 3, PACK_Y, PACK_WIDTH, PACK_HEIGHT)},
    "Antiga":       {"cost": 1000, "rect": (start_shop_x + (PACK_WIDTH + PACK_PADDING) * 4, PACK_Y, PACK_WIDTH, PACK_HEIGHT)}
}

WEAPON_WIDTH, WEAPON_HEIGHT, WEAPON_Y, WEAPON_PADDING = 180, 80, SCREEN_HEIGHT - 220, 10
WEAPON_START_X = (SCREEN_WIDTH - (WEAPON_WIDTH * 3 + WEAPON_PADDING * 2)) // 2
WEAPON_SHOP_ITEMS_DATA = {
    "Tênis": {"cost": 100, "desc": "Velocidade +2", "rect": (WEAPON_START_X, WEAPON_Y, WEAPON_WIDTH, WEAPON_HEIGHT), "type": "passive"},
    "Bateria Extra": {"cost": 250, "desc": "Escudo +15s", "rect": (WEAPON_START_X + (WEAPON_WIDTH + WEAPON_PADDING), WEAPON_Y, WEAPON_WIDTH, WEAPON_HEIGHT), "type": "passive"},
    "Raio Orbital": {"cost": 500, "desc": "Atordoa(3s)+Devolve", "rect": (WEAPON_START_X + (WEAPON_WIDTH + WEAPON_PADDING) * 2, WEAPON_Y, WEAPON_WIDTH, WEAPON_HEIGHT), "type": "consumable"}
}

TROPHY_SHOP_COST = 25000
TROPHY_SHOP_RECT_DATA = ((SCREEN_WIDTH // 2) - 75, 65, 150, 70)

# --- Resenha (CORRIGIDO) ---
RESENHA_DURATION_SEC = 90
RESENHA_MIN_INTERVAL_SEC = 240
RESENHA_MAX_INTERVAL_SEC = 360
# CORRIGIDO: Removida a definição duplicada e errada.
# Esta lista é usada: RESENHA_RARITY_WEIGHTS = [5, 10, 20, 25, 15, 10, 5, 5, 5]

# --- Sistema de Códigos ---
def get_local_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except:
        return "127.0.0.1"

def ip_to_code(ip):
    try:
        packed = socket.inet_aton(ip)
        return packed.hex().upper()
    except:
        return "ERRO"

def code_to_ip(code):
    try:
        packed = bytes.fromhex(code)
        return socket.inet_ntoa(packed)
    except:
        return None