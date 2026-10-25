import json
import os
from urllib.error import HTTPError
from urllib.request import Request, urlopen

api_key = ''
model = ''
env_file = '.env'
if os.path.exists(env_file):
    with open(env_file) as f:
        for line in f:
            if line.startswith('GROQ_API_KEY='):
                api_key = line.strip().split('=', 1)[1]
            if line.startswith('GROQ_MODEL='):
                model = line.strip().split('=', 1)[1]

req = Request(
    'https://api.groq.com/openai/v1/chat/completions',
    data=json.dumps({
        "model": model, 
        "messages": [{"role": "user", "content": "Return the json {'test': 'test'}"}],
        "response_format": {"type": "json_object"}
    }).encode(),
    headers={
        'Authorization': f'Bearer {api_key}', 
        'Content-Type': 'application/json',
        'User-Agent': 'Mozilla/5.0'
    },
    method='POST'
)
try:
    res = urlopen(req)
    print(res.read().decode())
except HTTPError as e:
    print(f"HTTP ERROR: {e.code}")
    print(e.read().decode())
except Exception as e:
    print(f"OTHER ERROR: {e}")
