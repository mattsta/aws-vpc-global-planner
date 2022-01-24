locals {
  # Pattern borrowed from https://github.com/terraform-aws-modules/terraform-aws-vpc/blob/master/main.tf
  # Use `local.vpc_id` to give a hint to Terraform that subnets should be deleted before secondary CIDR blocks can be free!
  # TODO: investigate if this could also be defined by a depends on the subnets for all of the secondary cidr blocks?

  vpc_id = try(aws_vpc_ipv4_cidr_block_association.primary[0].vpc_id, aws_vpc.primary.id, "")
}

