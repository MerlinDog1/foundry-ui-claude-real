import base64, json, urllib.request, urllib.error

base='http://127.0.0.1:8791'
with open('/data/data/com.termux/files/home/.openclaw/workspace/skills/foundry/wise_old_man.jpg','rb') as f:
    b64=base64.b64encode(f.read()).decode()

def post(path,obj):
    req=urllib.request.Request(base+path,data=json.dumps(obj).encode(),headers={'Content-Type':'application/json'})
    try:
        with urllib.request.urlopen(req) as r:
            print(path, r.read().decode())
    except urllib.error.HTTPError as e:
        print(path, 'ERR', e.code, e.read().decode())

post('/upload',{'dataUrl':'data:image/jpeg;base64,'+b64})
post('/style',{'style':'woodcut'})
post('/upscale',{'scale':4})
post('/trace',{'speckle':4,'format':'svg'})
