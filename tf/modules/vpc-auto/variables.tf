variable "cidr_primary" {
  description = "Primary cidr block for VPC"
  type        = string
}

variable "cidr_secondaries" {
  description = "List of secondary cidr blocks for VPC"
  type        = list(string)
}

variable "cidr_secondaries_unused" {
  description = "List of unused secondary cidr blocks for VPC (for documentation only, not used by the deploy)"
  type        = list(string)
}

variable "subnets" {
  description = "Map of subnet names to map of region ids to subnet cidr networks"
  type        = map(map(string))
}

