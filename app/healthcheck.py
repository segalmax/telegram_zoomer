import asyncio
from aiohttp import web

async def handle(request):
    return web.Response(text="OK")

app = web.Application()
app.add_routes([web.get("/health", handle)])

if __name__ == "__main__":
    web.run_app(app, port=8080)
