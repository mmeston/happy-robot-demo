from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from api.config import API_KEY
from api.database import init_db, seed_demo_loads
from api.errors import error_payload
from api.routes import router


PUBLIC_PATHS = {"/health", "/docs", "/openapi.json", "/redoc"}


def create_app() -> FastAPI:
    app = FastAPI(
        title="HappyRobot Carrier Sales API",
        description="Backend tools for inbound carrier verification, load search, negotiation, booking intake, and call logging.",
        version="0.1.0",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(router)

    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException):
        if isinstance(exc.detail, dict) and "error_code" in exc.detail:
            return JSONResponse(status_code=exc.status_code, content=exc.detail)

        return JSONResponse(
            status_code=exc.status_code,
            content=error_payload(
                "HTTP_ERROR",
                str(exc.detail),
            ),
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        request: Request,
        exc: RequestValidationError,
    ):
        errors = []
        for error in exc.errors():
            errors.append(
                {
                    "field": ".".join(str(part) for part in error["loc"]),
                    "message": error["msg"],
                    "type": error["type"],
                }
            )

        return JSONResponse(
            status_code=422,
            content=error_payload(
                "VALIDATION_ERROR",
                "Request did not pass validation. Check the listed fields and try again.",
                details={"errors": errors},
            ),
        )

    @app.middleware("http")
    async def api_key_auth(request: Request, call_next):
        if API_KEY and request.url.path not in PUBLIC_PATHS:
            provided_key = request.headers.get("x-api-key")
            if provided_key != API_KEY:
                return JSONResponse(
                    status_code=401,
                    content=error_payload(
                        "UNAUTHORIZED",
                        "Invalid or missing API key.",
                        field="x-api-key",
                    ),
                )

        return await call_next(request)

    @app.on_event("startup")
    def startup() -> None:
        init_db()
        seed_demo_loads()

    return app


app = create_app()
