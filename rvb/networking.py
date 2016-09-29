class Zone(object):
    def __init__(self, public=True):
        self.public = public
        self.subnets = []
        self.efs_mount_targets = []
        self.azs = []
