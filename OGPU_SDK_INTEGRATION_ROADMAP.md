# OGPU SDK Integration Roadmap

## Contexto

OpenReef usa la API del SDK de OGPU (`ogpu` v0.2.1) como su capa de compute. Actualmente estamos alineados a ~80% con el SDK, pero hay funcionalidades probadas que no estamos aprovechando. Este documento cataloga qué usamos, qué nos falta, y el plan de integración por prioridad.

---

## 1. Estado actual vs SDK completo

### Módulos del SDK disponibles

| Módulo | Qué hace | ¿Lo usamos? |
|---|---|---|
| `ogpu.client` | Funciones de alto nivel: publish, cancel, confirm | ✅ Parcialmente |
| `ogpu.protocol` | Clases de instancia: Source, Task, Response, Provider, Master | ✅ Parcialmente |
| `ogpu.types` | Enums, errores tipados, Receipt, dataclasses de metadata | ✅ Parcialmente |
| `ogpu.chain` | ChainConfig, ChainId, setup de RPC | ✅ Sí |
| `ogpu.events` | 6 async watchers de eventos on-chain | ❌ No |
| `ogpu.agent` | Agent scheduler para providers | ❌ No |
| `ogpu.ipfs` | Publish/fetch de contenido off-chain | ❌ No |
| `ogpu.service` | Framework para desarrolladores de source | ❌ No |

### Lo que ya usamos correctamente

- `publish_source(SourceInfo(...))` — publica source on-chain
- `publish_task(TaskInfo(...))` — publica task con escrow
- `Task(addr).get_status()` — mapeo de estados (NEW→queued, ATTEMPTED→running, etc.)
- `Task(addr).get_confirmed_response().fetch_data()` — obtiene resultado final
- `ChainConfig.set_chain(ChainId.OGPU_TESTNET)` — testnet/mainnet
- `cancel_task(task_addr)` — cancelación best-effort
- `DeliveryMethod.FIRST_RESPONSE` — correcto, lo usamos implícitamente

### Lo que usamos pero con gap

| En nuestro código | SDK real | Gap |
|---|---|---|
| `get_task_status()` → `get_num_attempts()` | `get_attempt_count()` | Nombre diferente (no critical) |
| `get_task_result()` → `response.fetch_data()` | `task.get_confirmed_response().fetch_data()` | Funcionalmente igual ✅ |
| `cancel_task()` sin receipt | `cancel_task()` → `Receipt` | Perdemos tx_hash y gas_used |

---

## 2. Features del SDK que NO usamos (ordenadas por valor)

### A. Event watchers (`ogpu.events`)

El SDK ofrece 6 async generators que hacen polling de logs on-chain y yieldan dataclasses tipados:

| Watcher | Qué devuelve | Para qué nos sirve |
|---|---|---|
| `watch_attempted(task)` | `AttemptedEvent(task, provider, suggested_payment, block_number)` | **Saber qué provider intentó el job — llena `job.provider_address` automáticamente** |
| `watch_task_status_changed(task)` | `TaskStatusChangedEvent(task, status, block_number)` | **Reemplazar polling de 30s por event-driven updates** |
| `watch_response_submitted(task)` | `ResponseSubmittedEvent(task, response, provider)` | Saber cuándo hay resultado sin polling |
| `watch_response_status_changed(response)` | `ResponseStatusChangedEvent(response, status)` | Confirmación de respuesta finalizada |
| `watch_task_published(source)` | `TaskPublishedEvent(source, task, client)` | Dashboard admin: ver tasks nuevos del source |
| `watch_registered(source)` | `RegisteredEvent(source, provider)` | Tracking de provider registrations |

**Impacto:** Eliminar polling manual, reemplazar por event-driven. Reducir RPC calls de ~2 por ciclo (cada 30s) a solo recibir eventos cuando ocurren.

### B. Task reads adicionales (`ogpu.protocol.Task`)

| Método | Qué devuelve | Para qué nos sirve |
|---|---|---|
| `task.get_attempters()` | `list[str]` — provider addresses | **Identificar quién está trabajando el job** |
| `task.get_attempt_timestamps()` | `list[int]` — unix timestamps | Calcular duración real del job |
| `task.get_winning_provider()` | `str | None` | **Quién completó el job — para reputación** |
| `task.get_payment()` | `int` (wei) | Verificar monto escrow |
| `task.get_expiry_time()` | `int` (unix) | Timeout dinámico basado en expiry real |
| `task.get_delivery_method()` | `DeliveryMethod` | Validar configuración |
| `task.get_responses()` | `list[Response]` | Ver todas las respuestas (no solo la confirmada) |
| `task.snapshot()` | `TaskSnapshot` (frozen dataclass) | **Captura todo el estado en un batch RPC** — reduce N calls a 1 |

### C. Typed errors (`ogpu.types`)

| Error | Cuándo se lanza | Para qué nos sirve |
|---|---|---|
| `InsufficientBalanceError` | Vault no tiene suficiente para el payment | Feedback claro al usuario antes de intentar publicar |
| `SourceInactiveError` | El source fue desactivado | Alerta de que hay que publicar nuevo source |
| `TaskAlreadyFinalizedError` | Intentar cancelar task ya completada | Evitar intentos de cancel innecesarios |
| `NotTaskOwnerError` | No eres el dueño del task | Validación de ownership |
| `MissingSignerError` | No hay private key configurada | Debug de configuración |
| `IPFSGatewayError` | Fallo al subir/bajar de IPFS | Retry o fallback |

### D. Vault operations (`ogpu.protocol.vault`)

| Método | Qué hace | Para qué nos sirve |
|---|---|---|
| `vault.deposit(address, amount)` | Depositar fondos en vault | Funding del escrow desde backend |
| `vault.lock(amount)` | Lock funds para una operación | Preparar payment |
| `vault.get_balance_of(address)` | Consultar balance del vault | **Verificar fondos antes de publicar task** |
| `vault.get_lockup_of(address)` | Consultar fondos bloqueados | Tracking de escrow |
| `vault.unbond()` | Iniciar unbonding | Liberar fondos |

### E. Source operations (`ogpu.client`)

| Función | Qué hace | Para qué nos sirve |
|---|---|---|
| `update_source(source, new_info)` | Actualizar parámetros del source | Cambiar imagen, payment, etc. |
| `inactivate_source(source)` | Desactivar source (one-way) | Parar nuevos jobs en un source viejo |
| `get_task_responses(task_addr)` | Listar todas las respuestas | Ver historial de intentos |

### F. Agent framework (`ogpu.agent`)

| Feature | Qué hace | Para qué nos sirve |
|---|---|---|
| `set_agent(address, value)` | Delegar operaciones a un agent | Operaciones automáticas sin firma manual |
| Agent scheduler | Responder a eventos on-chain | **Podría automatizar requeue/cancel desde el SDK** |

### G. IPFS utilities (`ogpu.ipfs`)

| Feature | Qué hace | Para qué nos sirve |
|---|---|---|
| `ipfs.publish(data)` | Subir contenido a IPFS | Metadata de config Axolotl (ya lo hace `publish_task` internamente) |
| `ipfs.fetch(cid)` | Bajar contenido de IPFS | Obtener task config sin SDK wrapper |

---

## 3. Roadmap de integración

### Prioridad 1 — Inmediata (mejora directa del código existente)

**1.1 Usar `task.snapshot()` en el polling de Celery**

Actualmente hacemos `get_status()` + `get_num_attempts()` en cada ciclo de polling — 2 RPC calls. Con `snapshot()` capturamos todo en un batch.

```python
# Antes (2 RPC calls por ciclo)
status = task.get_status()
attempts = task.get_num_attempts()

# Después (1 batch RPC)
snap = task.snapshot()
status = snap.status
attempts = snap.attempt_count
```

**Archivo:** `backend/app/services/ogpu_real.py`

**1.2 Usar `task.get_attempters()` para tracking de provider**

```python
attempters = task.get_attempters()
if attempters:
    job.provider_address = attempters[0]  # primer provider
```

Esto llena `job.provider_address` con datos reales, no None. Esencial para el sistema de reputación.

**Archivo:** `backend/app/services/ogpu_real.py`, `backend/app/tasks/training.py`

**1.3 Usar `task.get_winning_provider()` para reputación**

```python
winner = task.get_winning_provider()
if winner:
    provider_service.record_provider_completion(session, winner)
```

**Archivo:** `backend/app/tasks/training.py`

**1.4 Usar `task.get_attempt_timestamps()` para duración real**

```python
timestamps = task.get_attempt_timestamps()
if timestamps:
    duration = timestamps[-1] - timestamps[0]
    # log de duración para pricing futuro
```

**Archivo:** `backend/app/tasks/training.py`

**1.5 Capturar `Receipt` de `cancel_task`**

```python
receipt = cancel_task(task_addr)
# receipt.tx_hash, receipt.gas_used → log/auditoría
```

**Archivo:** `backend/app/services/ogpu_real.py`

---

### Prioridad 2 — Corto plazo (nuevas funcionalidades)

**2.1 Pre-flight balance check con `vault.get_balance_of()`**

Antes de publicar un task, verificar que el vault tiene fondos suficientes:

```python
from ogpu.protocol import vault
balance = vault.get_balance_of(source_address)
if balance < payment:
    raise InsufficientBalanceError(...)
```

Esto da feedback al usuario **antes** de intentar publicar, en vez de recibir un error on-chain.

**Archivo:** `backend/app/services/ogpu_real.py`, `backend/app/services/job_service.py`

**2.2 Typed error handling**

Reemplazar el `except Exception: pass` genérico con catch de errores específicos:

```python
from ogpu.types import (
    InsufficientBalanceError, SourceInactiveError,
    TaskAlreadyFinalizedError, MissingSignerError,
    IPFSGatewayError
)

try:
    task = publish_task(task_info)
except InsufficientBalanceError:
    # Mensaje claro: "Fondos insuficientes en vault"
except SourceInactiveError:
    # Alerta: "Source desactivado, contacta admin"
except IPFSGatewayError:
    # Retry: "IPFS temporalmente no disponible"
```

**Archivo:** `backend/app/services/ogpu_real.py`

**2.3 Dynamic timeout con `task.get_expiry_time()`**

Usar el expiry real del task on-chain para calcular timeout dinámico:

```python
expiry = task.get_expiry_time()
remaining = expiry - int(time.time())
# timeout = remaining * 0.9 (90% del tiempo disponible)
```

**Archivo:** `backend/app/tasks/training.py`

---

### Prioridad 3 — Medio plazo (cambios arquitecturales)

**3.1 Reemplazar polling por event watchers (`ogpu.events`)**

El Celery worker actualmente hace polling cada 30s. Con `watch_task_status_changed` podemos hacerlo event-driven:

```python
import asyncio
from ogpu.events import watch_task_status_changed

async def monitor_task_lifecycle(task_addr: str):
    async for event in watch_task_status_changed(task_addr, poll_interval=5.0):
        # event.status es TaskStatus typed enum
        handle_status_change(event.status)
        if event.status in (TaskStatus.FINALIZED, TaskStatus.EXPIRED, TaskStatus.CANCELED):
            break

asyncio.run(monitor_task_lifecycle(task_address))
```

Esto elimina completamente el patrón de self-rescheduling del Celery task. En su lugar, un async generator escucha eventos y actualiza la DB cuando ocurren.

**Archivo:** `backend/app/tasks/training.py` (rewritten)

**3.2 Usar `watch_attempted` para tracking de provider en tiempo real**

```python
from ogpu.events import watch_attempted

async def track_first_attempter(task_addr: str) -> str:
    async for event in watch_attempted(task_addr):
        return event.provider  # primer provider en intentar
```

Esto da el provider address instantáneamente cuando alguien intenta el job, sin tener que hacer polling de `get_attempters()`.

---

### Prioridad 4 — Largo plazo (nuevos sistemas)

**4.1 Agent framework para automatización**

Usar `set_agent()` para delegar operaciones de cancel/retry a un agent address. El agent podría:

- Detectar `EXPIRED` events y auto-requeue jobs
- Monitorizar múltiples jobs simultáneamente
- Ejecutar refunds automáticos

**4.2 Source management dashboard**

Usar `Source.get_tasks()`, `Source.get_registrants()`, `Source.get_task_count()` para un panel admin que muestre:

- Cuántos jobs hay por source
- Cuántos providers están registrados
- Health del source

**4.3 IPFS metadata tracking**

Usar `task.get_metadata()` y `response.fetch_data()` para validar configs y resultados directamente desde IPFS, sin depender del SDK wrapper.

---

## 4. Resumen de archivos a modificar

| Archivo | Prioridad | Cambios |
|---|---|---|
| `backend/app/services/ogpu_real.py` | 1, 2 | `snapshot()`, `get_attempters()`, `get_winning_provider()`, typed errors, vault balance, expiry |
| `backend/app/tasks/training.py` | 1, 3 | `snapshot()` en polling, provider tracking desde attempters, event watchers |
| `backend/app/services/job_service.py` | 2 | Pre-flight balance check |
| `backend/app/services/provider_service.py` | 1 | `record_provider_completion` con `get_winning_provider()` |
| `backend/app/api/providers.py` | 1 | Cancel con Receipt |

## 5. Reglas de integración

- **Nunca romper el adapter mock**: El mock debe seguir funcionando para desarrollo. Todos los cambios van solo en el adapter real.
- **Nunca añadir dependencias nuevas**: Todo usa el SDK `ogpu` ya instalado.
- **Los watchers de eventos son async**: El Celery worker actual es sync. Para usarlos necesitamos un async loop aislado (como hace el propio SDK en su guía de eventos).
- **Typed errors son opcionales pero recomendados**: Mejoran el debug sin cambiar la lógica.
- **Prioridad 1 es mergeable hoy**: No requiere cambios arquitecturales, solo aprovechar mejor lo que ya usamos.
