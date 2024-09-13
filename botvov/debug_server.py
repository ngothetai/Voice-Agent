from main import app
import uvicorn

if __name__ == "__main__":
    uvicorn.run("debug_server:app", host="0.0.0.0", port=5000, reload=True)
