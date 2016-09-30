from troposphere import (Template, ec2, GetAZs, Select, Ref, Parameter, Base64,
                         Join, GetAtt, Output, efs, ecr)

from troposphere.iam import (Role, InstanceProfile)
# from troposphere.ecr import Repository
from awacs.aws import (Allow, Policy, Principal, Statement)
from awacs.sts import (AssumeRole)
from rvb.networking import Zone

t = Template()

t.add_description("CF Troposphere template")
t.add_version("2010-09-09")

instance_type = t.add_parameter(Parameter(
    "InstanceType",
    Type="String",
    Default="t2.micro",
    AllowedValues=["t2.micro", "t2.medium"],
    Description="Instance types",
))

management_ip = t.add_parameter(Parameter(
    "ManagementIP",
    Type="String",
    Description="Your white listed IP"
))

ami = t.add_parameter(Parameter(
    "Ami",
    Type="String",
    Description="Ami",
    Default="ami-665b8406"
))

go_pipelines = t.add_resource(efs.FileSystem(
    "GoPipelines"
))

repository = t.add_resource(ecr.Repository(
    "GoRegistry"
))

docker_role = t.add_resource(Role(
    "DockerRole",
    AssumeRolePolicyDocument=Policy(
        Version="2012-10-17",
        Statement=[
            Statement(
                Effect=Allow,
                Action=[AssumeRole],
                Principal=Principal("Service", ["ec2.amazonaws.com"])
            )
        ]
    )
))

docker_instanceprofile = t.add_resource(InstanceProfile(
    "Dockerprofile",
    Roles=[Ref(docker_role)]
))

my_vpc = t.add_resource(ec2.VPC(
    "GoVpc",
    CidrBlock="10.0.0.0/16",
    EnableDnsSupport=True,
    EnableDnsHostnames=True
))

public_sg = t.add_resource(ec2.SecurityGroup(
    "RvbGoSG",
    VpcId=Ref(my_vpc),
    GroupDescription="rvb go test SG",
    SecurityGroupIngress=[
        ec2.SecurityGroupRule(
            IpProtocol="tcp",
            FromPort="22",
            ToPort="22",
            CidrIp=Ref(management_ip),
        ),
        ec2.SecurityGroupRule(
            IpProtocol="tcp",
            FromPort="8153",
            ToPort="8154",
            CidrIp=Ref(management_ip),
        )
    ]
))

public_mount_target_sg = t.add_resource(ec2.SecurityGroup(
    "MountTargetSG",
    VpcId=Ref(my_vpc),
    GroupDescription="efs SG",
    SecurityGroupIngress=[
        ec2.SecurityGroupRule(
            IpProtocol="tcp",
            FromPort="2049",
            ToPort="2049",
            SourceSecurityGroupId=Ref(public_sg)
            # CidrIp=Ref(management_ip),
        ),
    ]

))

public_zone = Zone(public=True)

for k, v in [('a', 0), ('b', 1), ('c', 2)]:
    public_zone.subnets.append(t.add_resource(ec2.Subnet(
        "PublicSubnet{}".format(k.capitalize()),
        AvailabilityZone=Select(v, GetAZs()),
        CidrBlock="10.0.{}.0/24".format(v),
        MapPublicIpOnLaunch=public_zone.public,
        VpcId=Ref(my_vpc),
    )))
    public_zone.efs_mount_targets.append(t.add_resource(efs.MountTarget(
        "PublicMountTarget{}".format(k.capitalize()),
        FileSystemId=Ref(go_pipelines),
        SubnetId=Ref(public_zone.subnets[-1]),
        SecurityGroups=[Ref(public_mount_target_sg)]
    )))

my_igw = t.add_resource(ec2.InternetGateway(
    "GoIgw",
))

my_igw_attachement = t.add_resource(ec2.VPCGatewayAttachment(
    "GoIgwAttachment",
    VpcId=Ref(my_vpc),
    InternetGatewayId=Ref(my_igw),
))

route_table = t.add_resource(ec2.RouteTable(
    "RouteTable",
    VpcId=Ref(my_vpc),
))

public_route = t.add_resource(ec2.Route(
    "PublicRoute",
    DependsOn=[my_igw_attachement.title],
    DestinationCidrBlock="0.0.0.0/0",
    GatewayId=Ref(my_igw),
    RouteTableId=Ref(route_table),
))

for s in public_zone.subnets:
    t.add_resource(ec2.SubnetRouteTableAssociation(
        "Assoc{}".format(s.title),
        RouteTableId=Ref(route_table),
        SubnetId=Ref(s)

    ))

az = 0

mount_point = "/efs"
mount_options = "nfsvers=4.1,rsize=1048576,wsize=1048576,hard,timeo=600,retrans=2"
mount_cmd = "mount -t nfs4 -o"
mount_target = Join(".", [
    public_zone.subnets[az].AvailabilityZone,
    Ref(go_pipelines),
    "efs",
    Ref("AWS::Region"),
    "amazonaws.com:/"
])
full_mount_cmd = Join(" ", [
    mount_cmd,
    mount_options,
    mount_target,
    mount_point
])

instance = t.add_resource(ec2.Instance(
    "InstanceAs",
    InstanceType=Ref(instance_type),
    KeyName="rvb-test",
    ImageId=Ref(ami),  # Amazon Linux AMI
    IamInstanceProfile=Ref(docker_instanceprofile),
    SecurityGroupIds=[Ref(public_sg)],
    SubnetId=Ref(public_zone.subnets[az]),
    UserData=Base64(
        Join(
            "\n",
            [
                "#!/bin/bash -x",
                # Join(" ", ["echo", Ref("AWS::Region")]),
                # Join(" ", ["echo", Ref("AWS::StackName")]),
                # Join(" ", ["echo", Ref(instance_type)]),
                # Join(" ", ["echo", Ref(my_vpc)]),
                # Join(" ", ["echo", GetAtt(my_vpc, "DefaultSecurityGroup")]),
                "yum -y install nfs-utils",
                "mkdir -p {}".format(mount_point),
                full_mount_cmd

            ]
        )
    )

))
t.add_output(Output(
    "PubIp",
    Value=GetAtt(instance, "PublicIp")
))

t.add_output(Output(
    "PubDns",
    Value=GetAtt(instance, "PublicDnsName")
))

goal = "mount -t nfs4 -o  $(curl -s http://169.254.169.254/latest/meta-data/placement/availability-zone).file-system-ID.efs.aws-region.amazonaws.com:/ efs"

print t.to_json()
