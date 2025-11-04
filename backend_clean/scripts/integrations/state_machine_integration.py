"""
Integración de State Machine con el sistema actual
"""

async def smart_state_machine_flow(worker, ticket_data: dict, context: str = "") -> dict:
    """
    Flujo de automatización usando State Machine inteligente.
    """
    from modules.invoicing_agent.state_machine import StateMachine, AutomationState, StateDecision
    import json
    import time
    import asyncio
    import logging

    logger = logging.getLogger(__name__)

    # Inicializar state machine
    state_machine = StateMachine(initial_state=AutomationState.NAVIGATION)
    max_steps = 25
    step_count = 0

    # 🧠 Sistema de memoria inteligente anti-loop
    clicked_elements = set()  # Elementos ya clickeados
    selector_attempts = {}    # {selector: {"count": 2, "last_step": 3, "worked": False}}
    url_history = []         # Historial de URLs para detectar progreso
    stagnant_steps = 0       # Contador de pasos sin progreso

    results = {
        "success": False,
        "steps": [],
        "final_reason": "",
        "screenshots": [],
        "state_transitions": [],
        "final_state": ""
    }

    logger.info(f"🚀 Iniciando flujo con State Machine - Estado inicial: {state_machine.current_state.value}")

    try:
        while step_count < max_steps and state_machine.current_state not in [AutomationState.DONE, AutomationState.ERROR]:
            step_count += 1

            # Obtener contexto actual
            html_content = worker.driver.page_source
            current_url = worker.driver.current_url

            logger.info(f"📍 Paso {step_count} - Estado: {state_machine.current_state.value} - URL: {current_url}")

            # Análisis DOM simplificado
            elementos_detectados = await analyze_page_for_state(worker, state_machine.current_state)

            # Obtener prompt específico del estado
            state_prompt = state_machine.get_state_prompt(ticket_data, html_content[:2000], elementos_detectados)

            # Llamar al LLM con contexto específico del estado (Claude o OpenAI)
            try:
                # Intentar Claude primero si está disponible
                import sys
                sys.path.append('/Users/danielgoes96/Desktop/mcp-server')
                from claude_integration import call_llm_hybrid
                decision_dict = await call_llm_hybrid(state_prompt, prefer_claude=True)
            except (ImportError, Exception) as e:
                logger.warning(f"Claude falló: {e}, usando OpenAI")
                # Fallback a OpenAI
                decision_dict = await call_llm_for_state(state_prompt)
            decision = StateDecision.from_llm_response(json.dumps(decision_dict))

            # Log de decisión
            logger.info(f"🤖 Decisión LLM: {decision.action} | {decision.selector} | {decision.reason}")

            # Guardar paso
            step_result = {
                "step": step_count,
                "state": state_machine.current_state.value,
                "url": current_url,
                "decision": decision.__dict__,
                "elements_found": len(elementos_detectados),
                "timestamp": time.time()
            }
            results["steps"].append(step_result)

            # Ejecutar acción con memoria inteligente
            success = await execute_state_action(
                worker, decision, state_machine, current_url,
                clicked_elements, selector_attempts, step_count
            )

            if decision.action in ["done", "error"]:
                results["success"] = (decision.action == "done")
                results["final_reason"] = decision.reason
                break

            # Screenshot
            try:
                screenshot_path = f"/tmp/state_automation_step_{step_count}.png"
                worker.driver.save_screenshot(screenshot_path)
                results["screenshots"].append(screenshot_path)
            except:
                pass

            await asyncio.sleep(1)

        # Estado final
        results["final_state"] = state_machine.current_state.value
        results["state_transitions"] = state_machine.history

        if state_machine.current_state == AutomationState.DONE:
            results["success"] = True

        return results

    except Exception as e:
        logger.error(f"Error crítico en state machine: {e}")
        return {
            "success": False,
            "error": str(e),
            "final_reason": f"Error en state machine: {e}",
            "final_state": state_machine.current_state.value
        }


async def analyze_page_for_state(worker, current_state):
    """Analizar página según el estado actual"""
    import logging
    elementos = []

    try:
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(worker.driver.page_source, 'html.parser')

        from modules.invoicing_agent.state_machine import AutomationState

        if current_state == AutomationState.NAVIGATION:
            # Buscar enlaces de facturación
            links = soup.find_all('a', string=lambda text: text and any(
                word in text.lower() for word in ['facturación', 'factura', 'servicio', 'portal']
            ))
            for link in links[:5]:
                elementos.append({
                    "tipo": "enlace",
                    "texto": link.get_text(strip=True),
                    "selector": f"a[href='{link.get('href')}']" if link.get('href') else ".nav-item",
                    "prioridad": 0.9
                })

        elif current_state == AutomationState.FORM_FILLING:
            # Buscar campos de formulario
            inputs = soup.find_all(['input', 'select'])
            for inp in inputs[:8]:
                name = inp.get('name', '').lower()
                placeholder = inp.get('placeholder', '').lower()

                campo_tipo = "generico"
                if any(term in name + placeholder for term in ['rfc']):
                    campo_tipo = "rfc"
                elif any(term in name + placeholder for term in ['email']):
                    campo_tipo = "email"

                elementos.append({
                    "tipo": f"campo_{campo_tipo}",
                    "texto": placeholder or name,
                    "selector": f"#{inp.get('id')}" if inp.get('id') else f"input[name='{name}']",
                    "campo_tipo": campo_tipo,
                    "prioridad": 0.9 if campo_tipo in ['rfc', 'email'] else 0.7
                })

        elif current_state == AutomationState.CONFIRMATION:
            # Buscar botones de confirmación
            buttons = soup.find_all(['button', 'input'], string=lambda text: text and any(
                word in text.lower() for word in ['generar', 'crear', 'confirmar']
            ))
            for btn in buttons[:3]:
                elementos.append({
                    "tipo": "boton",
                    "texto": btn.get_text(strip=True) if hasattr(btn, 'get_text') else btn.get('value', ''),
                    "selector": f"#{btn.get('id')}" if btn.get('id') else "button",
                    "prioridad": 0.95
                })

    except Exception as e:
        logging.warning(f"Error analizando DOM: {e}")

    return elementos


async def call_llm_for_state(prompt):
    """Llamar al LLM para decisión de estado"""
    from openai import OpenAI
    import os
    import json
    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

    try:
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "Responde SOLO con JSON válido."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=300,
            temperature=0.1
        )

        text = response.choices[0].message.content.strip()

        # Limpiar JSON
        if "```json" in text:
            text = text.split("```json")[1].split("```")[0].strip()

        return json.loads(text)

    except Exception as e:
        return {
            "action": "error",
            "selector": "",
            "reason": f"Error LLM: {e}",
            "confidence": 0.0
        }


async def execute_state_action(worker, decision, state_machine, current_url,
                              clicked_elements, selector_attempts, step_count):
    """Ejecutar acción del estado con protección anti-loop"""
    import logging
    import time
    import hashlib

    logger = logging.getLogger(__name__)

    try:
        if decision.action == "click":
            # Generar ID único del elemento
            element_id = f"{decision.selector}|{current_url}"
            element_hash = hashlib.md5(element_id.encode()).hexdigest()[:8]

            # 🔒 Protección 1: Elemento ya clickeado
            if element_hash in clicked_elements:
                logger.warning(f"🚫 Elemento ya clickeado anteriormente: {decision.selector}")
                return False

            # 🔒 Protección 2: Límite de intentos por selector
            selector_key = decision.selector
            if selector_key not in selector_attempts:
                selector_attempts[selector_key] = {"count": 0, "last_step": 0, "worked": False}

            attempt_info = selector_attempts[selector_key]
            if attempt_info["count"] >= 3:
                logger.warning(f"🚫 Selector {selector_key} ha fallado {attempt_info['count']} veces")
                return False

            # 🔒 Protección 3: Cooldown entre intentos
            if step_count - attempt_info["last_step"] < 2:
                logger.warning(f"🚫 Cooldown activo para {selector_key}")
                return False

            # Buscar elemento
            element = worker.find_element_safe(decision.selector)
            if element and element.is_displayed():
                # Registrar intento
                clicked_elements.add(element_hash)
                selector_attempts[selector_key]["count"] += 1
                selector_attempts[selector_key]["last_step"] = step_count

                logger.info(f"🖱️ Clicking: {decision.selector}")
                element.click()
                time.sleep(2)

                # Verificar progreso
                new_url = worker.driver.current_url
                if new_url != current_url:
                    selector_attempts[selector_key]["worked"] = True
                    if decision.next_state:
                        state_machine.transition_to(decision.next_state, f"Progreso detectado")
                    logger.info(f"✅ Click exitoso - URL cambió: {current_url} → {new_url}")
                    return True
                else:
                    logger.warning(f"⚠️ Click no produjo cambio de URL")
                    return False
            else:
                logger.warning(f"❌ Elemento no encontrado o no visible: {decision.selector}")
                return False

        elif decision.action == "input":
            element = worker.find_element_safe(decision.selector)
            if element and element.is_displayed():
                logger.info(f"⌨️ Inputing en: {decision.selector} = {decision.value}")
                element.clear()
                element.send_keys(decision.value)
                time.sleep(1)

                if decision.next_state:
                    state_machine.transition_to(decision.next_state, f"Campo llenado")
                return True
            else:
                logger.warning(f"❌ Campo no encontrado: {decision.selector}")
                return False

    except Exception as e:
        logger.error(f"💥 Error ejecutando acción: {e}")

    return False