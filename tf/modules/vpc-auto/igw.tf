# VPC only needs one internet gateway

# Basically a router acting as the default gateway for public Internet access
# Nothing else to configure here. It's just an API-requested ISP.
resource "aws_internet_gateway" "public" {
  vpc_id = local.vpc_id
}
