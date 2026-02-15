from web3 import Web3
import time
import random
import json
from eth_utils import keccak

# 1. Connect to Ganache
w3 = Web3(Web3.HTTPProvider("http://127.0.0.1:7545"))
assert w3.is_connected(), "❌ Ganache not connected"

print("✅ Connected to Ganache")

# 2. Account setup
account = w3.eth.accounts[0]
w3.eth.default_account = account

# 3. CONTRACT DETAILS (PASTE YOURS HERE)
contract_address = Web3.to_checksum_address("0x51A010E3acCAfc51b3100543b9432b785c107F78")

abi = json.loads("""
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
""")

contract = w3.eth.contract(address=contract_address, abi=abi)

# 4. Simulate IoT Sensor Data
def generate_sensor_data():
    temperature = random.randint(20, 90)   # normal range
    return f"TEMP:{temperature}"


def send_data(data):
    # Convert sensor data to bytes and hash it
    data_bytes = data.encode('utf-8')
    data_hash = keccak(data_bytes)

    tx = contract.functions.logSingle(data_hash).transact()
    receipt = w3.eth.wait_for_transaction_receipt(tx)

    print(f"📦 Data hash logged | Tx Hash: {receipt.transactionHash.hex()}")


# 6. Run simulation
print("🚀 Starting IoT simulation...\n")

for i in range(5):
    data = generate_sensor_data()
    print(f"📡 Sensor reading: {data}")
    send_data(data)
    time.sleep(2)

print("\n✅ Simulation completed")
