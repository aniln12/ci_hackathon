import argparse

from awacs.helpers import trust
from awacs.aws import (
    Allow, Policy, Statement
)
from awacs import logs as awacs_logs
from troposphere import autoscaling, Ref, logs, iam

import parameters
import stack


stack = stack.StackTemplate()

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



r_script_runner_lc = stack.add_resource(autoscaling.LaunchConfiguration(
    'RScriptRunnerLC',
    IamInstanceProfile=Ref(instance_profile),
    ImageId=parameters.r_processing_ami,
    InstanceType='m4.large',
    SecurityGroups=[
        parameters.database_client_sg,
    ]
))

r_script_runner_asg = stack.add_resource(autoscaling.AutoScalingGroup(
    'RScriptRunnerASG',
    LaunchConfigurationName=Ref(r_script_runner_lc),
    MaxSize=2,
    MinSize=1,
    VPCZoneIdentifier=parameters.private_subnets.values(),
))

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
