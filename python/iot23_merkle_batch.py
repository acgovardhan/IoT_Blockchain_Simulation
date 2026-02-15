#!/usr/bin/env python3
# python/iot23_merkle_batch.py
"""
Batch IoT-23 rows into Merkle trees where each leaf = keccak(data|timestamp|device_id),
anchor Merkle roots on-chain (logMerkleRoot) and save batch metadata to data/batches.json
"""

import os, time, json
import pandas as pd
from web3 import Web3
from eth_utils import keccak

# ---------------- CONFIG - EDIT THESE ----------------
RPC_URL = "http://127.0.0.1:7545"

# Replace with your deployed contract address (0x...)
CONTRACT_ADDRESS = "0xf99168daA337Aa6C934A544197fA31F38b08e74D"

# Paste full ABI JSON array text here (from Remix -> Compiler -> ABI)
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

# Data / batch parameters
DATA_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "iot23_sample.csv")
BATCH_SIZE = 10                 # change to 20/50 for experiments
SLEEP_BETWEEN_TX = 0.6
SAVE_BATCHES = True
BATCH_STORAGE_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "batches.json")
SAMPLE_ROWS = 100               # how many csv rows to read for experiment
# ----------------------------------------------------

def keccak_bytes(x: bytes) -> bytes:
    return keccak(x)

def prepare_record(row):
    """
    canonical record: device_id|timestamp|proto|service|label
    if ts missing, fallback to current unix int timestamp
    """
    device_id = str(row.get("id.orig_h", "") or "")
    ts = row.get("ts", None)
    if ts is None or (isinstance(ts, float) and pd.isna(ts)):
        ts = int(time.time())
    # ensure integer seconds
    try:
        ts_int = int(float(ts))
    except Exception:
        ts_int = int(time.time())
    proto = str(row.get("proto", "") or "")
    service = str(row.get("service", "") or "")
    label = str(row.get("label", "") or "")
    record = f"{device_id}|{ts_int}|{proto}|{service}|{label}"
    return record

def merkle_root_from_hashes(hashes: list[bytes]) -> bytes:
    """Compute Merkle root from list of 32-byte hashes. If odd, duplicate last."""
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

# Blockchain helpers
def connect():
    w3 = Web3(Web3.HTTPProvider(RPC_URL))
    if not w3.is_connected():
        raise SystemExit("❌ Cannot connect to Ganache at " + RPC_URL)
    w3.eth.default_account = w3.eth.accounts[0]
    return w3

def load_contract(w3):
    abi = json.loads(CONTRACT_ABI_JSON)
    contract = w3.eth.contract(address=Web3.to_checksum_address(CONTRACT_ADDRESS), abi=abi)
    return contract

def log_batches(w3, contract, csv_path=DATA_PATH, sample=SAMPLE_ROWS):
    if not os.path.exists(csv_path):
        raise SystemExit(f"❌ Data file not found: {csv_path}")
    df = pd.read_csv(csv_path, nrows=sample)
    print(f"ℹ️ Loaded {len(df)} rows from {csv_path}")

    batch_hashes = []
    batch_records = []
    stored_batches = []
    batch_index = 0

    for idx, row in df.iterrows():
        rec_text = prepare_record(row)
        rec_hash = keccak(text=rec_text)  # bytes
        batch_hashes.append(rec_hash)
        batch_records.append(rec_text)

        if len(batch_hashes) >= BATCH_SIZE:
            root = merkle_root_from_hashes(batch_hashes)
            try:
                tx = contract.functions.logMerkleRoot(root).transact({'from': w3.eth.default_account})
                receipt = w3.eth.wait_for_transaction_receipt(tx)
                print(f"[BATCH {batch_index}] logged {len(batch_hashes)} records -> root=0x{root.hex()} tx={receipt.transactionHash.hex()} gas={receipt.gasUsed}")
                if SAVE_BATCHES:
                    stored_batches.append({
                        "batch_index": batch_index,
                        "root": "0x" + root.hex(),
                        "tx": receipt.transactionHash.hex(),
                        "gas": receipt.gasUsed,
                        "records": batch_records[:]  # copy textual records
                    })
            except Exception as e:
                print(f"Error logging batch {batch_index}: {e}")

            batch_index += 1
            batch_hashes = []
            batch_records = []
            time.sleep(SLEEP_BETWEEN_TX)

    # commit any remaining partial batch
    if len(batch_hashes) > 0:
        root = merkle_root_from_hashes(batch_hashes)
        try:
            tx = contract.functions.logMerkleRoot(root).transact({'from': w3.eth.default_account})
            receipt = w3.eth.wait_for_transaction_receipt(tx)
            print(f"[BATCH {batch_index}] logged {len(batch_hashes)} records -> root=0x{root.hex()} tx={receipt.transactionHash.hex()} gas={receipt.gasUsed}")
            if SAVE_BATCHES:
                stored_batches.append({
                    "batch_index": batch_index,
                    "root": "0x" + root.hex(),
                    "tx": receipt.transactionHash.hex(),
                    "gas": receipt.gasUsed,
                    "records": batch_records[:]
                })
        except Exception as e:
            print(f"Error logging final batch {batch_index}: {e}")

    if SAVE_BATCHES and len(stored_batches) > 0:
        # ensure data folder exists
        os.makedirs(os.path.dirname(BATCH_STORAGE_PATH), exist_ok=True)
        with open(BATCH_STORAGE_PATH, "w", encoding="utf-8") as fh:
            json.dump(stored_batches, fh, indent=2)
        print(f"Saved {len(stored_batches)} batch metadata entries to {BATCH_STORAGE_PATH}")

if __name__ == "__main__":
    w3 = connect()
    contract = load_contract(w3)
    log_batches(w3, contract)
