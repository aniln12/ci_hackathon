import argparse

from troposphere import autoscaling, Ref

import parameters
import stack


stack = stack.StackTemplate()

r_script_runner_lc = stack.add_resource(autoscaling.LaunchConfiguration(
    'RScriptRunnerLC',
    ImageId=parameters.r_processing_ami,
    InstanceType='m4.large',
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
