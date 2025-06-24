async function fetchBlock() {
    const blockNumber = document.getElementById('blockNumber').value;
    const response = await fetch(`/block/${blockNumber}`);
    const data = await response.json();
    document.getElementById('result').innerHTML = `<pre>${JSON.stringify(data, null, 2)}</pre>`;
}

async function fetchTransaction() {
    const txHash = document.getElementById('txHash').value;
    const response = await fetch(`/transaction/${txHash}`);
    const data = await response.json();
    document.getElementById('result').innerHTML = `<pre>${JSON.stringify(data, null, 2)}</pre>`;
}

async function fetchAddress() {
    const address = document.getElementById('address').value;
    const response = await fetch(`/address/${address}`);
    const data = await response.json();
    document.getElementById('result').innerHTML = `<pre>${JSON.stringify(data, null, 2)}</pre>`;
}

async function fetchAddressTransactions() {
    const address = document.getElementById('addressTx').value;
    const response = await fetch(`/address/${address}/transactions`);
    const data = await response.json();
    document.getElementById('result').innerHTML = `<pre>${JSON.stringify(data, null, 2)}</pre>`;
}

async function deployContract() {
    const from = document.getElementById('contractFrom').value;
    const data = document.getElementById('contractData').value;
    const gas = document.getElementById('contractGas').value;
    
    const response = await fetch('/deployContract', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({ from, data, gas })
    });
    
    const result = await response.json();
    document.getElementById('result').innerHTML = `<pre>${JSON.stringify(result, null, 2)}</pre>`;
}
