output "aws_subnets_public" {
  value = toset(data.aws_subnets.public.ids)
}

output "aws_subnets_internal" {
  value = toset(data.aws_subnets.internal.ids)
}

output "aws_subnets_cidr_public" {
  value = [for s in aws_subnet.public : s.cidr_block]
}

output "aws_subnets_cidr_internal" {
  value = [for s in aws_subnet.internal : s.cidr_block]
}
