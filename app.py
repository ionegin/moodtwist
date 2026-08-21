import asyncio
import os

from aiohttp import web

from bot import run_bot
from config import BOT_TOKEN


async def health_check(request):
    return web.Response(text="Borderliner Bot is running!", status=200)


async def debug_info(request):
    debug_data = {
        "bot_token_exists": bool(BOT_TOKEN),
        "bot_token_length": len(BOT_TOKEN) if BOT_TOKEN else 0,
        "bot_token_prefix": BOT_TOKEN[:10] + "..." if BOT_TOKEN and len(BOT_TOKEN) > 10 else "INVALID",
    }
    return web.json_response(debug_data)


def should_start_health_server() -> bool:
    enabled = os.getenv("ENABLE_HEALTHCHECK", "").strip().lower()
    return enabled in {"1", "true", "yes", "on"} or bool(os.getenv("HEALTHCHECK_PORT"))


async def start_health_server():
    if not should_start_health_server():
        return None

    app = web.Application()
    app.router.add_get("/", health_check)
    app.router.add_get("/health", health_check)
    app.router.add_get("/debug", debug_info)

    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.getenv("PORT", 8080))
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    print(f"🌐 Health check server started on port {port}")
    return runner


async def main():
    print("🚀 Starting Borderliner bot...")
    print(f"🔧 Bot token exists: {bool(BOT_TOKEN)}")

    health_runner = await start_health_server()
    try:
        await run_bot()
    finally:
        if health_runner is not None:
            await health_runner.cleanup()


if __name__ == "__main__":
    asyncio.run(main())
