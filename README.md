# GitDigest

GitDigest lee los pull requests fusionados de un repositorio de GitHub y los convierte en un changelog en lenguaje claro, agrupado por fecha y ordenado por relevancia para quien usa el software.

<img src="./client/public/landing.png" alt="Pantalla inicial de GitDigest">


## Para qué sirve

Los pull requests están escritos para desarrolladores. Quien usa un emulador, una librería o una herramienta en pleno desarrollo suele querer saber otra cosa: si lo que le importa ha mejorado, ha cambiado o se ha roto. GitDigest traduce el texto técnico de cada PR a una explicación centrada en el efecto para el usuario, y deja el detalle técnico en un desplegable para quien quiera verlo.

El ejemplo de referencia es [KytyPS5/KytyPS5](https://github.com/KytyPS5/KytyPS5), un repositorio con mucha actividad diaria. El campo de software afectado no está atado a ese proyecto, así que el mismo esquema sirve para otros repositorios con tráfico alto.

Esta es una entrada real del digest de KytyPS5 (25 oct 2026):

```
Relevancia media

Corrige problemas visuales como "streaks" azules/blancas en UFC 6 al asegurar
que los render targets con formatos R8, R8G8 y R16_UINT se limpien correctamente.

Categorías: Corrección de Bugs, Gráficos
Afecta a: UFC 6
PR #1893: renderer: decode R8, R8G8 and R16_UINT color register clears
```

## Cómo funciona

```
API REST de GitHub -> filtro de PRs -> SQLite -> Gemini -> JSON validado -> digest
```

1. La ingesta pide a la API de GitHub los pull requests del repositorio y descarta los que no están fusionados y los borradores.
2. SQLite guarda el estado con una restricción UNIQUE(repo, pr_number). Un PR que ya está guardado no se vuelve a procesar, así que lanzar el pipeline dos veces no duplica datos ni gasta cuota.
3. Gemini 2.5 Flash recibe el texto de cada PR nuevo y responde en JSON estricto. El system prompt le prohíbe inventar datos que no estén en el PR.
4. El resultado se guarda y se muestra en el digest.

Para cada PR, el modelo devuelve estos campos: categoria, subsistema, relevancia, es_ruido, impacto_usuario, resumen_tecnico, software_afectado, plataformas y accion_requerida.

El código se reparte en cinco módulos: config, database, ingestion, processing y pipeline, que orquesta a los demás.

## Stack

- Python 3.14
- requests, para la API REST de GitHub
- google-genai, con Gemini 2.5 Flash
- SQLite
- Interfaz web: Astro v7 + Tailwind v4

## Ejecutar en local

Necesitas una API key de Google AI Studio. La capa gratuita basta para probarlo.

```bash
git clone https://github.com/gpagus/<nombre-del-repo>.git
cd <nombre-del-repo>
pip install -r requirements.txt
```

Define la clave de Gemini como variable de entorno (el nombre exacto está en el módulo config) y lanza el pipeline con el comando de entrada del proyecto: `[comando de entrada]`.

## Límites actuales

- Funciona con la API gratuita de Gemini, así que la cantidad de PRs que se pueden procesar en una ejecución depende de esa cuota.
- Los resúmenes los genera un modelo y pueden exagerar el efecto de un cambio. Por eso cada entrada enlaza al pull request original.
- La persistencia en el despliegue actual es temporal: al usar SQLite sobre el sistema de archivos efímero del plan gratuito de Render, los digests se reinician cuando el servicio entra en reposo por inactividad.

## Próximos pasos

- Ejecución periódica con cron o un worker.
- Filtros por relevancia, categoría y software afectado en el digest.

## Autor

Agustín Gómez Piñero, [@gpagus](https://github.com/gpagus). Feedback y bugs se pueden enviar desde el enlace al pie de la web.
