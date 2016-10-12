#!/usr/bin/env python
import subprocess, requests, json, tarfile, os, boto3, argparse
import xml.etree.ElementTree as ET


def make_tarfile(output_filename, source_dir):
    with tarfile.open(output_filename, "w:gz") as tar:
        tar.add(source_dir, arcname=os.path.basename(source_dir))


def backup(config, s3_bucket_name=None, prefix=None):
    backup_endpoint = "{}/go/api/backups".format(config["host"])
    config_endpoint = "{}/go/api/admin/config.xml".format(config["host"])

    if s3_bucket_name is None:
        s3_bucket_name = config['bucket']
    if prefix is None:
        prefix = config["prefix"]
    headers = {'Confirm': 'true', 'Accept': 'application/vnd.go.cd.v1+json'}

    r = requests.post(backup_endpoint, auth=(config["username"], config["password"]), headers=headers)
    response_object = json.loads(r.text)

    if not r.status_code == 200:
        print 'Something is wrong'
        print r.text
        exit(2)

    backup_path = response_object['path']  # use this form for immediate fail
    backup_file = "{}/{}.tgz".format(config["backup_path"], os.path.basename(backup_path))

    make_tarfile(backup_file, backup_path)
    os.chmod(backup_file, 0600)
    s3 = boto3.resource('s3')
    bucket = s3.Bucket(s3_bucket_name)
    bucket.upload_file(backup_file, '{}/config/{}'.format(prefix, os.path.basename(backup_file)))
    os.remove(backup_file)
    r = requests.post(config_endpoint, auth=(config["username"], config["password"]), headers=headers)
    artifacts_dir = None
    for node in ET.ElementTree(ET.fromstring(r.text)).getroot().findall('server'):
        artifacts_dir = node.get('artifactsdir')
    if artifacts_dir is None:
        print "Could not find artifacts dir"
        exit(2)
    command = ['service', 'go-server', 'stop']
    subprocess.call(command, shell=False)

    command = ['aws', 's3', 'sync', '{}/pipelines'.format(artifacts_dir),
               's3://{}/go_server/backups/pipelines'.format(s3_bucket_name)]
    subprocess.call(command, shell=False)

    command = ['service', 'go-server', 'start']
    subprocess.call(command, shell=False)


parser = argparse.ArgumentParser()

parser.add_argument("--config-file", help="Config file location", default="/etc/go-ctl.conf")

subparsers = parser.add_subparsers(help='commands')

set_parser = subparsers.add_parser("set", help="Sets config values")
set_parser.add_argument("--key", help="Key")
set_parser.add_argument("--value", help="Value")
set_parser.set_defaults(which='set')

get_parser = subparsers.add_parser("get", help="Get config value associated with key")
get_parser.set_defaults(which='get')
get_parser.add_argument('key', help='an integer for the accumulator')

backup_parser = subparsers.add_parser("backup", help="Backups the pipelines and config")
backup_parser.add_argument("--bucket", default=None, help="Bucket to use")
backup_parser.add_argument("--prefix", default=None, help="Bucket prefix")
backup_parser.set_defaults(which="backup")

args = parser.parse_args()

print args
config = {
    "backup_path": "/tmp/go-backups",
    "prefix": "go_server/backups",
    "host": "http://localhost:8153",
    "bucket": "rvbgo-s3bucket-10utfkgtekakz"
}
if os.path.isfile(args.config_file):
    with open(args.config_file) as data_file:
        config = json.load(data_file)

if args.which == "set":
    print "We now set {} = {}".format(args.key, args.value)
    config[args.key] = args.value
    with open(args.config_file, 'w') as outfile:
        json.dump(config, outfile)
    os.chmod(args.config_file, 0600)
elif args.which == "get":
    print "Now we get the value of {}".format(args.key)
    print config.get(args.key)
elif args.which == "backup":
    backup(config, s3_bucket_name=args.bucket, prefix=args.prefix)
