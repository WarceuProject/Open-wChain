const grpc = require('@grpc/grpc-js');
const protoLoader = require('@grpc/proto-loader');
const packageDefinition = protoLoader.loadSync('blockchain.proto', {});
const blockchainProto = grpc.loadPackageDefinition(packageDefinition).blockchain;

const client = new blockchainProto.BlockchainService(
    'localhost:50051',
    grpc.credentials.createInsecure()
);

module.exports = client;
