"""Gemini 2.5 Computer Use automation engine for ticket invoicing portals.

This module integrates Google's Gemini 2.5 Computer Use preview model with
Playwright to drive portals using coordinate-based interactions.  It replaces
traditional DOM-driven automation while keeping a Playwright fallback for
portals that require deterministic selectors.

The engine operates as an async agent loop:
  1. Navigate to the target portal using Playwright.
  2. Capture a screenshot and build an instruction prompt with ticket/fiscal data.
  3. Call Gemini Computer Use to obtain UI actions expressed as function calls.
  4. Execute each action via Playwright (click/type/scroll, etc.).
  5. Capture the new state and feed it back to the model as a function_response.
  6. Repeat until the model returns a natural language conclusion or step limit.

If the model raises a safety confirmation we auto-approve for now, but the
result is marked so the caller can request human confirmation if needed.
"""

from __future__ import annotations

import asyncio
import base64
import logging
import os
import re
import time
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

import httpx
from playwright.async_api import (
    async_playwright,
    Browser,
    BrowserContext,
    Page,
    TimeoutError as PlaywrightTimeoutError,
)

logger = logging.getLogger(__name__)


DEFAULT_MODEL = os.getenv(
    "GEMINI_COMPUTER_USE_MODEL", "gemini-2.5-computer-use-preview-10-2025"
)
SCREEN_WIDTH = int(os.getenv("GEMINI_SCREEN_WIDTH", "960"))
SCREEN_HEIGHT = int(os.getenv("GEMINI_SCREEN_HEIGHT", "540"))
MAX_ACTION_STEPS = int(os.getenv("GEMINI_COMPUTER_USE_MAX_STEPS", "18"))


@dataclass
class GeminiActionRecord:
    step: int
    function_name: str
    args: Dict[str, Any]
    success: bool
    error: Optional[str] = None
    screenshot_path: Optional[str] = None
    url_after: Optional[str] = None
    safety_acknowledged: bool = False


class GeminiComputerUseEngine:
    """Coordinate-first automation engine powered by Gemini Computer Use."""

    def __init__(
        self,
        *,
        ticket: Dict[str, Any],
        portal_url: str,
        fiscal_profile: Dict[str, Any],
        processing_context: Optional[Dict[str, Any]] = None,
        screenshot_dir: Optional[Path] = None,
        headless: bool = True,
    ) -> None:
        self.ticket = ticket
        self.portal_url = portal_url
        self.fiscal_profile = fiscal_profile or {}
        self.processing_context = processing_context or {}

        self.api_key = os.getenv("GOOGLE_AI_API_KEY") or os.getenv("GEMINI_API_KEY")
        if not self.api_key:
            raise RuntimeError(
                "Gemini API key not configured. Set GOOGLE_AI_API_KEY or GEMINI_API_KEY."
            )

        self.model_name = DEFAULT_MODEL

        # Permitir override via variable de entorno GEMINI_HEADLESS.
        headless_override = os.getenv("GEMINI_HEADLESS")
        if headless_override is not None:
            self.headless = headless_override.strip().lower() not in {"0", "false", "no"}
        else:
            self.headless = headless

        # Runtime state
        self.playwright = None
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None
        self.initial_domain = urlparse(self.portal_url).netloc.lower() if self.portal_url else ""
        self._preferred_page: Optional[Page] = None
        self._pre_navigation_completed = False

        self.steps: List[GeminiActionRecord] = []
        self.screenshot_dir = screenshot_dir or Path("static/automation_screenshots")
        self.screenshot_dir.mkdir(parents=True, exist_ok=True)
        self.session_id = f"ticket_{self.ticket.get('id', 'unknown')}_{int(time.time())}"

        self.http_client: Optional[httpx.AsyncClient] = None
        self.tools_payload = [
            {
                "computerUse": {
                    "environment": "ENVIRONMENT_BROWSER",
                }
            }
        ]
        self.thinking_config = {"includeIntermediateResults": False}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    async def run(self) -> Dict[str, Any]:
        """Execute the Gemini Computer Use loop for the configured portal."""

        logger.info("🧠 [GeminiComputerUse] Starting automation for %s", self.portal_url)
        try:
            await self._initialize_browser()
            await self.page.goto(self.portal_url, wait_until="networkidle")
            await self._apply_generic_heuristics()

            conversation: List[Dict[str, Any]] = []
            initial_screenshot = await self._capture_screenshot("initial")
            instruction = self._build_instruction()

            conversation.append(
                {
                    "role": "user",
                    "parts": [
                        {"text": instruction},
                        {
                            "inlineData": {
                                "mimeType": "image/png",
                                "data": self._encode_file(initial_screenshot),
                            }
                        },
                    ],
                }
            )

            final_summary: Optional[str] = None
            async with httpx.AsyncClient(timeout=httpx.Timeout(120.0)) as client:
                self.http_client = client

                for turn in range(1, MAX_ACTION_STEPS + 1):
                    logger.info("🧠 [GeminiComputerUse] Turn %s", turn)

                    response_payload = await self._generate_content(conversation)
                    candidates = response_payload.get("candidates", [])
                    if not candidates:
                        logger.warning("Gemini response without candidates; aborting")
                        break

                    candidate = candidates[0]
                    candidate_content = candidate.get("content", {})
                    conversation.append(candidate_content)

                    function_calls = self._extract_function_calls(candidate_content)
                    text_response = self._extract_text(candidate_content)

                    if not function_calls:
                        final_summary = text_response or "Gemini finished without actions"
                        logger.info(
                            "🧠 [GeminiComputerUse] Model returned without actions: %s",
                            final_summary,
                        )
                        break

                    execution_results = await self._execute_function_calls(function_calls)
                    function_responses = self._build_function_responses(execution_results)
                    conversation.append({"role": "user", "parts": function_responses})

                    if text_response and any(
                        phrase in text_response.lower()
                        for phrase in [
                            "done",
                            "completed",
                            "factura generada",
                            "invoice generated",
                        ]
                    ):
                        final_summary = text_response
                        break

            success = final_summary is not None
            if final_summary is None:
                final_summary = "Se alcanzó el límite de pasos sin confirmación de éxito."

            return {
                "success": success,
                "summary": final_summary,
                "steps": [asdict(step) for step in self.steps],
                "screenshot_dir": str(self.screenshot_dir),
                "session_id": self.session_id,
                "engine": "gemini_computer_use",
            }

        except Exception as exc:  # pragma: no cover - runtime issues
            logger.exception("Error executing Gemini computer use engine: %s", exc)
            return {
                "success": False,
                "error": str(exc),
                "steps": [asdict(step) for step in self.steps],
                "engine": "gemini_computer_use",
            }
        finally:
            await self._cleanup()

    # ------------------------------------------------------------------
    # Initialization & cleanup
    # ------------------------------------------------------------------
    async def _initialize_browser(self) -> None:
        self.playwright = await async_playwright().start()

        launch_kwargs: Dict[str, Any] = {
            "headless": self.headless,
            "args": [
                "--disable-dev-shm-usage",
                "--no-sandbox",
                "--disable-breakpad",
                "--disable-gpu",
            ],
        }

        try:
            self.browser = await self.playwright.chromium.launch(**launch_kwargs)
        except Exception as exc_primary:
            logger.warning(
                "⚠️ Chromium headless launch failed (%s). Retrying with headless=False",
                exc_primary,
            )
            launch_kwargs["headless"] = False
            try:
                self.browser = await self.playwright.chromium.launch(**launch_kwargs)
            except Exception as exc_secondary:
                logger.warning(
                    "⚠️ Chromium launch still failing (%s). Retrying with Chrome channel",
                    exc_secondary,
                )
                self.browser = await self.playwright.chromium.launch(
                    channel="chrome", headless=False
                )
        self.context = await self.browser.new_context(
            viewport={"width": SCREEN_WIDTH, "height": SCREEN_HEIGHT},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            " (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        )
        self.page = await self.context.new_page()
        self.page.set_default_timeout(30000)
        self.page.on("pageerror", lambda exc: logger.error("Page error: %s", exc))

    async def _cleanup(self) -> None:
        try:
            if self.context:
                await self.context.close()
            if self.browser:
                await self.browser.close()
        finally:
            if self.playwright:
                await self.playwright.stop()

    # ------------------------------------------------------------------
    # Prompt building & data helpers
    # ------------------------------------------------------------------
    def _build_instruction(self) -> str:
        ticket_text = self.processing_context.get("extracted_text") or ""
        ticket_text = ticket_text.strip()
        max_prompt_chars = int(os.getenv("GEMINI_TICKET_TEXT_MAX", "600"))
        if len(ticket_text) > max_prompt_chars:
            ticket_text = ticket_text[:max_prompt_chars] + "..."

        fields = self._extract_ticket_fields(ticket_text)
        fiscal = {
            "rfc": self.fiscal_profile.get("company_rfc") or os.getenv("COMPANY_RFC", "XAXX010101000"),
            "razon_social": self.fiscal_profile.get("company_name") or os.getenv("COMPANY_NAME", "Mi Empresa S.A. de C.V."),
            "correo": self.fiscal_profile.get("company_email") or os.getenv("COMPANY_EMAIL", "facturacion@miempresa.com"),
            "cp": self.fiscal_profile.get("company_zip") or os.getenv("COMPANY_ZIP", "01000"),
        }

        navigation_tips = """
Guía general para cualquier portal de facturación:
- Busca botones o enlaces con textos como "Facturar", "Facturación", "CFDI", "Portal", "Ticket" o "Factura electrónica".
- Si ves un botón de menú (ícono ☰ o texto "Menu"), ábrelo y revisa las opciones relacionadas con facturación.
- Si la página principal es un banner o landing, desplázate hacia abajo hasta encontrar formularios.
- Verifica si existen campos llamados Folio, Web ID, Ticket, RFC, Fecha, Total o similares.
- Si el portal muestra avisos sobre tickets "Copia" vs "Original", reporta lo que observas.
"""

        merchant_name = (self.fiscal_profile.get("merchant_name") or self.ticket.get("merchant_name") or "").lower()
        portal_tips: List[str] = []
        if "litro" in merchant_name or "litro mil" in merchant_name:
            portal_tips.extend(
                [
                    "Haz clic en el menú (☰) de la esquina superior derecha y luego en 'Facturación'.",
                    "Si ves un botón con texto 'CLICK AQUÍ' o 'Facturación en línea', haz clic y continúa en la pestaña nueva que se abra.",
                    "Después de abrir el formulario, llena Folio y Web ID con los valores del ticket y presiona el botón para validar antes de completar los datos fiscales.",
                ]
            )

        portal_hint_text = "\n- ".join(portal_tips)

        prompt = f"""
Eres un agente experto en facturación electrónica en México. Controlas un navegador
Chrome dentro de una máquina virtual. Tu objetivo es generar la factura CFDI
correspondiente al ticket proporcionado en el portal {self.portal_url}.

Sigue estas reglas:
- Usa exclusivamente acciones por coordenadas (click_at, type_text_at, scroll) provistas por la herramienta Computer Use.
- Navega paso a paso, leyendo los formularios y llenando los campos requeridos.
- Usa la información fiscal del cliente y los datos del ticket listados abajo.
- Después de enviar la solicitud, confirma visualmente que la factura se generó o se envió correctamente.
- Cuando termines, responde únicamente con la palabra DONE seguida de un resumen breve.

Datos fiscales del cliente:
- RFC: {fiscal['rfc']}
- Razón social: {fiscal['razon_social']}
- Código postal: {fiscal['cp']}
- Correo electrónico: {fiscal['correo']}

Datos del ticket a facturar:
- Folio: {fields.get('folio', 'No encontrado')}
- Total: {fields.get('total', 'No encontrado')}
- Fecha: {fields.get('fecha', 'No encontrada')}
- Texto del ticket (resumido): {ticket_text}

Instrucciones adicionales:
- Si aparece un aviso de cookies o privacidad, ciérralo para continuar.
- Si necesitas desplazarte, usa scroll_document o scroll_at.
- Antes de escribir en un campo, haz click para enfocarlo.
- Si el portal solicita captcha o verificación manual, informa la situación.
{navigation_tips}

Sugerencias específicas detectadas por el sistema:
{('- ' + portal_hint_text) if portal_hint_text else '- Ninguna sugerencia adicional disponible.'}
"""

        instruction = prompt

        return instruction.strip()

    async def _apply_generic_heuristics(self) -> None:
        """Perform simple navigation helpers before delegating to Gemini."""
        if not self.page or self._pre_navigation_completed:
            return

        # Intentar abrir un menú hamburguesa
        try:
            menu_button = await self.page.query_selector("text=/menu/i")
            if menu_button:
                await menu_button.click()
                await asyncio.sleep(0.8)
        except Exception as exc:  # pragma: no cover - heuristics best effort
            logger.debug("Pre-navigation menu attempt failed: %s", exc)

        # Desplazarse un poco para revelar formularios ocultos
        try:
            await self.page.mouse.wheel(0, 400)
            await asyncio.sleep(0.4)
        except Exception as exc:  # pragma: no cover
            logger.debug("Pre-navigation scroll failed: %s", exc)

        # Intentar localizar enlaces claros de facturación
        try:
            candidate = await self.page.query_selector(
                "text=/facturación|facturacion|factura|click aquí/i"
            )
            if candidate:
                await candidate.click()
                await asyncio.sleep(0.5)
                if self.context:
                    try:
                        captured: List[Page] = []
                        while True:
                            try:
                                new_page = await self.context.wait_for_event(
                                    "page", timeout=1000
                                )
                                await new_page.wait_for_load_state()
                                captured.append(new_page)
                            except PlaywrightTimeoutError:
                                break
                        if captured:
                            self.page = captured[-1]
                    except PlaywrightTimeoutError:
                        pass
                await self._switch_to_relevant_page()
        except Exception as exc:  # pragma: no cover
            logger.debug("Pre-navigation facturación hint failed: %s", exc)

        self._pre_navigation_completed = True
        await self._switch_to_relevant_page()

    async def _wait_for_stability(self) -> None:
        if not self.page:
            return
        try:
            await self.page.wait_for_load_state("networkidle", timeout=3000)
        except PlaywrightTimeoutError:
            pass
        cooldown = float(os.getenv("GEMINI_ACTION_COOLDOWN", "0.6"))
        if cooldown > 0:
            await asyncio.sleep(cooldown)
        await self._switch_to_relevant_page()

    async def _switch_to_relevant_page(self) -> None:
        if not self.context or not self.context.pages:
            return

        if self._preferred_page and self._preferred_page not in self.context.pages:
            self._preferred_page = None

        # Mantener la página preferida si aún está disponible
        if self._preferred_page and self._preferred_page in self.context.pages:
            try:
                await self._preferred_page.bring_to_front()
            except Exception:
                pass
            self.page = self._preferred_page
            return

        best_page = None
        best_score = -1.0
        for candidate_page in self.context.pages:
            try:
                url = candidate_page.url or ""
            except Exception:
                continue

            lower_url = url.lower()
            if not lower_url:
                continue
            if lower_url.startswith("about:blank"):
                continue
            if lower_url.startswith("chrome-error://"):
                continue

            score = 0.0
            if any(keyword in lower_url for keyword in ["factura", "facturacion", "cfdi", "ticket", "portal", "litromil"]):
                score += 5

            domain = urlparse(lower_url).netloc
            if self.initial_domain and domain != self.initial_domain:
                score += 2

            if candidate_page is self.page:
                score += 0.2

            if score > best_score:
                best_score = score
                best_page = candidate_page

        if best_page and best_page is not self.page:
            try:
                await best_page.bring_to_front()
            except Exception:
                pass
            self.page = best_page
            self._preferred_page = best_page
            current_url = (best_page.url or "").lower()
            if current_url:
                self.initial_domain = urlparse(current_url).netloc

    def _extract_ticket_fields(self, text: str) -> Dict[str, str]:
        fields: Dict[str, str] = {}
        try:
            folio = re.search(r"FOLIO\s*[:#-]?\s*([A-Z0-9\-]{4,})", text, re.IGNORECASE)
            total = re.search(r"TOTAL\s*\$?\s*([\d,]+\.\d{1,2}|[\d,]+)", text, re.IGNORECASE)
            fecha = re.search(r"(\d{2}[/-]\d{2}[/-]\d{2,4})", text)
            if folio:
                fields["folio"] = folio.group(1)
            if total:
                fields["total"] = total.group(1).replace(",", "")
            if fecha:
                fields["fecha"] = fecha.group(1)
        except Exception as exc:  # pragma: no cover - best effort parsing
            logger.debug("Ticket field extraction failed: %s", exc)
        return fields

    # ------------------------------------------------------------------
    # Gemini interaction helpers
    # ------------------------------------------------------------------
    def _extract_function_calls(self, candidate: genai_types.Candidate) -> List[genai_types.FunctionCall]:
        calls: List[genai_types.FunctionCall] = []
        for part in candidate.content.parts:
            if isinstance(part, genai_types.Part) and part.function_call:
                calls.append(part.function_call)
        return calls

    def _extract_text(self, candidate: genai_types.Candidate) -> str:
        texts: List[str] = []
        for part in candidate.content.parts:
            if part.text:
                texts.append(part.text)
        return " ".join(texts).strip()

    async def _execute_function_calls(
        self, function_calls: List[Dict[str, Any]]
    ) -> List[GeminiActionRecord]:
        results: List[GeminiActionRecord] = []
        for call in function_calls:
            success = True
            error_message = None
            safety_ack = False

            args = dict(call.get("args") or {})
            function_name = call.get("name", "")
            safety_decision = args.pop("safety_decision", None)
            if safety_decision:
                logger.info("⚠️ Gemini safety decision: %s", safety_decision)
                # For now automatically acknowledge; caller may decide to halt based on record
                safety_ack = True

            try:
                await self._execute_single_action(function_name, args)
                await self._wait_for_stability()
                url_after = self.page.url if self.page else None
                screenshot_path = await self._capture_screenshot(function_name)
            except Exception as exc:  # pragma: no cover - action failure
                logger.exception("Gemini action %s failed: %s", function_name, exc)
                success = False
                error_message = str(exc)
                await self._wait_for_stability()
                screenshot_path = await self._capture_screenshot(f"error_{function_name}")
                url_after = self.page.url if self.page else None

            record = GeminiActionRecord(
                step=len(self.steps) + 1,
                function_name=function_name,
                args=args,
                success=success,
                error=error_message,
                screenshot_path=screenshot_path,
                url_after=url_after,
                safety_acknowledged=safety_ack,
            )
            self.steps.append(record)
            results.append(record)

        return results

    async def _execute_single_action(self, name: str, args: Dict[str, Any]) -> None:
        if not self.page:
            raise RuntimeError("Playwright page not initialized")

        logger.info("🧠 [GeminiComputerUse] Executing %s(%s)", name, args)

        if name == "open_web_browser":
            return  # already open

        if name == "navigate":
            url = args.get("url")
            if not url:
                raise ValueError("navigate requires 'url'")
            await self.page.goto(url, wait_until="networkidle")
            return

        if name in {"click_at", "hover_at"}:
            x = self._denormalize_x(int(args.get("x", 0)))
            y = self._denormalize_y(int(args.get("y", 0)))
            if name == "click_at":
                await self.page.mouse.click(x, y)
            else:
                await self.page.mouse.move(x, y)
            await asyncio.sleep(0.5)
            return

        if name == "type_text_at":
            safety_decision = args.pop("safety_decision", None)
            if safety_decision:
                logger.info("⚠️ Seguimiento safety en type_text_at: %s", safety_decision)
            x = self._denormalize_x(int(args.get("x", 0)))
            y = self._denormalize_y(int(args.get("y", 0)))
            text = args.get("text", "")
            press_enter = bool(args.get("press_enter", False))
            clear_before = args.get("clear_before_typing", True)
            await self.page.mouse.click(x, y)
            if clear_before:
                await self.page.keyboard.press("Control+A")
                await self.page.keyboard.press("Backspace")
            if text:
                await self.page.keyboard.type(text)
            if press_enter:
                await self.page.keyboard.press("Enter")
            await asyncio.sleep(0.5)
            return

        if name == "scroll_document":
            direction = args.get("direction", "down").lower()
            amount = 800
            if direction == "down":
                await self.page.mouse.wheel(0, amount)
            elif direction == "up":
                await self.page.mouse.wheel(0, -amount)
            elif direction == "left":
                await self.page.mouse.wheel(-amount, 0)
            elif direction == "right":
                await self.page.mouse.wheel(amount, 0)
            else:
                raise ValueError(f"scroll_document direction unknown: {direction}")
            await asyncio.sleep(0.4)
            return

        if name == "scroll_at":
            x = self._denormalize_x(int(args.get("x", 0)))
            y = self._denormalize_y(int(args.get("y", 0)))
            direction = args.get("direction", "down").lower()
            magnitude = int(args.get("magnitude", 600))
            await self.page.mouse.move(x, y)
            delta = magnitude if direction in ("down", "right") else -magnitude
            if direction in ("down", "up"):
                await self.page.mouse.wheel(0, delta)
            else:
                await self.page.mouse.wheel(delta, 0)
            await asyncio.sleep(0.4)
            return

        if name == "wait_5_seconds":
            await asyncio.sleep(5)
            return

        if name == "go_back":
            await self.page.go_back(wait_until="networkidle")
            return

        if name == "go_forward":
            await self.page.go_forward(wait_until="networkidle")
            return

        if name == "key_combination":
            keys = args.get("keys")
            if not keys:
                raise ValueError("key_combination requires 'keys'")
            await self._press_key_combination(keys)
            return

        raise NotImplementedError(f"Gemini function {name} not implemented")

    async def _press_key_combination(self, combo: str) -> None:
        keys = combo.split("+")
        keys = [k.strip() for k in keys if k.strip()]
        if not keys:
            return
        # Playwright expects lowercase for modifier names
        await self.page.keyboard.down(keys[0])
        for key in keys[1:]:
            await self.page.keyboard.press(key)
        await self.page.keyboard.up(keys[0])
        await asyncio.sleep(0.2)

    def _build_function_responses(
        self, records: List[GeminiActionRecord]
    ) -> List[genai_types.Part]:
        parts: List[genai_types.Part] = []
        for record in records:
            response_payload = {
                "step": record.step,
                "success": record.success,
                "error": record.error,
                "url": record.url_after,
            }

            if record.safety_acknowledged:
                ack_payload = {"status": "acknowledged"}
                if record.error:
                    ack_payload["notes"] = record.error
                elif record.args:
                    ack_payload["reason"] = "accepted"

                response_payload["safety_acknowledgement"] = ack_payload
            screenshot_data = None
            if record.screenshot_path:
                screenshot_bytes = Path(record.screenshot_path).read_bytes()
                screenshot_data = genai_types.FunctionResponsePart(
                    inline_data=genai_types.FunctionResponseBlob(
                        mime_type="image/png", data=screenshot_bytes
                    )
                )

            function_response = genai_types.FunctionResponse(
                name=record.function_name,
                response=response_payload,
                parts=[screenshot_data] if screenshot_data else None,
            )

            parts.append(genai_types.Part(function_response=function_response))

        return parts

    async def _capture_screenshot(self, label: str) -> Path:
        if not self.page:
            raise RuntimeError("Playwright page not initialized")
        filename = f"{self.session_id}_{len(self.steps):02d}_{label}.png"
        path = self.screenshot_dir / filename
        await self.page.screenshot(
            path=path,
            full_page=False,
            type="jpeg",
            quality=int(os.getenv("GEMINI_SCREENSHOT_QUALITY", "45")),
            scale="css",
            omit_background=True,
        )
        return str(path)

    def _denormalize_x(self, x: int) -> int:
        return max(0, min(SCREEN_WIDTH, int(x / 1000 * SCREEN_WIDTH)))

    def _denormalize_y(self, y: int) -> int:
        return max(0, min(SCREEN_HEIGHT, int(y / 1000 * SCREEN_HEIGHT)))

    def _encode_file(self, path: Path | str) -> str:
        if isinstance(path, str):
            path = Path(path)
        return base64.b64encode(path.read_bytes()).decode("utf-8")

    async def _generate_content(self, conversation: List[Dict[str, Any]]) -> Dict[str, Any]:
        if not self.http_client:
            raise RuntimeError("HTTP client not initialized")

        endpoint = (
            f"https://generativelanguage.googleapis.com/v1beta/models/"
            f"{self.model_name}:generateContent?key={self.api_key}"
        )

        payload: Dict[str, Any] = {
            "contents": conversation,
            "tools": self.tools_payload,
        }

        response = await self.http_client.post(endpoint, json=payload)

        if response.status_code >= 400:
            try:
                error_json = response.json()
            except Exception:
                error_json = response.text

            logger.error(
                "Gemini Computer Use API error %s: %s",
                response.status_code,
                error_json,
            )

        response.raise_for_status()
        return response.json()

    def _extract_function_calls(self, content: Dict[str, Any]) -> List[Dict[str, Any]]:
        function_calls: List[Dict[str, Any]] = []
        for part in content.get("parts", []):
            function_call = part.get("functionCall")
            if function_call:
                function_calls.append(function_call)
        return function_calls

    def _extract_text(self, content: Dict[str, Any]) -> str:
        texts: List[str] = []
        for part in content.get("parts", []):
            if "text" in part:
                texts.append(part["text"])
        return " ".join(texts).strip()

    def _build_function_responses(
        self, records: List[GeminiActionRecord]
    ) -> List[Dict[str, Any]]:
        parts: List[Dict[str, Any]] = []
        for record in records:
            response_payload = {
                "step": record.step,
                "success": record.success,
                "error": record.error,
                "url": record.url_after,
                "safety_acknowledged": record.safety_acknowledged,
            }
            if record.screenshot_path:
                response_payload["screenshot_png_base64"] = self._encode_file(
                    Path(record.screenshot_path)
                )

            parts.append(
                {
                    "functionResponse": {
                        "name": record.function_name,
                        "response": response_payload,
                    }
                }
            )

        return parts


__all__ = ["GeminiComputerUseEngine", "GeminiActionRecord"]
