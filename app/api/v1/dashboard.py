import os
import secrets
from typing import Optional
from fastapi import APIRouter, Cookie, Query, Response
from fastapi.responses import HTMLResponse
from app.core.config import settings

router = APIRouter(tags=["Web Dashboard"])

TEMPLATE_PATH = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "templates", "dashboard.html")
)

LOGIN_GATE_HTML = """<!DOCTYPE html>
<html lang="en" class="dark">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Polyfollow Terminal - Security Gate</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <script src="https://unpkg.com/lucide@latest"></script>
</head>
<body class="bg-gray-950 text-gray-100 min-h-screen flex items-center justify-center p-4 font-sans selection:bg-indigo-500 selection:text-white">
    <div class="max-w-md w-full bg-gray-900/80 backdrop-blur-xl border border-gray-800/80 rounded-2xl p-8 shadow-2xl space-y-6 relative overflow-hidden">
        <div class="absolute -top-24 -right-24 w-48 h-48 bg-indigo-500/10 rounded-full blur-3xl pointer-events-none"></div>
        <div class="absolute -bottom-24 -left-24 w-48 h-48 bg-blue-500/10 rounded-full blur-3xl pointer-events-none"></div>

        <div class="text-center space-y-2">
            <div class="inline-flex items-center justify-center w-16 h-16 rounded-2xl bg-indigo-600/10 border border-indigo-500/20 mb-2">
                <span class="text-3xl">🐋</span>
            </div>
            <h1 class="text-2xl font-black tracking-tight text-white">Polyfollow Terminal</h1>
            <p class="text-xs text-gray-400">Polymarket Bandar Intelligence & Smart Consensus Engine</p>
        </div>

        <div class="bg-gray-950/60 border border-gray-800/80 rounded-xl p-4 text-xs text-gray-400 flex items-start gap-3">
            <i data-lucide="shield-alert" class="w-5 h-5 text-amber-400 shrink-0 mt-0.5"></i>
            <div>
                <span class="font-semibold text-gray-200 block">Protected Access Area</span>
                This terminal is secured with API Key authentication. Enter your security key to unlock the intelligence feed.
            </div>
        </div>

        <form onsubmit="handleAuth(event)" class="space-y-4">
            <div>
                <label for="apiKeyInput" class="block text-xs font-mono uppercase tracking-wider text-gray-400 mb-1.5 font-semibold">
                    Security API Key / Token
                </label>
                <div class="relative">
                    <input type="password" id="apiKeyInput" required autofocus
                           placeholder="Enter your API_KEY..."
                           class="w-full bg-gray-950 border border-gray-800 focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 rounded-xl px-4 py-3 text-sm text-white font-mono placeholder-gray-600 outline-none transition pr-10">
                    <button type="button" onclick="toggleVisibility()" class="absolute right-3 top-3 text-gray-500 hover:text-gray-300">
                        <i id="eyeIcon" data-lucide="eye" class="w-4 h-4"></i>
                    </button>
                </div>
            </div>

            <div id="errorMessage" class="hidden text-rose-400 text-xs font-medium text-center bg-rose-500/10 border border-rose-500/20 py-2 rounded-lg">
                Invalid API Key. Please check and try again.
            </div>

            <button type="submit" id="submitBtn"
                    class="w-full bg-indigo-600 hover:bg-indigo-500 active:scale-[0.99] text-white font-semibold py-3 px-4 rounded-xl text-sm transition shadow-lg shadow-indigo-600/20 flex items-center justify-center gap-2">
                <i data-lucide="lock" class="w-4 h-4"></i>
                <span>Unlock Terminal</span>
            </button>
        </form>

        <div class="text-center">
            <span class="text-[11px] text-gray-600 font-mono">POLYFOLLOW • SECURED SMART MONEY RADAR</span>
        </div>
    </div>

    <script>
        lucide.createIcons();

        function toggleVisibility() {
            const input = document.getElementById('apiKeyInput');
            const eye = document.getElementById('eyeIcon');
            if (input.type === 'password') {
                input.type = 'text';
                eye.setAttribute('data-lucide', 'eye-off');
            } else {
                input.type = 'password';
                eye.setAttribute('data-lucide', 'eye');
            }
            lucide.createIcons();
        }

        async function handleAuth(e) {
            e.preventDefault();
            const key = document.getElementById('apiKeyInput').value.trim();
            const btn = document.getElementById('submitBtn');
            const err = document.getElementById('errorMessage');

            if (!key) return;

            btn.disabled = true;
            btn.innerHTML = `<i data-lucide="loader" class="w-4 h-4 animate-spin"></i><span>Verifying...</span>`;
            lucide.createIcons();
            err.classList.add('hidden');

            try {
                // Test key against wallets endpoint
                const res = await fetch(`/api/v1/wallets?active_only=true`, {
                    headers: { 'X-API-Key': key }
                });

                if (res.ok) {
                    // Set cookie and localStorage for smooth persistent session
                    document.cookie = `polyfollow_api_key=${encodeURIComponent(key)}; path=/; max-age=2592000; SameSite=Lax`;
                    localStorage.setItem('polyfollow_api_key', key);
                    window.location.href = `/dashboard?api_key=${encodeURIComponent(key)}`;
                } else {
                    err.classList.remove('hidden');
                    btn.disabled = false;
                    btn.innerHTML = `<i data-lucide="lock" class="w-4 h-4"></i><span>Unlock Terminal</span>`;
                    lucide.createIcons();
                }
            } catch (error) {
                err.textContent = "Connection error. Please try again.";
                err.classList.remove('hidden');
                btn.disabled = false;
                btn.innerHTML = `<i data-lucide="lock" class="w-4 h-4"></i><span>Unlock Terminal</span>`;
                lucide.createIcons();
            }
        }

        // Auto-fill from localStorage if previously stored
        document.addEventListener('DOMContentLoaded', () => {
            const stored = localStorage.getItem('polyfollow_api_key');
            if (stored) {
                document.getElementById('apiKeyInput').value = stored;
            }
        });
    </script>
</body>
</html>
"""


@router.get("/dashboard", response_class=HTMLResponse)
async def get_dashboard(
    response: Response,
    api_key: Optional[str] = Query(None),
    polyfollow_api_key: Optional[str] = Cookie(None),
):
    """Render the Polyfollow Dark Mode Intelligence Dashboard protected by API_KEY."""
    expected_key = settings.API_KEY

    # If API_KEY is configured, enforce security
    if expected_key and expected_key.strip():
        provided_key = api_key or polyfollow_api_key
        if not provided_key or not secrets.compare_digest(provided_key, expected_key):
            # Render security gate login page
            return HTMLResponse(content=LOGIN_GATE_HTML, status_code=200)

        # Set persistent cookie if valid
        response.set_cookie(
            key="polyfollow_api_key",
            value=provided_key,
            max_age=2592000,
            samesite="lax",
            httponly=False,
        )

    if os.path.exists(TEMPLATE_PATH):
        with open(TEMPLATE_PATH, "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read())
    return HTMLResponse(content="<h1>Dashboard template not found.</h1>", status_code=404)
