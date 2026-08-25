"""K-town server entry point. Prefer run_server.ps1 to use python_class on port 8090."""
from main import main
import asyncio

if __name__ == "__main__":
    asyncio.run(main())
