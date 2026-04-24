import sqlite3
import os

db_path = "orgatec_sovereign.db"
if os.path.exists(db_path):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT id, data_auditoria, veredito_ia FROM laudos ORDER BY id DESC LIMIT 1;")
    row = cursor.fetchone()
    if row:
        print(f"ID: {row[0]}")
        print(f"Data: {row[1]}")
        print(f"Veredito: {row[2]}")
    else:
        print("Nenhum laudo encontrado.")
    conn.close()
else:
    print("Banco de dados não encontrado.")
