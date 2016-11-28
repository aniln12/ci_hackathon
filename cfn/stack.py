import boto3
import botocore
import difflib
import json
import sys
import troposphere


class StackTemplate(troposphere.Template):
    def __init__(self, *args, **kargs):
        self.region = kargs.pop('region', 'us-east-1')
        self.stack_name = kargs.pop('stack_name', 'ci-visibility')
        troposphere.Template.__init__(self, *args, **kargs)

    def get_stack(self):
        sess = boto3.Session(region_name=self.region)
        client = sess.client('cloudformation')
        try:
            template = client.get_template(StackName=self.stack_name)
        except botocore.exceptions.ClientError, e:
            print 'Unable to get template:', e
            return None
        return template['TemplateBody']

    def print_diff(self):
        new = self.to_json(indent=4, sort_keys=True)
        old = json.dumps(self.get_stack(), indent=4, sort_keys=True)
        new = map(lambda x: x.rstrip() + "\n", new.split("\n"))
        old = map(lambda x: x.rstrip() + "\n", old.split("\n"))
        had_diff = False
        for line in difflib.unified_diff(old, new):
            had_diff = True
            sys.stdout.write(line)
        if not had_diff:
            print 'Files are identical.'

    def create_or_update(self):
        sess = boto3.Session(region_name=self.region)
        client = sess.client('cloudformation')
        try:
            client.describe_stacks(StackName=self.stack_name)
            stack_exists = True
        except botocore.exceptions.ClientError, e:
            # We really don't get a good error back here that's ready for a
            # machine to parse. Our best bet is that if we see a
            # ValidationError on DescribeStacks that hopefully that is AWS
            # telling us the stack doesn't exist. Because that makes sense?
            if e.response['Error']['Code'] != 'ValidationError':
                raise
            stack_exists = False

        if stack_exists:
            ensure_stack = client.update_stack
        else:
            ensure_stack = client.create_stack
        ensure_stack(
            StackName=self.stack_name,
            TemplateBody=self.to_json(),
            Capabilities=['CAPABILITY_IAM'],
        )
