import uvicorn
from app.config import config

if __name__ == "__main__":
    print(f"🚀 Starting {config.APP_NAME} on http://localhost:{config.APP_PORT} ...")
    uvicorn.run(
        "app.main:app",
        host=config.APP_HOST,
        port=config.APP_PORT,
        reload=config.DEBUG
    )
