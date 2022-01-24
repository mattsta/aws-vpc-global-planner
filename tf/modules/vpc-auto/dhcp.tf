# We aren't creating custom DHCP options yet, but for reference:
# - https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/vpc_dhcp_options
# - https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/vpc_dhcp_options_association

# Basically only useful if we want our services to have a default DNS search domain
# or if we want to override the default AWS DNS or NTP servers.

# Also see: https://github.com/terraform-aws-modules/terraform-aws-vpc/blob/6f89db5c3094656f8f40e6d3c9d7d6b124597de9/main.tf#L87-L112
