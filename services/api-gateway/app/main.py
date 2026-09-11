import os
import logging
import httpx
from fastapi import FastAPI, Request, Depends, HTTPException
from fastapi.responses import JSONResponse
from common.auth import verify_token
from common.dto import HealthResponse
from common.observability import configure_logging, setup_metrics

app = FastAPI(title="Marketing Assistant API Gateway")
configure_logging("api-gateway")
setup_metrics(app, "api-gateway")
logger = logging.getLogger(__name__)

INSTAGRAM_SERVICE = os.getenv("INSTAGRAM_SERVICE", "http://instagram-analytics:8000")
GENERATOR_SERVICE = os.getenv("GENERATOR_SERVICE", "http://content-generator:8000")

@app.get("/healthz", response_model=HealthResponse)
async def health():
    return HealthResponse(service="api-gateway")

@app.api_route("/v1/instagram/{path:path}", methods=["GET", "POST", "PUT", "DELETE"])
async def proxy_instagram(path: str, request: Request, user: dict = Depends(verify_token)):
    return await proxy_request(f"{INSTAGRAM_SERVICE}/{path}", request)

@app.api_route("/v1/generator/{path:path}", methods=["GET", "POST", "PUT", "DELETE"])
async def proxy_generator(path: str, request: Request, user: dict = Depends(verify_token)):
    return await proxy_request(f"{GENERATOR_SERVICE}/{path}", request)

async def proxy_request(url: str, request: Request):
    async with httpx.AsyncClient() as client:
        method = request.method
        content = await request.body()
        headers = dict(request.headers)
        # Remove host header to avoid conflicts
        headers.pop("host", None)
        
        try:
            response = await client.request(
                method,
                url,
                params=request.query_params,
                headers=headers,
                content=content,
                timeout=60.0,
            )
            return JSONResponse(
                status_code=response.status_code,
                content=response.json()
            )
        except httpx.RequestError as e:
            logger.error("upstream_unavailable", extra={"url": url, "error": str(e)})
            raise HTTPException(status_code=502, detail=f"Service unavailable: {str(e)}")
        except Exception as e:
            logger.exception("gateway_error")
            raise HTTPException(status_code=500, detail=str(e))
