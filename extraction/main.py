from fastapi import FastAPI
from extraction.api import unstructured, markitdown

app = FastAPI()

app.include_router(unstructured.router, prefix="/unstructured")
app.include_router(markitdown.router, prefix="/markitdown")


if __name__ == "__main__":
    import uvicorn
    import os
    port = int(os.getenv("PORT", 8000))
    uvicorn.run("extraction.main:app", host="0.0.0.0", port=port, reload=True)
