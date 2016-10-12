#!/usr/bin/env python

import requests, json, tarfile, os, boto
from boto.s3.connection import S3Connection


from requests.auth import HTTPBasicAuth

url = 'http://ec2-54-218-128-110.us-west-2.compute.amazonaws.com:8153/go/api/backups'
headers = {'Confirm': 'true', 'Accept': 'application/vnd.go.cd.v1+json'}
s3_bucket_name = 'rvbgo-s3bucket-10utfkgtekakz'


def make_tarfile(output_filename, source_dir):
    with tarfile.open(output_filename, "w:gz") as tar:
        tar.add(source_dir, arcname=os.path.basename(source_dir))


r = requests.post(url, auth=('admin', 'admin'), headers=headers)
response_object = json.loads(r.text)

if not r.status_code == 200:
    print 'Something is wrong'
    print r.text
    exit(2)


backup_path = response_object['path']  # use this form for immediate fail
backup_dir = os.path.basename(backup_path)
backup_file = backup_dir+".tgz"

make_tarfile(backup_file, backup_path)


conn = S3Connection()
bucket = conn.get_bucket('s3_bucket_name')
key = boto.s3.key.Key(bucket, 'backup_file')

with open('backup_file') as f:
    key.send_file(f)

# print backup_path
# print r.text
# goal:
# curl 'http://ec2-54-218-128-110.us-west-2.compute.amazonaws.com:8153/go/api/backups' -u 'admin:admin' -H 'Confirm: true' -H 'Accept: application/vnd.go.cd.v1+json' -X POST
