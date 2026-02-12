LENS_ABI = [
    {
        "name": "getAmountOut",
        "type": "function",
        "stateMutability": "view",
        "inputs": [
            {"name": "token", "type": "address"},
            {"name": "amountIn", "type": "uint256"},
            {"name": "isBuy", "type": "bool"}
        ],
        "outputs": [
            {"name": "router", "type": "address"},
            {"name": "amountOut", "type": "uint256"}
        ]
    }
]

