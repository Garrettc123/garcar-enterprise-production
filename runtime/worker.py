import asyncio
import os
import socket
import httpx

API_URL = os.getenv('RUNTIME_API_URL', 'http://api:8000').rstrip('/')
INTERVAL = int(os.getenv('HEARTBEAT_INTERVAL_SECONDS', '30'))
WORKER_ID = os.getenv('WORKER_ID', socket.gethostname())

async def main():
    async with httpx.AsyncClient(timeout=10) as client:
        while True:
            try:
                response = await client.post(f'{API_URL}/internal/heartbeat/{WORKER_ID}')
                response.raise_for_status()
                print(f'heartbeat ok worker={WORKER_ID}', flush=True)
            except Exception as exc:
                print(f'heartbeat failed worker={WORKER_ID} error={exc}', flush=True)
            await asyncio.sleep(INTERVAL)

if __name__ == '__main__':
    asyncio.run(main())
