# OpenReef — Documento del MVP

## 1. Objetivo del MVP

El objetivo del MVP de OpenReef es validar que existe demanda real para una plataforma sencilla, usable y económica construida sobre OpenGPU Network, centrada en el caso de uso más valioso y más claro: **fine-tuning simple de modelos open-source pequeños/medios** sobre infraestructura descentralizada. OpenReef se apoya en una arquitectura web sencilla con backend API, cola de trabajos y workers desacoplados, un patrón bastante común para tareas pesadas y asíncronas. [web:128][web:131][web:137]

El MVP no busca resolver todo el roadmap. Busca demostrar que un usuario puede registrarse, subir un dataset, lanzar un fine-tune básico, seguir el progreso, descargar el resultado y pagar de forma simple, sin tener que tocar terminal, YAML ni pipelines complejos. Axolotl ya ofrece un flujo directo para LoRA y QLoRA a partir de configuraciones YAML y datasets tipo JSONL, lo que lo convierte en una base razonable para este primer alcance. [web:129]

## 2. Qué NO entra

Para mantener el MVP pequeño, quedan fuera o muy reducidos varios elementos del documento maestro. No habrá fallback a infraestructura centralizada; todo el cómputo seguirá dependiendo de OGPU. Tampoco habrá en esta fase un sistema completo de escrow on-chain, earnings avanzados para comunidad, DPO, formatos exóticos, ni observabilidad compleja. [web:129]

El criterio es simple: si una función no es necesaria para que el usuario complete el flujo “subir datos → entrenar → recibir modelo”, se pospone.

## 3. Problema que resuelve

Hoy hacer fine-tuning de un modelo open-source sigue siendo caro, fragmentado y demasiado técnico para muchos usuarios. Axolotl simplifica parte del entrenamiento, pero sigue siendo una herramienta de línea de comandos basada en configuración; OpenReef convierte ese flujo en una experiencia web asistida. [web:129]

El MVP valida tres hipótesis:
- que hay usuarios dispuestos a pagar por una experiencia de fine-tuning más simple;
- que OGPU puede servir como base operativa suficiente para este tipo de jobs;
- que el modelo pay-as-you-go tiene sentido frente a herramientas centralizadas más caras.

## 4. Alcance del MVP

### Funcionalidades incluidas

El MVP incluirá solo lo necesario para completar el flujo principal:

- Registro e inicio de sesión por email y contraseña.
- Dashboard básico de usuario.
- Subida de dataset en formatos limitados.
- Validación de dataset antes del entrenamiento.
- Selección de modelo base desde una lista cerrada.
- Configuración sencilla del fine-tuning con presets.
- Lanzamiento de job sobre OGPU.
- Seguimiento de estado del job.
- Checkpointing básico y reintento simple.
- Descarga del artefacto resultante.
- Pago con Stripe mediante créditos internos.
- Soporte por Telegram.

### Funcionalidades pospuestas

Se dejan para fases posteriores:

- Login con wallet y pagos directos en OGPU.
- Community Hub completo.
- Quantization Lab completo.
- Dataset Lab completo.
- API Hosting serverless.
- Escrow on-chain.
- Earnings para creadores.
- IA de soporte.
- Onboarding pulido de providers.

## 5. Caso de uso principal

El MVP está diseñado alrededor de un único caso de uso fuerte:

1. El usuario se registra.
2. Sube un dataset sencillo.
3. El sistema valida formato y tamaño.
4. Elige un modelo base compatible.
5. Selecciona un preset de entrenamiento.
6. Lanza el job.
7. Ve progreso y estado.
8. Si hay fallo, el sistema reintenta o devuelve el saldo.
9. Si todo va bien, descarga su LoRA o artefacto resultante.

Si este flujo funciona bien, el MVP ya habrá demostrado utilidad real.

## 6. Arquitectura simple del MVP

La arquitectura debe ser la más sencilla posible, pero suficientemente robusta para jobs asíncronos. Un stack tipo FastAPI + Celery + Redis + PostgreSQL encaja bien para separar API, cola de trabajos y ejecución en workers. [web:128][web:131][web:134][web:137]

### Componentes

- **Frontend**: Next.js + shadcn/ui.
- **Backend API**: FastAPI.
- **Base de datos**: PostgreSQL.
- **Cola de trabajos**: Celery + Redis.
- **Storage**: Cloudflare R2.
- **Training worker**: worker Python que genera config de Axolotl y lanza entrenamiento. Axolotl soporta LoRA y QLoRA de forma directa mediante YAML y CLI. [web:129]
- **Infraestructura de compute**: OpenGPU Network.
- **Pagos**: Stripe.

### Arquitectura lógica

```text
Frontend (Next.js)
      ↓
Backend API (FastAPI)
      ↓
PostgreSQL  ←→ Redis/Celery
      ↓
Job Orchestrator
      ↓
Worker sobre OGPU
      ↓
Axolotl + dataset + modelo base
      ↓
Output en R2
```

No hace falta microservicios complejos. El MVP puede funcionar bien con una estructura bastante monolítica en API/orquestación y un worker separado para los jobs pesados. [web:128][web:137]

## 7. Stack del MVP

### Frontend
- Next.js
- TypeScript
- shadcn/ui

### Backend
- FastAPI
- SQLAlchemy o similar
- PostgreSQL
- Redis
- Celery

### ML / jobs
- Axolotl para LoRA y QLoRA. Axolotl documenta ejemplos directos con `adapter: lora` y `adapter: qlora`, así como datasets JSONL tipo alpaca. [web:129]
- Python workers

### Infraestructura
- OpenGPU Network SDK
- Cloudflare R2
- Stripe
- Docker / Docker Compose para desarrollo local, un patrón común en stacks FastAPI + Celery + Redis. [web:131][web:137]

## 8. Qué implementaremos exactamente

### 8.1 Autenticación

Versión simple:
- email + contraseña;
- verificación básica de correo;
- recuperación de contraseña;
- JWT para sesión.

No entra wallet login todavía.

### 8.2 Dashboard

Un dashboard mínimo con:
- balance de créditos;
- lista de jobs;
- estado actual;
- acceso a datasets y modelos generados.

### 8.3 Dataset upload

Formatos iniciales:
- JSONL;
- CSV;
- TXT.

PDF o parseos más complejos quedan fuera o muy limitados.

### 8.4 Validación de dataset

Antes de permitir lanzar un job, el backend debe comprobar:
- tamaño máximo;
- filas máximas;
- columnas mínimas;
- estructura válida;
- estimación básica de tokens;
- si el dataset es compatible con el preset elegido.

Esto es clave para evitar errores caros antes de usar compute.

### 8.5 Fine-tuning

El MVP soportará:
- LoRA;
- QLoRA;
- modelos pequeños/medios, principalmente 7B y quizá algún 13B compatible.

No habrá libertad total de configuración. En vez de exponer decenas de hiperparámetros, se ofrecerán presets simples:
- **Rápido**
- **Equilibrado**
- **Calidad**

Internamente, esos presets se traducen a YAMLs concretos de Axolotl. Axolotl ya permite controlar parámetros como `adapter`, `load_in_8bit`, `load_in_4bit`, `micro_batch_size`, `num_epochs` y `learning_rate` desde configuración. [web:129]

### 8.6 SmartRoute MVP

Versión simple, sin optimización compleja:
- comprobar requisitos mínimos del job;
- consultar disponibilidad básica;
- elegir un nodo compatible;
- lanzar el job.

No hace falta aún un motor ultra sofisticado. Lo importante es que funcione de forma predecible.

### 8.7 Checkpointing y recuperación

Versión mínima:
- guardar checkpoints periódicos;
- si el nodo cae, reintentar una vez;
- si vuelve a fallar, reembolso completo.

No entra aún una política compleja de reanudación multiintento.

### 8.8 Pagos

Versión simple:
- créditos internos en USD;
- recarga con Stripe;
- coste mostrado antes de lanzar job;
- devolución automática del sobrante o reembolso cuando corresponda.

Stripe es una opción razonable y muy común para MVPs SaaS por su integración relativamente directa y su soporte global. [web:130][web:136]

## 9. Límites operativos del MVP

Para no romper la red ni la plataforma, el MVP nace con límites estrictos.

### Por usuario
- 1 job activo por cuenta.
- límite diario de jobs.
- límite de gasto si hace falta.

### Por dataset
- máximo 500 MB.
- máximo 100.000 filas.
- máximo 4.096 tokens por ejemplo.

### Por modelos
- lista cerrada de modelos base compatibles.
- foco en 7B y algunos 13B si el routing lo permite.

### Por configuración
- solo presets, no configuración libre total.

## 10. Versionado mínimo

El MVP no necesita un registry complejo, pero sí orden básico.

### Datasets
Cada dataset subido tendrá:
- `dataset_id`
- nombre
- fecha
- tamaño
- formato
- estado de validación

### Modelos
Cada resultado tendrá:
- `project_id`
- modelo base
- versión
- dataset usado
- preset empleado
- fecha
- estado
- ruta de descarga

Una conversión o cuantización futura podrá tratarse como artefacto derivado, pero si esa parte aún no está implementada no hace falta modelarla en exceso desde el día uno.

## 11. Seguridad MVP

La seguridad del MVP debe ser razonable, no maximalista.

### Qué sí haremos
- cifrar datasets en storage con `cryptography`/Fernet;
- usar TLS en tránsito;
- descifrar durante ejecución solo cuando sea necesario;
- borrar temporales al terminar;
- eliminar claves temporales del entorno del worker.

### Qué no prometemos aún
- TEE o aislamiento hardware avanzado;
- seguridad perfecta contra un provider malicioso con control profundo del host;
- escrow criptográfico completo desde el día uno.

## 12. Monitoring y operaciones

Versión mínima y suficiente:
- endpoint `/health` en FastAPI; hay librerías sencillas para esto y el patrón es muy común. [web:125]
- métricas básicas de errores, latencia y jobs;
- Flower para ver workers y colas Celery. Flower es precisamente la herramienta típica para monitorizar Celery. [web:126][web:137]

No entra aún OpenTelemetry ni un stack completo de observabilidad.

## 13. Soporte MVP

Soporte simple:
- canal de Telegram para anuncios;
- grupo de Telegram para soporte y comunidad;
- moderación básica.

Esto es suficiente para una beta privada o primeros usuarios.

## 14. Onboarding de providers

No es un objetivo del MVP cerrar un onboarding perfecto de providers propios dentro de OpenReef. En esta fase, el foco está en el lado usuario.

Lo que sí se dejará preparado a nivel conceptual:
- un worker instalable;
- la idea de un script de instalación futuro;
- documentación que se escribirá cuando el flujo sea real y esté probado.

## 15. Roadmap técnico del MVP

### Fase A — Base del sistema
- repositorio frontend y backend;
- auth email/password;
- PostgreSQL + Redis;
- estructura de jobs;
- dashboard mínimo.

### Fase B — Datos y entrenamiento
- subida y validación de dataset;
- storage en R2;
- generación de config Axolotl;
- integración con worker;
- lanzamiento de LoRA/QLoRA. Axolotl ya proporciona quickstarts claros para este flujo. [web:129]

### Fase C — Jobs reales sobre OGPU
- selección simple de nodo;
- ejecución remota;
- estados de job;
- checkpoints básicos;
- recuperación simple.

### Fase D — Cobro y operación
- integración Stripe;
- balance de créditos;
- coste estimado previo al job;
- reembolsos básicos;
- monitoring mínimo;
- Telegram como soporte.

## 16. Qué necesitamos para construirlo

### Desarrollo
- frontend web;
- backend API;
- worker ML;
- integración OGPU;
- integración Stripe;
- almacenamiento R2.

### Producto
- lista cerrada de modelos base iniciales;
- presets de entrenamiento bien definidos;
- política de errores y reembolsos;
- límites operativos claros;
- textos de UI simples y comprensibles.

### Operación
- cuenta Stripe;
- bucket R2;
- despliegue del backend;
- Redis/Postgres;
- acceso real a OGPU para pruebas;
- grupo y canal de Telegram.

## 17. Criterios de éxito del MVP

El MVP será exitoso si demuestra lo siguiente:

- un usuario puede completar de extremo a extremo un fine-tune sin tocar terminal;
- el sistema puede ejecutar jobs sobre OGPU con una tasa razonable de éxito;
- los costes reales permiten mantener ventaja económica frente a alternativas centralizadas;
- los usuarios entienden el producto sin una curva de aprendizaje excesiva;
- la base técnica es suficientemente simple como para ampliarla después sin rehacer todo.

## 18. Principio rector

La regla principal del MVP es esta: **versión sencilla de todo primero; ampliación después**.

Eso significa:
- menos libertad, más control;
- menos features, más claridad;
- menos promesas, más fiabilidad;
- menos magia, más flujo real funcionando.

Si el MVP resuelve muy bien el caso central de fine-tuning simple sobre OGPU, el resto del roadmap podrá construirse encima con mucha más solidez.