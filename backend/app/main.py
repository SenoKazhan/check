from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import auth, products
from app.api.v1 import measurement, packing, tasks

app = FastAPI(title="Warehouse CV", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(packing.router, prefix="/api/v1", tags=["Packing"])
app.include_router(tasks.router, prefix="/api/v1", tags=["Tasks"])
app.include_router(auth.router)
app.include_router(products.router)
app.include_router(measurement.router, prefix="/api/v1", tags=["Measurements"])
@app.get("/health")
def health_check():
    return {"status": "ok"}