// SPDX-License-Identifier: MIT
pragma solidity ^0.8.0;

contract LogManager {

    event MerkleLogged(bytes32 merkleRoot, uint256 timestamp);
    event SingleLog(bytes32 dataHash, uint256 timestamp);

    function logMerkleRoot(bytes32 _root) public {
        emit MerkleLogged(_root, block.timestamp);
    }

    function logSingle(bytes32 _hash) public {
        emit SingleLog(_hash, block.timestamp);
    }
}
