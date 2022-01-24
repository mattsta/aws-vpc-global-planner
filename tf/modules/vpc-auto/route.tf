resource "aws_route_table" "public" {
  vpc_id = local.vpc_id
}

resource "aws_route_table" "internal" {
  vpc_id = local.vpc_id
}

# For each public subnet, use 'public' route table (allows Internet access via default route)
resource "aws_route_table_association" "public" {
  for_each       = aws_subnet.public
  subnet_id      = each.value.id
  route_table_id = aws_route_table.public.id
}

# For each public subnet, use 'internal' route table (no defalt route defined, so no Internet access)
resource "aws_route_table_association" "internal" {
  for_each       = aws_subnet.internal
  subnet_id      = each.value.id
  route_table_id = aws_route_table.internal.id
}


# Give public subnet a default gateway by... default.
resource "aws_route" "public-v4" {
  route_table_id         = aws_route_table.public.id
  destination_cidr_block = "0.0.0.0/0"
  gateway_id             = aws_internet_gateway.public.id
}

resource "aws_route" "public-v6" {
  route_table_id              = aws_route_table.public.id
  destination_ipv6_cidr_block = "::/0"
  gateway_id                  = aws_internet_gateway.public.id
}

