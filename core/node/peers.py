import json
import os

PEERS_FILE = 'data/peers.json'

def load_peers():
    if not os.path(PEERS_FILE):
        return []
    with open(PEERS_FILE, 'r') as f:
        return json.load(f)

def save_peers(peers):
    with open(PEERS_FILE, 'w') as f:
        json.dump(peers, f, indent=2)

def add_peer(url):
    peers = load_peers()
    if url not in peers:
        peers.append(url)
        save_peers(peers)