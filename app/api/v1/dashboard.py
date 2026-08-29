import os
from fastapi import APIRouter
from fastapi.responses import HTMLResponse

router = APIRouter(tags=["Web Dashboard"])

TEMPLATE_PATH = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "templates", "dashboard.html")
)


@router.get("/dashboard", response_class=HTMLResponse)
async def get_dashboard():
    """Render the Polyfollow Dark Mode Intelligence Dashboard."""
    if os.path.exists(TEMPLATE_PATH):
        with open(TEMPLATE_PATH, "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read())
    return HTMLResponse(content="<h1>Dashboard template not found.</h1>", status_code=404)
