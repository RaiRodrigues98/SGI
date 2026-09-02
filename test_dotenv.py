import os
from dotenv import load_dotenv

result = load_dotenv('.env', override=True)
print(f'load_dotenv retornou: {result}')
print(f'DB_SERVER: {os.getenv("DB_SERVER")}')
print(f'DB_DATABASE: {os.getenv("DB_DATABASE")}')
print(f'DB_USER: {os.getenv("DB_USER")}')
print(f'DB_DRIVER: {os.getenv("DB_DRIVER")}')
