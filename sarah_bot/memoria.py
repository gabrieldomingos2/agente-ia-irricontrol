# memoria.py (v16.1 - Correção de Tipo)
import sqlite3
import json
import os
from datetime import datetime
from typing import Optional, Dict, Any, List

# Caminho para o banco de dados
DATA_DIR = "data"
DB_PATH = os.path.join(DATA_DIR, "sarah_bot.db")

def init_db():
    """Inicializa o banco de dados e cria/atualiza a tabela de clientes de forma idempotente."""
    os.makedirs(DATA_DIR, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS clientes (
        user_id TEXT PRIMARY KEY,
        nome TEXT,
        nome_fazenda TEXT,
        localizacao TEXT,
        perfil TEXT,
        pivos INTEGER,
        bombas INTEGER,
        estado_conversa TEXT,
        data_criacao TEXT,
        data_ultimo_contato TEXT,
        dor_mencionada TEXT,
        orcamento_enviado REAL,
        follow_up_enviado INTEGER,
        historico_conversa TEXT,
        tags_detectadas TEXT,
        lead_score INTEGER DEFAULT 0,
        video_enviado INTEGER DEFAULT 0,
        notificacao_enviada INTEGER DEFAULT 0,
        ultima_interacao_humana TEXT,
        lead_score_historico TEXT,
        estado_conversa_anterior TEXT,
        etapa_jornada TEXT 
    )
    """)
    
    colunas_existentes = [desc[1] for desc in cursor.execute("PRAGMA table_info(clientes)").fetchall()]
    
    colunas_a_adicionar = {
        'lead_score_historico': 'TEXT',
        'estado_conversa_anterior': 'TEXT',
        'etapa_jornada': 'TEXT'
    }

    for col, tipo in colunas_a_adicionar.items():
        if col not in colunas_existentes:
            cursor.execute(f"ALTER TABLE clientes ADD COLUMN {col} {tipo}")
            
    conn.commit()
    conn.close()

def dict_factory(cursor: sqlite3.Cursor, row: sqlite3.Row) -> Dict[str, Any]:
    """Converte uma linha do banco de dados em um dicionário."""
    d = {}
    for idx, col in enumerate(cursor.description):
        d[col[0]] = row[idx]
    return d

def get_cliente(user_id: str) -> Optional[Dict[str, Any]]:
    """Recupera os dados de um cliente específico do banco de dados."""
    user_id_str = str(user_id)
    try:
        conn = sqlite3.connect(DB_PATH, timeout=10)
        conn.row_factory = dict_factory
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM clientes WHERE user_id = ?", (user_id_str,))
        cliente = cursor.fetchone()
        conn.close()
        if cliente:
            for key in ['historico_conversa', 'tags_detectadas', 'lead_score_historico']:
                if cliente.get(key) and isinstance(cliente[key], str):
                    cliente[key] = json.loads(cliente[key])
                elif not cliente.get(key):
                    cliente[key] = []
        return cliente
    except (sqlite3.OperationalError, FileNotFoundError):
        return None

def recuperar_ou_criar_cliente(user_id: str, nome_telegram: str) -> Dict[str, Any]:
    """Busca um cliente. Se não existir, cria um registro e o retorna."""
    cliente = get_cliente(user_id)
    if cliente:
        return cliente
    
    now_iso = datetime.now().isoformat()
    novo_cliente = {
        "user_id": str(user_id),
        "nome": nome_telegram,
        "nome_fazenda": None,
        "localizacao": None,
        "perfil": "indefinido",
        "pivos": 0,
        "bombas": 0,
        "estado_conversa": "INICIANTE",
        "data_criacao": now_iso,
        "data_ultimo_contato": now_iso,
        "dor_mencionada": None,
        "orcamento_enviado": 0.0,
        "follow_up_enviado": 0,
        "historico_conversa": "[]",
        "tags_detectadas": "[]",
        "lead_score": 0,
        "video_enviado": 0,
        "notificacao_enviada": 0,
        "ultima_interacao_humana": None,
        "lead_score_historico": f'[{{"score": 0, "timestamp": "{now_iso}"}}]',
        "estado_conversa_anterior": None,
        "etapa_jornada": "DESCOBERTA"
    }

    colunas = ', '.join(novo_cliente.keys())
    placeholders = ', '.join(['?'] * len(novo_cliente))
    
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute(f"INSERT INTO clientes ({colunas}) VALUES ({placeholders})", tuple(novo_cliente.values()))
        conn.commit()
    
    novo_cliente['historico_conversa'] = []
    novo_cliente['tags_detectadas'] = []
    novo_cliente['lead_score_historico'] = [{"score": 0, "timestamp": now_iso}]
    return novo_cliente

def atualizar_cliente(user_id: str, dados_atualizados: Dict[str, Any]):
    """Atualiza um ou mais campos de um cliente no banco de dados."""
    user_id_str = str(user_id)
    dados_atualizados["data_ultimo_contato"] = datetime.now().isoformat()
    
    update_values = {}
    for key, value in dados_atualizados.items():
        if isinstance(value, (list, dict)):
            update_values[key] = json.dumps(value, ensure_ascii=False)
        else:
            update_values[key] = value

    update_fields = ", ".join([f"{key} = ?" for key in update_values])
    values = list(update_values.values()) + [user_id_str]
    query = f"UPDATE clientes SET {update_fields} WHERE user_id = ?"
    
    try:
        with sqlite3.connect(DB_PATH, timeout=10) as conn:
            cursor = conn.cursor()
            cursor.execute(query, tuple(values))
            conn.commit()
    except sqlite3.Error as e:
        print(f"Erro ao atualizar cliente {user_id_str}: {e}")

def adicionar_mensagem_historico(user_id: str, role: str, content: str):
    """Adiciona uma nova mensagem ao histórico de conversa de um cliente."""
    cliente = get_cliente(user_id)
    if not cliente: return

    historico = cliente.get("historico_conversa", [])
    historico.append({"role": role, "content": content})
    max_historico = 30
    historico = historico[-max_historico:]
    
    atualizar_cliente(user_id, {"historico_conversa": historico})

def deletar_cliente(user_id: str) -> bool:
    """Deleta um cliente do banco de dados."""
    user_id_str = str(user_id)
    try:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM clientes WHERE user_id = ?", (user_id_str,))
            conn.commit()
            return cursor.rowcount > 0
    except sqlite3.Error as e:
        print(f"Erro ao deletar cliente {user_id_str}: {e}")
        return False

def obter_clientes_ativos() -> List[Dict[str, Any]]:
    """Busca todos os clientes que não estão pausados ou com follow-up finalizado."""
    clientes_ativos = []
    try:
        with sqlite3.connect(DB_PATH, timeout=10) as conn:
            conn.row_factory = dict_factory
            cursor = conn.cursor()
            query = """
                SELECT * FROM clientes
                WHERE estado_conversa != 'PAUSADO_PELO_GERENTE' AND estado_conversa != 'FOLLOW_UP_FINALIZADO'
            """
            cursor.execute(query)
            clientes_ativos = cursor.fetchall()
    except sqlite3.Error as e:
        print(f"Erro ao buscar clientes ativos: {e}")
    return clientes_ativos
    
def obter_clientes_para_follow_up() -> List[Dict[str, Any]]:
    """Busca clientes que receberam um orçamento e estão em um estado que permite follow-up."""
    clientes_para_follow_up = []
    try:
        with sqlite3.connect(DB_PATH, timeout=10) as conn:
            conn.row_factory = dict_factory
            cursor = conn.cursor()
            query = """
                SELECT * FROM clientes
                WHERE orcamento_enviado > 0 AND follow_up_enviado < 2 AND estado_conversa != 'PAUSADO_PELO_GERENTE'
            """
            cursor.execute(query)
            clientes_para_follow_up = cursor.fetchall()
    except sqlite3.Error as e:
        print(f"Erro ao buscar clientes para follow-up: {e}")
    
    return clientes_para_follow_up