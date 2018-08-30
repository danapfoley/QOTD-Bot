from typing import List


def ignore_unused_args(*args):
    _ = args


def chunkify_text(string: str, max_chunk_size: int) -> List[str]:
    return [string[i:i + max_chunk_size] for i in range(0, len(string), max_chunk_size)]
