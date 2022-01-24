#!/usr/bin/env python

import boto3
import ipaddress
import pandas as pd
from loguru import logger
import pprint as pp
import itertools
import pathlib
import random
import json

from collections import defaultdict
from typing import Optional

# For terraform generation
import time
import hashlib
import datetime
import subprocess  # for terraform fmt cleanup

# Only import PROVISION_ORDER from config file because it doesn't make sense as a command line parameter
try:
    from myregions import PROVISION_ORDER
except:
    PROVISION_ORDER = [
        "us-east-1",
        "us-east-2",
        "us-west-1",
        "us-west-2",
        "ca-central-1",
        "eu-north-1",
        "eu-west-1",
        "eu-west-2",
        "eu-west-3",
        "eu-central-1",
        "eu-south-1",
        "ap-south-1",
        "ap-northeast-1",
        "ap-northeast-2",
        "ap-northeast-3",
        "ap-southeast-1",
        "ap-southeast-2",
        "ap-southeast-3",
        "ap-east-1",
        "sa-east-1",
        # "cn-north-1",
        # "cn-northwest-1",
        # "us-gov-east-1",
        # "us-gov-west-1",
        # "us-gov-secret-1",
        # "us-gov-topsecret-1",
        # "us-gov-topsecret-2",
        # "me-south-1",
        # "af-south-1",
        # ONLY APPEND NEW REGIONS.
        # DO NOT CHANGE ORDER OF ANY REGIONS ABOVE.
        # WE ALLOCATE VPC BLOCKS BASED ON POSITION IN THIS LIST,
        # SO IF POSITIONS CHANGE, ALL YOUR NETWORKS WILL RE-CREATE.
    ]

SUBNET_TYPES = ["public", "internal"]


class GlobalVPCBuilder:
    """Generate a non-overlaping subnet configuration for all AZs in all Regions."""

    def __init__(
        self,
        max_regions: int = None,
        max_cidr_blocks_per_vpc: int = None,
        az_subnet_prefix: int = None,
        account_offset: int = None,
        subnet_types: list[str] = ["public", "internal"],
        regions_cache: str = "cache.myregions.json",
        regions_result: str = "planned.myregions.json",
    ):

        self._establish_config(
            max_regions,
            max_cidr_blocks_per_vpc,
            az_subnet_prefix,
            account_offset,
            subnet_types,
        )

        self.regions_cache = pathlib.Path(regions_cache)
        self.regions_result = pathlib.Path(regions_result)

    def _load_region_az_mapping(self):
        """Load cached (or generate live) region to AZ mapping your AWS account/profile can see."""

        # region is:
        # region-name => {'ZoneName': [zones-by-name], 'ZoneId': [zones-by-id]}
        self.myregions: dict[str, dict[str, list[str]]] = dict()

        if self.regions_cache.is_file():
            logger.info("[{}] Loading cached myregions...", self.regions_cache)
            try:
                self.myregions = json.loads(self.regions_cache.read_text())
                # logger.info("Regions are: {}", self.myregions)
            except:
                # error loading, fetch new
                logger.error("Loading cache failed, will fetch live regions again.")
                pass

        # read cache, all done here
        if self.myregions:
            return

        # else, didn't have a cache so create a new one
        logger.info("Discovering live regions for account...")
        # Regions we have access to using the current profile
        s = boto3.session.Session()
        rs = s.get_available_regions("ec2")

        for r in rs:
            # yeah, we're using pandas to fix the JSON here; seems overkill but is also easy.
            try:
                logger.info("[{}] Asking for zones...", r)
                self.myregions[r] = pd.json_normalize(
                    boto3.client("ec2", region_name=r).describe_availability_zones()[
                        "AvailabilityZones"
                    ]
                )[["ZoneName", "ZoneId"]].to_dict("list")
            except:
                # regions we don't have access to will crash and be omitted
                logger.warning("[{}] Failed to access!", r)
                pass

        json.dump(self.myregions, self.regions_cache.open("w"), indent=4)
        logger.info("Cached regions at {}", self.regions_cache)

    def _establish_config(
        self,
        max_regions,
        max_cidr_blocks_per_vpc,
        az_subnet_prefix,
        account_offset,
        subnet_types,
    ):
        """Process combination of command line arguments, config file settings, and defaults."""

        # This tri-level config looks weird, but we want to handle:
        #   - config settings from python config file ("myregions.py")
        #   - config settings from command line overriding python config
        #   - reasonable defaults if no config provided
        # Sure, we could use env var overrides and a config provider, but also no.

        # See sample myregions.py for each setting documentation.
        if max_regions is None:
            try:
                from myregions import MAX_REGIONS

                self.MAX_REGIONS = MAX_REGIONS
            except:
                self.MAX_REGIONS = 25
        else:
            self.MAX_REGIONS = max_regions

        if max_cidr_blocks_per_vpc is None:
            try:
                from myregions import MAX_CIDR_BLOCKS_PER_VPC

                self.MAX_CIDR_BLOCKS_PER_VPC = MAX_CIDR_BLOCKS_PER_VPC
            except:
                self.MAX_CIDR_BLOCKS_PER_VPC = 5
        else:
            self.MAX_CIDR_BLOCKS_PER_VPC = max_cidr_blocks_per_vpc

        if az_subnet_prefix is None:
            try:
                from myregions import AZ_SUBNET_PREFIX

                self.AZ_SUBNET_PREFIX = AZ_SUBNET_PREFIX
            except:
                self.AZ_SUBNET_PREFIX = 19
        else:
            self.AZ_SUBNET_PREFIX = az_subnet_prefix

        if account_offset is None:
            try:
                from myregions import ACCOUNT_OFFSET

                self.ACCOUNT_OFFSET = ACCOUNT_OFFSET
            except:
                self.ACCOUNT_OFFSET = 0
        else:
            self.ACCOUNT_OFFSET = account_offset

        if subnet_types is None:
            try:
                from myregions import SUBNET_TYPES

                self.SUBNET_TYPES = SUBNET_TYPES
            except:
                self.SUBNET_TYPES = ["private", "internal"]
        else:
            self.SUBNET_TYPES = subnet_types

        logger.info(
            "Configuring with MAX_REGIONS={} CONFIGURED_REGIONS={} MAX_CIDR_BLOCKS_PER_VPC={}",
            self.MAX_REGIONS,
            len(PROVISION_ORDER),
            self.MAX_CIDR_BLOCKS_PER_VPC,
        )

        logger.info(
            "Configuring with AZ_SUBNET_PREFIX={} ACCOUNT_OFFSET={} SUBNET_TYPES={}",
            self.AZ_SUBNET_PREFIX,
            self.ACCOUNT_OFFSET,
            self.SUBNET_TYPES,
        )

    def build_subnets(self, shuffle: bool = False):
        """Build a globally non-overlapping subnet configuration for every region and every AZ."""
        self._load_region_az_mapping()

        # 10/8 gives us 2^(32-8) = 2^24 = 16 million IPs to allocate globally.
        # You could adjust this to other restricted IP space, but other assumptions in
        # the network generator may break.
        # i.e. you may need to shrink self.MAX_REGIONS and self.MAX_CIDR_BLOCKS_PER_VPC and self.AZ_SUBNET_PREFIX
        GLOBAL_SUPERNET = ipaddress.ip_network("10.0.0.0/8")

        # ================================================================================
        # Establish preconditions
        # ================================================================================
        # Start at 10.2.0.0 because AWS doesn't like users inside (10.0.0.0/15) (10.0.0.0/16 or 10.1.0.0/16)
        START_OFFSET = 2 + (
            self.ACCOUNT_OFFSET * self.MAX_REGIONS * self.MAX_CIDR_BLOCKS_PER_VPC
        )

        VPC_CIDR_BLOCK_HIGHEST_OFFSET = START_OFFSET + (
            self.MAX_REGIONS * self.MAX_CIDR_BLOCKS_PER_VPC
        )

        logger.info(
            "[regions max {}] [regions configured {}] HIGHEST VPC CIDR BLOCK PROVISIONED: 10.{}.0.0/16",
            self.MAX_REGIONS,
            len(self.myregions),
            VPC_CIDR_BLOCK_HIGHEST_OFFSET,
        )
        logger.info(
            "You have {} more /16s remaining (you can allocate {:,.2f} more VPCs since each allocates {} /16s)",
            255 - VPC_CIDR_BLOCK_HIGHEST_OFFSET,
            (255 - VPC_CIDR_BLOCK_HIGHEST_OFFSET) / self.MAX_CIDR_BLOCKS_PER_VPC,
            self.MAX_CIDR_BLOCKS_PER_VPC,
        )
        logger.info(
            "You can repeat this config into {:,.2f} more accounts ({} unused VPC-level CIDR blocks)",
            (255 - VPC_CIDR_BLOCK_HIGHEST_OFFSET)
            / (self.MAX_REGIONS * self.MAX_CIDR_BLOCKS_PER_VPC),
            (255 - VPC_CIDR_BLOCK_HIGHEST_OFFSET),
        )

        assert (
            VPC_CIDR_BLOCK_HIGHEST_OFFSET < 256
        ), f"Your total subnet request ({VPC_CIDR_BLOCK_HIGHEST_OFFSET}) is larger than the 10.0.0.0/8 capacity"

        # Also we start at 10.2.0.0/16 just because.
        # AWS restricts VPC subnet blocks to /16 maximum, but we can allocate up to 5 per VPC.
        SUBNETS = list(GLOBAL_SUPERNET.subnets(new_prefix=16))[START_OFFSET:]

        # Use math helpers to calculate the number of /19s (by default) we can fit into self.MAX_CIDR_BLOCKS_PER_VPC * /16
        # (e.g. 5 * (/19 subnets fitting inside a /16) == 5 * (8) == 40),
        # so using our defaults, we can have 40 subnets in each VPC without running out of our optimistic IP allocation.
        # [LOGGING / DEBUGGING ONLY]
        physical_subnets_per_vpc = (
            len(
                list(
                    ipaddress.ip_network("10.0.0.0/16").subnets(
                        new_prefix=self.AZ_SUBNET_PREFIX
                    )
                )
            )
            * self.MAX_CIDR_BLOCKS_PER_VPC
        )
        logger.info(
            "Current settings can allocate {} /{} subnets ({:,} total IPs per subnet) per VPC ({:,} IPs in each VPC)",
            physical_subnets_per_vpc,
            self.AZ_SUBNET_PREFIX,
            2 ** (32 - self.AZ_SUBNET_PREFIX),
            (2 ** (32 - self.AZ_SUBNET_PREFIX)) * physical_subnets_per_vpc,
        )

        # Start handing out self.MAX_CIDR_BLOCKS_PER_VPC for each region...
        # AWS limits each VPC subnet block to /16, but you can have up to 5 total subnet blocks in a VPC without quota increases.
        # https://docs.aws.amazon.com/vpc/latest/userguide/VPC_Subnets.html

        # First map subnets into ALL REGIONS even if we don't use them:
        if shuffle:
            # introduce chaos
            random.shuffle(SUBNETS)

        self.ALL_REGIONS_SUBNETS = {
            region: [SUBNETS.pop(0) for _ in range(self.MAX_CIDR_BLOCKS_PER_VPC)]
            for region in PROVISION_ORDER
        }

        # ================================================================================
        # Plan the subnets across all zones inside all regions
        # ================================================================================
        # Then use the regions we *do* have access to for creating in-region subnets in each availability zone we can see.
        subnets_per_region = defaultdict(dict)
        for region in PROVISION_ORDER:
            # Skip regions we discovered but don't have configured
            if region not in self.myregions:
                logger.error(
                    "[{}] Skipping region because not available in account!", region
                )
                continue

            zone_maps = self.myregions[region]
            subnet_blocks_for_vpc = self.ALL_REGIONS_SUBNETS[region]
            primary_subnet_block = subnet_blocks_for_vpc[0]
            secondary_subnet_blocks = subnet_blocks_for_vpc[1:]

            # Each requested az subnet of (SUBNET_TYPES * len(zones)) comes from the 5 subnets in the region sequentially.
            # Each az subnet is getting a /19 (8k IP addresses) by default (but can be adjusted by AZ_SUBNET_PREFIX above)
            contiguous_zone_subnets = list(
                itertools.chain(
                    *[
                        x.subnets(new_prefix=self.AZ_SUBNET_PREFIX)
                        for x in subnet_blocks_for_vpc
                    ]
                )
            )

            subnets_per_zone = {}
            subnets_per_region[region]["subnets"] = subnets_per_zone
            zones_legacy = zone_maps["ZoneName"]
            zones_direct = list(sorted(zone_maps["ZoneId"]))

            assert len(zones_legacy) == len(
                zones_direct
            ), "How are your zones not matching?"

            # A quick diversion to check if zones actually exist or if we need to make fake placeholders.
            # Note: this simple z[-1] to get the trailing integer will break if a region ever has > 9 zones
            zones_order = [int(z[-1]) for z in zones_direct]
            longest = max(zones_order)
            perfect_order = list(range(1, len(zones_order) + 1))
            zones_direct_synthetic_all = [
                zones_direct[0][:-1] + str(x) for x in range(1, longest + 1)
            ]

            if zones_order != perfect_order:
                logger.warning(
                    "[{}] Region has zone gaps: {} (allocating for future use anyway)",
                    region,
                    zones_direct,
                    zones_direct_synthetic_all,
                )

            for st in SUBNET_TYPES:
                # this is also self-correcting if we exhaust our subnet allocation because if we
                # run out of pre-calculated subnets, the .pop() will throw an exception then planning fails.
                try:
                    # reserve IP ranges for missing zones too becasue some regions have non-contiguous
                    # AZ definitions (like ['usw1-az1', 'usw1-az3'] but expected ['usw1-az1', 'usw1-az2', 'usw1-az3'])
                    zones = {
                        z: contiguous_zone_subnets.pop(0)
                        for z in zones_direct_synthetic_all
                    }

                    # now only return _actual_ zones if they exist in the actual configuration
                    subnets_per_zone[st] = {
                        z: subnets for z, subnets in zones.items() if z in zones_direct
                    }

                    # save last subnet to see if we can leave some secondary subnets unprovisioned
                    last_subnet = subnets_per_zone[st][zones_direct[-1]]
                except:
                    logger.error(
                        "Failed to provision all subnets for SUBNET_TYPES: {}",
                        SUBNET_TYPES,
                    )
                    logger.warning(
                        "Reduce number of subnet types generated or modify self.AZ_SUBNET_PREFIX so more subnets can be allocated"
                    )
                    raise

            # ================================================================================
            # Calculate unused subnets for reporting
            # ================================================================================
            subnets_per_zone["_unused"] = contiguous_zone_subnets

            # default keep is 0 because if no secondary vpc subnet blocks match,
            # we don't add any of them since we didn't use their IP space for allocations.
            keep_secondary_upto = 0

            for i, s in enumerate(reversed(secondary_subnet_blocks)):
                # 'last_subnet' is the HIGHEST internal subnet for this VPC,
                # so find the last used VPC subnet block holding the HIGHEST subnet,
                # then drop higher VPC subnet blocks not being used or allocated into yet.
                # logger.info("Checking {} => {}", s, last_subnet)
                if s.overlaps(last_subnet):
                    # logger.warning("[{}] Stopping at: {} {} => {}", region, -i, s, last_subnet)

                    # only record if NOT zero. If ZERO then we used ALL so keep ALL.
                    if i:
                        keep_secondary_upto = -i

                    # found a result, so stop.
                    break

            secondary_subnets_in_use = secondary_subnet_blocks[:keep_secondary_upto]
            unused_secondary_subnets = secondary_subnet_blocks[keep_secondary_upto:]

            if secondary_subnets_in_use:
                logger.info(
                    "[{}] Using {} secondary subnet!",
                    region,
                    len(secondary_subnets_in_use),
                )

            subnets_per_region[region]["vpc"] = dict(
                primary=primary_subnet_block,
                secondary=secondary_subnets_in_use,
                _unused=unused_secondary_subnets,
            )
            subnets_per_region[region]["ZoneId"] = zones_direct

        # Save planned result to file...
        json.dump(
            subnets_per_region,
            self.regions_result.open("w"),
            default=str,
            indent=4,
        )

        logger.info("[{}] Saved network plan", self.regions_result)

    def generate_terraform_config(
        self, profile="default", output="suggested.myregions.tf", include_unused=True
    ):
        """Generate a Terraform config for all regions and all subnets pre-planed by 'build_subnets'"""
        if not self.regions_result.is_file():
            self.build_subnets()

        # load plan from file instead of using live result because live
        # result (subnets_per_region from build_subnets()) has IPv4Network
        # instances instead of strings for subnet descriptions.
        src = self.regions_result.read_bytes()
        subnets_per_region = json.loads(src)
        base = pathlib.Path("./tf").mkdir(parents=True, exist_ok=True)

        m5 = hashlib.md5(src).hexdigest()
        s256 = hashlib.sha256(src).hexdigest()
        s3_256 = hashlib.sha3_256(src).hexdigest()
        b2 = hashlib.blake2b(src).hexdigest()

        layout = [
            f"# Autogenerated VPC Config using {self.regions_result} at {time.time()} ({datetime.datetime.now()})",
            "\n",
            f"# {self.regions_result} Last Change Timestamp: {self.regions_result.stat().st_ctime}",
            "\n",
            f"# {self.regions_result} md5: {m5}",
            "\n",
            f"# {self.regions_result} sha256: {s256}",
            "\n",
            f"# {self.regions_result} sha3-256: {s3_256}",
            "\n",
            f"# {self.regions_result} blake2b: {b2}",
        ]
        for region, config in subnets_per_region.items():
            cidr_primary = config["vpc"]["primary"]
            cidr_secondaries = config["vpc"]["secondary"]
            subnets = config["subnets"]

            # Allow show/hide of unused subnets directly in the config
            # so the saved config is a full reference for future hand-tuned
            # network allocations without needing to consult the original plan json.
            if include_unused:
                cidr_unused = "cidr_secondaries_unused = " + json.dumps(
                    config["vpc"]["_unused"]
                )

                # Convert the unused list to a map so terraform doesn't complain
                subnets["_unused"] = {
                    f"_{n}": x for n, x in enumerate(subnets["_unused"])
                }
            else:
                del subnets["_unused"]

            # Everything in programming eventually comes back to templates...
            layout.append(
                f"""
# ================================================================================
# module.planvpc-{region}:
# ================================================================================
provider "aws" {{
    profile = "{profile}"
    alias = "{region}"
    region = "{region}"
    default_tags {{
        tags = {{
            GeneratedBy = "https://github.com/mattsta/aws-vpc-global-planner"
        }}
    }}
}}

module "planvpc-{region}" {{
    source = "./tf/modules/vpc-auto"

    cidr_primary = {json.dumps(cidr_primary)}
    cidr_secondaries = {json.dumps(cidr_secondaries)}
    {cidr_unused if include_unused else ""}
    subnets = {json.dumps(subnets, indent=4).replace(":"," =")}

    providers = {{
        aws = aws.{region}
    }}
}}
"""
            )

        cleanup = subprocess.run(
            "terraform fmt -".split(),
            stdout=subprocess.PIPE,
            input="".join(layout).encode(),
        ).stdout
        plan = cleanup.decode()

        pathlib.Path(output).write_text(plan)
        logger.info("[{}] Wrote terraform plan", output)


def cmd():
    import fire

    fire.Fire(GlobalVPCBuilder)


if __name__ == "__main__":
    cmd()
