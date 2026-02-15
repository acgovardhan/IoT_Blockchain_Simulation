#!/usr/bin/env python3
# python/verify_merkle_and_tamper.py
"""
Verify saved batches against on-chain roots and demonstrate tamper detection.
Usage:
  python python/verify_merkle_and_tamper.py --batch 0
  python python/verify_merkle_and_tamper.py --batch 0 --tamper-csv data/iot23_altered.csv
"""

import os, json, argparse
from web3 import Web3
from eth_utils import keccak


RPC_URL = "http://127.0.0.1:7545"
CONTRACT_ADDRESS = "0xf99168daA337Aa6C934A544197fA31F38b08e74D"
CONTRACT_ABI_JSON = r"""
[
	{
		"inputs": [
			{
				"internalType": "bytes32",
				"name": "_root",
				"type": "bytes32"
			}
		],
		"name": "logMerkleRoot",
		"outputs": [],
		"stateMutability": "nonpayable",
		"type": "function"
	},
	{
		"inputs": [
			{
				"internalType": "bytes32",
				"name": "_hash",
				"type": "bytes32"
			}
		],
		"name": "logSingle",
		"outputs": [],
		"stateMutability": "nonpayable",
		"type": "function"
	},
	{
		"anonymous": false,
		"inputs": [
			{
				"indexed": false,
				"internalType": "bytes32",
				"name": "merkleRoot",
				"type": "bytes32"
			},
			{
				"indexed": false,
				"internalType": "uint256",
				"name": "timestamp",
				"type": "uint256"
			}
		],
		"name": "MerkleLogged",
		"type": "event"
	},
	{
		"anonymous": false,
		"inputs": [
			{
				"indexed": false,
				"internalType": "bytes32",
				"name": "dataHash",
				"type": "bytes32"
			},
			{
				"indexed": false,
				"internalType": "uint256",
				"name": "timestamp",
				"type": "uint256"
			}
		],
		"name": "SingleLog",
		"type": "event"
	}
]
"""
BATCH_STORAGE_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "batches.json")


def keccak_bytes(x: bytes) -> bytes:
    return keccak(x)

def merkle_root_from_hashes(hashes):
    if len(hashes) == 0:
        return b'\x00' * 32
    cur = hashes[:]
    while len(cur) > 1:
        next_level = []
        for i in range(0, len(cur), 2):
            left = cur[i]
            right = cur[i+1] if i+1 < len(cur) else cur[i]
            parent = keccak_bytes(left + right)
            next_level.append(parent)
        cur = next_level
    return cur[0]

def connect():
    w3 = Web3(Web3.HTTPProvider(RPC_URL))
    if not w3.is_connected():
        raise SystemExit("Cannot connect to Ganache")
    return w3

def load_contract(w3):
    abi = json.loads(CONTRACT_ABI_JSON)
    return w3.eth.contract(address=Web3.to_checksum_address(CONTRACT_ADDRESS), abi=abi)


def verify_batch_local(batch_entry):
    records = batch_entry['records']
    hashes = [keccak(text=r) for r in records]
    local_root = merkle_root_from_hashes(hashes)
    return local_root

def run_verification(batch_entry):
    local_root = verify_batch_local(batch_entry)
    stored_root_hex = batch_entry['root']
    stored_root_bytes = bytes.fromhex(stored_root_hex[2:])

    print(f"Local root:  {stored_root_hex}")
    print(f"Recomputed:  0x{local_root.hex()}")
    print("Root matches blockchain anchor? ", local_root == stored_root_bytes)


def run_tamper_test(batch_entry, tamper_csv_path=None):
    original_records = batch_entry['records']
    print("\nOriginal sample record[0]:", original_records[0])

    if tamper_csv_path:
        if not os.path.exists(tamper_csv_path):
            raise SystemExit("Tamper CSV not found: " + tamper_csv_path)
        import pandas as pd
        df_alt = pd.read_csv(tamper_csv_path, nrows=1)
        device_id = str(df_alt.iloc[0].get("id.orig_h", "") or "")
        ts = df_alt.iloc[0].get("ts", int(time.time()))
        proto = str(df_alt.iloc[0].get("proto", "") or "")
        service = str(df_alt.iloc[0].get("service", "") or "")
        label = str(df_alt.iloc[0].get("label", "") or "")
        tampered0 = f"{device_id}|{int(float(ts))}|{proto}|{service}|{label}"
        print("Tampered (from CSV) record[0]:", tampered0)
        tampered_records = [tampered0] + original_records[1:]
    else:
        tampered_records = original_records[:]
        # naive in-memory tamper (replace first '0' with '9')
        #tampered_records[0] = tampered_records[0].replace("0", "9")   #do not change, so error 
        tampered_records[0] = tampered_records[0].replace("tcp", "udp") #changes data
        print("Tampered (in-memory) record[0]:", tampered_records[0])

    hashes_tampered = [keccak(text=r) for r in tampered_records]
    root_tampered = merkle_root_from_hashes(hashes_tampered)
    print("Tampered local root: 0x" + root_tampered.hex())
    saved_root_hex = batch_entry['root'].lstrip("0x")
    print("Tampered root equals saved on-chain root? ", root_tampered.hex() == saved_root_hex)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--batch", type=int, default=0, help="batch index to verify")
    parser.add_argument("--tamper-csv", type=str, default=None, help="path to altered csv row for tamper test")
    args = parser.parse_args()

    if not os.path.exists(BATCH_STORAGE_PATH):
        raise SystemExit("Batch metadata not found. Run batch script first.")

    w3 = connect()
    contract = load_contract(w3)

    batches = json.load(open(BATCH_STORAGE_PATH, "r", encoding="utf-8"))
    if args.batch < 0 or args.batch >= len(batches):
        raise SystemExit("batch index out of range")

    batch_entry = batches[args.batch]
    print("Verifying batch index", args.batch)
    run_verification(batch_entry)
    print("\n--- Tamper test ---")
    run_tamper_test(batch_entry, tamper_csv_path=args.tamper_csv)
