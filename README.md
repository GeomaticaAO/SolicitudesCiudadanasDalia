# SolicitudesCiudadanasDalia

## Exportación automática de accesos a CSV (en tu PC)

Este proyecto incluye:

- `tools/exportar_accesos_csv.py`: exporta la colección `accesos` de Firestore a CSV.
- `auto_exportar_accesos.bat`: ejecuta la exportación automáticamente cada 5 minutos.

### 1) Requisitos

- Python instalado en Windows.
- Dependencias:

```bash
pip install firebase-admin
```

### 2) Llave de Firebase

Descarga la cuenta de servicio de Firebase y guárdala como:

`tools/serviceAccountKey.json`

Ruta en Firebase Console:

`Configuración del proyecto > Cuentas de servicio > Generar nueva clave privada`

### 3) Ejecutar exportación automática

Desde la carpeta del proyecto:

```bat
auto_exportar_accesos.bat
```

Esto crea y actualiza `accesos.csv` en la raíz del proyecto cada 5 minutos.

### 4) Ejecutar una sola vez

```bat
auto_exportar_accesos.bat once
```

