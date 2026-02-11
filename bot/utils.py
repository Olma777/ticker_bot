import asyncio
from typing import List, Any, Callable


async def batch_process(
    items: List[Any],
    processor: Callable[[Any], Any],
    concurrency: int = 5
) -> List[Any]:
    semaphore = asyncio.Semaphore(concurrency)

    async def _process(item):
        async with semaphore:
            return await processor(item)

    tasks = [_process(item) for item in items]
    return await asyncio.gather(*tasks, return_exceptions=True)
