#!/usr/bin/env python3
import os
import sys
import json as jsonlib
import csv
import shutil
import urllib.request

NOBLE_CONTRACT_ADDRESS = "0x7e9b9bA1A3B4873279857056279Cef6A4FCDf340"


def main():
    load_dotenv()

    if "ALCHEMY_API_BASE_URL" not in os.environ:
        print("Please set ALCHEMY_API_BASE_URL environment variable.")
        exit(1)

    block_number = int(sys.argv[1].strip()) if len(sys.argv) >= 2 else None

    if block_number:
        print("Block number: ", block_number)
        print(" ")

    print("Fetching Snapshot from Alchemy...\n")

    snapshot_entries = list(
        read_collection_ownership_from_alchemy(
            NOBLE_CONTRACT_ADDRESS, block=block_number
        )
    )
    snapshot_entries.sort()

    if len(snapshot_entries) == 0:
        print("WARNING: Snapshot is empty. Did you provide a correct block number?")

    snapshot = [
        f"{address}\t{token_id}\t{balance}"
        for address, token_id, balance in snapshot_entries
    ]

    snapshot = "\n".join(snapshot)

    raffle_prefix = "noble-raffle-"
    raffle_dirs = [f for f in os.listdir("raffles") if f.startswith(raffle_prefix)]
    raffle_indexes = [int(f.replace(raffle_prefix, "")) for f in raffle_dirs]
    raffle_index = max(raffle_indexes) + 1 if raffle_indexes else 1
    padded_raffle_index = str(raffle_index).zfill(3)

    target_dir = f"raffles/{raffle_prefix}{padded_raffle_index}"

    os.makedirs(target_dir, exist_ok=True)

    shutil.copy("raffle.py", f"{target_dir}/raffle.py")

    with open(f"{target_dir}/owners.csv", "w", newline="") as file:
        writer = csv.writer(file)

        writer.writerow(["address", "token_id", "balance"])

        for address, token_id, balance in snapshot_entries:
            writer.writerow([address, token_id, balance])

    with open(f"{target_dir}/mint_wallets.csv", "w") as file:
        file.write(request("https://security.noblegallery.workers.dev/account/getmintwallets"))

    with open(f"{target_dir}/raffle_options.csv", "w") as file:
        file.write(request(f"https://security.noblegallery.workers.dev/raffleoption/all/{block_number}"))

    print("Generated raffle:\n", target_dir)


def read_collection_ownership_from_alchemy(contract, *, block=None):
    base_url = os.environ["ALCHEMY_API_BASE_URL"]
    url = f"{base_url}/getOwnersForCollection?contractAddress={NOBLE_CONTRACT_ADDRESS}&withTokenBalances=true"
    if block is not None:
        url += f"&block={block}"

    res = request(url)

    for entries in res["ownerAddresses"]:
        owner_address = entries["ownerAddress"]

        for entry in entries["tokenBalances"]:
            yield owner_address, int(entry["tokenId"], 16), entry["balance"]


def request(url, *, json=None, method="GET"):
    headers = {
        "user-agent": "Mozilla/5.0 noblegallery.com",
    }
    data = None

    if json is not None:
        headers["accept"] = "application/json"
        headers["content-type"] = "application/json"
        data = json.dumps(json).encode("utf-8")

    request = urllib.request.Request(url, data=data, headers=headers, method=method)
    response = urllib.request.urlopen(request)
    content_type = response.getheader("content-type")
    response_data = response.read().decode("utf-8")

    if "application/json" in content_type:
        return jsonlib.loads(response_data)

    return response_data


def load_dotenv():
    try:
        # Open .env file and read its contents
        with open(".env") as f:
            # Loop through each line in the file
            for line in f:
                # Strip newline character from line
                line = line.strip()
                # Split line into key and value using "=" as separator
                key, value = line.split("=")
                # Set environment variable
                os.environ[key] = value
    except FileNotFoundError:
        pass


if __name__ == "__main__":
    main()
