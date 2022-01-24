# ============================================================================
# Configuration File for Network Generation
# ============================================================================

# ============================================================================
# Meta-Configuration
# ============================================================================


# As of this writing, AWS currently has 26 regions with 8 more announced
# for a near-term future total of 34 regions. Max regions of 50 should give
# us plenty of expansion room for future buildouts.
# Even though AWS has 26 regions, many are restricted (5 are US-Gov-Only) and
# others are in various areas of the world you may not need.
# Feel free to adjust "MAX_REGIONS" lower, but "MAX_REGIONS" should be the
# highest number of regions you EVER expect to use with this VPC configuration.
# For example, for my current account, even though there are 26 AWS regions,
# I only have 17 available without further opt-in or approvals.
# https://aws.amazon.com/about-aws/global-infrastructure/
MAX_REGIONS = 20

# 5 subnet blocks per VPC is a default AWS limit, so not worth fighting for increases yet.
# AWS lets us use a maximum of /16 per VPC subnet cidr block, so if we allocate 5 /16s we
# can use ~327,680 IP addresses per VPC (minus the usual 5 restricted addresses per AZ subnet).
MAX_CIDR_BLOCKS_PER_VPC = 5

# /19 gives us 8k IPs per AZ subnet created
AZ_SUBNET_PREFIX = 19

# If you need to use VPC Peering across multiple accounts, you want each of your
# VPCs to always have unique IP space across all accounts.
# You can increment ACCOUNT_OFFSET for each new account in your peer group so all your
# VPCs have non-overlapping IP space across every combination of account and region
# provisioned using this network planner.
# Note: adding more account offsets means you may need to reduce:
# - MAX_REGIONS
# - MAX_CIDR_BLOCKS_PER_VPC
# - AZ_SUBNET_PREFIX (larger number == more smaller subnets generated)
ACCOUNT_OFFSET = 0

# Subnet "categories" to provision per-VPC.
# Each subnet will use len(az) subnets of size AZ_SUBNET_PREFIX in each region.
# (e.g. uses 6 subnets in us-east-1, 2 subnets in us-west-1 per subnet type)
# Also note: logically, these subnet types should map to your infrastructure
# config for creating subnet network policies.
# In "AWS Speak"
#   - a "public" subnet has an internet gateway default route
#       - allows global inbound and outbound connections to each IP
#   - a "private" subnet has a NAT gateway as a default route
#       - allows global outbound connections but only internal inbound connections
#       - "private" in AWS speak isn't a security boundary since the network can still see the world.
#       - this type of network is basically useless for security as it doesn't restrict data flows
#         if you ever get popped via lateral movement inside your archietcture.
#   - and you can also create "internal" subnets with no global default route
#       - allows no global outbound and no global inbound, only internal private IP access.
#       - any public access would be mediated by defining custom proxies or tunnels on each server.
#       - but then you may need to provision some AWS services as PrivateLink relays since
#         e.g. you can't access most AWS services (ECR/S3/SQS/...) without a public IP to
#              hit their public API endpoints.
SUBNET_TYPES = ["public", "internal"]

# ============================================================================
# Regions to Create VPCs
# ============================================================================
# Provision Networks for these Regions.
# You can get a view of your regions mapped to locations at:
# https://console.aws.amazon.com/ec2globalview/home

# you can also view all regions easily at: https://awsregion.info/

# Note: after you generate your network, you can APPEND to this list, but DO NOT delete or move entries.
# You can comment out or delete or rearrange entries BEFORE you generate your network though.
# Deleting or moving entries will change the order your subnets are generated
# then all subsequent networks won't match prior configs.
# (These warnings only matter if you want to continue to generate the same region-ip mappings over time)
PROVISION_ORDER = [
    "us-east-1",  # VA
    "us-east-2",  # Ohio
    "us-west-1",  # CA (Northern)
    "us-west-2",  # OR
    "ca-central-1",  # Montreal
    "eu-north-1",  # Stockholm
    "eu-west-1",  # Ireland
    "eu-west-2",  # London
    "eu-west-3",  # Paris
    "eu-central-1",  # Frankfurt
    "ap-south-1",  # Mumbai
    "ap-northeast-1",  # Tokyo
    "ap-northeast-2",  # Seoul
    "ap-northeast-3",  # Osaka
    "ap-southeast-1",  # Singapore
    "ap-southeast-2",  # Sydney
    # "ap-southeast-3",  # Jakarta — REQUIRES OPT-IN
    # "eu-south-1", # Milan — REQUIRES OPT-IN
    # "ap-east-1", # HK — REQUIRES OPT-IN
    # "sa-east-1", # Sao Paulo
    # "cn-north-1", # Beijing — REQUIRES SPECIAL ACCOUNT
    # "cn-northwest-1", # Ningxia — REQUIRES SPECIAL ACCOUNT
    # "us-gov-east-1",
    # "us-gov-west-1",
    # "us-gov-secret-1",
    # "us-gov-topsecret-1",
    # "us-gov-topsecret-2",
    # "me-south-1", # Bahrain — REQUIRES OPT-IN
    # "af-south-1", # SA — REQUIRES OPT-IN
    # ONLY APPEND NEW REGIONS.
    # DO NOT CHANGE ORDER OF ANY ENABLED REGIONS ABOVE.
    # WE ALLOCATE VPC CIDR BLOCKS BASED ON POSITION IN THIS LIST,
    # SO IF POSITIONS CHANGE, ALL YOUR NETWORKS WILL RE-CREATE.
]

# Future Regions:
# "eu-east-1", # Spain
# "eu-central-2", # Zurich
# "ap-south-2", # Hyderabad
# "ap-southeast-3", # Melbourne
# "me-south-2", # UAE
# "eu-north-1", # Estonia
# "eu-south-1", # Cyprus
# "me-west-1", # Tel Aviv
# "ru-central-1", # RU ???
# "ap-southeast-4", # Auckland
# "ca-west-1", # Calgary
