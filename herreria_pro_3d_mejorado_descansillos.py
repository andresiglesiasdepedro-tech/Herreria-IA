"""
HerrerIA Pro — interfaz visual para diseño preliminar de escaleras y portillas metálicas.
Instalación: pip install streamlit pandas matplotlib plotly
Ejecución: streamlit run herreria_pro_3d_mejorado.py

IMPORTANTE: herramienta de estimación y despiece preliminar. No sustituye la comprobación
de un técnico competente, especialmente para cargas, anclajes, estabilidad, normativa y soldaduras.
"""
import math
import pandas as pd
import streamlit as st
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle
import plotly.graph_objects as go

st.set_page_config(page_title="HerrerIA Pro", page_icon="🔩", layout="wide")

# ---------- Estilo ----------
st.markdown("""
<style>
    .stApp { background: #f4f6f8; }
    .block-container { padding-top: 1.6rem; max-width: 1450px; }
    .hero { background: linear-gradient(120deg,#17212b,#30495b); color:white;
            padding: 25px 30px; border-radius: 16px; margin-bottom: 18px; }
    .hero h1 { color:white; margin:0; font-size:2.15rem; }
    .hero p { color:#d8e1e8; margin:8px 0 0 0; }
    div[data-testid="stMetric"] { background:white; padding:14px; border-radius:12px;
                                  border:1px solid #e0e5e9; }
    .note { background:#fff7e6; border-left:4px solid #e6a23c; padding:12px 15px;
            border-radius:6px; color:#624b20; }
</style>
""", unsafe_allow_html=True)

st.markdown("""
<div class="hero">
  <h1>🔩 HerrerIA Pro</h1>
  <p>Asistente de herrería metálica · diseño preliminar, materiales, cortes y presupuesto</p>
</div>
""", unsafe_allow_html=True)

with st.sidebar:
    st.title("⚙️ Configuración")
    st.caption("Personaliza el proyecto y los precios del taller.")
    proyecto = st.text_input("Nombre del proyecto", value="Nuevo proyecto")
    cliente = st.text_input("Cliente (opcional)", value="")
    precio_kg = st.number_input("Acero (€/kg)", min_value=0.0, value=1.30, step=0.10)
    tarifa_hora = st.number_input("Mano de obra (€/hora)", min_value=0.0, value=35.0, step=1.0)
    acabado_pct = st.number_input("Acabado (% del material)", min_value=0.0, value=20.0, step=1.0) / 100
    iva_pct = st.number_input("IVA (%)", min_value=0.0, value=21.0, step=1.0) / 100
    largo_barra = st.number_input("Largo de barra comercial (m)", min_value=1.0, value=6.0, step=0.5)
    perdida_corte = st.number_input("Pérdida por corte (mm)", min_value=0.0, value=3.0, step=0.5) / 1000
    st.divider()
    st.caption("Los resultados son orientativos; revisa medidas y normativa antes de fabricar.")

DENSIDAD = 7850

def kg_tubo(a, b, e):
    return max(0, e * (2 * (a + b) - 4 * e) / 1e6 * DENSIDAD)

def kg_redondo_tubo(d, e):
    return max(0, math.pi * (d - e) * e / 1e6 * DENSIDAD)

def kg_pletina(a, e):
    return a * e / 1e6 * DENSIDAD

def kg_chapa(area, e):
    return area * e / 1000 * DENSIDAD

def add_piece(pieces, profile, kg_m, length, qty, kind="Perfil"):
    pieces.append({"Elemento": profile, "Tipo": kind, "Cantidad": int(qty),
                   "Largo unitario (m)": round(float(length), 3),
                   "Total lineal (m)": round(float(length)*int(qty), 3),
                   "kg/m": round(float(kg_m), 3),
                   "Peso aprox. (kg)": round(float(kg_m)*float(length)*int(qty), 2)})

def group_cut_list(pieces, stock_len, kerf):
    """Optimización aproximada tipo first-fit decreasing para perfiles lineales."""
    groups = {}
    oversized = []
    for p in pieces:
        if p["Tipo"] != "Perfil":
            continue
        key = p["Elemento"]
        groups.setdefault(key, {"kg_m": p["kg/m"], "cuts": []})
        for cut in [p["Largo unitario (m)"]] * p["Cantidad"]:
            if cut > stock_len:
                oversized.append({"Perfil": key, "Corte (m)": round(cut, 3), "Barra disponible (m)": round(stock_len, 3)})
            else:
                groups[key]["cuts"].append(cut)
    rows = []
    for profile, data in groups.items():
        cuts = sorted(data["cuts"], reverse=True)
        bars = []
        for cut in cuts:
            found = False
            for i in range(len(bars)):
                if bars[i] + 1e-9 >= cut + kerf:
                    bars[i] -= cut + kerf
                    found = True
                    break
            if not found:
                bars.append(max(0.0, stock_len - cut - kerf))
        purchased = len(bars) * stock_len
        used = sum(cuts)
        rows.append({"Perfil": profile, "Cortes": len(cuts), "Barras": len(bars),
                     "Compra (m)": round(purchased, 2),
                     "Peso compra (kg)": round(purchased * data["kg_m"], 2),
                     "Sobrante estimado (%)": round(max(0, (purchased-used)/purchased*100), 1) if purchased else 0})
    result = pd.DataFrame(rows)
    if oversized:
        st.warning("Hay piezas más largas que la barra comercial seleccionada; revisa esos cortes.")
        st.dataframe(pd.DataFrame(oversized), use_container_width=True, hide_index=True)
    return result

def stair_landing_plan(risers, kind, requested=None):
    """Devuelve el número de vuelos y descansillos solicitado por el usuario."""
    kind_text = str(kind).lower()
    if requested is not None:
        landings = max(0, min(int(requested), max(0, int(risers) - 1)))
        return landings + 1, landings
    if "caracol" in kind_text:
        flights = 1
    elif kind_text.startswith("en l") or kind_text.startswith("en u") or "descansillo" in kind_text:
        flights = 2
    else:
        flights = 1
    flights = min(flights, max(1, int(risers)))
    return flights, flights - 1


def draw_stair(risers, rise, tread, width, kind):
    fig, ax = plt.subplots(figsize=(10, 4.8))
    flights, landings = stair_landing_plan(risers, kind)
    # Reparte las contrahuellas entre vuelos sin cambiar la altura total.
    base, extra = divmod(risers, flights)
    counts = [base + (1 if i < extra else 0) for i in range(flights)]
    x, y = 0.0, 0.0
    ax.plot([x - 0.25, x], [y, y], color="#9aa5ad", linewidth=1.5)
    landing_depth = max(0.9, width)
    for idx, flight_risers in enumerate(counts):
        # Cada contrahuella sube verticalmente; entre dos contrahuellas hay una huella.
        # El último nivel lo aporta el suelo/planta superior, por eso hay risers-1 huellas.
        for step_idx in range(flight_risers):
            ax.plot([x, x], [y, y + rise], color="#34495e", linewidth=2.6)
            y += rise
            if step_idx < flight_risers - 1:
                ax.plot([x, x + tread], [y, y], color="#34495e", linewidth=2.6)
                x += tread
        if idx < len(counts) - 1:
            # Descansillo horizontal a la altura alcanzada.
            ax.plot([x, x + landing_depth], [y, y], color="#c47b35", linewidth=5,
                    solid_capstyle="butt", label="Descansillo" if idx == 0 else None)
            ax.text(x + landing_depth/2, y + max(rise*0.55, 0.08),
                    f"Descansillo {idx+1}", ha="center", va="bottom", fontsize=8, color="#8a4f18")
            x += landing_depth
    ax.plot([x, x + 0.25], [y, y], color="#9aa5ad", linewidth=1.5)
    ax.set_title(f"Vista lateral esquemática · {kind} · {landings} descansillo(s)", fontsize=12)
    ax.set_xlabel("Desarrollo horizontal aproximado (m)")
    ax.set_ylabel("Altura (m)")
    ax.grid(True, alpha=.2)
    ax.set_aspect("equal", adjustable="datalim")
    fig.tight_layout()
    return fig

def _cuboid_mesh(fig, x, y, z, length, width, height, angle, color, name, opacity=0.98):
    """Añade un peldaño como prisma cerrado, rotado alrededor de su centro."""
    # Rectángulo local con origen en la esquina delantera izquierda.
    local = [(0, 0), (length, 0), (length, width), (0, width)]
    cx, cy = length / 2, width / 2
    c, sn = math.cos(angle), math.sin(angle)
    xy = [(x + cx + (u-cx)*c - (v-cy)*sn,
           y + cy + (u-cx)*sn + (v-cy)*c) for u, v in local]
    verts = [(xx, yy, zz) for zz in (z, z + height) for xx, yy in xy]
    vx, vy, vz = zip(*verts)
    # 12 triángulos: tapa superior/inferior y las cuatro caras laterales.
    ii = [0, 0, 4, 4, 0, 0, 1, 1, 2, 2, 3, 3]
    jj = [1, 2, 5, 6, 1, 5, 2, 6, 3, 7, 0, 4]
    kk = [2, 3, 6, 7, 5, 4, 6, 5, 7, 6, 4, 7]
    fig.add_trace(go.Mesh3d(x=vx, y=vy, z=vz, i=ii, j=jj, k=kk,
        color=color, opacity=opacity, flatshading=True, showscale=False,
        name=name, hovertemplate=f"{name}<extra></extra>"))


def draw_stair_3d(risers, rise, tread, width, kind, finish="Roble", metal_color="#263746", railing="Dos lados", landing_count=0):
    """Vista 3D conceptual interactiva. Las medidas se expresan en metros."""
    risers = max(1, int(risers))
    rise = max(0.01, float(rise))
    tread = max(0.18, float(tread))
    width = max(0.5, float(width))
    thickness = max(0.035, min(0.07, rise * 0.18))
    top_color = {
        "Roble": "#b78350", "Chapa lagrimada": "#788692",
        "Rejilla metálica": "#9aa6af", "Vidrio": "#b9d9e8"
    }.get(finish, "#b78350")
    kind_lower = str(kind).lower()
    fig = go.Figure()

    # Hay n contrahuellas, pero normalmente n-1 huellas independientes.
    tread_count = max(1, risers - 1)
    first_flight = max(1, tread_count // 2)
    positions = []  # (x, y, z, orientation, flight)
    gap = max(0.08, width * 0.12)
    for i in range(tread_count):
        if "caracol" in kind_lower:
            # Peldaños radiales alrededor de un eje central; z avanza de forma uniforme.
            radius = max(0.45, width * 0.58)
            angle = (i / max(tread_count, 1)) * 2 * math.pi * 1.5
            x = radius * math.cos(angle)
            y = radius * math.sin(angle)
            positions.append((x, y, (i + 1) * rise, angle, 0))
        elif ("en l" in kind_lower or "en u" in kind_lower or "descansillo" in kind_lower) and i >= first_flight:
            j = i - first_flight
            if "en u" in kind_lower:
                # Segundo vuelo paralelo y en sentido contrario.
                x = (first_flight - 1 - j) * tread
                y = width + gap
                angle = math.pi
                flight = 1
            else:
                # Segundo vuelo gira 90 grados.
                x = max(0, first_flight - 1) * tread
                y = (j + 1) * tread
                angle = math.pi / 2
                flight = 1
            positions.append((x, y, (i + 1) * rise, angle, flight))
        else:
            positions.append((i * tread, 0.0, (i + 1) * rise, 0.0, 0))

    # Distribuye los descansillos solicitados entre los peldaños.
    # Son plataformas conceptuales; la geometría definitiva debe revisarse en planta.
    landing_indices = set()
    if landing_count > 0 and tread_count > 1 and "caracol" not in kind_lower:
        landing_count = min(int(landing_count), tread_count - 1)
        for k in range(1, landing_count + 1):
            landing_indices.add(round(k * tread_count / (landing_count + 1)) + 1)

    for idx, (x, y, z, angle, flight) in enumerate(positions, start=1):
        if idx in landing_indices and "caracol" not in kind_lower:
            _cuboid_mesh(fig, x, y, z-thickness, max(tread * 2.0, width * 0.9),
                         width, thickness, angle, "#c47b35", f"Descansillo {len([i for i in landing_indices if i <= idx])}")
        elif "caracol" in kind_lower:
            # Peldaño en cuña representado como un prisma angular extruido.
            radius = max(0.45, width * 0.58)
            inner = max(0.12, radius * 0.20)
            a0, a1 = angle - 0.38, angle + 0.38
            cx, cy = 0.0, 0.0
            xy = [(cx + r*math.cos(a), cy + r*math.sin(a))
                  for r, a in [(inner,a0),(radius,a0),(radius,a1),(inner,a1)]]
            verts = [(xx, yy, zz) for zz in (z-thickness, z) for xx, yy in xy]
            vx, vy, vz = zip(*verts)
            # Superficie superior e inferior y caras laterales de la cuña.
            ii = [0, 0, 4, 4, 0, 0, 1, 1, 2, 2, 3, 3]
            jj = [1, 2, 5, 6, 1, 5, 2, 6, 3, 7, 0, 4]
            kk = [2, 3, 6, 7, 5, 4, 6, 5, 7, 6, 4, 7]
            fig.add_trace(go.Mesh3d(x=vx,y=vy,z=vz,i=ii,j=jj,k=kk,
                color=top_color, opacity=0.97, flatshading=True, showscale=False,
                name=f"Peldaño {idx}", hovertemplate=f"Peldaño {idx}<extra></extra>"))
        else:
            # El centro de cada peldaño queda alineado con su posición.
            _cuboid_mesh(fig, x, y, z-thickness, tread, width, thickness,
                         angle, top_color, f"Peldaño {idx}")

    # Estructura y barandillas conceptuales.
    if positions and "caracol" not in kind_lower:
        # La posición lateral se mide desde el borde de cada peldaño (no desde el centro).
        sides = ([0.04, width - 0.04] if railing == "Dos lados"
                 else ([width - 0.04] if railing == "Un lado" else []))
        for side_index, rail_side in enumerate(sides):
            # Separar los tramos evita que el pasamanos cruce en diagonal entre vuelos.
            flight_ids = sorted(set(pos[4] for pos in positions))
            for flight_id in flight_ids:
                flight_positions = [pos for pos in positions if pos[4] == flight_id]
                rx, ry, rz = [], [], []
                for x, y, z, angle, flight in flight_positions:
                    lateral = rail_side - width / 2
                    rx.append(x + tread * 0.5 - math.sin(angle) * lateral)
                    ry.append(y + width * 0.5 + math.cos(angle) * lateral)
                    rz.append(z + 0.95)
                if not rx:
                    continue
                fig.add_trace(go.Scatter3d(x=rx, y=ry, z=rz, mode="lines",
                    line=dict(color=metal_color, width=7),
                    name="Pasamanos" if flight_id == flight_ids[0] else None,
                    showlegend=(flight_id == flight_ids[0]), hoverinfo="skip"))
                # Montantes visibles a lo largo de cada vuelo, incluidos ambos extremos.
                post_indices = sorted(set([0, len(rx)-1] + list(range(0, len(rx), max(1, len(rx)//8)))))
                for j in post_indices:
                    fig.add_trace(go.Scatter3d(x=[rx[j], rx[j]], y=[ry[j], ry[j]],
                        z=[max(0.02, rz[j]-0.9), rz[j]], mode="lines",
                        line=dict(color=metal_color, width=4), showlegend=False, hoverinfo="skip"))
        # Zanca central ilustrativa, siguiendo la trayectoria aproximada.
        sx, sy, sz = [], [], []
        for x, y, z, angle, flight in positions:
            sx.append(x + tread * 0.5)
            sy.append(y + width * 0.5)
            sz.append(z - thickness / 2)
        fig.add_trace(go.Scatter3d(x=sx, y=sy, z=sz, mode="lines",
            line=dict(color=metal_color, width=7), name="Estructura esquemática", hoverinfo="skip"))

    fig.update_layout(
        height=560, margin=dict(l=0, r=0, t=40, b=0),
        paper_bgcolor="rgba(0,0,0,0)",
        scene=dict(xaxis_title="Largo (m)", yaxis_title="Fondo (m)", zaxis_title="Altura (m)",
            aspectmode="data", bgcolor="rgba(245,247,249,1)",
            xaxis=dict(showbackground=True, backgroundcolor="#f3f5f7", gridcolor="#d7dde2"),
            yaxis=dict(showbackground=True, backgroundcolor="#f3f5f7", gridcolor="#d7dde2"),
            zaxis=dict(showbackground=True, backgroundcolor="#f3f5f7", gridcolor="#d7dde2")),
        legend=dict(orientation="h", yanchor="bottom", y=1.01, x=0))
    return fig

def draw_gate(width, height, leaves, bars):
    fig, ax = plt.subplots(figsize=(8, 4.8))
    ax.add_patch(Rectangle((0, 0), width, height, fill=False, linewidth=4, edgecolor="#34495e"))
    leaf_w = width / leaves
    for i in range(1, leaves):
        ax.plot([i*leaf_w, i*leaf_w], [0, height], color="#34495e", linewidth=2)
    for i in range(leaves):
        left = i*leaf_w + 0.05
        right = (i+1)*leaf_w - 0.05
        count = max(1, bars)
        for j in range(count):
            xx = left + (j+1)*(right-left)/(count+1)
            ax.plot([xx, xx], [0.05, height-0.05], color="#536d7a", linewidth=1.5)
        if leaf_w > 1.0:
            ax.plot([i*leaf_w+0.06, (i+1)*leaf_w-0.06], [0.08, height-0.08],
                    color="#a66b35", linewidth=1.8)
    ax.set_xlim(-0.1, width+0.1); ax.set_ylim(-0.1, height+0.15)
    ax.set_aspect("equal", adjustable="datalim")
    ax.set_title("Vista frontal esquemática · no es un plano de fabricación")
    ax.set_xlabel("Ancho (m)"); ax.set_ylabel("Alto (m)")
    ax.grid(True, alpha=.15)
    fig.tight_layout()
    return fig

def show_budget(pieces, extra_hours, cut_df=None):
    material_rows = [p for p in pieces if p["Tipo"] == "Perfil"]
    kg_used_profiles = sum(p["Peso aprox. (kg)"] for p in material_rows)
    kg_chapas = sum(p.get("Peso chapa (kg)", 0) for p in pieces)
    # Para presupuestar la compra, se usa el peso de barras completas cuando está disponible.
    kg_purchase_profiles = float(cut_df["Peso compra (kg)"].sum()) if cut_df is not None and not cut_df.empty else kg_used_profiles
    kg_total = kg_purchase_profiles + kg_chapas
    material_cost = kg_total * precio_kg
    labor_cost = extra_hours * tarifa_hora
    finish_cost = material_cost * acabado_pct
    base = material_cost + labor_cost + finish_cost
    total = base * (1 + iva_pct)
    a,b,c,d,e = st.columns(5)
    a.metric("Peso calculado", f"{kg_total:.1f} kg")
    b.metric("Material", f"{material_cost:.2f} €")
    c.metric("Mano de obra", f"{labor_cost:.2f} €")
    d.metric("Acabado", f"{finish_cost:.2f} €")
    e.metric("Total con IVA", f"{total:.2f} €")
    return kg_total, total

tabs = st.tabs(["🪜 Escaleras", "🚪 Portillas", "📐 Peso de perfiles", "🧾 Presupuesto y cortes", "ℹ️ Ayuda"])

if "pieces" not in st.session_state:
    st.session_state.pieces = []

with tabs[0]:
    st.subheader("Diseñador de escaleras metálicas 3D")
    st.caption("Elige una geometría, personaliza el acabado y gira el modelo para inspeccionarlo desde cualquier ángulo.")
    left, right = st.columns([1, 1.25], gap="large")
    with left:
        tipo = st.selectbox("Tipo de escalera", ["Recta", "En L", "En U", "De caracol", "Flotante", "Zanca central", "Industrial con rejilla", "Con descansillo"])
        descansillos_elegidos = st.number_input("Número de descansillos que quieres", min_value=0, max_value=10, value=1 if tipo in ["En L", "En U", "Con descansillo"] else 0, step=1)
        acabado_escalon = st.selectbox("Acabado de peldaños", ["Roble", "Chapa lagrimada", "Rejilla metálica", "Vidrio"])
        color_estructura = st.selectbox("Color de estructura", ["Antracita", "Negro", "Gris metalizado", "Blanco"], index=0)
        color_hex = {"Antracita":"#263746", "Negro":"#17191c", "Gris metalizado":"#87929a", "Blanco":"#e7e9eb"}[color_estructura]
        altura_cm = st.number_input("Altura entre plantas (cm)", min_value=50.0, max_value=600.0, value=280.0, step=1.0)
        largo_cm = st.number_input("Espacio disponible de largo (cm)", min_value=50.0, max_value=1000.0, value=350.0, step=1.0)
        ancho_cm = st.number_input("Ancho útil de escalera (cm)", min_value=50.0, max_value=300.0, value=100.0, step=5.0)
        fondo_cm = st.number_input("Espacio disponible de fondo (cm)", min_value=50.0, max_value=1000.0, value=250.0, step=1.0)
        barandilla = st.selectbox("Barandilla", ["Sin barandilla", "Un lado", "Dos lados"])
        material_peldano = st.selectbox("Peldaños", ["Chapa lagrimada (estimación)", "Rejilla metálica (calcular aparte)"])
        horas = st.number_input("Horas de fabricación estimadas", min_value=0.0, value=12.0, step=1.0)
        calc_stair = st.button("Calcular escalera", type="primary", use_container_width=True)
    with right:
        st.markdown("**Vista previa**")
        if calc_stair:
            n = max(2, round(altura_cm / 17.5))
            rise_cm = altura_cm / n
            # Fórmula ergonómica orientativa: 2 contrahuellas + huella ≈ 63 cm.
            tread_cm = max(20.0, 63 - 2 * rise_cm)
            run_cm = (n - 1) * tread_cm
            st.session_state.stair_data = (n, rise_cm, tread_cm, run_cm, altura_cm, ancho_cm, tipo, barandilla, material_peldano, horas, int(descansillos_elegidos))
            if rise_cm < 14 or rise_cm > 20:
                st.warning("La contrahuella calculada queda fuera de 14–20 cm, rango orientativo. Revisa el diseño y la normativa aplicable.")
        if "stair_data" in st.session_state:
            n, rise_cm, tread_cm, run_cm, h_cm, w_cm, kind, rail, treadmat, hours, descansillos_elegidos_guardados = st.session_state.stair_data
            vuelos, descansillos = stair_landing_plan(n, kind, descansillos_elegidos_guardados)
            st.plotly_chart(draw_stair_3d(n, rise_cm/100, tread_cm/100, w_cm/100, kind, acabado_escalon, color_hex, rail, descansillos), use_container_width=True, config={"displaylogo": False, "scrollZoom": True, "responsive": True})
            st.caption("Vista 3D interactiva: arrastra para girar, usa la rueda para acercar y los controles de la esquina para restablecer la cámara. Los descansillos se distribuyen de forma conceptual; revisa su posición real en planta antes de fabricar.")
            c1,c2,c3,c4 = st.columns(4)
            c1.metric("Contrahuellas", str(n))
            c2.metric("Contrahuella", f"{rise_cm:.1f} cm")
            c3.metric("Huella", f"{tread_cm:.1f} cm")
            c4.metric("Descansillos dibujados", str(descansillos))
            # Un descansillo sustituye una huella normal; no se suma encima de ella.
            profundidad_descansillo_cm = max(90.0, w_cm)
            desarrollo_con_descansillos = run_cm + descansillos * max(0.0, profundidad_descansillo_cm - tread_cm)
            st.write(f"Desarrollo horizontal sin descansillos: **{run_cm:.1f} cm** · desarrollo incluyendo descansillos: **{desarrollo_con_descansillos:.1f} cm aprox.** · Ancho: **{w_cm:.0f} cm**")
            # Orientación y cortes orientativos de los extremos de la zanca.
            inclinacion_deg = math.degrees(math.atan2(h_cm, max(run_cm, 0.01)))
            complementario_deg = 90.0 - inclinacion_deg
            st.markdown("#### 📐 Grados de los perfiles y cortes de la zanca")
            a1, a2 = st.columns(2)
            a1.metric("Inclinación de la zanca", f"{inclinacion_deg:.1f}°")
            a2.metric("Complementario", f"{complementario_deg:.1f}°")
            st.markdown("**Ángulo de corte respecto a un corte a escuadra (90°)**")
            c1, c2 = st.columns(2)
            c1.metric("Extremo inferior · apoyo horizontal", f"{inclinacion_deg:.1f}°")
            c2.metric("Extremo superior · apoyo vertical", f"{complementario_deg:.1f}°")
            st.caption("Estos dos últimos valores son el giro orientativo respecto al corte a escuadra para los apoyos indicados; no son universales. Si la zanca apoya contra otra cara, lleva placa, inglete o descansillo, el corte cambia. Verifica la orientación en un croquis y presenta el perfil antes de cortar la pieza definitiva.")
            if desarrollo_con_descansillos > largo_cm:
                st.warning("El desarrollo estimado con descansillos supera el largo disponible. Revisa el espacio o la distribución de los tramos.")
            if "en l" in kind.lower() and (profundidad_descansillo_cm + max(0, (n // 2) - 1) * tread_cm) > fondo_cm:
                st.warning("La huella en planta estimada para la escalera en L puede superar el fondo disponible.")
            if "en u" in kind.lower() and (2 * w_cm + max(0, (n // 2) - 1) * tread_cm) > fondo_cm:
                st.warning("La distribución en U puede superar el fondo disponible; comprueba la planta en el modelo antes de fabricar.")
            if run_cm <= largo_cm and (h_cm / 100) / max(run_cm / 100, 0.01) > 1.0:
                st.warning("La pendiente estimada es muy pronunciada; revisa la geometría con un profesional.")
            if descansillos:
                st.info("Se han incluido descansillos en el dibujo de forma automática. En una escalera en L, la vista lateral es solo esquemática: confirma la distribución en planta antes de fabricar.")
            if h_cm > 320:
                st.warning("La altura supera 3,20 m: revisa descansillos, geometría y normativa aplicable.")
            if 2*rise_cm+tread_cm < 54 or 2*rise_cm+tread_cm > 70:
                st.warning("La relación entre huella y contrahuella queda fuera del rango orientativo 54–70 cm.")
            st.markdown('<div class="note">La vista previa es geométrica y orientativa. No calcula resistencia estructural, anclajes ni dimensiones certificadas.</div>', unsafe_allow_html=True)
            if st.button("Añadir lista preliminar de materiales de escalera"):
                pieces = []
                width_m = w_cm/100
                rise_m = rise_cm/100
                tread_m = tread_cm/100
                slope_len = math.hypot(h_cm/100, run_cm/100)
                add_piece(pieces, "Tubo rectangular 120x60x4 · zancas", kg_tubo(120,60,4), slope_len, 2)
                add_piece(pieces, "Angular 40x40x4 · soportes", (4*(2*40-4)/1e6*DENSIDAD), tread_m, 2*(n-1))
                if material_peldano.startswith("Chapa"):
                    area = max(0, n-1) * width_m * (tread_m + 0.03)
                    weight = kg_chapa(area, 3)
                    pieces.append({"Elemento":"Chapa lagrimada 3 mm · estimación", "Tipo":"Chapa",
                                   "Cantidad":1, "Largo unitario (m)":0, "Total lineal (m)":0,
                                   "kg/m":0, "Peso aprox. (kg)":round(weight,2), "Peso chapa (kg)":weight})
                else:
                    st.warning("La rejilla metálica no se incluye en el peso ni en el coste porque depende del modelo y del fabricante. Añádela como partida aparte con su peso real.")
                if rail != "Sin barandilla":
                    sides = 1 if rail == "Un lado" else 2
                    add_piece(pieces, "Tubo 20x20x1.5 · barrotes", kg_tubo(20,20,1.5), 0.9, max(1, math.ceil(run_cm/12))*sides)
                    add_piece(pieces, "Tubo redondo 40x2 · pasamanos", kg_redondo_tubo(40,2), slope_len+0.2, sides)
                st.session_state.pieces = pieces
                st.session_state.hours = hours
                st.success("Lista preliminar añadida a la pestaña Presupuesto y cortes.")

with tabs[1]:
    st.subheader("Diseñador de portillas metálicas")
    c1,c2 = st.columns([1,1.2], gap="large")
    with c1:
        width = st.number_input("Ancho total del hueco (m)", min_value=0.3, max_value=10.0, value=2.5, step=0.1)
        height = st.number_input("Alto total (m)", min_value=0.3, max_value=4.0, value=1.5, step=0.1)
        leaves = st.selectbox("Número de hojas", [1,2], index=1)
        profile = st.selectbox("Perfil del marco", ["40x40x2", "40x40x3", "50x50x2", "60x40x2"])
        bar_spacing = st.number_input("Separación máxima orientativa entre barrotes (mm)", min_value=50, max_value=200, value=100, step=10)
        gate_hours = st.number_input("Horas de fabricación estimadas", min_value=0.0, value=8.0, step=1.0)
        calc_gate = st.button("Calcular portilla", type="primary", use_container_width=True)
    with c2:
        if calc_gate:
            bars = max(1, math.ceil((width/leaves*1000 - 160 - bar_spacing)/(20+bar_spacing)))
            st.session_state.gate_data = (width,height,leaves,bars,profile,bar_spacing,gate_hours)
        if "gate_data" in st.session_state:
            w,h,l,bars,prof,spacing,hours = st.session_state.gate_data
            st.pyplot(draw_gate(w,h,l,bars), use_container_width=True)
            st.caption("Esquema frontal generado a partir de las dimensiones introducidas.")
            st.write(f"**Ancho aproximado por hoja:** {w/l:.2f} m · **Barrotes estimados por hoja:** {bars}")
            if w/l > 1.5:
                st.warning("Hoja ancha: revisa peso, flecha, bisagras, postes y necesidad de refuerzos.")
            if h > 2.0:
                st.warning("Portilla alta: revisa cargas de viento, fijaciones y rigidez.")
            if st.button("Añadir lista preliminar de materiales de portilla"):
                frame = {"40x40x2":(40,40,2),"40x40x3":(40,40,3),"50x50x2":(50,50,2),"60x40x2":(60,40,2)}[prof]
                fw, fh = w/l-0.03, h-0.05
                pieces=[]
                add_piece(pieces, f"Tubo {prof} · laterales", kg_tubo(*frame), fh, 2*l)
                add_piece(pieces, f"Tubo {prof} · travesaños", kg_tubo(*frame), max(0.1,fw), 2*l)
                add_piece(pieces, "Tubo 20x20x1.5 · barrotes", kg_tubo(20,20,1.5), max(0.1,fh-0.08), bars*l)
                if fw > 1.0:
                    add_piece(pieces, "Tubo 30x30x2 · diagonales orientativas", kg_tubo(30,30,2),
                              math.hypot(max(.1,fw-.08),max(.1,fh-.08)), l)
                st.session_state.pieces = pieces
                st.session_state.hours = hours
                st.success("Lista preliminar añadida a la pestaña Presupuesto y cortes.")

with tabs[2]:
    st.subheader("Calculadora de peso de perfiles")
    c1,c2,c3 = st.columns(3)
    shape = c1.selectbox("Forma", ["Tubo cuadrado/rectangular", "Tubo redondo", "Pletina", "Redondo macizo", "Chapa"])
    if shape == "Tubo cuadrado/rectangular":
        a = c1.number_input("Lado A (mm)", min_value=1.0, value=40.0)
        b = c2.number_input("Lado B (mm)", min_value=1.0, value=40.0)
        e = c3.number_input("Espesor (mm)", min_value=0.5, value=2.0)
        kgm = kg_tubo(a,b,e)
    elif shape == "Tubo redondo":
        d = c1.number_input("Diámetro exterior (mm)", min_value=1.0, value=40.0)
        e = c2.number_input("Espesor (mm)", min_value=0.5, value=2.0)
        kgm = kg_redondo_tubo(d,e)
    elif shape == "Pletina":
        a = c1.number_input("Ancho (mm)", min_value=1.0, value=40.0)
        e = c2.number_input("Espesor (mm)", min_value=0.5, value=5.0)
        kgm = kg_pletina(a,e)
    elif shape == "Redondo macizo":
        d = c1.number_input("Diámetro (mm)", min_value=1.0, value=12.0)
        kgm = math.pi*d*d/4/1e6*DENSIDAD
    else:
        a = c1.number_input("Largo (m)", min_value=0.01, value=1.0)
        b = c2.number_input("Ancho (m)", min_value=0.01, value=1.0)
        e = c3.number_input("Espesor (mm)", min_value=0.5, value=3.0)
        kgm = kg_chapa(a*b,e)
    st.metric("Peso estimado", f"{kgm:.3f} kg/m" if shape != "Chapa" else f"{kgm:.2f} kg por pieza")
    c1, c2 = st.columns(2)
    length_m = c1.number_input("Largo por pieza (m)", min_value=0.01, value=1.0, step=0.1, key="calc_piece_length")
    qty = c2.number_input("Cantidad de piezas", min_value=1, value=1, step=1, key="calc_piece_qty")
    if shape == "Chapa":
        total_weight = kgm * qty
    else:
        total_weight = kgm * length_m * qty
    st.write(f"Peso total de esta partida: **{total_weight:.2f} kg**")
    if st.button("➕ Añadir esta partida al presupuesto", type="primary"):
        if shape == "Chapa":
            st.session_state.pieces.append({"Elemento": f"Chapa {e:g} mm ({a:g} × {b:g} m)", "Tipo": "Chapa",
                "Cantidad": int(qty), "Largo unitario (m)": 0, "Total lineal (m)": 0,
                "kg/m": 0, "Peso aprox. (kg)": round(total_weight, 2), "Peso chapa (kg)": round(total_weight, 2)})
        else:
            if shape == "Tubo cuadrado/rectangular":
                label = f"Tubo {a:g}x{b:g}x{e:g} mm"
            elif shape == "Tubo redondo":
                label = f"Tubo redondo Ø{d:g}x{e:g} mm"
            elif shape == "Pletina":
                label = f"Pletina {a:g}x{e:g} mm"
            else:
                label = f"Redondo macizo Ø{d:g} mm"
            add_piece(st.session_state.pieces, label, kgm, length_m, qty)
        st.success("Partida añadida. Ve a Presupuesto y cortes para revisar el total.")
    st.caption("Estimación por geometría y densidad teórica del acero. Los perfiles comerciales reales pueden variar.")

with tabs[3]:
    st.subheader("Lista de materiales, barras y presupuesto")
    st.caption(f"Proyecto: **{proyecto}**" + (f" · Cliente: **{cliente}**" if cliente.strip() else ""))
    if not st.session_state.pieces:
        st.info("Calcula una escalera o una portilla y pulsa «Añadir lista preliminar de materiales».")
    else:
        df = pd.DataFrame(st.session_state.pieces)
        st.dataframe(df, use_container_width=True, hide_index=True)
        cut_df = group_cut_list(st.session_state.pieces, largo_barra, perdida_corte)
        if not cut_df.empty:
            st.markdown("#### Optimización orientativa de barras")
            st.dataframe(cut_df, use_container_width=True, hide_index=True)
        default_hours = float(st.session_state.get("hours", 8.0))
        hours = st.number_input("Horas totales de trabajo", min_value=0.0, value=default_hours, step=1.0)
        show_budget(st.session_state.pieces, hours, cut_df)
        csv = df.to_csv(index=False).encode("utf-8-sig")
        st.download_button("⬇️ Descargar lista de materiales CSV", csv, "lista_materiales_herreria.csv", "text/csv")
        kg_profiles_purchase = float(cut_df["Peso compra (kg)"].sum()) if not cut_df.empty and "Peso compra (kg)" in cut_df.columns else sum(p["Peso aprox. (kg)"] for p in st.session_state.pieces if p["Tipo"] == "Perfil")
        kg_sheets = sum(p.get("Peso chapa (kg)", 0) for p in st.session_state.pieces)
        summary = (f"HERRERIA PRO\nProyecto: {proyecto}\nCliente: {cliente or 'No indicado'}\n"
                   f"Peso estimado de compra: {kg_profiles_purchase + kg_sheets:.2f} kg\n"
                   f"Precios configurados: acero {precio_kg:.2f} €/kg, mano de obra {tarifa_hora:.2f} €/h, IVA {iva_pct*100:.1f}%\n"
                   "Documento orientativo; comprobar medidas, estructura, anclajes y normativa antes de fabricar.\n")
        st.download_button("⬇️ Descargar resumen del proyecto TXT", summary, "resumen_herreria.txt", "text/plain")
        if st.button("Vaciar lista de materiales"):
            st.session_state.pieces=[]
            st.rerun()

with tabs[4]:
    st.subheader("Cómo usar HerrerIA Pro")
    st.markdown("""
1. Entra en **Escaleras** o **Portillas**.
2. Introduce las medidas reales del hueco y selecciona las opciones.
3. Pulsa **Calcular** para obtener una vista previa y medidas orientativas.
4. Pulsa **Añadir lista preliminar de materiales**.
5. Abre **Presupuesto y cortes** para consultar perfiles, barras, peso y precio.
6. Ajusta precios, IVA, longitud de barras y pérdida de corte en la barra lateral.

**Límites importantes**
- La vista 3D es un modelo visual preliminar, no un plano CAD ni un plano de fabricación.
- La lista de materiales usa perfiles orientativos y no verifica resistencia estructural.
- Antes de fabricar, hay que comprobar normativa aplicable, cargas, estabilidad, anclajes, soldaduras, corrosión, holguras y herrajes con un profesional competente.
- Los precios son editables y no representan cotizaciones reales de proveedores.
""")
    st.markdown('<div class="note">Consejo: usa medidas en metros o centímetros tal como indica cada campo. Revisa siempre las unidades antes de cortar el material.</div>', unsafe_allow_html=True)
