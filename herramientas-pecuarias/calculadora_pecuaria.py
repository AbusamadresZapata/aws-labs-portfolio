#!/usr/bin/env python3
"""
Calculadora financiera para unidades productivas pecuarias - Colombia 2025
Uso: python calculadora_pecuaria.py --especie tilapia --cantidad 5000 --inversion 25000000
"""
import argparse
import sys

# Forzar UTF-8 en terminales Windows (cp1252 no soporta caracteres de caja)
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# ---------------------------------------------------------------------------
# Parametros tecnicos por especie (Colombia 2025)
# ---------------------------------------------------------------------------

ESPECIES = {
    "tilapia": {
        "nombre": "Tilapia roja",
        "ciclo_dias": 180,
        "vacio_dias": 30,
        "ciclos_anio": 1.7,
        "costo_cria": 500,
        "costo_alimento_unidad": 2560,
        "costo_otros_unidad": 700,
        "mortalidad": 0.10,
        "peso_venta_kg": 0.5,
        "precio_canal": {"granja": 8000, "mercado": 11000, "restaurante": 14000},
        "densidad_m2": 4,
        "infra_costo_m2": 30000,
        "vida_util_infra": 15,
    },
    "pollo": {
        "nombre": "Pollo de engorde",
        "ciclo_dias": 45,
        "vacio_dias": 10,
        "ciclos_anio": 5.9,
        "costo_cria": 3200,
        "costo_alimento_unidad": 8100,
        "costo_otros_unidad": 1600,
        "mortalidad": 0.04,
        "peso_venta_kg": 2.3,
        "precio_canal": {"granja": 5500, "mercado": 7000, "restaurante": 9500},
        "densidad_m2": 10,
        "infra_costo_m2": 180000,
        "vida_util_infra": 20,
    },
    "gallina": {
        "nombre": "Gallina ponedora",
        "ciclo_dias": 504,
        "vacio_dias": 30,
        "ciclos_anio": 0.69,
        "costo_cria": 20000,
        "costo_alimento_unidad": 84000,
        "costo_otros_unidad": 12000,
        "mortalidad": 0.06,
        "peso_venta_kg": None,
        "precio_canal": {"granja": 375, "mercado": 420, "restaurante": 500},
        "densidad_m2": 6,
        "infra_costo_m2": 150000,
        "vida_util_infra": 20,
        "unidades_por_anio": 285,
    },
    "cuy": {
        "nombre": "Cuy",
        "ciclo_dias": 365,
        "vacio_dias": 0,
        "ciclos_anio": 1,
        "costo_cria": 20000,
        "costo_alimento_unidad": 4500,
        "costo_otros_unidad": 500,
        "mortalidad": 0.15,
        "peso_venta_kg": 0.9,
        "precio_canal": {"granja": 15000, "mercado": 18000, "restaurante": 22000},
        "densidad_m2": 8,
        "infra_costo_m2": 80000,
        "vida_util_infra": 10,
        "crias_por_hembra_anio": 30,
    },
    "conejo": {
        "nombre": "Conejo",
        "ciclo_dias": 365,
        "vacio_dias": 0,
        "ciclos_anio": 1,
        "costo_cria": 35000,
        "costo_alimento_unidad": 18000,
        "costo_otros_unidad": 3000,
        "mortalidad": 0.10,
        "peso_venta_kg": 2.0,
        "precio_canal": {"granja": 14000, "mercado": 18000, "restaurante": 25000},
        "densidad_m2": 5,
        "infra_costo_m2": 100000,
        "vida_util_infra": 10,
        "crias_por_hembra_anio": 42,
    },
    "cerdo": {
        "nombre": "Cerdo (engorde)",
        "ciclo_dias": 180,
        "vacio_dias": 15,
        "ciclos_anio": 1.9,
        "costo_cria": 250000,
        "costo_alimento_unidad": 420000,
        "costo_otros_unidad": 80000,
        "mortalidad": 0.03,
        "peso_venta_kg": 110,
        "precio_canal": {"granja": 6000, "mercado": 7000, "restaurante": 8500},
        "densidad_m2": 1.2,
        "infra_costo_m2": 250000,
        "vida_util_infra": 20,
    },
    "codorniz": {
        "nombre": "Codorniz",
        "ciclo_dias": 540,
        "vacio_dias": 30,
        "ciclos_anio": 0.64,
        "costo_cria": 4500,
        "costo_alimento_unidad": 13200,
        "costo_otros_unidad": 3000,
        "mortalidad": 0.08,
        "peso_venta_kg": None,
        "precio_canal": {"granja": 375, "mercado": 420, "restaurante": 480},
        "densidad_m2": 40,
        "infra_costo_m2": 120000,
        "vida_util_infra": 15,
        "unidades_por_anio": 280,
    },
}

TASA_DESCUENTO_DEFAULT = 0.15
CRECIMIENTO_SECTORIAL_DEFAULT = 0.035
INCREMENTO_PRECIO_DEFAULT = 0.05


# ---------------------------------------------------------------------------
# Calculos financieros
# ---------------------------------------------------------------------------

def calcular_vpn(flujos, tasa):
    return sum(f / (1 + tasa) ** n for n, f in enumerate(flujos))


def calcular_tir(flujos, precision=1e-6):
    if flujos[0] >= 0:
        return None
    lo, hi = -0.9999, 10.0
    for _ in range(300):
        mid = (lo + hi) / 2
        vpn = calcular_vpn(flujos, mid)
        if abs(vpn) < precision:
            return mid
        if vpn > 0:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


def tabla_amortizacion(monto, tasa_anual, anos):
    if monto <= 0 or anos <= 0:
        return 0, []
    cuota = monto * (tasa_anual * (1 + tasa_anual) ** anos) / ((1 + tasa_anual) ** anos - 1)
    filas = []
    saldo = monto
    for n in range(1, anos + 1):
        interes = saldo * tasa_anual
        abono = cuota - interes
        saldo -= abono
        filas.append({
            "ano": n,
            "saldo_inicial": saldo + abono,
            "cuota": cuota,
            "interes": interes,
            "abono_capital": abono,
            "saldo_final": max(saldo, 0),
        })
    return cuota, filas


# ---------------------------------------------------------------------------
# Nucleo del analisis
# ---------------------------------------------------------------------------

def analizar(args):
    especie_key = args.especie.lower()
    if especie_key not in ESPECIES:
        print(f"[ERROR] Especie '{args.especie}' no reconocida.")
        print(f"Opciones: {', '.join(ESPECIES.keys())}")
        sys.exit(1)

    p = ESPECIES[especie_key]
    canal = args.canal.lower()
    if canal not in p["precio_canal"]:
        canal = "mercado"

    cantidad = args.cantidad
    anos = args.anos
    tasa_descuento = args.tasa_descuento

    # Precio unitario de venta
    precio_kg = p["precio_canal"][canal]
    if p["peso_venta_kg"]:
        precio_unitario = precio_kg * p["peso_venta_kg"]
    else:
        precio_unitario = precio_kg  # gallina/codorniz: precio por huevo

    # Unidades vendibles al ano
    if especie_key == "cuy":
        unidades_vendibles_anio = cantidad * p["crias_por_hembra_anio"] * (1 - p["mortalidad"])
    elif especie_key == "conejo":
        unidades_vendibles_anio = cantidad * p["crias_por_hembra_anio"] * (1 - p["mortalidad"])
    elif especie_key in ("gallina", "codorniz"):
        unidades_vendibles_anio = cantidad * (1 - p["mortalidad"]) * p["unidades_por_anio"]
    else:
        unidades_vendibles_anio = cantidad * (1 - p["mortalidad"]) * p["ciclos_anio"]

    # Inversion inicial calculada
    infra_valor = 0.0
    if not args.tiene_infraestructura:
        if especie_key == "cerdo":
            m2_requeridos = cantidad * p["densidad_m2"]
        elif especie_key in ("cuy", "conejo"):
            m2_requeridos = cantidad / p["densidad_m2"]
        else:
            m2_requeridos = cantidad / p["densidad_m2"]
        infra_valor = m2_requeridos * p["infra_costo_m2"]

    costo_animales = cantidad * p["costo_cria"]
    capital_trabajo = cantidad * (p["costo_alimento_unidad"] + p["costo_otros_unidad"]) * 1.1

    inversion_calculada = infra_valor + costo_animales + capital_trabajo
    inversion_usuario = args.inversion is not None

    if inversion_usuario:
        inversion_total = args.inversion
        # Advertencia si el presupuesto no cubre ni la infraestructura
        if args.inversion < infra_valor:
            print(
                f"\n[ADVERTENCIA] El presupuesto ${args.inversion:,.0f} COP "
                f"es menor que la infraestructura requerida "
                f"${infra_valor:,.0f} COP."
            )
            print("  Se usa el presupuesto indicado. Los resultados reflejan ese capital.\n")
    else:
        inversion_total = inversion_calculada

    monto_credito = inversion_total * args.financiacion
    capital_propio = inversion_total * (1 - args.financiacion)

    # Costos anuales
    costo_variable_anio = cantidad * (p["costo_cria"] + p["costo_alimento_unidad"] + p["costo_otros_unidad"])
    mano_obra_anio = args.mano_obra_anual
    depreciacion_anio = infra_valor / p["vida_util_infra"] if infra_valor > 0 and p["vida_util_infra"] > 0 else 0

    cuota_credito, tabla_amort = tabla_amortizacion(monto_credito, args.tasa_credito, anos)

    # Proyeccion anual
    flujos = [-inversion_total]
    tabla_anual = []

    for n in range(1, anos + 1):
        factor_u = (1 + args.crecimiento_sectorial) ** (n - 1)
        factor_p = (1 + args.incremento_precio) ** (n - 1)
        factor_c = (1 + args.incremento_costos) ** (n - 1)

        unidades_n = unidades_vendibles_anio * factor_u
        precio_n = precio_unitario * factor_p
        ingresos_n = unidades_n * precio_n
        costo_n = (costo_variable_anio + mano_obra_anio) * factor_c

        interes_n = tabla_amort[n - 1]["interes"] if tabla_amort else 0
        abono_n = tabla_amort[n - 1]["abono_capital"] if tabla_amort else 0

        utilidad_antes_imp = ingresos_n - costo_n - depreciacion_anio - interes_n
        impuesto = max(0, utilidad_antes_imp * args.tasa_impuesto)
        utilidad_neta = utilidad_antes_imp - impuesto
        flujo_caja = utilidad_neta + depreciacion_anio - abono_n

        tabla_anual.append({
            "ano": n,
            "unidades": round(unidades_n),
            "precio_unit": round(precio_n),
            "ingresos": round(ingresos_n),
            "costos_operacion": round(costo_n),
            "depreciacion": round(depreciacion_anio),
            "intereses": round(interes_n),
            "utilidad_antes_imp": round(utilidad_antes_imp),
            "impuesto": round(impuesto),
            "utilidad_neta": round(utilidad_neta),
            "flujo_caja": round(flujo_caja),
        })
        flujos.append(flujo_caja)

    vpn = calcular_vpn(flujos, tasa_descuento)
    tir = calcular_tir(flujos)

    vp_ingresos = sum(a["ingresos"] / (1 + tasa_descuento) ** a["ano"] for a in tabla_anual)
    vp_egresos = sum(
        (a["costos_operacion"] + a["depreciacion"] + a["intereses"])
        / (1 + tasa_descuento) ** a["ano"]
        for a in tabla_anual
    ) + inversion_total
    bc = vp_ingresos / vp_egresos if vp_egresos > 0 else 0

    acumulado = -inversion_total
    pri_anos = None
    for i, a in enumerate(tabla_anual):
        acumulado += a["flujo_caja"]
        if acumulado >= 0 and pri_anos is None:
            pri_anos = i + 1

    return {
        "especie": p["nombre"],
        "canal": canal,
        "cantidad": cantidad,
        "anos": anos,
        "inversion_total": round(inversion_total),
        "inversion_calculada": round(inversion_calculada),
        "inversion_usuario": inversion_usuario,
        "infra_valor": round(infra_valor),
        "costo_animales": round(costo_animales),
        "capital_trabajo": round(capital_trabajo),
        "monto_credito": round(monto_credito),
        "capital_propio": round(capital_propio),
        "tabla_anual": tabla_anual,
        "tabla_amort": tabla_amort,
        "vpn": round(vpn),
        "tir": tir,
        "bc": round(bc, 4),
        "pri_anos": pri_anos,
        "depreciacion_anio": round(depreciacion_anio),
        "cuota_credito": round(cuota_credito),
        "tasa_descuento": tasa_descuento,
    }


# ---------------------------------------------------------------------------
# Presentacion
# ---------------------------------------------------------------------------

def cop(n):
    try:
        return f"${int(n):>14,.0f} COP"
    except Exception:
        return str(n)


def imprimir_resultado(r):
    sep = "=" * 66

    print(f"\n{sep}")
    print(f"  ANALISIS FINANCIERO -- {r['especie'].upper()}")
    print(f"  Canal: {r['canal']} | Cantidad: {r['cantidad']:,} unidades | Proyeccion: {r['anos']} anios")
    print(sep)

    print("\n--- INVERSION INICIAL ---")
    if r["inversion_usuario"]:
        print(f"  (Presupuesto indicado por el usuario -- componentes son estimados)")
    print(f"  Infraestructura:          {cop(r['infra_valor'])}")
    print(f"  Animales / crias:         {cop(r['costo_animales'])}")
    print(f"  Capital de trabajo (+10%): {cop(r['capital_trabajo'])}")
    print(f"  TOTAL:                    {cop(r['inversion_total'])}")
    if r["inversion_usuario"] and r["inversion_total"] != r["inversion_calculada"]:
        print(f"  (Calculado sin ajuste:     {cop(r['inversion_calculada'])})")
    print(f"  +-- Capital propio:       {cop(r['capital_propio'])}")
    print(f"  +-- Credito:              {cop(r['monto_credito'])}")
    if r["cuota_credito"] > 0:
        print(f"      Cuota fija anual:     {cop(r['cuota_credito'])}")

    print("\n--- FLUJO DE CAJA PROYECTADO (anual) ---")
    print(f"  {'Anio':>4} | {'Unidades':>9} | {'Ingresos':>15} | {'Costos Op':>15} | {'Util. Neta':>14} | {'Flujo Caja':>14}")
    print("  " + "-" * 78)
    acumulado = -r["inversion_total"]
    for a in r["tabla_anual"]:
        acumulado += a["flujo_caja"]
        marca = " <-- PRI" if acumulado >= 0 and (acumulado - a["flujo_caja"]) < 0 else ""
        print(
            f"  {a['ano']:>4} | {a['unidades']:>9,} | "
            f"${a['ingresos']:>13,.0f} | "
            f"${a['costos_operacion']:>13,.0f} | "
            f"${a['utilidad_neta']:>12,.0f} | "
            f"${a['flujo_caja']:>12,.0f}{marca}"
        )

    print("\n--- INDICADORES DE VIABILIDAD ---")
    tasa_pct = r["tasa_descuento"] * 100
    print(f"  VPN  (tasa {tasa_pct:.0f}%):       {cop(r['vpn'])}")
    if r["tir"] is not None:
        print(f"  TIR:                      {r['tir'] * 100:>13.2f} %")
    else:
        print("  TIR:                      No calculable")
    print(f"  Relacion B/C:             {r['bc']:>14.4f}")
    if r["pri_anos"]:
        print(f"  PRI:                      {r['pri_anos']:>12} anios")
    else:
        print("  PRI:                      No se recupera en el horizonte")

    if r["tabla_amort"]:
        print("\n--- TABLA DE AMORTIZACION ---")
        print(f"  {'Anio':>4} | {'Saldo Inicial':>15} | {'Intereses':>13} | {'Abono Cap':>13} | {'Saldo Final':>15}")
        print("  " + "-" * 65)
        for f in r["tabla_amort"]:
            print(
                f"  {f['ano']:>4} | ${f['saldo_inicial']:>13,.0f} | "
                f"${f['interes']:>11,.0f} | "
                f"${f['abono_capital']:>11,.0f} | "
                f"${f['saldo_final']:>13,.0f}"
            )

    print("\n--- VEREDICTO ---")
    viable = r["vpn"] > 0 and r["bc"] >= 1
    if viable:
        pri_txt = f"en {r['pri_anos']} anios" if r["pri_anos"] else "fuera del horizonte"
        print(f"  [VIABLE] VPN positivo | B/C {r['bc']:.2f} | Recuperacion {pri_txt}")
    else:
        print(f"  [NO VIABLE] VPN {cop(r['vpn'])} | B/C {r['bc']:.2f}")
        print("  Revisar: cantidad, canal de venta o incluir infraestructura existente")

    print(f"\n  Precios base 2025. Variacion tipica +-15% por region y temporada.")
    print(sep + "\n")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Calculadora financiera pecuaria Colombia 2025",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos:
  python calculadora_pecuaria.py --especie tilapia --cantidad 5000 --inversion 25000000
  python calculadora_pecuaria.py --especie cerdo --cantidad 25 --financiacion 0.3 --tasa-credito 0.18
  python calculadora_pecuaria.py --especie pollo --cantidad 500 --canal restaurante --anos 3
  python calculadora_pecuaria.py --especie tilapia --cantidad 5000 --tiene-infraestructura --canal mercado
        """,
    )

    parser.add_argument("--especie", required=True,
                        help=f"Especie: {', '.join(ESPECIES.keys())}")
    parser.add_argument("--cantidad", type=int, required=True,
                        help="Animales (reproductoras en cuy/conejo)")
    parser.add_argument("--inversion", type=float, default=None,
                        help="Presupuesto total en COP (si se omite, se calcula)")
    parser.add_argument("--tiene-infraestructura", action="store_true",
                        help="Indica que ya cuenta con infraestructura construida")
    parser.add_argument("--canal", default="mercado",
                        choices=["granja", "mercado", "restaurante"],
                        help="Canal de venta (default: mercado)")
    parser.add_argument("--financiacion", type=float, default=0.0,
                        help="Fraccion financiada con credito, ej: 0.30 (default: 0)")
    parser.add_argument("--tasa-credito", type=float, default=0.18,
                        help="Tasa de interes anual del credito (default: 18%%)")
    parser.add_argument("--anos", type=int, default=5,
                        help="Anios de proyeccion (default: 5)")
    parser.add_argument("--tasa-descuento", type=float, default=TASA_DESCUENTO_DEFAULT,
                        help=f"Tasa de descuento para VPN (default: {TASA_DESCUENTO_DEFAULT*100:.0f}%%)")
    parser.add_argument("--mano-obra-anual", type=float, default=0.0,
                        help="Costo anual de mano de obra pagada en COP (default: 0)")
    parser.add_argument("--tasa-impuesto", type=float, default=0.0,
                        help="Impuesto renta: 0=informal | 0.25=persona natural | 0.33=juridica")
    parser.add_argument("--crecimiento-sectorial", type=float, default=CRECIMIENTO_SECTORIAL_DEFAULT,
                        help=f"Crecimiento anual de unidades (default: {CRECIMIENTO_SECTORIAL_DEFAULT*100:.1f}%%)")
    parser.add_argument("--incremento-precio", type=float, default=INCREMENTO_PRECIO_DEFAULT,
                        help=f"Incremento anual del precio de venta (default: {INCREMENTO_PRECIO_DEFAULT*100:.0f}%%)")
    parser.add_argument("--incremento-costos", type=float, default=0.04,
                        help="Incremento anual de costos (default: 4%%)")

    args = parser.parse_args()
    resultado = analizar(args)
    imprimir_resultado(resultado)


if __name__ == "__main__":
    main()
