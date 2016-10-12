#!/usr/bin/env python
import subprocess, requests, json, tarfile, os, boto3, argparse, logging
import xml.etree.ElementTree as ET


def setup_logger():
    """
    Configure the logger
    :return: logger
    """
    logger = logging.getLogger()
    logging.basicConfig()
    logger.setLevel(logging.INFO)
    logging.getLogger('requests').setLevel(logging.WARNING)
    logging.getLogger('botocore').setLevel(logging.WARNING)
    logging.getLogger('urllib3').setLevel(logging.WARNING)
    return logger


def make_tarfile(output_filename, source_dir):
    with tarfile.open(output_filename, "w:gz") as tar:
        tar.add(source_dir, arcname=os.path.basename(source_dir))


def backup(config, s3_bucket_name=None, prefix=None):
    logger = setup_logger()
    backup_endpoint = "{}/go/api/backups".format(config["host"])
    config_endpoint = "{}/go/api/admin/config.xml".format(config["host"])

    if s3_bucket_name is None:
        s3_bucket_name = config['bucket']
    else:
        logger.info("Changed bucket to %s", s3_bucket_name)
    if prefix is None:
        prefix = config["prefix"]
    else:
        logger.info("Changed prefix to %s", prefix)
    headers = {'Confirm': 'true', 'Accept': 'application/vnd.go.cd.v1+json'}

    r = requests.post(backup_endpoint, auth=(config["username"], config["password"]), headers=headers)
    response_object = json.loads(r.text)
    logger.debug("Json response")
    logger.debug(r.text)
    if not r.status_code == 200:
        logger.error("Non 200 response from server %s", r.text)
        exit(1)

    backup_path = response_object['path']
    backup_file = "{}/{}.tgz".format(config["backup_path"], os.path.basename(backup_path))
    if not os.path.exists(os.path.dirname(backup_file)):
        os.makedirs(os.path.dirname(backup_file))
        logger.info("Creating backup dir %s", os.path.dirname(backup_file))
    make_tarfile(backup_file, backup_path)
    logger.info("Created tarball from %s in %s", backup_path, backup_file)
    os.chmod(backup_file, 0600)
    s3 = boto3.resource('s3')
    bucket = s3.Bucket(s3_bucket_name)
    bucket.upload_file(backup_file, '{}/config/{}'.format(prefix, os.path.basename(backup_file)))
    logger.info("Uploaded %s to %s", backup_file, '{}/config/{}'.format(prefix, os.path.basename(backup_file)))
    os.remove(backup_file)
    r = requests.get(config_endpoint, auth=(config["username"], config["password"]))
    if not r.status_code == 200:
        logger.error("Non 200 response from server %s", r.text)
        exit(1)
    artifacts_dir = None
    for node in ET.ElementTree(ET.fromstring(r.text)).getroot().findall('server'):
        artifacts_dir = node.get('artifactsdir')
    if artifacts_dir is None:
        logger.error("Could not find artifacts dir %s", r.text)
        exit(1)
    command = ['service', 'go-server', 'stop']
    subprocess.call(command, shell=False)
    logger.info("Starting s3 sync")
    command = ['aws', 's3', 'sync', '{}/pipelines'.format(artifacts_dir),
               's3://{}/go_server/backups/pipelines'.format(s3_bucket_name)]
    subprocess.call(command, shell=False)
    logger.info("Done syncing %s to %s", '{}/pipelines'.format(artifacts_dir),
                's3://{}/go_server/backups/pipelines'.format(s3_bucket_name))
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
    config[args.key] = args.value
    with open(args.config_file, 'w') as outfile:
        json.dump(config, outfile)
    os.chmod(args.config_file, 0600)
elif args.which == "get":
    print config.get(args.key)
elif args.which == "backup":
    backup(config, s3_bucket_name=args.bucket, prefix=args.prefix)
