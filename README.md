# TP de Apache Kafka: procesamiento de pedidos

Demo educativa de un e-commerce con Python 3.12, FastAPI, Apache Kafka en
modo KRaft, consumidores independientes y SQLite. El objetivo es mostrar que
un productor publica un evento sin esperar a que terminen los consumidores.

## Arquitectura

```text
Navegador -> API FastAPI -> orders -> payments -> payments
                                      |
                                      v
                              notifications -> notifications
```

La API, el consumidor de pagos y el consumidor de notificaciones son
contenedores separados. Los tres acceden a la base SQLite del volumen
`orders-data`, que guarda cada estado y su historial.

## Requisitos

- Docker Desktop con Docker Compose v2.
- No es necesario instalar Kafka, Python ni Maven para ejecutar la demo con
  Docker.

## Ejecución desde cero

Desde PowerShell:

```powershell
cd C:\Users\Usuario\Desktop\KafkaTp
docker compose up --build
```

Abrir <http://localhost:8000>. En otra terminal se pueden observar los logs:

```powershell
docker compose logs -f api payments notifications
```

Para detener sin borrar los datos:

```powershell
docker compose down
```

Para reiniciar una demo limpia:

```powershell
docker compose down -v
docker compose up --build
```

## Prueba de punta a punta

1. En la interfaz completar cliente, producto, cantidad y precio.
2. Elegir **Aprobado** y publicar el pedido.
3. Observar el recorrido `CREATED` -> `PAYMENT_APPROVED` ->
   `NOTIFICATION_SENT`.
4. Crear otro pedido eligiendo **Rechazado**.
5. Observar `CREATED` -> `PAYMENT_REJECTED` -> `NOTIFICATION_SENT`. El
   historial conserva el resultado del pago rechazado.

También se pueden probar los endpoints:

```powershell
curl.exe http://localhost:8000/health
curl.exe http://localhost:8000/api/status
curl.exe -X POST http://localhost:8000/orders `
  -H "Content-Type: application/json" `
  -d '{"customer":"Juan","product":"Notebook","quantity":1,"price":850000,"payment_decision":"APPROVED"}'
```

## Topics y consumidores

- `orders`: pedidos nuevos publicados por la API.
- `payments`: resultado aprobado o rechazado producido por `payments`.
- `notifications`: notificaciones generadas por `notifications`.

El consumidor de pagos usa el grupo `payments-service`; el de notificaciones
usa `notifications-service`. Como los grupos son distintos, cada servicio
recibe sus propios eventos. Los topics se crean automáticamente al iniciar
los servicios con una partición y factor de replicación 1, adecuados para un
broker local.

Los consumidores usan `enable.auto.commit=false` y confirman el offset sólo
después de actualizar SQLite y publicar el siguiente evento. Si ocurre un
error antes del commit, Kafka vuelve a entregar el mensaje. La implementación
ofrece procesamiento **at-least-once**; no afirma exactly-once y puede
reprocesar un evento ante una caída.

Para inspeccionar mensajes desde el host, con Kafka instalado localmente:

```powershell
C:\kafka\bin\windows\kafka-console-consumer.bat `
  --bootstrap-server localhost:9092 --topic orders --from-beginning
```

Dentro del contenedor también se puede usar:

```powershell
docker compose exec kafka /opt/kafka/bin/kafka-topics.sh `
  --bootstrap-server localhost:29092 --list
```

## Variables y desarrollo local

La configuración usa `KAFKA_BOOTSTRAP_SERVERS` y `DATABASE_PATH`. Para ejecutar
fuera de Docker se necesita Python 3.12, Kafka accesible en
`localhost:9092`, un entorno virtual y:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
$env:KAFKA_BOOTSTRAP_SERVERS = "localhost:9092"
uvicorn api.main:app --port 8000
```

En terminales separadas:

```powershell
python -m payments.consumer
python -m notifications.consumer
```

## Limitaciones y posibles mejoras

Es una topología de demostración con un solo broker, una partición y
replicación 1, por lo que no ofrece alta disponibilidad. SQLite sirve para
la presentación, pero una instalación real usaría PostgreSQL y un patrón
outbox para coordinar base de datos y publicación Kafka. También faltan
autenticación, TLS, métricas y escalado horizontal.
