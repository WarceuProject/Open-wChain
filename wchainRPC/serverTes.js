const express = require('express');
const bodyParser = require('body-parser');
const cors = require('cors');
const fs = require('fs');
const path = require('path');
const Wallet = require('ethereumjs-wallet').default;
const client = require('./client');

const app = express();
app.use(cors());
app.use(bodyParser.json());

const CHAIN_ID = '14006';
const WALLET_DB_PATH = path.join(__dirname, 'wallets.json');

// ------------------- Helpers -------------------

function readWalletsDB() {
    return new Promise((resolve, reject) => {
        fs.readFile(WALLET_DB_PATH, 'utf8', (err, data) => {
            if (err) return reject(err);
            resolve(JSON.parse(data));
        });
    });
}

function writeWalletsDB(wallets) {
    return new Promise((resolve, reject) => {
        fs.writeFile(WALLET_DB_PATH, JSON.stringify(wallets, null, 2), 'utf8', (err) => {
            if (err) return reject(err);
            resolve();
        });
    });
}

function createRandomWallet() {
    const wallet = Wallet.generate();
    return {
        address: 'Wa' + wallet.getAddressString().slice(2),
        privateKey: 'Wp' + wallet.getPrivateKeyString().slice(2),
        balance: 'Wb0'
    };
}

function parseBalance(balanceWithPrefix) {
    return BigInt('0x' + balanceWithPrefix.slice(2));
}

// ------------------- RPC Handler -------------------

app.post('/blockchain', async (req, res) => {
    const { method, params, id } = req.body;
    console.log('Received request:', req.body);

    try {
        switch (method) {

            case 'GetChainId':
                client.GetChainId({}, (error, response) => {
                    if (error) {
                        return res.status(500).json({ jsonrpc: '2.0', error: { code: -32603, message: error.message }, id });
                    }
                    res.json({ jsonrpc: '2.0', result: { chainId: response.chainId }, id });
                });
                break;

            case 'wcn_chainId':
                res.json({ jsonrpc: '2.0', result: `0x${parseInt(CHAIN_ID).toString(16)}`, id });
                break;

            case 'wcn_blockNumber':
                res.json({ jsonrpc: '2.0', result: '0x1', id });
                break;

            case 'net_version':
                res.json({ jsonrpc: '2.0', result: CHAIN_ID, id });
                break;

            case 'wcn_getBalance': {
                const [address] = params;
                const walletsDB = await readWalletsDB();
                const wallet = walletsDB.wallets.find(w => w.address === address);
                if (!wallet) {
                    return res.status(404).json({ jsonrpc: '2.0', error: { code: -32602, message: 'Address not found' }, id });
                }
                const hexBalance = '0x' + wallet.balance.slice(2);
                res.json({ jsonrpc: '2.0', result: hexBalance, id });
                break;
            }

            case 'wcn_getBlockByNumber':
                res.json({
                    jsonrpc: '2.0',
                    result: {
                        number: '0x1',
                        hash: '0x0',
                        parentHash: '0x0',
                        nonce: '0x0',
                        sha3Uncles: '0x0',
                        logsBloom: '0x0',
                        transactionsRoot: '0x0',
                        stateRoot: '0x0',
                        receiptsRoot: '0x0',
                        miner: '0x0',
                        difficulty: '0x0',
                        totalDifficulty: '0x0',
                        extraData: '0x0',
                        size: '0x0',
                        gasLimit: '0x0',
                        gasUsed: '0x0',
                        timestamp: '0x0',
                        transactions: [],
                        uncles: []
                    },
                    id
                });
                break;

            case 'addWallets': {
                const [count] = params;
                const walletsDB = await readWalletsDB();
                for (let i = 0; i < count; i++) {
                    walletsDB.wallets.push(createRandomWallet());
                }
                await writeWalletsDB(walletsDB);
                res.json({ jsonrpc: '2.0', result: `${count} wallets added successfully`, id });
                break;
            }

            case 'addBalance': {
                const [address, amount] = params;
                const walletsDB = await readWalletsDB();
                const wallet = walletsDB.wallets.find(w => w.address === address);
                if (!wallet) {
                    return res.status(404).json({ jsonrpc: '2.0', error: { code: -32602, message: 'Address not found' }, id });
                }
                const current = parseBalance(wallet.balance);
                wallet.balance = 'Wb' + (current + BigInt(amount)).toString(16);
                await writeWalletsDB(walletsDB);
                res.json({ jsonrpc: '2.0', result: 'Balance added successfully', id });
                break;
            }

            case 'wcn_sendTransaction': {
                const [tx] = params;
                const from = tx.from;
                const to = tx.to;
                const value = BigInt(tx.value);
                const walletsDB = await readWalletsDB();

                const sender = walletsDB.wallets.find(w => w.address === from);
                const receiver = walletsDB.wallets.find(w => w.address === to);

                if (!sender || !receiver) {
                    return res.status(404).json({ jsonrpc: '2.0', error: { code: -32602, message: 'Sender or Receiver not found' }, id });
                }

                const senderBalance = parseBalance(sender.balance);
                if (senderBalance < value) {
                    return res.status(400).json({ jsonrpc: '2.0', error: { code: -32000, message: 'Insufficient funds' }, id });
                }

                sender.balance = 'Wb' + (senderBalance - value).toString(16);
                receiver.balance = 'Wb' + (parseBalance(receiver.balance) + value).toString(16);
                await writeWalletsDB(walletsDB);

                res.json({ jsonrpc: '2.0', result: 'Transaction successful', id });
                break;
            }

            case 'wcn_gasPrice':
                res.json({ jsonrpc: '2.0', result: '0x12a05f200', id }); // 5 gwei
                break;

            case 'wcn_estimateGas':
                res.json({ jsonrpc: '2.0', result: '0x5208', id }); // 21000 gas
                break;

            case 'wcn_getTransactionCount':
                res.json({ jsonrpc: '2.0', result: '0x1', id }); // dummy
                break;

            case 'info': {
                const walletsDB = await readWalletsDB();
                const result = walletsDB.wallets.map(w => ({
                    address: w.address,
                    balance: w.balance
                }));
                res.json({ jsonrpc: '2.0', result, id });
                break;
            }

            default:
                res.status(400).json({ jsonrpc: '2.0', error: { code: -32601, message: 'Method not found' }, id });
        }
    } catch (error) {
        console.error(`Error processing method ${method}:`, error);
        res.status(500).json({
            jsonrpc: '2.0',
            error: { code: -32603, message: 'Internal server error', data: error.message },
            id
        });
    }
});

// ------------------- Start Server -------------------

app.listen(8000, () => {
    console.log('Server HTTP berjalan di port 8000');
});
