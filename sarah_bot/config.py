# sarah_bot/config.py (v23.0 - Completo)
import os
from dotenv import load_dotenv

load_dotenv()

# --- Chaves de API e Tokens ---
BOT_TOKEN = os.getenv("BOT_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# --- Modelos de IA da OpenAI ---
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o")
OPENAI_ANALYSIS_MODEL = os.getenv("OPENAI_ANALYSIS_MODEL", "gpt-3.5-turbo")

# --- Configurações do Bot e Notificações ---
GERENTE_CHAT_ID = os.getenv("GERENTE_CHAT_ID")
VIDEO_DEMO_FILE_ID = os.getenv("VIDEO_DEMO_FILE_ID", "BAACAgEAAxkBAAIBM2iBG2JPXgTSZeig4lYeDDA28IwCAALRBQACVrQIRHM4RcdO3tx8NgQ")
# NOVO: Número do supervisor para contato via WhatsApp (formato internacional sem + ou espaços)
SUPERVISOR_WHATSAPP_NUMERO = os.getenv("SUPERVISOR_WHATSAPP_NUMERO", "5519997960052") # Ex: 55 DDD NUMERO

# --- Prazos e Informações do Produto ---
PRAZO_FABRICACAO_ENTREGA = os.getenv("PRAZO_FABRICACAO_ENTREGA", "30 dias") # NOVO

# --- GATILHO DE RECIPROCIDADE ---
GUIA_PDF_URL = os.getenv("GUIA_PDF_URL", "https://irricontrol.com.br/saf-sistema-de-alarme/")

# --- Configurações de Preço do Produto (SAF) ---
PRECO_SAF = float(os.getenv("PRECO_SAF", 11900))
PRECO_INSTALACAO = float(os.getenv("PRECO_INSTALACAO", 2500))
MENSALIDADE = float(os.getenv("MENSALIDADE", 150))

# --- Lógica de Negócio e Lead Scoring ---
LIMITE_LEAD_QUENTE = int(os.getenv("LIMITE_LEAD_QUENTE", 40))

# Pesos para o cálculo do Lead Score
TAG_WEIGHTS = {
    # PESOS POSITIVOS
    "INTENCAO_FECHAMENTO": 50,
    "DOR_FURTO_PROPRIO": 25,
    "PEDIDO_ORCAMENTO": 20,
    "DOR_INSEGURANCA_REGIAO": 15,
    "INFORMOU_QUANTIDADE": 10,
    "OBJECÃO_PRECO": 10,
    "PEDIDO_INFORMACOES_GERAIS": 5,
    "PEDIDO_VIDEO": 5,
    "OBJECÃO_ADIAMENTO": 2,
    "SAUDACAO": 1,
    
    # PESOS NEGATIVOS
    "APENAS_CURIOSIDADE": -15,
    "CONCORRENTE_MENCIONADO": -5,
    "FORA_DE_ESCOPO": -20,
}

# Validação para garantir que as chaves essenciais foram carregadas
if not BOT_TOKEN or not OPENAI_API_KEY or not GERENTE_CHAT_ID:
    raise ValueError("Variáveis de ambiente críticas (BOT_TOKEN, OPENAI_API_KEY, GERENTE_CHAT_ID) não foram definidas. Verifique seu arquivo .env")