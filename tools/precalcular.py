import json
import os
import sys
from datetime import datetime
import unicodedata

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
INPUT_SOLICITUDES = os.path.join(BASE_DIR, "archivos", "solicitudes", "Solicitudes.geojson")
INPUT_COLONIAS = os.path.join(BASE_DIR, "archivos", "vectores", "colonias_wgs84_geojson_renombrado.geojson")
INPUT_SECCIONES = os.path.join(BASE_DIR, "archivos", "vectores", "secciones.geojson")
OUTPUT_DIR = os.path.join(BASE_DIR, "archivos", "precalculos")

MONTHS = [
    "enero", "febrero", "marzo", "abril", "mayo", "junio",
    "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"
]
MONTHS_UP = [m.upper() for m in MONTHS]

DATE_FORMATS = [
    "%Y-%m-%d",
    "%Y/%m/%d",
    "%d/%m/%Y",
    "%d-%m-%Y",
    "%Y-%m-%d %H:%M:%S",
    "%Y/%m/%d %H:%M:%S",
    "%d/%m/%Y %H:%M:%S",
    "%d-%m-%Y %H:%M:%S",
]


def normalize_key(value):
    if value is None:
        return None
    text = str(value).strip().upper()
    text = unicodedata.normalize("NFD", text)
    text = "".join(ch for ch in text if unicodedata.category(ch) != "Mn")
    cleaned = []
    last_space = False
    for ch in text:
        if ch.isalnum():
            cleaned.append(ch)
            last_space = False
        elif ch.isspace():
            if not last_space:
                cleaned.append(" ")
                last_space = True
    return "".join(cleaned).strip()


def normalize_seccion(value):
    if value is None:
        return None
    text = str(value).strip()
    digits = "".join(ch for ch in text if ch.isdigit())
    if digits:
        return digits
    return normalize_key(text)


def find_key(sample_props, candidates):
    for key in candidates:
        if key in sample_props:
            return key
    return None


def parse_month(value):
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None

    # If text has letters, try to map month names
    if any(ch.isalpha() for ch in text):
        norm = normalize_key(text)
        if norm:
            for idx, name in enumerate(MONTHS_UP):
                if norm == name or norm.startswith(name[:3]):
                    return MONTHS[idx]
        return text.strip().lower()

    # If it looks like a plain month number
    digits = "".join(ch for ch in text if ch.isdigit())
    if digits and len(digits) <= 2:
        try:
            month_num = int(digits)
            if 1 <= month_num <= 12:
                return MONTHS[month_num - 1]
        except ValueError:
            pass

    # Try date formats
    for fmt in DATE_FORMATS:
        try:
            dt = datetime.strptime(text, fmt)
            return MONTHS[dt.month - 1]
        except ValueError:
            continue

    # Try ISO without timezone
    try:
        dt = datetime.fromisoformat(text.replace("Z", ""))
        return MONTHS[dt.month - 1]
    except ValueError:
        return None


def increment(counter, key, amount=1):
    if key is None:
        return
    counter[key] = counter.get(key, 0) + amount


def ensure_entity(container, key, label):
    if key not in container:
        container[key] = {
            "label": label,
            "total": 0,
            "mes": {},
            "tipo": {},
            "estado": {},
            "mes_tipo": {},
            "mes_estado": {},
            "tipo_estado": {},
            "mes_tipo_estado": {},
        }
    return container[key]


def load_geojson(path):
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def save_geojson(path, data):
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(data, handle, ensure_ascii=True)


def get_bbox(polygon):
    """Obtener bounding box de un polígono"""
    if not polygon:
        return None
    lons = [c[0] for c in polygon]
    lats = [c[1] for c in polygon]
    return (min(lons), min(lats), max(lons), max(lats))


def point_in_polygon(point, polygon):
    """
    Verificar si un punto [lon, lat] está dentro de un polígono.
    Usa algoritmo de ray casting.
    polygon debe ser lista de coordenadas: [[lon, lat], [lon, lat], ...]
    """
    if not polygon or len(polygon) < 3:
        return False
    
    # Usar bounding box para descartar rápidamente
    bbox = get_bbox(polygon)
    if not bbox:
        return False
    
    x, y = point[0], point[1]
    min_x, min_y, max_x, max_y = bbox
    
    # Si el punto está fuera del bounding box, no puede estar en el polígono
    if not (min_x <= x <= max_x and min_y <= y <= max_y):
        return False
    
    # Ray casting algorithm
    inside = False
    
    p1x, p1y = polygon[0]
    for i in range(1, len(polygon)):
        p2x, p2y = polygon[i]
        if y > min(p1y, p2y):
            if y <= max(p1y, p2y):
                if x <= max(p1x, p2x):
                    if p1y != p2y:
                        xinters = (y - p1y) * (p2x - p1x) / (p2y - p1y) + p1x
                    if p1x == p2x or x <= xinters:
                        inside = not inside
        p1x, p1y = p2x, p2y
    
    return inside


def count_in_vialidades(features_list, vialidades_data):
    """
    Contar solicitudes en vialidades primarias.
    Las locales se calculan como: total - primarias - error_coords
    Maneja MultiPolygon y Polygon.
    Retorna diccionario con conteos.
    """
    result = {
        "total": 0,
        "primarias": 0,
        "locales": 0,
        "error_coords": 0,
    }
    
    vial_features = vialidades_data.get("features", [])
    if not vial_features:
        return result
    
    # Solo extraer polígonos de vías primarias
    vial_primarias = []
    
    for vf in vial_features:
        if not vf or not isinstance(vf, dict):
            continue
        
        geom = vf.get("geometry") or {}
        props = vf.get("properties", {})
        tipo = (props.get("TIPO_VIA") or "").lower()  # Convertir a minúsculas para comparación
        
        if not isinstance(geom, dict):
            continue
        
        geom_type = geom.get("type", "")
        coords_all = geom.get("coordinates", [])
        
        # Procesar Polygon
        if geom_type == "Polygon" and coords_all:
            poly_coords = coords_all[0]  # Primera coordenada es el exterior
            if poly_coords and "primaria" in tipo:
                vial_primarias.append(poly_coords)
        
        # Procesar MultiPolygon
        elif geom_type == "MultiPolygon" and coords_all:
            if "primaria" in tipo:
                for poly in coords_all:  # Cada poly es [exterior, hole1, hole2, ...]
                    if poly:
                        exterior = poly[0]  # Primera coordenada es el exterior
                        if exterior:
                            vial_primarias.append(exterior)
    
    print(f"DEBUG: Vialidades primarias cargadas: {len(vial_primarias)}")
    
    # Contar solicitudes en vialidades
    try:
        for feature in features_list:
            result["total"] += 1
            
            if not feature or not isinstance(feature, dict):
                result["error_coords"] += 1
                continue
            
            geom = feature.get("geometry") or {}
            if not isinstance(geom, dict):
                result["error_coords"] += 1
                continue
                
            coords = geom.get("coordinates", [])
            
            if not coords or len(coords) < 2:
                result["error_coords"] += 1
                continue
            
            try:
                point = [float(coords[0]), float(coords[1])]
                
                # Solo verificar si está en vías primarias
                in_primaria = any(point_in_polygon(point, poly) for poly in vial_primarias)
                
                if in_primaria:
                    result["primarias"] += 1
                    
            except (ValueError, TypeError):
                result["error_coords"] += 1
    except Exception as e:
        print(f"ERROR en procesamiento de vialidades: {e}")
        import traceback
        traceback.print_exc()
    
    # Calcular locales como la diferencia: total - primarias - errores
    result["locales"] = result["total"] - result["primarias"] - result["error_coords"]
    
    return result


def main():
    # Configurar encoding UTF-8 para Windows
    import sys
    if sys.stdout.encoding != 'utf-8':
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    
    if not os.path.exists(INPUT_SOLICITUDES):
        print("ERROR: No existe", INPUT_SOLICITUDES)
        return 1

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    print("Leyendo solicitudes...", INPUT_SOLICITUDES)
    solicitudes = load_geojson(INPUT_SOLICITUDES)
    features = solicitudes.get("features", [])
    if not features:
        print("ERROR: No se encontraron features en Solicitudes.geojson")
        return 1

    sample_props = features[0].get("properties", {})

    colonia_key = find_key(sample_props, ["Colonia", "COLONIA", "colonia", "name", "NOMBRE"])
    name_key = find_key(sample_props, ["name", "NAME", "Name"])
    seccion_key = find_key(sample_props, ["seccion", "SECCION", "Seccion", "SECCIÓN", "SECCION"])
    tipo_key = find_key(sample_props, ["Tipo de reporte", "Tipo de Reporte", "tipo", "TIPO", "Tipo"])
    estado_key = find_key(sample_props, ["Estado Reporte", "Estado reporte", "Estado", "ESTADO", "estado"])
    mes_key = find_key(sample_props, ["mes", "Mes", "MES"])
    fecha_key = find_key(sample_props, ["Fecha reporte", "Fecha Reporte", "Fecha", "FECHA"])

    if colonia_key is None or seccion_key is None or tipo_key is None or estado_key is None:
        print("ERROR: No se pudieron detectar columnas clave en Solicitudes.geojson")
        print("Columnas detectadas:", ", ".join(sorted(sample_props.keys())))
        return 1

    print("Columnas detectadas:")
    print("  Colonia:", colonia_key)
    print("  Seccion:", seccion_key)
    print("  Tipo:", tipo_key)
    print("  Estado:", estado_key)
    print("  Mes:", mes_key if mes_key else "(se obtiene de fecha)")
    print("  Fecha:", fecha_key if fecha_key else "(no detectada)")

    stats_global = {
        "total": 0,
        "mes": {},
        "tipo": {},
        "estado": {},
        "mes_tipo": {},
        "mes_estado": {},
        "tipo_estado": {},
        "mes_tipo_estado": {},
    }
    stats_colonias = {}
    stats_secciones = {}
    values_mes = set()
    values_tipo = set()
    values_estado = set()
    
    # Tracking para coordenadas
    coords_stats = {
        "total": 0,
        "with_coords": 0,
        "missing_x": 0,
        "missing_y": 0,
        "missing_both": 0,
        "invalid_coords": []
    }
    
    # ===== CARGAR COLONIAS PARA SPATIAL JOIN =====
    colonias_poligonos = []
    if os.path.exists(INPUT_COLONIAS):
        print("Cargando colonias para spatial join...")
        colonias_geo = load_geojson(INPUT_COLONIAS)
        col_features = colonias_geo.get("features", [])
        
        if col_features:
            col_props = col_features[0].get("properties", {})
            col_name_key = find_key(col_props, ["NOMBRE", "Nombre", "nombre", "name", "NAME"])
            
            for col_feature in col_features:
                props = col_feature.get("properties", {})
                nombre_colonia = props.get(col_name_key) if col_name_key else None
                if not nombre_colonia:
                    continue
                    
                geom = col_feature.get("geometry", {})
                geom_type = geom.get("type", "")
                coords_all = geom.get("coordinates", [])
                
                # Extraer polígonos
                if geom_type == "Polygon" and coords_all:
                    poly_coords = coords_all[0]  # exterior ring
                    if poly_coords:
                        colonias_poligonos.append({
                            "nombre": nombre_colonia,
                            "polygon": poly_coords,
                            "bbox": get_bbox(poly_coords)
                        })
                elif geom_type == "MultiPolygon" and coords_all:
                    for poly in coords_all:
                        if poly:
                            exterior = poly[0]
                            if exterior:
                                colonias_poligonos.append({
                                    "nombre": nombre_colonia,
                                    "polygon": exterior,
                                    "bbox": get_bbox(exterior)
                                })
            
            print(f"OK: Cargados {len(colonias_poligonos)} poligonos de colonias para spatial join")
    
    # Contador de actualizaciones
    colonias_actualizadas = 0
    procesadas = 0

    print("Procesando solicitudes...")
    for idx, feature in enumerate(features):
        # Progress indicator cada 5000
        if idx > 0 and idx % 5000 == 0:
            print(f"  Procesadas: {idx}/{len(features)} - Actualizadas: {colonias_actualizadas}")
        
        # Skip None or invalid features
        if not feature or not isinstance(feature, dict):
            coords_stats["missing_both"] += 1
            coords_stats["total"] += 1
            continue
            
        props = feature.get("properties", {})
        
        # Check coordinates - proteger contra geometry null
        geom = feature.get("geometry") or {}
        coords = geom.get("coordinates", []) if isinstance(geom, dict) else []
        
        # ===== VALIDAR COORDENADAS Y DESCARTAR SI NO SON VÁLIDAS =====
        coords_stats["total"] += 1
        has_valid_coords = False
        
        if coords and len(coords) >= 2:
            try:
                lon, lat = float(coords[0]), float(coords[1])
                if -180 <= lon <= 180 and -90 <= lat <= 90:
                    coords_stats["with_coords"] += 1
                    has_valid_coords = True
                    
                    # ===== SPATIAL JOIN: Buscar colonia real basada en coordenadas =====
                    if colonias_poligonos:
                        punto = [lon, lat]
                        colonia_encontrada = None
                        
                        for col_data in colonias_poligonos:
                            # Verificar bounding box primero (optimización)
                            bbox = col_data["bbox"]
                            if bbox:
                                min_lon, min_lat, max_lon, max_lat = bbox
                                if not (min_lon <= lon <= max_lon and min_lat <= lat <= max_lat):
                                    continue
                            
                            # Verificar si el punto está dentro del polígono
                            if point_in_polygon(punto, col_data["polygon"]):
                                colonia_encontrada = col_data["nombre"]
                                break
                        
                        # Actualizar campo Colonia si se encontró diferencia
                        if colonia_encontrada:
                            colonia_actual = props.get(colonia_key)
                            if colonia_actual != colonia_encontrada:
                                props[colonia_key] = colonia_encontrada
                                colonias_actualizadas += 1
                                if colonias_actualizadas <= 5:  # Mostrar primeros 5 ejemplos
                                    print(f"  Actualizado: '{colonia_actual}' -> '{colonia_encontrada}'")
                    
                else:
                    coords_stats["invalid_coords"].append({
                        "idx": idx,
                        "colonia": props.get(colonia_key),
                        "coords": coords
                    })
            except (ValueError, TypeError):
                coords_stats["invalid_coords"].append({
                    "idx": idx,
                    "colonia": props.get(colonia_key),
                    "coords": coords
                })
        else:
            coords_stats["missing_both"] += 1
        
        # DESCARTAR SOLICITUDES SIN COORDENADAS VALIDAS
        if not has_valid_coords:
            continue
        
        # ===== SINCRONIZAR CAMPOS name Y Colonia =====
        # Dar prioridad al campo 'name' si existe y el campo 'Colonia' está diferente
        if name_key and colonia_key:
            name_value = props.get(name_key)
            colonia_value = props.get(colonia_key)
            
            # Si name existe y es diferente a Colonia, actualizar Colonia con name
            if name_value and name_value != colonia_value:
                props[colonia_key] = name_value
                colonias_actualizadas += 1
                if colonias_actualizadas <= 10:  # Mostrar primeros 10 ejemplos
                    print(f"  Sincronizando: Colonia '{colonia_value}' -> '{name_value}'")
        
        # Resto del procesamiento (solo para solicitudes CON coordenadas válidas)
        colonia = props.get(colonia_key)
        seccion = props.get(seccion_key)
        tipo = props.get(tipo_key)
        estado = props.get(estado_key)

        if mes_key:
            mes = parse_month(props.get(mes_key))
        else:
            mes = None
            if fecha_key:
                mes = parse_month(props.get(fecha_key))

        if not tipo:
            tipo = "Sin tipo"
        if not estado:
            estado = "Sin estado"
        if not mes:
            mes = "sin_mes"

        colonia_key_norm = normalize_key(colonia) or "SIN_COLONIA"
        seccion_key_norm = normalize_seccion(seccion) or "SIN_SECCION"

        stats_global["total"] += 1
        increment(stats_global["mes"], mes)
        increment(stats_global["tipo"], tipo)
        increment(stats_global["estado"], estado)
        increment(stats_global["mes_tipo"], f"{mes}|{tipo}")
        increment(stats_global["mes_estado"], f"{mes}|{estado}")
        increment(stats_global["tipo_estado"], f"{tipo}|{estado}")
        increment(stats_global["mes_tipo_estado"], f"{mes}|{tipo}|{estado}")

        col_entry = ensure_entity(stats_colonias, colonia_key_norm, colonia)
        col_entry["total"] += 1
        increment(col_entry["mes"], mes)
        increment(col_entry["tipo"], tipo)
        increment(col_entry["estado"], estado)
        increment(col_entry["mes_tipo"], f"{mes}|{tipo}")
        increment(col_entry["mes_estado"], f"{mes}|{estado}")
        increment(col_entry["tipo_estado"], f"{tipo}|{estado}")
        increment(col_entry["mes_tipo_estado"], f"{mes}|{tipo}|{estado}")

        sec_entry = ensure_entity(stats_secciones, seccion_key_norm, seccion)
        sec_entry["total"] += 1
        increment(sec_entry["mes"], mes)
        increment(sec_entry["tipo"], tipo)
        increment(sec_entry["estado"], estado)
        increment(sec_entry["mes_tipo"], f"{mes}|{tipo}")
        increment(sec_entry["mes_estado"], f"{mes}|{estado}")
        increment(sec_entry["tipo_estado"], f"{tipo}|{estado}")
        increment(sec_entry["mes_tipo_estado"], f"{mes}|{tipo}|{estado}")

        values_mes.add(mes)
        values_tipo.add(tipo)
        values_estado.add(estado)

    # ===== CONTAR SOLICITUDES EN VIALIDADES =====
    print("Calculando solicitudes en vialidades...")
    vialidades_stats = {
        "total": 0,
        "primarias": 0,
        "locales": 0,
        "intersecciones": 0,
    }
    
    INPUT_VIALIDADES = os.path.join(BASE_DIR, "archivos", "vectores", "vialidades.geojson")
    if os.path.exists(INPUT_VIALIDADES):
        try:
            vialidades_data = load_geojson(INPUT_VIALIDADES)
            vialidades_stats = count_in_vialidades(features, vialidades_data)
            print(f"Vialidades - Total: {vialidades_stats['total']}, "
                  f"Primarias: {vialidades_stats['primarias']}, "
                  f"Locales: {vialidades_stats['locales']}, "
                  f"Intersecciones: {vialidades_stats['intersecciones']}")
        except Exception as e:
            print(f"WARN: Error al procesar vialidades: {e}")
    else:
        print(f"WARN: No existe {INPUT_VIALIDADES}")

    output_stats = {
        "meta": {
            "generatedAt": datetime.utcnow().isoformat() + "Z",
            "source": "archivos/solicitudes/Solicitudes.geojson",
            "columns": {
                "colonia": colonia_key,
                "seccion": seccion_key,
                "tipo": tipo_key,
                "estado": estado_key,
                "mes": mes_key,
                "fecha": fecha_key,
            },
            "records": stats_global["total"],
            "coords": coords_stats,
            "vialidades": vialidades_stats,
        },
        "values": {
            "mes": sorted(values_mes),
            "tipo": sorted(values_tipo),
            "estado": sorted(values_estado),
        },
        "global": stats_global,
        "colonias": stats_colonias,
        "secciones": stats_secciones,
    }

    stats_path = os.path.join(OUTPUT_DIR, "estadisticas.json")
    print("Guardando", stats_path)
    with open(stats_path, "w", encoding="utf-8") as handle:
        json.dump(output_stats, handle, ensure_ascii=True)
    
    # ===== GUARDAR SOLICITUDES ACTUALIZADAS CON COLONIAS CORREGIDAS =====
    if colonias_actualizadas > 0:
        print(f"\nOK: {colonias_actualizadas} solicitudes con campo Colonia actualizado")
        print("Guardando Solicitudes.geojson actualizado...")
        save_geojson(INPUT_SOLICITUDES, solicitudes)
        print(f"OK: {INPUT_SOLICITUDES} actualizado con spatial join")
    else:
        print("\nINFO: No se encontraron diferencias en campos de Colonia")
    
    # Print coordinates summary
    print("\n=== REPORTE DE COORDENADAS ===")
    print(f"Total de solicitudes: {coords_stats['total']}")
    print(f"Con coordenadas válidas: {coords_stats['with_coords']}")
    print(f"Sin coordenadas: {coords_stats['missing_both']}")
    print(f"Con coordenadas inválidas: {len(coords_stats['invalid_coords'])}")
    
    if coords_stats["invalid_coords"]:
        print("\nSolicitudes con coordenadas inválidas (primeras 5):")
        for item in coords_stats["invalid_coords"][:5]:
            print(f"  [Índice {item['idx']}] {item['colonia']}: {item['coords']}")

    print("Preparando poligonos...")
    if os.path.exists(INPUT_COLONIAS):
        colonias_geo = load_geojson(INPUT_COLONIAS)
        col_features = colonias_geo.get("features", [])
        if col_features:
            col_props = col_features[0].get("properties", {})
            col_name_key = find_key(col_props, ["NOMBRE", "name", "Nombre", "COLONIA", "Colonia"])
        else:
            col_name_key = None

        for feature in col_features:
            props = feature.get("properties", {})
            label = props.get(col_name_key) if col_name_key else None
            props["STAT_KEY"] = normalize_key(label) or "SIN_COLONIA"
            feature["properties"] = props

        out_colonias = os.path.join(OUTPUT_DIR, "colonias_enriquecidas.geojson")
        print("Guardando", out_colonias)
        save_geojson(out_colonias, colonias_geo)
    else:
        print("WARN: No existe", INPUT_COLONIAS)

    if os.path.exists(INPUT_SECCIONES):
        secciones_geo = load_geojson(INPUT_SECCIONES)
        sec_features = secciones_geo.get("features", [])
        if sec_features:
            sec_props = sec_features[0].get("properties", {})
            sec_name_key = find_key(sec_props, ["seccion", "SECCION", "Seccion", "SECCIÓN"])
        else:
            sec_name_key = None

        for feature in sec_features:
            props = feature.get("properties", {})
            label = props.get(sec_name_key) if sec_name_key else None
            props["STAT_KEY"] = normalize_seccion(label) or "SIN_SECCION"
            feature["properties"] = props

        out_secciones = os.path.join(OUTPUT_DIR, "secciones_enriquecidas.geojson")
        print("Guardando", out_secciones)
        save_geojson(out_secciones, secciones_geo)
    else:
        print("WARN: No existe", INPUT_SECCIONES)

    print("OK: Precalculo terminado")
    return 0


if __name__ == "__main__":
    sys.exit(main())
