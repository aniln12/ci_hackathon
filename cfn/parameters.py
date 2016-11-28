private_subnets = {
    'us-east-1a': 'subnet-bb843de0',
    'us-east-1c': 'subnet-20b7330d',
    'us-east-1d': 'subnet-937c0bda',
    'us-east-1e': 'subnet-4106de7d',
}

public_subnets = {
    'us-east-1a': 'subnet-4d902916',
    'us-east-1c': 'subnet-65991d48',
    'us-east-1d': 'subnet-8b0275c2',
    'us-east-1e': 'subnet-fc16cec0',
}

r_processing_ami = 'ami-40d28157'
webapp_ami = 'ami-40d28157'


# It is assumed that the RDS instance is outside the purview of this cfn stack.
# Therefore provide a security group id that is "trusted" by RDS.
database_client_sg = 'sg-8dd5b1f0'

