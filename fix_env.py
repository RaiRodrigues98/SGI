import os
from dotenv import load_dotenv

path = '.env'

with open(path, 'rb') as f:
    raw = f.read()

print('Primeiros bytes:', raw[:25])
print('BOM presente:', raw.startswith(b'\xef\xbb\xbf'))

if raw.startswith(b'\xef\xbb\xbf'):
    with open(path, 'wb') as f:
        f.write(raw[3:])
    print('✅ BOM removido do .env')

load_dotenv(path, override=True)
server = os.getenv('DB_SERVER')
pwd = os.getenv('DB_PASSWORD')
print('DB_SERVER:', server)
print('DB_PASSWORD: carregada (tamanho=%d)' % (len(pwd) if pwd else 0))
