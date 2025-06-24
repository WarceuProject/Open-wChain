const express = require('express');
const axios = require('axios');
const path = require('path');
const fs = require('fs');
const app = express();
const PORT = 3000;

app.use(express.static('public'));
app.use(express.json());

const rpcUrl = 'http://localhost:8080/blockchain'; // Ganti dengan URL RPC node Anda

let contractsDb = {};

if (fs.existsSync('contracts.json')) {
    contractsDb = JSON.parse(fs.readFileSync('contracts.json'));
}

app.get('/', (req, res) => {
    res.sendFile(path.join(__dirname, 'public', 'index.html'));
});

app.get('/block/:number', async (req, res) => {
    const blockNumber = req.params.number;
    try {
        const response = await axios.post(rpcUrl, {
            jsonrpc: '2.0',
            method: 'eth_getBlockByNumber',
            params: [blockNumber, true],
            id: 1
        });
        res.json(response.data);
    } catch (error) {
        res.status(500).send('Error fetching block data');
    }
});

app.get('/transaction/:hash', async (req, res) => {
    const txHash = req.params.hash;
    try {
        const response = await axios.post(rpcUrl, {
            jsonrpc: '2.0',
            method: 'eth_getTransactionByHash',
            params: [txHash],
            id: 1
        });
        res.json(response.data);
    } catch (error) {
        res.status(500).send('Error fetching transaction data');
    }
});

app.get('/address/:address', async (req, res) => {
    const address = req.params.address;
    try {
        const response = await axios.post(rpcUrl, {
            jsonrpc: '2.0',
            method: 'eth_getBalance',
            params: [address, 'latest'],
            id: 1
        });
        res.json(response.data);
    } catch (error) {
        res.status(500).send('Error fetching address data');
    }
});

app.get('/address/:address/transactions', async (req, res) => {
    const address = req.params.address;
    const transactions = [];
    try {
        // Assuming the blockchain has 100 blocks for simplicity.
        for (let i = 0; i < 100; i++) {
            const blockResponse = await axios.post(rpcUrl, {
                jsonrpc: '2.0',
                method: 'eth_getBlockByNumber',
                params: [i.toString(16), true],
                id: 1
            });
            const block = blockResponse.data.result;
            block.transactions.forEach(tx => {
                if (tx.from.toLowerCase() === address.toLowerCase() || tx.to.toLowerCase() === address.toLowerCase()) {
                    transactions.push(tx);
                }
            });
        }
        res.json(transactions);
    } catch (error) {
        res.status(500).send('Error fetching transactions for address');
    }
});

app.post('/deployContract', async (req, res) => {
    const { from, data, gas } = req.body;
    try {
        const response = await axios.post(rpcUrl, {
            jsonrpc: '2.0',
            method: 'eth_sendTransaction',
            params: [{
                from: from,
                data: data,
                gas: gas
            }],
            id: 1
        });
        
        const txHash = response.data.result;
        const receiptResponse = await axios.post(rpcUrl, {
            jsonrpc: '2.0',
            method: 'eth_getTransactionReceipt',
            params: [txHash],
            id: 1
        });
        
        const contractAddress = receiptResponse.data.result.contractAddress;
        contractsDb[contractAddress] = { txHash, from, data };
        fs.writeFileSync('contracts.json', JSON.stringify(contractsDb, null, 2));
        
        res.json({ contractAddress });
    } catch (error) {
        res.status(500).send('Error deploying contract');
    }
});

app.listen(PORT, () => {
    console.log(`Block explorer server running on port ${PORT}`);
});
