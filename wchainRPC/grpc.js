const grpc = require('@grpc/grpc-js');
const protoLoader = require('@grpc/proto-loader');
const packageDefinition = protoLoader.loadSync('blockchain.proto', {});
const blockchainProto = grpc.loadPackageDefinition(packageDefinition).blockchain;

const server = new grpc.Server();

server.addService(blockchainProto.BlockchainService.service, {
    GetBalance: (call, callback) => {
        const balance = "1000"; // Implementasi mendapatkan saldo (dalam bentuk desimal)
        callback(null, { balance: balance });
    },
    SendTransaction: (call, callback) => {
        const transactionHash = "0x1234567890abcdef"; // Implementasi mengirim transaksi (dalam bentuk hexadesimal)
        callback(null, { transactionHash: transactionHash });
    },
    GetChainId: (call, callback) => { 
        const chainId = "14006"; // Ganti dengan 14006 tanpa nol di depan(dalam bentuk desimal), Gunakan ChainID yang belum pernah di pakai oleh Blockchain lain.
        callback(null, { chainId: chainId });
    },
});

server.bindAsync('0.0.0.0:50051', grpc.ServerCredentials.createInsecure(), () => {
    console.log('Server gRPC berjalan di port 50051');
});
