# OpenReef — Documento de Visión y Estructuración del Proyecto

## 1. Visión General

OpenReef es una plataforma web de inteligencia artificial end-to-end construida sobre la infraestructura descentralizada de OpenGPU Network. Su objetivo es permitir que cualquier persona —con o sin conocimientos técnicos— pueda entrenar, optimizar, convertir, desplegar y compartir modelos de IA open-source pagando únicamente por lo que usa, sin suscripciones mensuales y con un coste significativamente menor que las alternativas centralizadas.

La plataforma no se plantea como un simple wrapper sobre herramientas existentes, sino como una capa de producto completa encima de OGPU: accesible para usuarios no técnicos, modular para usuarios avanzados y diseñada para hacer útil la red en casos reales de fine-tuning, cuantización, conversión e inferencia.

---

## 2. Identidad del Producto

### Propuesta de valor

> *"Tu laboratorio de IA personal y comunitario. Sin suscripciones. Sin sobreprecios. Solo pagas lo que usas."*

Los pilares que definen OpenReef son:

- **Accesibilidad**: interfaz visual intuitiva, sin depender de terminal, YAML ni configuraciones manuales complejas.
- **Modularidad**: cada módulo funciona de forma independiente; el usuario entra directamente en la herramienta que necesita.
- **Precio**: el modelo está diseñado para ser normalmente entre 40% y 70% más barato que opciones centralizadas, dependiendo del tipo de job, tamaño del modelo y disponibilidad de nodos.
- **Eficiencia**: SmartRoute selecciona automáticamente el hardware justo para cada tarea.
- **Comunidad**: los usuarios pueden compartir modelos y datasets, y generar un ecosistema de reutilización y monetización alrededor de la red.

### Posicionamiento

OpenReef no busca competir como suite enterprise de MLOps ni como proveedor de modelos propietarios. Su espacio es el de los desarrolladores indie, estudiantes, investigadores, usuarios de IA local y pequeñas startups que quieren trabajar con modelos open-source sin pagar precios de infraestructura enterprise.

### Nombre y branding

El nombre provisional del proyecto es **OpenReef**. Comunica apertura, red, ecosistema vivo y cooperación distribuida entre múltiples nodos. Aunque existen referencias menores en otros sectores, no parecen generar conflicto directo con el posicionamiento del producto, por lo que puede mantenerse como nombre de trabajo mientras más adelante se validan dominio, handles y viabilidad de marca.

---

## 3. Filosofía de Uso

La plataforma se diseña bajo una idea central: **potente para quien sabe, accesible para quien empieza**.

### Modo Libre

Cada módulo es completamente independiente. El usuario entra al módulo que necesita y ejecuta solo esa tarea, sin obligación de seguir ningún flujo prefijado.

Ejemplos:
- solo cuantizar;
- solo convertir un modelo a GGUF o MLX;
- solo hacer fine-tuning;
- solo desplegar un endpoint.

### Modo Guiado

Además del modo libre, OpenReef ofrecerá un flujo visual paso a paso para usuarios menos técnicos. Este pipeline no será obligatorio: sugerirá el siguiente paso lógico, pero siempre permitirá saltar módulos.

```text
[1. Dataset Lab] → [2. Fine-Tuning] → [3. Quantization] → [4. Conversion] → [5. Deploy & API]
   (opcional)         (opcional)          (opcional)          (opcional)        (opcional)
```

La idea no es imponer un guion fijo, sino ofrecer una ruta asistida para que el producto sea más accesible sin sacrificar modularidad.

---

## 4. Arquitectura de Participantes

En OpenReef existen dos perfiles claramente diferenciados:

### Usuario cliente

Es quien consume los servicios de la plataforma: sube datasets, lanza jobs, entrena modelos, los convierte, despliega endpoints o usa el playground. Puede acceder inicialmente con email y contraseña, y más adelante conectar una wallet para pagar directamente en OGPU.

### Provider

Es quien aporta hardware a la red y ejecuta los jobs. Su wallet y registro base pertenecen al flujo nativo de OpenGPU Network a través de la Provider App de OGPU. OpenReef no gestiona su wallet ni su onboarding principal dentro del protocolo; solo interactúa con su nodo a través del SDK y del worker específico de la plataforma.

Esta separación es importante: la wallet del provider pertenece al ecosistema OGPU, mientras que la wallet del usuario cliente es una opción de pago dentro de OpenReef.

---

## 5. Autenticación y Acceso

### Fase 1 — Email + contraseña

El MVP prioriza onboarding sencillo. La autenticación inicial será clásica: registro con email, contraseña, verificación de correo y sesiones vía JWT.

Implementación prevista:
- FastAPI en backend.
- `passlib` con bcrypt para hash de contraseñas.
- `python-jose` para JWT.
- PostgreSQL para persistencia de usuarios.

Esto evita depender de OAuth o servicios externos en la primera versión.

### Fase 2 — Wallet login opcional

Más adelante, el usuario podrá conectar una wallet para identificarse y pagar directamente en OGPU. El estándar previsto es **SIWE (Sign-In with Ethereum)**, usando firma de mensaje sin coste de gas.

Stack previsto:
- RainbowKit para UI de conexión.
- wagmi para estado wallet en frontend.
- siwe para verificación de firma.

La wallet se asociará a la cuenta existente de email, no la sustituirá.

---

## 6. Sistema de Pagos

OpenReef tendrá dos vías de pago para el usuario cliente, pero una sola lógica interna de ejecución.

### Pago con tarjeta

El usuario recarga créditos en USD mediante Stripe. Cuando lanza un job, la plataforma calcula el coste estimado en OGPU al precio de mercado y añade un buffer del 5%. Si el job termina por debajo de lo estimado, el sobrante vuelve automáticamente a su saldo en créditos.

### Pago con wallet OGPU

De forma opcional, el usuario podrá pagar directamente en OGPU con su wallet conectada y recibir un descuento del 10%. El sistema calculará el coste del job en tiempo real, añadirá un buffer del 5% y bloqueará ese importe mediante smart contract o flujo equivalente cuando esa capa esté activa.

### Separación de wallets

- **Wallet del provider**: gestionada enteramente por OGPU Network.
- **Wallet del usuario**: opcional, usada para pagar servicios dentro de OpenReef.

### Sostenibilidad económica del modelo

La rentabilidad interna se plantea con un reparto aproximado del ingreso por job:

- **70–75%** para el provider.
- **20–25%** para la plataforma.
- **5%** para un buffer de contingencia orientado a cubrir reembolsos y fallos operativos.

Con los rangos de precio estimados definidos hasta ahora, la plataforma sigue situándose por debajo de referencias centralizadas como Together AI o Modal en trabajos equivalentes de fine-tuning, mientras mantiene margen para plataforma y providers.

La comunicación externa debe formularse con prudencia: **normalmente entre 40% y 70% más barato que alternativas centralizadas**, según tipo de job, tamaño de modelo y disponibilidad real de nodos.

---

## 7. SmartRoute y Asignación de Hardware

SmartRoute es la capa transversal de inteligencia operativa de OpenReef. No es un módulo aislado, sino el sistema que analiza cada trabajo y decide dónde ejecutarlo dentro de la red OGPU.

### Qué analiza

- tamaño del modelo;
- técnica elegida (LoRA, QLoRA, DPO, cuantización, conversión, inferencia);
- tamaño del dataset y longitud de secuencia;
- disponibilidad de nodos;
- precio en tiempo real;
- fiabilidad histórica;
- preferencia del usuario: barato, equilibrado o rápido.

### Hardware profiling

SmartRoute se apoya en el SDK de OGPU y en un perfil extendido de cada nodo verificado mediante benchmark sintético automatizado al registrarse. No depende de una validación manual.

Se evaluarán:
- GPU: arquitectura, VRAM total/libre, soporte FP16/BF16/INT4/INT8/FP8.
- RAM: cantidad, disponibilidad, generación (DDR4/DDR5), velocidad.
- CPU: modelo, núcleos, soporte AVX2/AVX-512.
- almacenamiento: espacio libre, tipo de disco, velocidad de lectura.
- red: ancho de banda de subida y latencia al storage.

### Perfil estático y dinámico

- **Perfil estático**: verificado al registrar el nodo.
- **Estado dinámico**: consultado antes de cada job (VRAM libre, RAM disponible, disco libre, carga).

Un nodo que no cumpla los requisitos mínimos jamás se ofrece para un job incompatible.

### Restricción estratégica

OpenReef operará **100% sobre OpenGPU Network**. No se contempla fallback a infraestructura centralizada en el MVP. Si no hay capacidad compatible, el job espera o no se ejecuta, pero no se redirige a otra nube.

---

## 8. Seguridad, Cifrado y Ciclo de Vida del Job

### Principio general

La seguridad debe estar resuelta de forma pragmática para el MVP, sin prometer un nivel irreal de protección enterprise. El enfoque elegido es sencillo, razonable y compatible con la arquitectura descentralizada del proyecto.

### Cifrado

El cifrado se implementará con `cryptography` en Python, usando Fernet como capa simple y robusta para el MVP.

Objetivos:
- cifrar datasets antes de subirlos a storage;
- descifrar solo en memoria dentro del worker;
- cifrar el output final antes de devolverlo al usuario;
- evitar depender de esquemas complejos de gestión criptográfica en una primera fase.

### Almacenamiento y borrado

Los archivos temporales se considerarán siempre cifrados en disco. Esto reduce el problema del borrado seguro en SSD, ya que la inutilización de la clave convierte el residuo físico en algo criptográficamente irrelevante.

### Limpieza automatizada

La limpieza forma parte del ciclo de vida del worker:
- borrado de temporales;
- limpieza de caché de GPU;
- limpieza de caché de frameworks;
- eliminación de claves temporales del entorno.

En fases posteriores, esta lógica podrá ligarse a verificación remota y escrow on-chain.

---

## 9. Fiabilidad, Checkpointing y Gestión de Fallos

La red OGPU se compone de hardware distribuido y doméstico, por lo que la fiabilidad no puede darse por supuesta. OpenReef debe asumir desde el principio que habrá desconexiones, caídas y trabajos interrumpidos.

### Checkpointing

Los jobs de entrenamiento se diseñan para guardar progreso periódicamente. Esto permite recuperar trabajo útil y no reiniciar desde cero en cada fallo.

### Heartbeat y failover

Cada worker enviará heartbeats al backend. Si el nodo deja de responder durante el umbral definido, el sistema intentará recuperar el job desde el último checkpoint válido y reanudarlo en otro nodo compatible.

### Política de reembolsos MVP

Para el MVP, la regla debe ser simple y generar confianza:

- si el job no llega a arrancar correctamente, reembolso completo;
- si falla por la plataforma o por el nodo, un reintento automático;
- si tras el reintento sigue fallando, reembolso completo;
- si termina pero el artefacto final es inválido, reembolso completo o regeneración gratuita;
- si el error se detecta antes del arranque, no se cobra.

### Protección del provider

Cuando el fallo no sea culpa del provider pero sí haya usado hardware, el modelo económico prevé que parte del buffer sirva como colchón para una compensación mínima, evitando que el provider soporte todo el coste de fallos ajenos.

---

## 10. Límites Operativos del MVP

Para proteger la red y mantener la primera versión bajo control, OpenReef tendrá límites claros desde el día uno.

### Rate limiting

En la fase inicial:
- **1 job activo por cuenta**.
- límite diario razonable de jobs por usuario.
- timeout máximo por job.

La restricción de un único job simultáneo por cuenta es especialmente importante porque la pool inicial de providers será reducida y no conviene saturar la red.

### Tamaño máximo de dataset

Para el MVP, enfocado sobre todo en modelos 7B/13B:
- máximo **500 MB** por dataset;
- máximo **100.000 filas**;
- máximo **4.096 tokens por ejemplo**.

### Chunking y streaming

Cuando un dataset supere determinados umbrales (por ejemplo 100 MB o 25.000 filas), el sistema activará un modo especial de procesamiento por chunks y, cuando el flujo lo soporte, entrenamiento en streaming.

Esto permite:
- reducir el consumo de RAM;
- no cargar datasets enteros innecesariamente;
- mantener trabajos grandes dentro de márgenes razonables.

Si el flujo concreto no soporta chunking/streaming real, el job se bloquea **antes del cobro** y se sugiere al usuario reducir, muestrear o limpiar el dataset.

---

## 11. Gestión de Datasets y Modelos

### Dataset versioning

Cada dataset relevante debe quedar versionado para mantener trazabilidad. El objetivo es saber siempre con qué datos se entrenó cada modelo.

### Model versioning

La estructura recomendada es:
- **Proyecto** → caso de uso del usuario.
- **Familia de modelo** → línea principal derivada de un modelo base.
- **Versión** → cada nuevo entrenamiento relevante.
- **Artefactos derivados** → cuantizaciones y conversiones de esa versión.

Reglas:
- un nuevo entrenamiento crea una nueva versión;
- una cuantización o conversión crea un artefacto derivado, no una nueva versión base;
- cada versión debe guardar base model, dataset usado, técnica, hiperparámetros, métricas y formatos disponibles.

También se contemplan alias humanos como `production`, `best-quality`, `fastest` o `experimental` para mejorar UX.

---

## 12. Módulos del Producto

### 1. Fine-Tuning Studio

Entrenamiento visual de modelos open-source con soporte inicial para LoRA y QLoRA, y más adelante DPO.

### 2. Quantization Lab

Cuantización a formatos como GGUF y GPTQ en Fase 1, con AWQ y métodos más avanzados en fases posteriores.

### 3. Dataset Lab

Generación sintética, limpieza, validación y anotación asistida de datasets.

### 4. Model Converter

Conversión entre formatos como Safetensors, GGUF, MLX, GPTQ, AWQ o EXL2.

### 5. Model Playground & API Hosting

Pruebas rápidas, comparación A/B y despliegue serverless de endpoints privados.

### 6. Community Hub

Repositorio social de modelos y datasets públicos, con posibilidad de earning basado en uso dentro de la plataforma.

---

## 13. Observabilidad y Operaciones

OpenReef no necesita un sistema complejo de observabilidad en el MVP, pero sí un mínimo que permita no operar a ciegas.

### Monitoring MVP

Se plantea:
- endpoint `/health` en FastAPI;
- métricas básicas de aplicación;
- Flower para supervisión de colas y workers de Celery.

Esto es suficiente para beta privada y primeras operaciones.

### Soporte y comunicación

El soporte inicial será deliberadamente simple:
- **canal de Telegram** para anuncios;
- **grupo de Telegram** para soporte y comunidad;
- moderación básica con bot para controlar spam.

Más adelante podrá incorporarse un agente de IA conectado a documentación, FAQs y estado de plataforma para responder dudas frecuentes.

---

## 14. Providers y Onboarding

El onboarding específico de providers dentro de OpenReef no se cerrará hasta que exista un worker operativo real, pero la dirección está definida.

### Dirección prevista

Se desarrollará un **script de instalación único** para providers que automatice:
- verificación de dependencias;
- instalación o comprobación de Docker;
- despliegue del worker;
- registro del nodo dentro del flujo de OpenReef;
- persistencia del servicio.

La documentación detallada se redactará más adelante, en paralelo al desarrollo real del worker, para reflejar el proceso verdadero y no una instalación teórica.

---

## 15. Términos, Cumplimiento y Responsabilidad

OpenReef no puede controlar de manera real y previa todo lo que sube cada usuario. Por eso el enfoque legal debe basarse en responsabilidad del usuario, términos claros y mecanismos de retirada o actuación razonable ante abuso.

### Términos mínimos necesarios

El usuario deberá aceptar que:
- tiene derechos sobre el dataset que sube;
- no introduce datos personales de terceros sin consentimiento;
- no usa la plataforma para fines ilegales;
- es responsable del contenido que entrena o despliega.

### GDPR y privacidad

Para el MVP, la estrategia pragmática es:
- política de privacidad clara;
- retención mínima de datos;
- opción de borrado de cuenta y datos;
- advertencia explícita de no subir datos personales;
- evolución futura hacia filtros geográficos o medidas más avanzadas si el uso lo exige.

No se trata de simular control total, sino de tener un marco legal razonable y defendible para una plataforma open-source y descentralizada.

---

## 16. Stack Tecnológico

### Frontend
- Next.js
- shadcn/ui

### Backend
- FastAPI
- PostgreSQL
- Redis
- Celery

### Entrenamiento y optimización
- Axolotl
- Unsloth
- llama.cpp
- AutoGPTQ
- AutoAWQ
- mlx-lm
- exllamav2

### Infraestructura
- OpenGPU Network SDK
- Cloudflare R2
- Stripe
- RainbowKit / wagmi / siwe
- Weights & Biases

### Seguridad
- `cryptography` con Fernet/AES para cifrado MVP

---

## 17. Roadmap por Fases

### Fase 1 — MVP

- Fine-Tuning Studio para 7B/13B con LoRA y QLoRA.
- Conversión básica a GGUF y MLX.
- Playground inicial.
- SmartRoute v1.
- Email + contraseña.
- Pagos con Stripe y créditos internos.
- Cifrado simple y limpieza automática.
- Checkpointing básico.
- Rate limiting inicial.
- Monitoring mínimo.
- Telegram como soporte oficial.

### Fase 2 — Consolidación

- Login wallet.
- Pagos directos en OGPU.
- Escrow on-chain.
- Dataset Lab completo.
- Quantization Lab ampliado.
- Community Hub y earnings.
- SmartRoute con mayor fiabilidad histórica.

### Fase 3 — Potencia

- DPO y alineación avanzada.
- Formatos avanzados como EXL2 y TurboQuant.
- Soporte de modelos más grandes y multimodales.
- IA de soporte conectada a documentación/plataforma.

---

## 18. Público Objetivo

OpenReef está pensado para:
- desarrolladores indie;
- estudiantes e investigadores;
- usuarios de IA local (Ollama, LM Studio, Apple Silicon);
- pequeñas startups;
- equipos que quieren experimentar con modelos open-source sin pagar costes enterprise.

---

## 19. Oportunidad Estratégica

OpenReef encaja de forma natural en el Acceleration Program de OpenGPU Network porque:
- genera demanda real y recurrente sobre la red;
- amplía casos de uso más allá del compute bruto;
- mejora la utilidad percibida del ecosistema OGPU;
- incentiva tanto a usuarios como a providers;
- construye una capa de producto que puede atraer adopción no técnica sobre infraestructura descentralizada.
