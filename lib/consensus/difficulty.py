# lib/consensus/difficulty.py
import time
from . import config

def adjust_difficulty(chain):
    if len(chain) < config.DIFFICULTY_ADJUSTMENT_INTERVAL + 1:
        return config.INITIAL_DIFFICULTY

    latest_block = chain[-1]
    prev_adjustment_block = chain[-1 - config.DIFFICULTY_ADJUSTMENT_INTERVAL]

    actual_time = latest_block['timestamp'] - prev_adjustment_block['timestamp']
    expected_time = config.BLOCK_TIME * config.DIFFICULTY_ADJUSTMENT_INTERVAL

    difficulty = latest_block.get('difficulty', config.INITIAL_DIFFICULTY)

    if actual_time < expected_time / 2:
        difficulty += 1
    elif actual_time > expected_time * 2 and difficulty > 1:
        difficulty -= 1

    return difficulty
