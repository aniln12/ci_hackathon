import base64
import copy
import argparse

from awacs.helpers import trust
from awacs.aws import (
    Allow, Policy, Statement
)
from awacs import logs as awacs_logs
from troposphere import autoscaling, Ref, logs, iam, ec2, GetAtt, Tags, Output, Join
from troposphere import elasticloadbalancingv2 as elb
from troposphere import cloudfront, waf

import parameters
import stack
import yaml


cloudwatch_logs_agent_cfg = """\
[general]
state_file = /var/awslogs/state/agent-state

[/var/log/syslog]
file = /var/log/syslog
log_group_name = conservationintl
log_stream_name = {instance_id}-syslog
datetime_format = %b %d %H:%M:%S

[/var/log/uwsgi/conservationintl.log]
file = /var/log/uwsgi/conservationintl.log
log_group_name = conservationintl
log_stream_name = {instance_id}-uwsgi
datetime_format = %b %d %H:%M:%S
"""

awslogs_systemd = """\
[Unit]
After=cloud-final.target
Requires=networking.service

[Service]
ExecStart=/var/awslogs/bin/awslogs-agent-launcher.sh
"""

# This is disgusting. It should be done at AMI creation time using packer.
user_data = {
    'apt_sources': [
        {
            'source': 'deb http://cran.case.edu/bin/linux/ubuntu xenial/',
            'keyid': 'E084DAB9',
        },
    ],
    'write_files': [
        {
            'content': cloudwatch_logs_agent_cfg,
            'path': '/tmp/awslogs.conf',
        },
        {
            'content': awslogs_systemd,
            'path': '/lib/systemd/system/awslogs.service',
        }
    ],
    'runcmd': [
        ['/usr/bin/sudo', '/usr/bin/apt', 'update'],
        # Need python installed before we run python down there. The packages
        # directive apparently runs after runcmd. Gah.
        ['/usr/bin/sudo', '/usr/bin/apt', 'install', '-y',
            'python', 'python-setuptools', 'python-pip', 'python-psycopg2',
            'unzip'],
        [
            '/usr/bin/curl',
            'https://s3.amazonaws.com/aws-cloudwatch/downloads/latest/awslogs-agent-setup.py',
            '-o',
            '/tmp/awslogs-agent-setup.py',
        ],
        [
            '/usr/bin/sudo',
            '/usr/bin/python',
            '/tmp/awslogs-agent-setup.py',
            '--region', 'us-east-1',
            '-n', '-c', '/tmp/awslogs.conf',
        ],
        ['/bin/systemctl', 'daemon-reload'],
        ['/usr/bin/pip', 'install', 'pandas', 'sqlalchemy', 'psycopg2'],
        [
            '/usr/bin/curl', '-L', '-O',
            'https://github.com/xsmaster/ci_hackathon/archive/master.zip'
        ],
        ['/usr/bin/unzip', 'master.zip',],
        ['/usr/bin/sudo', 'ci_hackathon-master/setup.sh',],
    ]
}
if 'packages' not in user_data:
    user_data['packages'] = []

r_packages = [
    "ggplot2",
    "knitr",
    "dplyr",
    "lubridate",
    "reshape2",
    "DT",
    "maps",
    "mapdata",
    "RPostgreSQL",
    "zoo",
    "lme4",
    "lmerTest",
]

r_server_user_data = copy.deepcopy(user_data)
for package in r_packages:
    line = ['R', '-q', '-e', '"install.packages(\'%s\', repos=\'http://cran.rstudio.com/\')"' % (package,)]
    r_server_user_data['runcmd'].append(line)

r_server_user_data['runcmd'].append(
    ['/usr/bin/sudo', '/usr/bin/apt', 'install', '-y', 'libpq-dev', 'r-base']
)


webserver_user_data = copy.deepcopy(user_data)
webserver_user_data['packages'].extend([
    'nginx',
    'uwsgi',
    'uwsgi-plugin-python',
])

stack = stack.StackTemplate()

stack.add_resource(logs.LogGroup(
    'LogGroupConservationIntl',
    LogGroupName='conservationintl',
))

logs_writer_policy_doc = Policy(
    Version="2012-10-17",
    Statement=[
        Statement(
            Action=[
                awacs_logs.CreateLogGroup,
                awacs_logs.CreateLogStream,
                awacs_logs.PutLogEvents,
                awacs_logs.DescribeLogStreams,
            ],
            Effect=Allow,
            Resource=["arn:aws:logs:*:*:*"],
        ),
    ]
)

logs_writer_policy = iam.Policy(
    'LogsWriterPolicy',
    PolicyName='LogsWriterPolicy',
    PolicyDocument=logs_writer_policy_doc
)

our_only_role = stack.add_resource(iam.Role('OurOnlyRole',
    AssumeRolePolicyDocument=trust.get_default_assumerole_policy(),
    Policies=[logs_writer_policy],
))
instance_profile = stack.add_resource(iam.InstanceProfile(
    'OurOnlyInstanceProfile',
    Roles=[Ref(our_only_role)],
))

default_instance_sg = stack.add_resource(ec2.SecurityGroup(
    'DefaultInstanceSG',
    GroupDescription='Default group for instances to be in',
    SecurityGroupIngress=[
        ec2.SecurityGroupRule(
            IpProtocol='6',
            CidrIp='172.31.22.10/32',
            ToPort=22,
            FromPort=22,
        )
    ]
))

elb_sg = stack.add_resource(ec2.SecurityGroup(
    'elbSG',
    GroupDescription='elb sg',
    SecurityGroupIngress=[
        ec2.SecurityGroupRule(
            IpProtocol='6',
            CidrIp='0.0.0.0/0',
            ToPort=80,
            FromPort=80,
        )
    ]
))

web_sg = stack.add_resource(ec2.SecurityGroup(
    'webSG',
    GroupDescription='web sg',
    SecurityGroupIngress=[
        ec2.SecurityGroupRule(
            IpProtocol='6',
            SourceSecurityGroupId=GetAtt(elb_sg, 'GroupId'),
            ToPort=80,
            FromPort=80,
        )
    ]
))

r_script_runner_lc = stack.add_resource(autoscaling.LaunchConfiguration(
    'RScriptRunnerLC',
    IamInstanceProfile=Ref(instance_profile),
    ImageId=parameters.r_processing_ami,
    InstanceType='m4.large',
    UserData=base64.b64encode('#cloud-config\n' + yaml.safe_dump(r_server_user_data)),
    KeyName='bvanzant',
    SecurityGroups=[
        parameters.database_client_sg,
        GetAtt(default_instance_sg, 'GroupId'),
    ]
))

r_script_runner_asg = stack.add_resource(autoscaling.AutoScalingGroup(
    'RScriptRunnerASG',
    LaunchConfigurationName=Ref(r_script_runner_lc),
    MaxSize=2,
    MinSize=1,
    Tags=autoscaling.Tags(Name='RScriptRunner'),
    VPCZoneIdentifier=parameters.private_subnets.values(),
))


ourelb = stack.add_resource(elb.LoadBalancer(
    "ApplicationElasticLB",
    Name="ApplicationElasticLB",
    Scheme="internet-facing",
    Subnets=parameters.public_subnets.values(),
    SecurityGroups=[GetAtt(elb_sg, 'GroupId')],
))

webserver_target_group = stack.add_resource(elb.TargetGroup(
    "WebserverTarget",
    Port=80,
    Protocol='HTTP',
    VpcId=parameters.vpc_id,
))

webserver_listener = stack.add_resource(elb.Listener(
    "WebserverListener",
    Port=80,
    Protocol='HTTP',
    LoadBalancerArn=Ref(ourelb),
    DefaultActions=[elb.Action(
        Type="forward",
        TargetGroupArn=Ref(webserver_target_group),
    )]
))



webserver_lc = stack.add_resource(autoscaling.LaunchConfiguration(
    'WebServerLC',
    IamInstanceProfile=Ref(instance_profile),
    ImageId=parameters.r_processing_ami,
    InstanceType='m4.large',
    UserData=base64.b64encode('#cloud-config\n' + yaml.safe_dump(webserver_user_data)),
    KeyName='bvanzant',
    SecurityGroups=[
        parameters.database_client_sg,
        GetAtt(default_instance_sg, 'GroupId'),
        GetAtt(web_sg, 'GroupId'),
    ]
))

web_server_asg = stack.add_resource(autoscaling.AutoScalingGroup(
    'WebServerASG',
    LaunchConfigurationName=Ref(webserver_lc),
    MaxSize=2,
    MinSize=2,
    Tags=autoscaling.Tags(Name='webserver'),
    TargetGroupARNs=[Ref(webserver_target_group)],
    VPCZoneIdentifier=parameters.private_subnets.values(),
    DependsOn=ourelb.name,
))

sql_injection_rule = stack.add_resource(waf.SqlInjectionMatchSet(
    'SqlInjectionRule',
    Name='VisSqlInjectionRule',
    SqlInjectionMatchTuples=[
        waf.SqlInjectionMatchTuples(
            FieldToMatch=waf.FieldToMatch(
                Type="QUERY_STRING",
            ),
            TextTransformation="URL_DECODE",
        ),
    ],
))

waf = stack.add_resource(waf.WebACL(
    'VisWaf',
    DefaultAction=waf.Action(Type='ALLOW'),
    Name='VisibilityWaf',
    MetricName='VisibilityWaf',
    #Rules=[
        #waf.Rules(
            #Action=waf.Action(Type='BLOCK'),
            #Priority=1,
            #RuleId=Ref(sql_injection_rule),
        #),
    #],
))

cloudfront_distribution = stack.add_resource(cloudfront.Distribution(
    'visibilitycloudfront',
    DistributionConfig=cloudfront.DistributionConfig(
        WebACLId=Ref(waf),
        Origins=[
            cloudfront.Origin(
                Id='apiv1',
                DomainName='applicationelasticlb-208988572.us-east-1.elb.amazonaws.com',
                CustomOriginConfig=cloudfront.CustomOrigin(
                    HTTPPort="80",
                    OriginProtocolPolicy="http-only",
                ),
            ),
            cloudfront.Origin(
                Id='staticv1',
                DomainName='cihackathon.s3.amazonaws.com',
                S3OriginConfig=cloudfront.S3Origin(),
            ),
        ],
        DefaultCacheBehavior=cloudfront.DefaultCacheBehavior(
            TargetOriginId="staticv1",
            ForwardedValues=cloudfront.ForwardedValues(
                QueryString=False,
            ),
            ViewerProtocolPolicy="allow-all",
            MinTTL=1,
            MaxTTL=60,
        ),
        CacheBehaviors=[
            cloudfront.CacheBehavior(
                TargetOriginId='apiv1',
                ForwardedValues=cloudfront.ForwardedValues(
                    QueryString=True,
                ),
                ViewerProtocolPolicy="allow-all",
                MinTTL=1,
                MaxTTL=60,
                PathPattern='/api/v1/*',
            ),
        ],
        Enabled=True,
        HttpVersion='http1.1',
    ),
))
stack.add_output([
    Output(
        "VisibilityUrl",
        Value=Join("", ["http://", GetAtt(cloudfront_distribution, "DomainName")])
    )
])




if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--print-stack',
        action='store_true', help='Print the template. Take no other action.')
    parser.add_argument('--diff-stack',
        action='store_true', help='Diff the current template with the one currently running.')
    args = parser.parse_args()

    if args.print_stack:
        print stack.to_json()
    elif args.diff_stack:
        stack.print_diff()
    else:
        stack.create_or_update()
