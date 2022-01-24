resource "aws_vpc" "primary" {
  cidr_block                       = var.cidr_primary
  assign_generated_ipv6_cidr_block = true
  enable_dns_hostnames             = true
  enable_dns_support               = true
  instance_tenancy                 = "default"

  tags = {
    "Name" = "primary"
  }
}

resource "aws_vpc_ipv4_cidr_block_association" "primary" {
  for_each   = toset(var.cidr_secondaries)
  cidr_block = each.key

  # note: don't use local.vpc_id here because it would create a circular reference
  vpc_id = aws_vpc.primary.id
}

# Default Network ACL for all Subnets.
# You can add more rules here if you are cloning the repo for your own management,
# or you can create new individual Network ACLs and assign them to subnets as needed.
# Also see this option if you want to block the default ACL and always require custom
# per-subnet Network ACL attachments:
# https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/default_network_acl#example-deny-all-traffic-to-any-subnet-in-the-default-network-acl
resource "aws_default_network_acl" "default" {
  default_network_acl_id = aws_vpc.primary.default_network_acl_id

  # All subnets will belong to this resource by default, so the state updates
  # on the AWS-side with all subnet_ids in this VPC unattatched to any other Network ACL,
  # but we don't want other subnet<->ACL bindings to cause this resource to change.
  lifecycle {
    ignore_changes = [subnet_ids]
  }

  # default ACL allows ALL INBOUND
  # (control further security via Security Groups attached to ENIs directly)
  ingress {
    protocol   = -1
    rule_no    = 100
    action     = "allow"
    cidr_block = "0.0.0.0/0"
    from_port  = 0
    to_port    = 0
  }

  # default ACL allows ALL OUTBOUND
  egress {
    protocol   = -1
    rule_no    = 100
    action     = "allow"
    cidr_block = "0.0.0.0/0"
    from_port  = 0
    to_port    = 0
  }
}
