"""K-town server - run with: python -m server"""
from .main import main
import asyncio

if __name__ == "__main__":
    asyncio.run(main())