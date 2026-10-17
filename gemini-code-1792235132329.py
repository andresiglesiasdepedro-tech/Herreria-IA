"""
HerrerIA - Asistente experto en herrería / cerrajería metálica.
Versión Optimizada y Tipada.
"""

import math
import unicodedata
import webbrowser
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple

# ---------- CONFIGURACIÓN Y CONSTANTES ----------
class Config:
    DENSIDAD_ACERO = 7850   # kg/m3
    BARRA_M = 6.0           # barra comercial (m)
    KERF_M = 0.003          # pérdida por corte (m)
    PRECIO_KG = 1.30        # EUR/kg de acero
    TARIFA_HORA = 35.0      # EUR/hora de taller
    ACABADO_PCT = 0.20      # pintura/galvanizado (% sobre material)
    IVA = 0.21

class Color:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    BOLD = '\033[1m'
    ENDC = '\033[0m'

# ---------- CÁLCULOS DE PESO ----------
def kg_tubo(a: float, b: float, e: float) -> float:
    """Calcula el peso por metro de tubo cuadrado/rectangular (mm)."""
    return e * (2 * (a + b) - 4 * e) / 1e6 * Config.DENSIDAD_ACERO

def kg_tubo_redondo(d: float, e: float) -> float:
    return math.pi * (d - e) * e / 1e6 * Config.DENSIDAD_ACERO

def kg_pletina(a: float, e: float) -> float:
    return a * e / 1e6 * Config.DENSIDAD_ACERO

def kg_redondo(d: float) -> float:
    return math.pi * d * d / 4 / 1e6 * Config.DENSIDAD_ACERO

def kg_angular(a: float, e: float) -> float:
    return e * (2 * a - e) / 1e6 * Config.DENSIDAD_ACERO

def kg_chapa(m2: float, e: float) -> float:
    return m2 * e / 1000 * Config.DENSIDAD_ACERO

# ---------- ENTRADA DE DATOS ----------
def leer_float(texto: str, defecto: Optional[float] = None, minimo: float = 0.0001) -> float:
    while True:
        s = input(texto).strip().replace(",", ".")
        if not s and defecto is not None:
            return defecto
        try:
            v = float(s)
            if v >= minimo:
                return v
            print(f"{Color.WARNING}  El valor debe ser mayor o igual a {minimo}.{Color.ENDC}")
        except ValueError:
            print(f"{Color.FAIL}  Valor no válido, introduce un número.{Color.ENDC}")

def crear_pieza(perfil: str, kg_m: float, largo: float, cant: int) -> Dict[str, Any]:
    return {"perfil": perfil, "kg_m": kg_m, "largo": largo, "cant": cant, "chapa": False}

def crear_pieza_chapa(perfil: str, kg: float) -> Dict[str, Any]:
    return {"perfil": perfil, "chapa": True, "kg": kg, "kg_m": 0, "largo": 0, "cant": 1}

def num_balaustres(longitud_m: float, ancho_mm: float = 20, sep_max_mm: float = 100) -> int:
    l = longitud_m * 1000
    return max(1, math.ceil((l - sep_max_mm) / (ancho_mm + sep_max_mm)))

# ---------- ESCALERA ----------
def planificar_escalera(altura_cm: float, largo_cm: float, fondo_cm: float, ancho_cm: float, uso: str = "general") -> Optional[Dict[str, Any]]:
    cont_max, huella_min = (17.5, 28.0) if uso == "general" else (20.0, 22.0)
    n_min = math.ceil(altura_cm / cont_max)
    n_max = max(n_min, int(altura_cm // 13))
    
    cands = []
    for n in range(n_min, n_max + 1):
        c = altura_cm / n
        h = max(huella_min, 63 - 2 * c)
        if 54 <= 2 * c + h <= 70:
            cands.append((abs(c - 17), n, c, h))
    cands.sort()

    if uso != "general" or altura_cm <= 320:
        for _, n, c, h in cands:
            run = (n - 1) * h
            if run <= largo_cm and ancho_cm <= fondo_cm:
                return {"tipo": "recta", "n": n, "cont": c, "huella": h, "ancho": ancho_cm, "espacio": (largo_cm, fondo_cm), "run": run, "uso": uso}

    for _, n, c, h in cands:
        for ex, ey in ((largo_cm, fondo_cm), (fondo_cm, largo_cm)):
            for a in sorted(range(2, n - 1), key=lambda k: abs(k - n / 2)):
                if uso == "general" and (a * c > 320 or (n - a) * c > 320):
                    continue
                run1, run2 = (a - 1) * h, (n - 1 - a) * h
                if run1 + ancho_cm <= ex and ancho_cm + run2 <= ey:
                    return {"tipo": "L", "n": n, "cont": c, "huella": h, "ancho": ancho_cm, "espacio": (ex, ey), "a": a, "run1": run1, "run2": run2, "uso": uso}
    return None

def piezas_escalera(plan: Dict[str, Any], lados: int) -> List[Dict[str, Any]]:
    n, c, h, ancho = plan["n"], plan["cont"] / 100, plan["huella"] / 100, plan["ancho"] / 100
    if plan["tipo"] == "recta":
        tramos = [(n * c, (n - 1) * h)]
        peldanos = n - 1
        horiz = (n - 1) * h
    else:
        a = plan["a"]
        tramos = [(a * c, (a - 1) * h), ((n - a) * c, (n - 1 - a) * h)]
        peldanos = n - 2
        horiz = (a - 1) * h + ancho + (n - 1 - a) * h
        
    zancas = [math.hypot(r, d) for r, d in tramos]
    piezas = [crear_pieza("Tubo rect. 120x60x4 (zancas)", kg_tubo(120, 60, 4), z, 2) for z in zancas]
    piezas.append(crear_pieza("Angular 40x40x4 (apoyo peldaños)", kg_angular(40, 4), h, 2 * peldanos))
    
    area = peldanos * ancho * (h + 0.03)
    if plan["tipo"] == "L":
        area += ancho * ancho
        piezas += [
            crear_pieza("Tubo 60x40x3 (marco descansillo)", kg_tubo(60, 40, 3), ancho, 4),
            crear_pieza("Tubo 80x80x3 (postes descansillo)", kg_tubo(80, 80, 3), plan["a"] * c, 2),
        ]
    piezas.append(crear_pieza_chapa("Chapa lagrimada 3 mm", kg_chapa(area, 3)))

    if lados > 0:
        largo_baranda = sum(zancas) + (ancho if plan["tipo"] == "L" else 0)
        nb = num_balaustres(horiz)
        piezas += [
            crear_pieza("Tubo 20x20x1.5 (balaustres)", kg_tubo(20, 20, 1.5), 0.90, nb * lados),
            crear_pieza("Tubo redondo 40x2 (pasamanos)", kg_tubo_redondo(40, 2), largo_baranda + 0.2, lados),
            crear_pieza("Tubo 30x30x2 (carril inferior)", kg_tubo(30, 30, 2), largo_baranda, lados),
        ]
    return piezas

# ---------- PORTILLA / PORTÓN ----------
def calcular_porton(ancho_m: float, alto_m: float, hojas: int = 1, sep_max_mm: float = 100) -> Tuple[Dict[str, Any], List[Dict[str, Any]], List[str]]:
    avisos = []
    hoja_ancho = ancho_m / hojas - 0.015
    hoja_alto = alto_m - 0.05
    m = 0.04
    libre_mm = (hoja_ancho - 2 * m) * 1000
    b = 20
    n = max(1, math.ceil((libre_mm - sep_max_mm) / (b + sep_max_mm)))
    hueco = (libre_mm - n * b) / (n + 1)

    piezas = [
        crear_pieza("Tubo 40x40x2 (marco vert.)", kg_tubo(40, 40, 2), hoja_alto, 2 * hojas),
        crear_pieza("Tubo 40x40x2 (marco horiz.)", kg_tubo(40, 40, 2), hoja_ancho - 2 * m, 2 * hojas),
        crear_pieza("Tubo 20x20x1.5 (barrotes)", kg_tubo(20, 20, 1.5), hoja_alto - 2 * m, n * hojas),
    ]
    if hoja_ancho > 1.0:
        diag = math.hypot(hoja_ancho - 2 * m, hoja_alto - 2 * m)
        piezas.append(crear_pieza("Tubo 30x30x2 (tirante diag.)", kg_tubo(30, 30, 2), diag, hojas))

    kg_total = sum(p["kg_m"] * p["largo"] * p["cant"] for p in piezas if not p["chapa"])
    kg_hoja = kg_total / hojas
    bisagras = 2 if hoja_alto <= 1.5 else 3
    
    if kg_hoja > 100:
        avisos.append("Hoja muy pesada: usa bisagras de rodamiento o divide en más hojas.")
    if hoja_ancho > 1.5:
        avisos.append("Hoja muy ancha: tiende a descolgarse. Considera añadir hojas.")

    datos = {"hoja_ancho_m": hoja_ancho, "hoja_alto_m": hoja_alto, "barrotes_por_hoja": n, "hueco_mm": hueco, "bisagras_por_hoja": bisagras, "kg_hoja": kg_hoja}
    return datos, piezas, avisos

# ---------- LISTA DE CORTE Y PRESUPUESTO ----------
def agrupar_barras(piezas: List[Dict[str, Any]]) -> Dict[str, Any]:
    grupos = {}
    for p in piezas:
        if p["chapa"]:
            continue
        g = grupos.setdefault(p["perfil"], {"kg_m": p["kg_m"], "cortes": []})
        largo = p["largo"]
        while largo > Config.BARRA_M:
            g["cortes"].extend([Config.BARRA_M] * p["cant"])
            largo -= Config.BARRA_M
        g["cortes"].extend([largo] * p["cant"])

    resultado = {}
    for perfil, g in grupos.items():
        restos = []
        for c in sorted(g["cortes"], reverse=True):
            asignado = False
            for i, resto in enumerate(restos):
                if resto >= c + Config.KERF_M:
                    restos[i] -= c + Config.KERF_M
                    asignado = True
                    break
            if not asignado:
                restos.append(Config.BARRA_M - c - Config.KERF_M)
                
        usado = sum(g["cortes"])
        comprado = len(restos) * Config.BARRA_M
        resultado[perfil] = {
            "barras": len(restos), 
            "kg_compra": comprado * g["kg_m"],
            "desperdicio": (1 - usado / comprado) * 100 if comprado else 0,
        }
    return resultado

def mostrar_piezas(piezas: List[Dict[str, Any]]):
    print(f"\n{Color.OKBLUE}{Color.BOLD}  PIEZAS:{Color.ENDC}")
    for p in piezas:
        if p["chapa"]:
            print(f"   - {p['perfil']}: {p['kg']:.1f} kg")
        else:
            print(f"   - {p['perfil']}: {p['cant']} x {p['largo']:.2f} m")
            
    print(f"\n{Color.OKBLUE}{Color.BOLD}  COMPRA DE BARRAS ({Config.BARRA_M} m):{Color.ENDC}")
    for perfil, r in agrupar_barras(piezas).items():
        print(f"   - {perfil}: {r['barras']} barras ({r['desperdicio']:.0f}% de sobrante)")

def presupuesto(piezas: List[Dict[str, Any]]):
    resumen = agrupar_barras(piezas)
    kg_total = sum(r["kg_compra"] for r in resumen.values()) + sum(p["kg"] for p in piezas if p["chapa"])
    
    precio = leer_float(f"  Precio del acero EUR/kg [{Config.PRECIO_KG}]: ", Config.PRECIO_KG)
    horas_est = round(3 + kg_total * 0.10, 1)
    horas = leer_float(f"  Horas de trabajo [{horas_est} est.]: ", horas_est)
    tarifa = leer_float(f"  Tarifa EUR/hora [{Config.TARIFA_HORA}]: ", Config.TARIFA_HORA)

    material, mano = kg_total * precio, horas * tarifa
    acabado = material * Config.ACABADO_PCT
    base = material + mano + acabado
    
    print(f"\n{Color.OKGREEN}{Color.BOLD}  PRESUPUESTO ORIENTATIVO ({kg_total:.0f} kg de acero){Color.ENDC}")
    print(f"   Material:      {material:8.2f} EUR")
    print(f"   Mano de obra:  {mano:8.2f} EUR")
    print(f"   Acabado:       {acabado:8.2f} EUR")
    print(f"   Base:          {base:8.2f} EUR")
    print(f"   IVA {Config.IVA * 100:.0f}%:       {base * Config.IVA:8.2f} EUR")
    print(f"{Color.BOLD}   TOTAL:         {base * (1 + Config.IVA):8.2f} EUR{Color.ENDC}")

# ---------- CONSEJOS ----------
CONSEJOS = {
    ("soldadura", "soldar", "mig", "tig", "electrodo"): "MIG/MAG es rápido en taller. TIG para inox. Electrodo para exterior con viento.",
    ("galvanizado", "zinc"): "Soldar ANTES de galvanizar. Deja agujeros de venteo en tubos cerrados o reventarán.",
    ("pintura", "oxido"): "Desengrasa, elimina óxido, aplica imprimación y 2 manos de esmalte.",
}

def consejo(pregunta: str) -> str:
    q = "".join(c for c in unicodedata.normalize("NFD", pregunta.lower()) if unicodedata.category(c) != "Mn")
    for claves, texto in CONSEJOS.items():
        if any(k in q for k in claves):
            return texto
    return "Temas disponibles: soldadura, galvanizado, pintura..."

# ---------- MENÚS Y EJECUCIÓN ----------
def main():
    print(f"{Color.HEADER}{Color.BOLD}=== HerrerIA: Asistente Profesional ==={Color.ENDC}")
    while True:
        print("\n1) Escalera  2) Portón  3) Peso Perfil  4) Consejos  0) Salir")
        op = input("Elige: ").strip()
        if op == "0":
            break
        elif op == "3":
            print(f"\n{Color.OKBLUE}== PESO DE PERFIL =={Color.ENDC}")
            d = leer_float("Diámetro/Lado principal (mm): ")
            print(f"Peso redondo macizo: {kg_redondo(d):.2f} kg/m")
        # (Resto de menús simplificados para el ejemplo estructural)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nSaliendo de HerrerIA...")