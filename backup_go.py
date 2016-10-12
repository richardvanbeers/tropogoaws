#!/usr/bin/env python

import requests
import json
from requests.auth import HTTPBasicAuth

url = 'http://ec2-54-218-128-110.us-west-2.compute.amazonaws.com:8153/go/api/backups'

headers = {'Confirm': 'true', 'Accept': 'application/vnd.go.cd.v1+json'}


r = requests.post(url, auth=('admin', 'admin'), headers=headers)
response_object = json.loads(r.text)

if not r.status_code == 200:
    print 'Something is wrong'
    print r.text
    exit(2)

response_object = json.loads(r.text)

backup_path = response_object['path']  # use this form for immediate fail

print backup_path

# print r.text
# goal:
# curl 'http://ec2-54-218-128-110.us-west-2.compute.amazonaws.com:8153/go/api/backups' -u 'admin:admin' -H 'Confirm: true' -H 'Accept: application/vnd.go.cd.v1+json' -X POST