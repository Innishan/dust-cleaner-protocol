NADFUN_ROUTER_ABI = [
    {
        "name": "sell",
        "type": "function",
        "stateMutability": "nonpayable",
        "inputs": [
            {
                "name": "p",
                "type": "tuple",
                "components": [
                    {"name": "amountIn", "type": "uint256"},
                    {"name": "amountOutMin", "type": "uint256"},
                    {"name": "token", "type": "address"},
                    {"name": "to", "type": "address"},
                    {"name": "deadline", "type": "uint256"}
                ]
            }
        ],
        "outputs": []
    }
]

