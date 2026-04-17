import asyncio

from .rules_engine import consume


if __name__ == "__main__":
    asyncio.run(consume())
