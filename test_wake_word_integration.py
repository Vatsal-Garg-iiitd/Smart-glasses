import asyncio
import httpx
import uvicorn
from multiprocessing import Process
from main import app

def run_server():
    uvicorn.run(app, host="127.0.0.1", port=8002, log_level="error")

async def test_flow():
    server_process = Process(target=run_server)
    server_process.start()
    
    events_received = []
    
    async def listen_for_events():
        # wait until server is up
        for _ in range(10):
            try:
                async with httpx.AsyncClient() as client:
                    response = await client.get('http://127.0.0.1:8002/health')
                    if response.status_code == 200:
                        break
            except:
                await asyncio.sleep(1)
        
        print("Server is up, listening to events...")
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                async with client.stream('GET', 'http://127.0.0.1:8002/events') as response:
                    async for line in response.aiter_lines():
                        if line:
                            print(f"Received event: {line}")
                            events_received.append(line)
                            break
        except Exception as e:
            print(f"Error in SSE listener: {e}")

    listener_task = asyncio.create_task(listen_for_events())
    
    # Wait for listener to connect
    await asyncio.sleep(5)
    
    print("Triggering wake word...")
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post('http://127.0.0.1:8002/trigger-wake-word')
            print(f"Trigger response: {response.status_code}")
    except Exception as e:
        print(f"Trigger error: {e}")
    
    await asyncio.sleep(2)
    
    listener_task.cancel()
    server_process.terminate()
    server_process.join()
    
    if any("data: trigger" in event for event in events_received):
        print("SUCCESS! Wake word SSE event received perfectly.")
    else:
        print("FAILED! Event not received.", events_received)

if __name__ == "__main__":
    asyncio.run(test_flow())
