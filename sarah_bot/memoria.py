# memoria.py
import sqlite3
import json
import os
from datetime import datetime
from typing import Optional, Dict, Any, List

# Caminho para o banco de dados
DATA_DIR = "data"
DB_PATH = os.path.join(DATA_DIR, "sarah_bot.db")

def init_db():
    """
    Inicializa o banco de dados e cria/atualiza a tabela de clientes.
    Adiciona colunas de forma idempotente para não quebrar bancos antigos.
    """
    os.makedirs(DATA_DIR, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Cria a tabela se ela não existir, já com os novos campos
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
        notificacao_enviada INTEGER DEFAULT 0, -- NOVO CAMPO
        ultima_interacao_humana TEXT -- NOVO CAMPO
    )
    """)
    
    # Adiciona colunas de forma segura para garantir retrocompatibilidade
    colunas_existentes = [desc[1] for desc in cursor.execute("PRAGMA table_info(clientes)").fetchall()]
    
    colunas_a_adicionar = {
        'nome_fazenda': 'TEXT',
        'localizacao': 'TEXT',
        'notificacao_enviada': 'INTEGER DEFAULT 0',
        'ultima_interacao_humana': 'TEXT'
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
    """
    Recupera os dados de um cliente específico do banco de dados.
    NOTA: O uso de sqlite3 em um ambiente concorrente (ex: web app com múltiplos threads)
    pode exigir estratégias de pooling de conexão ou uma fila de escrita para evitar "database is locked".
    Para um bot do Telegram com `python-telegram-bot`, que geralmente processa updates sequencialmente,
    o risco é baixo, mas é um ponto de atenção para escalabilidade futura.
    """
    user_id_str = str(user_id)
    try:
        conn = sqlite3.connect(DB_PATH, timeout=10) # Timeout para evitar lock
        conn.row_factory = dict_factory
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM clientes WHERE user_id = ?", (user_id_str,))
        cliente = cursor.fetchone()
        conn.close()
        if cliente:
            # Deserializa campos JSON
            if cliente.get('historico_conversa'):
                cliente['historico_conversa'] = json.loads(cliente['historico_conversa'])
            else:
                cliente['historico_conversa'] = []
                
            if cliente.get('tags_detectadas'):
                cliente['tags_detectadas'] = json.loads(cliente['tags_detectadas'])
            else:
                cliente['tags_detectadas'] = []
        return cliente
    except (sqlite3.OperationalError, FileNotFoundError):
        return None


def recuperar_ou_criar_cliente(user_id: str, nome_telegram: str) -> Dict[str, Any]:
    """Busca um cliente. Se não existir, cria um registro e o retorna."""
    cliente = get_cliente(user_id)
    if cliente:
        return cliente
    
    novo_cliente = {
        "user_id": str(user_id),
        "nome": nome_telegram,
        "nome_fazenda": None,
        "localizacao": None,
        "perfil": "indefinido",
        "pivos": 0,
        "bombas": 0,
        "estado_conversa": "INICIANTE",
        "data_criacao": datetime.now().isoformat(),
        "data_ultimo_contato": datetime.now().isoformat(),
        "dor_mencionada": None,
        "orcamento_enviado": 0.0,
        "follow_up_enviado": 0,
        "historico_conversa": "[]",
        "tags_detectadas": "[]",
        "lead_score": 0,
        "video_enviado": 0,
        "notificacao_enviada": 0,
        "ultima_interacao_humana": None,
    }

    colunas = ', '.join(novo_cliente.keys())
    placeholders = ', '.join(['?'] * len(novo_cliente))
    
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute(f"INSERT INTO clientes ({colunas}) VALUES ({placeholders})", tuple(novo_cliente.values()))
        conn.commit()
    
    # Retorna o dicionário com as listas vazias, e não o JSON string "[]"
    novo_cliente['historico_conversa'] = []
    novo_cliente['tags_detectadas'] = []
    return novo_cliente

def atualizar_cliente(user_id: str, dados_atualizados: Dict[str, Any]):
    """Atualiza um ou mais campos de um cliente no banco de dados."""
    user_id_str = str(user_id)
    dados_atualizados["data_ultimo_contato"] = datetime.now().isoformat()
    
    update_values = {}
    for key, value in dados_atualizados.items():
        if isinstance(value, (list, dict)):
            # Garante que o JSON é salvo sem caracteres de escape ASCII
            update_values[key] = json.dumps(value, ensure_ascii=False)
        else:
            update_values[key] = value

    # Constrói a query de forma dinâmica e segura
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
    if not cliente:
        print(f"Tentativa de adicionar mensagem para cliente inexistente: {user_id}")
        return

    historico = cliente.get("historico_conversa", [])
    if not isinstance(historico, list): # Verificação de segurança caso o dado esteja corrompido
        historico = []
        
    historico.append({"role": role, "content": content})
    
    # Limita o histórico às últimas 30 mensagens para performance e custo
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
            return cursor.rowcount > 0 # Retorna True se uma linha foi deletada
    except sqlite3.Error as e:
        print(f"Erro ao deletar cliente {user_id_str}: {e}")
        return False
    
def obter_clientes_para_follow_up() -> List[Dict[str, Any]]:
    """
    Busca clientes que receberam um orçamento e estão em um estado que permite follow-up.
    - O orçamento foi enviado (orcamento_enviado > 0).
    - O ciclo de follow-up não foi finalizado (follow_up_enviado < 2).
    """
    clientes_para_follow_up = []
    try:
        # Conexão com timeout para evitar locks em caso de concorrência
        with sqlite3.connect(DB_PATH, timeout=10) as conn:
            conn.row_factory = dict_factory
            cursor = conn.cursor()
            # Seleciona clientes que receberam orçamento e não estão em um estado final
            query = """
                SELECT user_id, nome, data_ultimo_contato, follow_up_enviado, dor_mencionada
                FROM clientes
                WHERE orcamento_enviado > 0 AND follow_up_enviado < 2
            """
            cursor.execute(query)
            clientes_para_follow_up = cursor.fetchall()
    except sqlite3.Error as e:
        print(f"Erro ao buscar clientes para follow-up: {e}")
    
    return clientes_para_follow_up
