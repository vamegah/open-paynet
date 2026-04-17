import asyncio

from .elastic_logger import consume


if __name__ == "__main__":
    asyncio.run(consume())
