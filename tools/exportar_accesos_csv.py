import argparse
import csv
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

import firebase_admin
from firebase_admin import credentials, firestore


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Exporta la colección 'accesos' de Firestore a un archivo CSV."
    )
    parser.add_argument(
        "--service-account",
        default="tools/serviceAccountKey.json",
        help="Ruta al archivo JSON de cuenta de servicio de Firebase.",
    )
    parser.add_argument(
        "--output",
        default="accesos.csv",
        help="Ruta de salida del CSV.",
    )
    parser.add_argument(
        "--collection",
        default="accesos",
        help="Nombre de la colección de Firestore a exportar.",
    )
    return parser.parse_args()


def to_local_iso(value: Any) -> str:
    if value is None:
        return ""

    if hasattr(value, "to_datetime"):
        value = value.to_datetime()

    if isinstance(value, datetime):
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.astimezone().isoformat(timespec="seconds")

    return str(value)


def to_utc_iso(value: Any) -> str:
    if value is None:
        return ""

    if hasattr(value, "to_datetime"):
        value = value.to_datetime()

    if isinstance(value, datetime):
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc).isoformat(timespec="seconds")

    return str(value)


def init_firestore(service_account_path: Path):
    if not service_account_path.exists():
        raise FileNotFoundError(
            f"No se encontró el archivo de cuenta de servicio: {service_account_path}"
        )

    if not firebase_admin._apps:
        cred = credentials.Certificate(str(service_account_path))
        firebase_admin.initialize_app(cred)

    return firestore.client()


def build_row(document_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    fecha = payload.get("fecha")

    return {
        "id": document_id,
        "email": payload.get("email", ""),
        "ip": payload.get("ip", ""),
        "fecha_utc": to_utc_iso(fecha),
        "fecha_local": to_local_iso(fecha),
        "navegador": payload.get("navegador", ""),
        "dispositivo": payload.get("dispositivo", ""),
    }


def export_collection(client, collection_name: str, output_file: Path) -> int:
    docs = client.collection(collection_name).stream()

    rows = []
    for doc in docs:
        payload = doc.to_dict() or {}
        rows.append(build_row(doc.id, payload))

    rows.sort(key=lambda item: item.get("fecha_utc", ""), reverse=True)

    output_file.parent.mkdir(parents=True, exist_ok=True)

    fieldnames = [
        "id",
        "email",
        "ip",
        "fecha_utc",
        "fecha_local",
        "navegador",
        "dispositivo",
    ]

    with output_file.open("w", newline="", encoding="utf-8-sig") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    return len(rows)


def main() -> None:
    args = parse_args()

    script_dir = Path(__file__).resolve().parent
    project_root = script_dir.parent

    service_account_path = Path(args.service_account)
    if not service_account_path.is_absolute():
        service_account_path = (project_root / service_account_path).resolve()

    output_path = Path(args.output)
    if not output_path.is_absolute():
        output_path = (project_root / output_path).resolve()

    client = init_firestore(service_account_path)
    total = export_collection(client, args.collection, output_path)
    print(f"✅ CSV actualizado: {output_path} | registros: {total}")


if __name__ == "__main__":
    main()
