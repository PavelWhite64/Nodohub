import uvicorn
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from database import engine, Base
from routers import auth_router, dashboard_router, pages_router, account_router

app = FastAPI(title="Nodohub")

@app.on_event("startup")
async def startup():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

app.include_router(auth_router.router)
app.include_router(dashboard_router.router)
app.include_router(pages_router.router)
app.include_router(account_router.router)

# Раздача аватаров
app.mount("/avatars", StaticFiles(directory="static/avatars"), name="avatars")

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)