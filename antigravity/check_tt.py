import os
from pymongo import MongoClient
from urllib.parse import quote_plus, urlparse, urlunparse
from dotenv import load_dotenv

load_dotenv(r'./.env')

def safe_encode_uri(uri):
    p = urlparse(uri)
    if p.username or p.password:
        auth = quote_plus(p.username or '')
        if p.password:
            auth += f':{quote_plus(p.password)}'
        netloc = f'{auth}@{p.hostname}' + (f':{p.port}' if p.port else '')
        return urlunparse((p.scheme, netloc, p.path, p.params, p.query, p.fragment))
    return uri

central = MongoClient(safe_encode_uri(os.getenv('MONGO_URI')))
cred = central['mongo_creds']['creds'].find_one({'domain': 'prod_jobiak_ai'}, {'_id': 0, 'mongo_uri': 1})
client = MongoClient(safe_encode_uri(cred['mongo_uri']))
db = client['prod_jobiak_ai']

emp_id = '6a86c3d7060e8f0b78b0dc66'
docs = list(db.jobiak_keyword_Updation.find({'employerId': emp_id, 'keywordType': 'titleToTitle'}, {'_id': 0, 'keyword': 1, 'title': 1}).limit(25))
print('Sample existing titleToTitle keywords:')
for d in docs:
    print(f"  {d['title']}: {d['keyword']}")
