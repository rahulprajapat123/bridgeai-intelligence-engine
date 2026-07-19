import httpx
import asyncio

async def test():
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                'http://127.0.0.1:8000/api/signal-filter/run',
                json={
                    'batch_id': 'b17b3cea489414f1719d5b63c27a59f2',
                    'novelty_threshold': 7.0,
                    'relevance_threshold': 75.0,
                    'max_items': 20,
                    'enable_clustering': True,
                    'enable_qa': True
                },
                timeout=30.0
            )
            print(f'Status: {resp.status_code}')
            print(f'Response: {resp.text}')
    except Exception as e:
        print(f'Error: {e}')

if __name__ == '__main__':
    asyncio.run(test())
