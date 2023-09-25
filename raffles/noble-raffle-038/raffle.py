#!/usr/bin/env python3
""""
This Python program runs a Noble Raffle given ownership snapshot and block hash.
"""
import argparse
import random
import csv
import sys
import re

HEADER = """
 _____ _____ _____ __    _____    _____ _____ _____ _____ __    _____ 
|   | |     | __  |  |  |   __|  | __  |  _  |   __|   __|  |  |   __|
| | | |  |  | __ -|  |__|   __|  |    -|     |   __|   __|  |__|   __|
|_|___|_____|_____|_____|_____|  |__|__|__|__|__|  |__|  |_____|_____|
"""

RNG_SEED_PREFIX = "NobleRaffle"

IGNORED_ADDRESSES = [
    # Burn wallets
    "0x0000000000000000000000000000000000000000",
    "0x000000000000000000000000000000000000dead",
    # Noble Treasury
    "0x1fd8df37b360d7366db649703014e637ee214f4a",
]

LETS_PLAY_TOKEN_ID = 34


def raffle(*, owners=[], raffle_options={}, supply=100):
    """
    Returns a list of winners. Sorted by address. May contain duplicates.
    """
    # 100% of supply goes to Let's Play holders.
    lp_picks = int(1.0 * supply)
    # Remaining goes to all other holders.
    base_picks = supply - lp_picks

    print("Total supply:      ", supply)
    print("Let's Play supply: ", lp_picks)
    print("Remaining supply:  ", base_picks)
    print()

    lps_entries = []
    base_entries = []

    for address, token_id, balance in owners:
        # For all Let's Play holders, add a new entry for each token.
        if token_id == LETS_PLAY_TOKEN_ID:
            lps_entries += [address] * balance
        # For any other token, add a single entry for each unique token.
        else:
            base_entries += [address]

    # Split the addresses into those that want to participate, those that don't,
    # and those that didn't indicate a preference.
    participate = [address for address in lps_entries if raffle_options.get(address) == True]
    dont_participate = [address for address in lps_entries if address in raffle_options and not raffle_options[address]]
    no_preference = [address for address in lps_entries if address not in raffle_options]

    # First pick from those that want to participate.
    if len(participate) >= lp_picks:
        lp_winners = random.sample(participate, k=lp_picks)
    else:
        # If there aren't enough, also pick from those that didn't indicate a preference.
        lp_winners = participate
        remaining_picks = lp_picks - len(lp_winners)
        if len(no_preference) >= remaining_picks:
            lp_winners += random.sample(no_preference, k=remaining_picks)
        else:
            # If there still aren't enough, also pick from those that didn't want to participate.
            lp_winners += no_preference + random.sample(dont_participate, k=remaining_picks - len(no_preference))

    base_winners = random.sample(base_entries, k=base_picks)

    # Sort winners by address so the output is always the same.
    lp_winners.sort()
    base_winners.sort()

    print("Raffling...")
    print()

    print("Let's Play winners", len(lp_winners))
    print("\n".join(lp_winners))

    print()

    print("Remaining winners", len(base_winners))
    print("\n".join(base_winners))

    return sorted(
        [
            *lp_winners,
            *base_winners,
        ]
    )


def main():
    """
    It runs when you run this file from command line.
    It loads snapshot data and then run the raffle.
    """
    parser = argparse.ArgumentParser(
        prog="Noble Raffle",
    )
    parser.add_argument("--hash", required=True, help="Block hash to use for raffle")
    parser.add_argument(
        "--owners", default="owners.csv", help="Path to owners snapshot file"
    )
    parser.add_argument("--winners", default="winners.csv", help="Path to result file")
    parser.add_argument(
        "--mint_wallets", default="mint_wallets.csv", help="Map to mint wallets"
    )
    parser.add_argument(
    "--raffle_options", default="raffle_options.csv", help="Path to raffle options file"
    )
    parser.add_argument(
        "--supply", default=100, help="Number of winners to generate", type=int
    )
    parser.add_argument(
        "--no-out",
        default=False,
        help="Don't generate output file",
        action="store_true",
    )

    cli_args = parser.parse_args()

    owners = [
        (address, int(token_id), int(balance))
        for address, token_id, balance in read_csv(cli_args.owners)
        if address not in IGNORED_ADDRESSES
    ]

    if not cli_args.no_out:
        sys.stdout = TeeLogger("output.txt")

    print(HEADER.strip())
    print()

    print("Running Noble Raffle...")
    print()

    print("Using following hash as a seed")
    print(cli_args.hash)
    print()

    if not is_valid_ethereum_block_hash(cli_args.hash):
        print("🔴 WARNING: Provided hash does not look like Ethereum block hash.")
        print("            Are you sure it's correct?")
        print()

    # Create RNG with a seed based
    # on passed block_hash and constant prefix.
    #
    # By providing a seed, we  ensure raffle winners are
    # deterministic and could be reproduced by others.
    random.seed(f"{RNG_SEED_PREFIX}-{cli_args.hash}")

    raffle_options = dict(read_csv(cli_args.raffle_options, True))

    # Get the winners from a raffle.
    winners = raffle(owners=owners, raffle_options=raffle_options, supply=cli_args.supply)

    # Load map of hold wallet to mint wallet.
    mint_wallet_map = {
        addr: mint_addr for addr, mint_addr in read_csv(cli_args.mint_wallets)
    }

    # Replace hold wallet with mint wallet, if exists.
    winners = [mint_wallet_map.get(addr, addr) for addr in winners]

    grouped_winners = {
        address: len([w for w in winners if w == address]) for address in winners
    }

    with open(cli_args.winners, "w", newline="") as file:
        writer = csv.writer(file)

        writer.writerow(["address", "count"])

        for winner, count in sorted(grouped_winners.items()):
            writer.writerow([winner, count])

    print()
    print("Congratulations!")


def read_csv(path, for_raffle_options=False):
    """
    Yields rows from a CSV. Ignores header.
    """
    try:
        with open(path, "r") as file:
            csv_reader = csv.reader(file, delimiter=",")

            # Ignore header
            next(csv_reader)

            if for_raffle_options:
                for row in csv_reader:
                    yield row[0], row[1].lower() == 'true'
            else: 
                for row in csv_reader:
                    yield row
    except FileNotFoundError as e:
        print("File not found:", e.filename)
        exit(1)


def is_valid_ethereum_block_hash(hash):
    """
    Checks if passed string looks like Ethereum block hash (0x hex).
    """
    return re.match(r"^0x[0-9a-fA-F]{64}$", hash)


class TeeLogger(object):
    def __init__(self, filename):
        self.terminal = sys.stdout
        self.file = open(filename, "w")

    def write(self, message):
        self.terminal.write(message)
        self.file.write(message)

    def flush(self):
        self.file.flush()


if __name__ == "__main__":
    main()
