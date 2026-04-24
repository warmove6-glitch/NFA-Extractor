import os
from google import genai

def get_env_variable(chave):
    # Tenta carregar do config.env na raiz
    env_path = 'config.env'
    if os.path.exists(env_path):
        with open(env_path, 'r') as f:
            for line in f:
                if line.startswith(f'{chave}='):
                    return line.split('=', 1)[1].strip().replace('"', '').replace("'", "")
    return os.getenv(chave, '')

api_key = get_env_variable('GOOGLE_API_KEY')
if not api_key:
    print("Erro: GOOGLE_API_KEY não encontrada.")
    exit(1)

client = genai.Client(api_key=api_key)
try:
    print("Listando modelos...")
    for model in client.models.list():
        print(f"Nome: {model.name}, Supported: {model.supported_actions}")
except Exception as e:
    print(f"Erro ao listar modelos: {e}")
