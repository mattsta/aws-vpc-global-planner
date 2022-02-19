# ref: https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/subnet
# Could also add:
#  - https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/default_subnet
#  - https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/default_security_group
resource "aws_subnet" "public" {
  for_each                            = var.subnets.public
  availability_zone_id                = each.key
  cidr_block                          = each.value
  vpc_id                              = local.vpc_id
  map_public_ip_on_launch             = true
  private_dns_hostname_type_on_launch = "ip-name"

  # only works if your CIDR block is ipv6
  # assign_ipv6_address_on_creation     = true

  # You can add IPv6 to the subnet with key:
  # ipv6_cidr_block = "::xx/64"
  # and even make it ipv6 only with:
  # ipv6_native = true

  tags = {
    "Name"     = "public/${each.key}"
    "Location" = each.key
  }
}


resource "aws_subnet" "internal" {
  # Note: due to how AWS network services work, a purely internal
  #       subnet can't access any public services like S3, ECR, SQS,
  #       etc, because AWS requires public routing for those services.
  #       If you want internal-only private-IP access for AWS services,
  #       you need to create a PrivateLink vpc endpoint for each service
  #       you want to access privately.
  #       And, of course, with AWS these PrivateLink endpoints cost
  #       $7.20 per month PER AZ _and_ PER SERVICE deployed PLUS $0.01/GB for
  #       all traffic over the private link interface:
  #       https://aws.amazon.com/privatelink/pricing/
  #       (So, if you enable PrivateLink for all the basic services of
  #        S3, SQS, ECR, Lambda, RDS, SSM, SES, SNS, CloudWatch in 40 AZs
  #        (https://docs.aws.amazon.com/vpc/latest/privatelink/integrated-services-vpce-list.html),
  #        then you'll pay 10 * $7.20 * 40 = almost $3,000 per month just for
  #        the privilege of using AWS's own infrastructure you're already
  #        paying for—looks like a bit of a scam. Just using public subnets
  #        for everything with good Network ACLs and Security Groups is
  #        a saner choice from a cost-benefit view.)
  for_each                            = var.subnets.internal
  availability_zone_id                = each.key
  cidr_block                          = each.value
  vpc_id                              = local.vpc_id
  map_public_ip_on_launch             = false
  private_dns_hostname_type_on_launch = "ip-name"

  tags = {
    "Name"     = "internal/${each.key}"
    "Location" = each.key
  }
}

# collect subnets for export
data "aws_subnets" "public" {
  filter {
    name   = "vpc-id"
    values = [local.vpc_id]
  }

  tags = {
    Name = "public/*"
  }

  # verify the resources are created before attempting to populate the data
  depends_on = [aws_subnet.public]
}

data "aws_subnets" "internal" {
  filter {
    name   = "vpc-id"
    values = [local.vpc_id]
  }

  tags = {
    Name = "internal/*"
  }

  depends_on = [aws_subnet.internal]
}

# You could add more subnets if needed, or you can just use this clean
# division of "public" and "internal" then partition your infrastructure
# with security groups and IAM assume_role features for various roles/policies.

# If you do want to configure PrivateLink, it looks something like:
# - https://github.com/terraform-aws-modules/terraform-aws-vpc/pull/534/commits/70b368d79d6a33275f81aa1ba1c0c02e8902cedd
# - https://github.com/aspectcapital/terraform-aws-vpc/commit/1976823bc128e02e10e6b4ea614049848e8c6c4e
