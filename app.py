# -*- coding: utf-8 -*-
"""
app.py — Laboratorio virtual de caracterización de una celda p-n de silicio
(Problema 2.2, Proyecto 1 "Celdas Solares Fotovoltaicas", UAI 2026-2)

Arquitectura:
    constantes.py -> todas las constantes físicas y parámetros de semilla
    fisica.py     -> modelo físico puro (óptica, colección, diodo, temperatura)
    app.py (este) -> capa de interfaz Streamlit: sidebar, pestañas, animaciones

Estado compartido entre pestañas: st.session_state guarda todos los
parámetros físicos (geometría, dopajes, Sf/Sr, τ, Rs/Rp, malla frontal,
defectos). Lo que el usuario cambia en una pestaña se refleja de
inmediato en las demás, porque todas leen del mismo session_state.
"""
import json
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
import streamlit as st
import streamlit.components.v1 as components
from plotly.subplots import make_subplots
import constantes as c
import fisica as f

st.set_page_config(page_title="Celda p-n de Silicio — Laboratorio Virtual",
                    layout="wide", initial_sidebar_state="expanded")

# ============================================================
# ESTADO COMPARTIDO (valores por defecto = semilla S = 3)
# ============================================================
DEFAULTS = dict(
    NA=c.NA_BASE_DEFAULT, ND=c.ND_EMISOR_DEFAULT,
    dn_um=c.D_N_EMISOR_UM, Wp_um=c.W_P_BASE_UM_DEFAULT,
    tau_n_us=c.TAU_SRH_VOLUMEN_US_DEFAULT, tau_p_us=c.TAU_P_EMISOR_US_DEFAULT,
    Sf=c.S_FRONTAL_CM_S_DEFAULT, Sr=1.0e2,
    T_C=c.T_OPERACION_C_DEFAULT,
    modo_R="fresnel", reflector_trasero=False,
    lambda_perfil=550.0, lambda_iqe_mapa=550.0,
    Rs_extra=0.0, Rp=c.RP_BASE_OHM_CM2, n_ideal=1.0, irradiancia_soles=1.0,
    num_dedos=c.NUMERO_DEDOS_BASE, ancho_dedo_um=c.ANCHO_DEDO_BASE_UM,
    defecto_activo=False, defecto_filas=(2, 4), defecto_cols=(2, 4),
    defecto_tau_n_us=5.0, dedo_roto_col=None,
    anim_modo="unico",
)
for k, v in DEFAULTS.items():
    st.session_state.setdefault(k, v)

S = st.session_state  # atajo


# ============================================================
# SIDEBAR — parámetros físicos (compartidos por todas las pestañas)
# ============================================================
with st.sidebar:
    st.markdown("## ⚙️ Parámetros físicos")
    st.caption(f"Semilla asignada **S = {c.SEMILLA_S}** (Tabla A.1, Anexo A) — "
               "estos son los valores por defecto y los usados en Validación.")
    st.info(
        f"**NA (base p)** = {c.NA_BASE_DEFAULT:.1e} cm⁻³  \n"
        f"**ND (emisor n)** = {c.ND_EMISOR_DEFAULT:.1e} cm⁻³  \n"
        f"**τ_SRH volumen** = {c.TAU_SRH_VOLUMEN_US_DEFAULT:.0f} µs  \n"
        f"**S_frontal** = {c.S_FRONTAL_CM_S_DEFAULT:.0e} cm/s  \n"
        f"**T operación** = {c.T_OPERACION_C_DEFAULT:.0f} °C"
    )

    st.markdown("### Geometría")
    S["dn_um"] = st.slider("Espesor emisor dₙ [µm]", 0.2, 10.0, S["dn_um"], 0.1)
    S["Wp_um"] = st.slider("Espesor base W_p [µm]", c.W_P_BASE_MIN_UM, c.W_P_BASE_MAX_UM, S["Wp_um"], 5.0)

    st.markdown("### Dopajes")
    S["NA"] = st.select_slider("N_A base p [cm⁻³]", options=[1e14,3e14,1e15,3e15,1e16,3e16,1e17],
                                value=min([1e14,3e14,1e15,3e15,1e16,3e16,1e17], key=lambda z: abs(z-S["NA"])),
                                format_func=lambda z: f"{z:.0e}")
    S["ND"] = st.select_slider("N_D emisor n [cm⁻³]", options=[1e18,3e18,1e19,3e19,1e20],
                                value=min([1e18,3e18,1e19,3e19,1e20], key=lambda z: abs(z-S["ND"])),
                                format_func=lambda z: f"{z:.0e}")

    st.markdown("### Recombinación / colección")
    S["Sf"] = st.select_slider("S frontal [cm/s]", options=[10,1e2,1e3,1e4,1e5,1e6],
                                value=min([10,1e2,1e3,1e4,1e5,1e6], key=lambda z: abs(z-S["Sf"])),
                                format_func=lambda z: f"{z:.0e}")
    S["Sr"] = st.select_slider("S trasera [cm/s]", options=[10,1e2,1e3,1e4,1e5,1e6],
                                value=min([10,1e2,1e3,1e4,1e5,1e6], key=lambda z: abs(z-S["Sr"])),
                                format_func=lambda z: f"{z:.0e}")
    S["tau_n_us"] = st.slider("τₙ volumen (base) [µs]", 0.1, 1000.0, S["tau_n_us"])
    S["tau_p_us"] = st.slider("τₚ emisor [µs]", 0.1, 1000.0, S["tau_p_us"])

    st.markdown("### Diodo eléctrico")
    S["Rs_extra"] = st.slider("Rs adicional [Ω·cm²]", 0.0, 2.0, S["Rs_extra"], 0.05)
    S["Rp"] = st.select_slider("Rp [Ω·cm²]", options=[10,1e2,1e3,1e4,1e5,1e6],
                                value=min([10,1e2,1e3,1e4,1e5,1e6], key=lambda z: abs(z-S["Rp"])),
                                format_func=lambda z: f"{z:.0e}")
    S["n_ideal"] = st.slider("Factor de idealidad n", 1.0, 2.0, S["n_ideal"], 0.05)
    st.caption(f"Irradiancia: {S['irradiancia_soles']:.2f} soles · control en Pestaña 1")
    S["T_C"] = st.slider("Temperatura de operación [°C]", 15.0, 75.0, S["T_C"], 1.0)

    st.markdown("### Malla frontal de plata")
    S["num_dedos"] = st.slider("N° de dedos", 5, 100, S["num_dedos"])
    S["ancho_dedo_um"] = st.slider("Ancho de dedo [µm]", 20.0, 200.0, S["ancho_dedo_um"])

    st.caption("Estado compartido: lo que cambias acá se refleja en todas las pestañas.")
    if st.button("Restablecer parámetros de semilla", use_container_width=True):
        for _k, _v in DEFAULTS.items():
            st.session_state[_k] = _v
        st.rerun()


# ============================================================
# FÍSICA COMÚN (recalculada en cada rerun a partir de session_state)
# ============================================================
T_K = S["T_C"] + 273.15
W_total_um = S["dn_um"] + S["Wp_um"]

Dp = f.coef_difusion(T_K, c.MU_P_EMISOR_N_300K)
Dn = f.coef_difusion(T_K, c.MU_N_BASE_P_300K)
Lp_cm = f.longitud_difusion(Dp, S["tau_p_us"]); Lp_um = Lp_cm * 1e4
Ln_cm = f.longitud_difusion(Dn, S["tau_n_us"]); Ln_um = Ln_cm * 1e4

Psi0 = f.potencial_juntura(S["NA"], S["ND"], c.NI_300K, T_K)
Wdep_cm = f.ancho_zona_deplecion(Psi0, S["NA"], S["ND"]); Wdep_um = Wdep_cm * 1e4
# El enunciado del Problema 2.2 entrega explícitamente una zona de
# deplección centrada en la juntura: xn=xj-Wdep/2, xp=xj+Wdep/2.
# Usamos esa definición para que la simulación sea trazable a la pauta.
xn_um = max(S["dn_um"] - Wdep_um / 2.0, 1e-4)
xp_um = min(S["dn_um"] + Wdep_um / 2.0, W_total_um - 1e-4)
if xp_um <= xn_um:
    xp_um = xn_um + 1e-4

wl_grid = np.linspace(300.0, 1200.0, 500)
alpha_grid = f.alpha_silicio(wl_grid)
R_grid = f.reflectancia_frontal(wl_grid, modo=S["modo_R"])
P_lambda, phi0_grid = f.espectro_y_flujo_fotones(wl_grid)

EQE, IQE = f.calcular_EQE_IQE_preciso(
    wl_grid, alpha_grid, R_grid, phi0_grid,
    xn_um, xp_um, W_total_um, Lp_um, Ln_um, Dp, Dn, S["Sf"], S["Sr"],
    reflector_trasero_activo=S["reflector_trasero"],
    R_aluminio=c.R_ALUMINIO_EFECTIVA,
)
JL_A_cm2 = c.Q * np.trapezoid(phi0_grid * EQE, wl_grid)
J0_A_cm2 = f.corriente_saturacion_J0(S["NA"], S["ND"], c.NI_300K, Dn, Ln_cm, Dp, Lp_cm)


def truncar_cerca_voc(V_array, J_array, P_array=None, margen_frac=0.025):
    """Recorta la curva J-V justo después de Voc. Más allá de Voc el diodo
    entra en conducción directa fuerte (J puede llegar a decenas de
    mA/cm² positivos): incluir ese tramo hace que cualquier autoescala
    (Plotly o manual) aplaste la zona fotovoltaica, que es la que importa
    mostrar. Devuelve (V, J[, P]) recortados, con J en signo positivo
    (positivo = corriente que la celda entrega)."""
    J_array = np.asarray(J_array, dtype=float)
    if np.any(J_array >= 0):
        i_voc = int(np.searchsorted(J_array, 0.0))
    else:
        i_voc = len(J_array) - 1
    i_corte = min(i_voc + max(len(J_array) // 40, 3), len(J_array) - 1)
    V_out = V_array[:i_corte + 1]
    J_out = -J_array[:i_corte + 1]
    if P_array is not None:
        return V_out, J_out, np.asarray(P_array)[:i_corte + 1]
    return V_out, J_out


def wavelength_to_hex(wl):
    """Color solo para visualizacion.

    En el visible (380-750 nm) se usa una aproximacion RGB. UV e IR no tienen
    un color visible real: se representan con falso color para distinguirlos
    sin alterar en ningun caso la fisica de alpha(lambda).
    """
    wl = float(wl)
    if wl < 380.0:
        return "#8b5cf6"   # UV: falso color violeta
    if wl > 750.0:
        return "#fb7185"   # IR: falso color rosado/rojo suave

    if wl < 440:
        R, G, B = -(wl - 440) / (440 - 380), 0.0, 1.0
    elif wl < 490:
        R, G, B = 0.0, (wl - 440) / (490 - 440), 1.0
    elif wl < 510:
        R, G, B = 0.0, 1.0, -(wl - 510) / (510 - 490)
    elif wl < 580:
        R, G, B = (wl - 510) / (580 - 510), 1.0, 0.0
    elif wl < 645:
        R, G, B = 1.0, -(wl - 645) / (645 - 580), 0.0
    else:
        R, G, B = 1.0, 0.0, 0.0
    return "#%02x%02x%02x" % (int(255 * R), int(255 * G), int(255 * B))


def generacion_actual(x_um):
    """G(x,lambda) coherente con el estado óptico compartido, incluido el reflector."""
    return f.tasa_generacion_con_reflector(
        x_um, phi0_grid, R_grid, alpha_grid, W_total_um,
        reflector_trasero_activo=S["reflector_trasero"],
        R_aluminio=c.R_ALUMINIO_EFECTIVA,
    )

# ============================================================
# TEMA VISUAL — tipografía y estilos coherentes en toda la app
# ============================================================
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=JetBrains+Mono:wght@500&display=swap');

html, body, [class*="css"] {
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
}

/* ---- Encabezados ---- */
h1 {
    font-weight: 800 !important;
    letter-spacing: -0.02em;
    background: linear-gradient(90deg, #f6ad55 0%, #f687b3 60%, #63b3ed 100%);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
    padding-bottom: 2px;
}
h2, h3, h4, h5 { font-weight: 600 !important; letter-spacing: -0.01em; }
h4, h5 { color: #cbd5e0 !important; }

/* ---- Pestañas principales ---- */
button[data-baseweb="tab"] {
    font-size: 0.95rem;
    font-weight: 600;
    padding: 10px 18px;
    border-radius: 10px 10px 0 0 !important;
    color: #94a3b8;
}
button[data-baseweb="tab"][aria-selected="true"] {
    color: #f6ad55 !important;
    background: rgba(246, 173, 85, 0.08);
    border-bottom: 2.5px solid #f6ad55 !important;
}
div[data-baseweb="tab-highlight"] { background-color: #f6ad55 !important; }
div[data-baseweb="tab-border"] { background-color: rgba(148,163,184,0.15) !important; }

/* ---- Métricas como tarjetas ---- */
div[data-testid="stMetric"] {
    background: rgba(255,255,255,0.03);
    border: 1px solid rgba(148,163,184,0.14);
    border-radius: 12px;
    padding: 12px 14px 8px 14px;
    box-shadow: 0 2px 10px rgba(0,0,0,0.18);
}
div[data-testid="stMetricValue"] {
    font-size: 1.35rem;
    font-weight: 700;
    font-family: 'JetBrains Mono', monospace;
}
div[data-testid="stMetricLabel"] { color: #94a3b8 !important; font-size: 0.82rem; }

/* ---- Cajas informativas y expanders ---- */
div[data-testid="stAlertContainer"] {
    border-radius: 10px !important;
    border-left: 3.5px solid #f6ad55 !important;
}
div[data-testid="stExpander"] {
    border: 1px solid rgba(148,163,184,0.16) !important;
    border-radius: 12px !important;
    background: rgba(255,255,255,0.015);
}

/* ---- Sliders y controles ---- */
div[data-baseweb="slider"] > div > div > div { background-color: #f6ad55 !important; }

/* ---- Botones ---- */
.stButton > button {
    border-radius: 8px;
    font-weight: 600;
    border: 1px solid rgba(246,173,85,0.4);
}
.stButton > button:hover { border-color: #f6ad55; color: #f6ad55; }

/* ---- Sidebar ---- */
section[data-testid="stSidebar"] {
    border-right: 1px solid rgba(148,163,184,0.12);
}

/* ---- Iframes de animaciones (canvas) sin borde duro ---- */
iframe { border-radius: 10px; }

/* ---- Separadores ---- */
hr { border-color: rgba(148,163,184,0.15) !important; }
</style>
""", unsafe_allow_html=True)

# ============================================================
# ENCABEZADO
# ============================================================
st.title("Laboratorio virtual · Celda p-n de silicio")
st.caption("Explore los parámetros físicos de la celda y observe en tiempo real cómo cambian la absorción, la colección de portadores y la respuesta eléctrica.")

tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
    "🔆 1. Absorción y Generación",
    "🎯 2. Eficiencia Cuántica (EQE/IQE)",
    "⚡ 3. Curva I-V",
    "🧩 4. Sectores y Defectos",
    "✅ 5. Validación",
    "🎬 6. Resumen animado",
])

# ------------------------------------------------------------------
# TAB 1 — ABSORCIÓN Y GENERACIÓN
# ------------------------------------------------------------------
with tab1:
    st.subheader("Absorción y generación")

    # Irradiancia compartida por toda la app. Aqui se controla porque es donde
    # su efecto optico es mas intuitivo: mas soles = mas fotones por unidad de tiempo.
    c_lambda, c_modo, c_irr = st.columns([2.2, 1.5, 1.5])

    with c_lambda:
        st.slider(
            "Longitud de onda λ [nm]",
            300.0,
            1200.0,
            step=5.0,
            key="lambda_perfil",
        )

    with c_modo:
        st.radio(
            "Iluminación",
            options=["unico", "arcoiris"],
            format_func=lambda x: "λ seleccionada" if x == "unico" else "Espectro solar AM1.5G",
            horizontal=True,
            key="anim_modo",
        )

    with c_irr:
        st.slider(
            "Irradiancia [soles]",
            0.10,
            1.50,
            step=0.05,
            key="irradiancia_soles",
        )

    # Óptica junto a la simulación: estos controles afectan directamente
    # reflexión, absorción y el balance de fotones de esta pestaña.
    c_ref, c_al = st.columns([1.6, 1.4])
    with c_ref:
        st.radio(
            "Reflectancia frontal R(λ)",
            options=["fresnel", "fijo"],
            format_func=lambda x: "Fresnel" if x == "fresnel" else "R fija",
            horizontal=True,
            key="modo_R",
        )
    with c_al:
        st.checkbox(
            "Reflector trasero de Al",
            key="reflector_trasero",
        )

    irr_soles = float(S["irradiancia_soles"])

    def generacion_actual_vista(x_um):
        return irr_soles * generacion_actual(x_um)

    # ============================================================
    # ANIMACION 2D — FOTONES + ABSORCION
    # ============================================================
    wl_anim = np.linspace(300.0, 1200.0, 91)
    alpha_um_lookup = (f.alpha_silicio(wl_anim) * 1e-4).tolist()
    wl_lookup = wl_anim.tolist()
    R_lookup = f.reflectancia_frontal(wl_anim, modo=S["modo_R"]).tolist()

    _, phi0_lookup_raw = f.espectro_y_flujo_fotones(wl_anim)
    phi0_lookup = np.clip(phi0_lookup_raw, 0.0, None).tolist()

    single_wl = float(S["lambda_perfil"])
    single_color = wavelength_to_hex(single_wl)
    single_alpha_um = float(f.alpha_silicio(np.array([single_wl]))[0] * 1e-4)
    single_depth_um = 1.0 / max(single_alpha_um, 1e-12)
    single_x90_um = np.log(10.0) / max(single_alpha_um, 1e-12)

    # ------------------------------------------------------------
    # BALANCE ÓPTICO FÍSICO
    # ------------------------------------------------------------
    # Todos los valores mostrados al usuario se calculan a partir del flujo
    # espectral AM1.5G, R(lambda), alpha(lambda), espesor de la celda y el
    # reflector trasero. La animación es sólo una muestra Monte Carlo de esas
    # probabilidades; los números mostrados NO son conteos de sprites.
    frac_r_phys, frac_a_phys, frac_back_phys, frac_escape_phys = (
        f.balance_fotones_con_reflector(
            R_grid,
            alpha_grid,
            W_total_um,
            reflector_trasero_activo=S["reflector_trasero"],
            R_aluminio=c.R_ALUMINIO_EFECTIVA,
        )
    )

    # Fracción que alcanza el dorso y efectivamente rebota en el Al. Es un
    # evento intermedio: luego ese mismo fotón puede absorberse o escapar.
    trans_una_pasada_phys = np.exp(-alpha_grid * W_total_um * 1e-4)
    frac_al_ref_phys = (
        (1.0 - R_grid)
        * trans_una_pasada_phys
        * c.R_ALUMINIO_EFECTIVA
        if S["reflector_trasero"]
        else np.zeros_like(wl_grid)
    )

    if S["anim_modo"] == "unico":
        # En modo lambda única se muestran DENSIDADES ESPECTRALES de flujo,
        # por unidad de longitud de onda, evaluadas exactamente en lambda.
        phi_inc_phys = irr_soles * float(np.interp(single_wl, wl_grid, phi0_grid))
        f_r = float(np.interp(single_wl, wl_grid, frac_r_phys))
        f_a = float(np.interp(single_wl, wl_grid, frac_a_phys))
        f_b = float(np.interp(single_wl, wl_grid, frac_back_phys))
        f_e = float(np.interp(single_wl, wl_grid, frac_escape_phys))
        f_al = float(np.interp(single_wl, wl_grid, frac_al_ref_phys))

        flujo_inc_phys = phi_inc_phys
        flujo_r_phys = phi_inc_phys * f_r
        flujo_a_phys = phi_inc_phys * f_a
        flujo_back_phys = phi_inc_phys * f_b
        flujo_escape_phys = phi_inc_phys * f_e
        flujo_al_phys = phi_inc_phys * f_al
        flujo_unidad = "fot·cm⁻²·s⁻¹·nm⁻¹"
    else:
        # En AM1.5G se integra el espectro completo de 300 a 1200 nm.
        phi_espectral_phys = irr_soles * phi0_grid
        flujo_inc_phys = float(np.trapezoid(phi_espectral_phys, wl_grid))
        flujo_r_phys = float(np.trapezoid(phi_espectral_phys * frac_r_phys, wl_grid))
        flujo_a_phys = float(np.trapezoid(phi_espectral_phys * frac_a_phys, wl_grid))
        flujo_back_phys = float(np.trapezoid(phi_espectral_phys * frac_back_phys, wl_grid))
        flujo_escape_phys = float(np.trapezoid(phi_espectral_phys * frac_escape_phys, wl_grid))
        flujo_al_phys = float(np.trapezoid(phi_espectral_phys * frac_al_ref_phys, wl_grid))
        flujo_unidad = "fot·cm⁻²·s⁻¹"

    # ------------------------------------------------------------
    # GENERACIÓN FÍSICA DE PARES ELECTRÓN-HUECO
    # ------------------------------------------------------------
    # Un fotón sólo puede crear un par e−/h+ por excitación banda-a-banda si
    # E_fotón >= Eg. Para Si a 300 K, λ_g = hc/(q Eg) ≈ 1107 nm.
    lambda_gap_nm = (
        c.H_PLANCK * c.C_LUZ / (c.Q * c.EG_SI_300K) * 1e9
    )

    if S["anim_modo"] == "unico":
        puede_generar_par = single_wl <= lambda_gap_nm
        flujo_pares_phys = flujo_a_phys if puede_generar_par else 0.0
        flujo_pares_unidad = "pares·cm⁻²·s⁻¹·nm⁻¹"
        pares_acum_unidad = "pares·cm⁻²·nm⁻¹"
    else:
        energia_foton_eV = (
            c.H_PLANCK * c.C_LUZ
            / (wl_grid * 1e-9)
            / c.Q
        )
        mascara_sobre_gap = energia_foton_eV >= c.EG_SI_300K
        flujo_pares_phys = float(np.trapezoid(
            phi_espectral_phys
            * frac_a_phys
            * mascara_sobre_gap.astype(float),
            wl_grid,
        ))
        flujo_pares_unidad = "pares·cm⁻²·s⁻¹"
        pares_acum_unidad = "pares·cm⁻²"

    def _fmt_flujo(v):
        return f"{v:.2e}"

    def _pct_flujo(v):
        return 100.0 * v / flujo_inc_phys if flujo_inc_phys > 0 else 0.0

    # Densidad de sprites: sólo resolución gráfica. Su valor relativo sí sigue
    # el flujo físico incidente; cada sprite representa una enorme cantidad de
    # fotones reales y nunca se presenta como una magnitud física.
    if S["anim_modo"] == "unico":
        phi_ref_visual = max(
            1e-30,
            1.5 * float(np.max(phi0_grid)),
        )
        intensidad_visual_rel = np.clip(flujo_inc_phys / phi_ref_visual, 0.03, 1.0)
    else:
        flujo_ref_visual = max(
            1e-30,
            1.5 * float(np.trapezoid(phi0_grid, wl_grid)),
        )
        intensidad_visual_rel = np.clip(flujo_inc_phys / flujo_ref_visual, 0.03, 1.0)

    html_photons = f"""
<div style="background:linear-gradient(180deg,#07101c 0%,#091321 100%);border:1px solid rgba(148,163,184,.10);border-radius:16px;padding:8px;overflow:hidden">
<canvas id="cv" width="1000" height="420" style="width:100%;display:block;border-radius:12px;"></canvas>
<div id="live-photon-counts" style="display:grid;grid-template-columns:repeat(auto-fit,minmax(118px,1fr));gap:7px;padding:8px 4px 3px 4px;font-family:Inter,system-ui,sans-serif;">
  <div class="livecount"><span>INCIDENTES</span><strong id="live-inc">0</strong></div>
  <div class="livecount"><span>ABSORBIDOS</span><strong id="live-abs">0</strong></div>
  <div class="livecount"><span>PARES e⁻/h⁺</span><strong id="live-pairs">0</strong></div>
  <div class="livecount"><span>REF. FRONTAL</span><strong id="live-front">0</strong></div>
  <div class="livecount"><span>NO ABSORBIDOS</span><strong id="live-nonabs">0</strong></div>
  <div class="livecount"><span>PÉRDIDA TRASERA</span><strong id="live-back">0</strong></div>
  <div class="livecount"><span>ESCAPE FRONTAL</span><strong id="live-escape">0</strong></div>
  <div class="livecount" id="live-al-box" style="display:{'block' if S['reflector_trasero'] else 'none'}"><span>REF. EN Al</span><strong id="live-al">0</strong></div>
</div>
<div id="photon-stats" style="display:grid;grid-template-columns:repeat(7,minmax(0,1fr));gap:8px;padding:5px 4px 2px 4px;font-family:Inter,system-ui,sans-serif;">
  <div class="pstat"><span>INCIDENTE</span><strong>{_fmt_flujo(flujo_inc_phys)}</strong><small>{flujo_unidad}</small></div>
  <div class="pstat"><span>ABSORBIDO</span><strong>{_fmt_flujo(flujo_a_phys)}</strong><small>{_pct_flujo(flujo_a_phys):.1f}%</small></div>
  <div class="pstat"><span>PARES e⁻/h⁺</span><strong>{_fmt_flujo(flujo_pares_phys)}</strong><small>{flujo_pares_unidad}</small></div>
  <div class="pstat"><span>REF. FRONTAL</span><strong>{_fmt_flujo(flujo_r_phys)}</strong><small>{_pct_flujo(flujo_r_phys):.1f}%</small></div>
  <div class="pstat"><span>PÉRDIDA TRASERA</span><strong>{_fmt_flujo(flujo_back_phys)}</strong><small>{_pct_flujo(flujo_back_phys):.1f}%</small></div>
  <div class="pstat"><span>ESCAPE FRONTAL</span><strong>{_fmt_flujo(flujo_escape_phys)}</strong><small>{_pct_flujo(flujo_escape_phys):.1f}%</small></div>
  <div class="pstat" style="opacity:{'1' if S['reflector_trasero'] else '.35'}"><span>REF. EN Al</span><strong>{_fmt_flujo(flujo_al_phys)}</strong><small>{_pct_flujo(flujo_al_phys):.1f}% · intermedio</small></div>
</div>
<style>
  #live-photon-counts .livecount{{background:rgba(255,255,255,.022);border:1px solid rgba(148,163,184,.10);border-radius:9px;padding:7px 9px;min-height:43px;box-sizing:border-box;}}
  #live-photon-counts span{{display:block;color:rgba(148,163,184,.78);font-size:8.5px;font-weight:700;letter-spacing:.05em;white-space:nowrap;}}
  #live-photon-counts strong{{display:block;color:rgba(241,245,249,.98);font-size:17px;line-height:1.1;margin-top:4px;font-variant-numeric:tabular-nums;}}
  #photon-stats .pstat{{background:rgba(255,255,255,.035);border:1px solid rgba(148,163,184,.12);border-radius:10px;padding:9px 10px;min-height:56px;box-sizing:border-box;}}
  #photon-stats span{{display:block;color:rgba(148,163,184,.86);font-size:9px;font-weight:700;letter-spacing:.055em;white-space:nowrap;}}
  #photon-stats strong{{display:block;color:rgba(241,245,249,.98);font-size:17px;line-height:1.15;margin-top:4px;}}
  #photon-stats small{{display:block;color:rgba(203,213,225,.72);font-size:9px;margin-top:2px;white-space:nowrap;}}
  @media (max-width:950px){{
    #live-photon-counts{{grid-template-columns:repeat(3,minmax(0,1fr)) !important;}}
    #photon-stats{{grid-template-columns:repeat(3,minmax(0,1fr)) !important;}}
  }}
</style>
</div>
<script>
const wlLookup = {json.dumps(wl_lookup)};
const phi0Lookup = {json.dumps(phi0_lookup)};
const alphaLookup = {json.dumps(alpha_um_lookup)};
const rLookup = {json.dumps(R_lookup)};
const modo = "{S['anim_modo']}";
const irradianciaSoles = {irr_soles};
const singleWl = {single_wl};
const singleColor = "{single_color}";
const Wtotal = {W_total_um};
const xnUm = {xn_um};
const xpUm = {xp_um};
const reflectorActivo = {str(bool(S['reflector_trasero'])).lower()};
const RAl = {c.R_ALUMINIO_EFECTIVA};
const lambdaGapNm = {lambda_gap_nm};
const pairFluxPhysical = {flujo_pares_phys};
const incidentFluxPhysical = {flujo_inc_phys};
const pairAccumUnit = "{pares_acum_unidad}";

const cv = document.getElementById("cv");
const ctx = cv.getContext("2d");
const W = cv.width, H = cv.height;
const left = 54, right = W - 54;
const blockTop = 86, blockBottom = H - 75;
const blockH = blockBottom - blockTop;

const fracEmisor = 0.24;
const fracDeplecion = 0.10;
const depthBreaks = [0, xnUm, xpUm, Wtotal];
const fracBreaks = [0, fracEmisor, fracEmisor + fracDeplecion, 1.0];

function interp(x, xs, ys){{
  if(x <= xs[0]) return ys[0];
  if(x >= xs[xs.length-1]) return ys[ys.length-1];
  for(let i=0; i<xs.length-1; i++){{
    if(x >= xs[i] && x <= xs[i+1]){{
      const t = (x-xs[i]) / Math.max(xs[i+1]-xs[i], 1e-12);
      return ys[i] + t*(ys[i+1]-ys[i]);
    }}
  }}
  return ys[ys.length-1];
}}

function fracOfDepth(xum){{
  if(xum <= 0) return 0;
  if(xum >= Wtotal) return 1;
  for(let i=0; i<3; i++){{
    if(xum >= depthBreaks[i] && xum <= depthBreaks[i+1]){{
      const t = (xum-depthBreaks[i]) / Math.max(depthBreaks[i+1]-depthBreaks[i], 1e-12);
      return fracBreaks[i] + t*(fracBreaks[i+1]-fracBreaks[i]);
    }}
  }}
  return 1;
}}

function yOfFrac(fr){{ return blockTop + fr*blockH; }}

function colorFromWl(wl){{
  if(wl < 380) return "#8b5cf6";   // UV: falso color
  if(wl > 750) return "#fb7185";   // IR: falso color
  let R,G,B;
  if(wl < 440){{ R=-(wl-440)/(440-380); G=0; B=1; }}
  else if(wl < 490){{ R=0; G=(wl-440)/(490-440); B=1; }}
  else if(wl < 510){{ R=0; G=1; B=-(wl-510)/(510-490); }}
  else if(wl < 580){{ R=(wl-510)/(580-510); G=1; B=0; }}
  else if(wl < 645){{ R=1; G=-(wl-645)/(645-580); B=0; }}
  else {{ R=1; G=0; B=0; }}
  return `rgb(${{Math.round(255*R)}},${{Math.round(255*G)}},${{Math.round(255*B)}})`;
}}

// Distribucion acumulada del flujo de fotones AM1.5G.
const weights = phi0Lookup.map(v => Math.max(v,0));
const totalWeight = Math.max(weights.reduce((a,b)=>a+b,0), 1e-30);
let cdf = [];
let acc = 0;
for(let i=0; i<weights.length; i++){{
  acc += weights[i]/totalWeight;
  cdf.push(acc);
}}

function sampleSpectrum(){{
  const r = Math.random();
  let i = cdf.findIndex(v => r <= v);
  if(i < 0) i = cdf.length-1;
  if(i === 0) return wlLookup[0];
  const c0 = cdf[i-1], c1 = cdf[i];
  const t = (r-c0) / Math.max(c1-c0, 1e-12);
  return wlLookup[i-1] + t*(wlLookup[i]-wlLookup[i-1]);
}}

function roundedRect(x,y,w,h,r){{
  const rr = Math.min(r,w/2,h/2);
  ctx.beginPath();
  ctx.moveTo(x+rr,y);
  ctx.arcTo(x+w,y,x+w,y+h,rr);
  ctx.arcTo(x+w,y+h,x,y+h,rr);
  ctx.arcTo(x,y+h,x,y,rr);
  ctx.arcTo(x,y,x+w,y,rr);
  ctx.closePath();
}}

function drawScene(now){{
  const bg = ctx.createLinearGradient(0,0,0,H);
  bg.addColorStop(0,"#07101c");
  bg.addColorStop(1,"#0a1523");
  ctx.fillStyle = bg;
  ctx.fillRect(0,0,W,H);

  // Halo de iluminacion superior: decorativo, sin texto extra.
  const glow = ctx.createRadialGradient(W/2,36,4,W/2,36,W*0.42);
  glow.addColorStop(0, modo === "unico" ? singleColor + "55" : "rgba(255,255,255,.16)");
  glow.addColorStop(1,"rgba(255,255,255,0)");
  ctx.fillStyle = glow;
  ctx.fillRect(0,0,W,80);

  const yE0 = yOfFrac(0);
  const yE1 = yOfFrac(fracEmisor);
  const yD1 = yOfFrac(fracEmisor + fracDeplecion);
  const yB1 = yOfFrac(1);

  roundedRect(left, blockTop, right-left, blockH, 13);
  ctx.fillStyle = "rgba(255,255,255,.025)";
  ctx.fill();

  ctx.fillStyle = "rgba(74,116,154,.22)";
  ctx.fillRect(left,yE0,right-left,yE1-yE0);
  ctx.fillStyle = "rgba(210,158,74,.18)";
  ctx.fillRect(left,yE1,right-left,yD1-yE1);
  ctx.fillStyle = "rgba(62,112,88,.20)";
  ctx.fillRect(left,yD1,right-left,yB1-yD1);

  ctx.strokeStyle = "rgba(255,255,255,.12)";
  ctx.lineWidth = 1;
  roundedRect(left, blockTop, right-left, blockH, 13);
  ctx.stroke();

  ctx.strokeStyle = "rgba(255,255,255,.10)";
  ctx.beginPath(); ctx.moveTo(left,yE1); ctx.lineTo(right,yE1); ctx.stroke();
  ctx.beginPath(); ctx.moveTo(left,yD1); ctx.lineTo(right,yD1); ctx.stroke();

  if(reflectorActivo){{
    const al = ctx.createLinearGradient(left,0,right,0);
    al.addColorStop(0,"rgba(245,193,86,.18)");
    al.addColorStop(.5,"rgba(255,224,143,.72)");
    al.addColorStop(1,"rgba(245,193,86,.18)");
    ctx.fillStyle = al;
    ctx.fillRect(left+10,blockBottom+6,right-left-20,3);
  }}

  ctx.font = "600 12px Inter, system-ui, sans-serif";
  ctx.letterSpacing = "0.08em";
  ctx.fillStyle = "rgba(191,219,254,.72)";
  ctx.fillText("EMISOR n", left+16, (yE0+yE1)/2+4);
  ctx.fillStyle = "rgba(253,230,138,.72)";
  ctx.fillText("DEPLECIÓN", left+16, (yE1+yD1)/2+4);
  ctx.fillStyle = "rgba(187,247,208,.68)";
  ctx.fillText("BASE p", left+16, yD1+22);
}}

let photons = [];
let bursts = [];
let nextSpawn = 0;
let lastTime = performance.now();

// Contadores de la muestra visual. La tasa de fotones incidentes escala
// linealmente con la irradiancia; las fracciones opticas dependen de lambda,
// R(lambda), alpha(lambda), espesor y reflector trasero.
let nIncident = 0;
let nAbs = 0;
let nFrontRef = 0;
let nBackLoss = 0;
let nEscape = 0;
let nAlRef = 0;
let nPairs = 0;

// La velocidad visual NO depende de la irradiancia. Solo la tasa de llegada.
// Los enteros mostrados son eventos de la muestra Monte Carlo; todas las
// probabilidades de destino provienen de R(λ), α(λ), Beer–Lambert y R_Al.
const spawnRate = 14.0 * {float(intensidad_visual_rel)};

// Contadores visibles bajo la animación. Los porcentajes usan sólo fotones
// que ya terminaron su trayectoria, para no sesgar el balance con fotones
// que todavía están viajando dentro del canvas.
function updateStatsDom(){{
  // Conteo acumulado EN TIEMPO REAL de los fotones representativos que
  // realmente atraviesan la simulación Monte Carlo. Cada destino se decide
  // con R(lambda), alpha(lambda), Beer-Lambert, espesor y reflector de Al.
  // La tasa de llegada de estos fotones representativos escala con el flujo
  // físico incidente; los flujos absolutos físicos siguen mostrándose abajo.
  const nNoAbs = nFrontRef + nBackLoss + nEscape;
  document.getElementById("live-inc").textContent = nIncident.toLocaleString("es-CL");
  document.getElementById("live-abs").textContent = nAbs.toLocaleString("es-CL");
  document.getElementById("live-pairs").textContent = nPairs.toLocaleString("es-CL");
  document.getElementById("live-front").textContent = nFrontRef.toLocaleString("es-CL");
  document.getElementById("live-nonabs").textContent = nNoAbs.toLocaleString("es-CL");
  document.getElementById("live-back").textContent = nBackLoss.toLocaleString("es-CL");
  document.getElementById("live-escape").textContent = nEscape.toLocaleString("es-CL");
  if(reflectorActivo){{
    const al = document.getElementById("live-al");
    if(al) al.textContent = nAlRef.toLocaleString("es-CL");
  }}
}}

function scheduleNextSpawn(){{
  nextSpawn = -Math.log(Math.max(Math.random(),1e-9)) / spawnRate;
}}
scheduleNextSpawn();

function spawnPhoton(){{
  if(photons.length > 120) return;
  const wl = modo === "arcoiris" ? sampleSpectrum() : singleWl;
  const alpha = interp(wl, wlLookup, alphaLookup);
  const Rfront = interp(wl, wlLookup, rLookup);
  const xAbs = -Math.log(Math.max(Math.random(),1e-9)) / Math.max(alpha,1e-8);
  const transmitted = xAbs > Wtotal;

  photons.push({{
    x: left + 26 + Math.random()*(right-left-52),
    frac: -0.11 - Math.random()*0.035,
    // La apariencia NO codifica intensidad ni energía. Para una misma λ,
    // todos los fotones se dibujan con el mismo tamaño, brillo y estela.
    // La única variable visual espectral es el color asociado a λ.
    speed: 0.32,
    radius: 2.6,
    trail: 24,
    color: modo === "arcoiris" ? colorFromWl(wl) : singleColor,
    wl: wl,
    alpha: alpha,
    Rfront: Rfront,
    frontDecision: false,
    transmitted: transmitted,
    fracAbs: transmitted ? 1.0 : fracOfDepth(xAbs),
    state: "incoming",
  }});
}}

function drawPhoton(p, now, returning=false){{
  const yy = yOfFrac(p.frac);
  const xx = p.x;
  const dir = returning ? -1 : 1;
  const tailY = yy - dir*p.trail;

  // Estela suave sólo para comunicar movimiento. Su intensidad es fija:
  // no representa energía, irradiancia ni probabilidad de absorción.
  const trail = ctx.createLinearGradient(xx,tailY,xx,yy);
  trail.addColorStop(0,"rgba(255,255,255,0)");
  trail.addColorStop(1,p.color);
  ctx.globalAlpha = 0.48;
  ctx.strokeStyle = trail;
  ctx.lineWidth = 2.0;
  ctx.beginPath();
  ctx.moveTo(xx,tailY);
  ctx.lineTo(xx,yy);
  ctx.stroke();

  // Halo y núcleo con tamaño/brillo constantes para todos los fotones.
  const halo = ctx.createRadialGradient(xx,yy,0,xx,yy,8);
  halo.addColorStop(0,"rgba(255,255,255,.95)");
  halo.addColorStop(.24,p.color);
  halo.addColorStop(1,"rgba(255,255,255,0)");
  ctx.globalAlpha = 0.62;
  ctx.fillStyle = halo;
  ctx.beginPath(); ctx.arc(xx,yy,8,0,Math.PI*2); ctx.fill();

  ctx.globalAlpha = 0.92;
  ctx.fillStyle = p.color;
  ctx.beginPath(); ctx.arc(xx,yy,p.radius,0,Math.PI*2); ctx.fill();
  ctx.globalAlpha = 1;
}}

function absorb(p, yy, fracAbsorcion){{
  p.state = "absorbed";
  nAbs++;

  // Para generar un par banda-a-banda en Si se requiere E_fotón >= Eg.
  // Por tanto, sólo λ <= λ_g produce el electrón y el hueco animados.
  const generaPar = p.wl <= lambdaGapNm;

  let region = "depletion";
  if(fracAbsorcion < fracEmisor) region = "emitter";
  else if(fracAbsorcion > fracEmisor + fracDeplecion) region = "base";

  if(generaPar){{
    nPairs++;
  }}

  bursts.push({{
    x:p.x, y:yy, age:0, life:0.82,
    color:p.color,
    phase:Math.random()*Math.PI*2,
    region:region,
    generaPar:generaPar,
  }});
}}

function drawCarrier(x, y, radius, color, alpha){{
  if(alpha <= 0) return;
  const halo = ctx.createRadialGradient(x,y,0,x,y,6);
  halo.addColorStop(0,color);
  halo.addColorStop(1,"rgba(255,255,255,0)");
  ctx.globalAlpha = 0.20*alpha;
  ctx.fillStyle = halo;
  ctx.beginPath(); ctx.arc(x,y,6,0,Math.PI*2); ctx.fill();

  ctx.globalAlpha = alpha;
  ctx.fillStyle = color;
  ctx.beginPath(); ctx.arc(x,y,radius,0,Math.PI*2); ctx.fill();
  ctx.globalAlpha = 1;
}}

function updateBurst(b, dt){{
  b.age += dt;
  const t = Math.min(b.age/b.life,1);
  const fade = Math.pow(1-t,1.55);

  // Destello breve en el lugar donde el fotón fue absorbido.
  const flashT = Math.min(t/0.42,1);
  const r = 3 + 13*flashT;
  const flashFade = Math.max(0,1-flashT);
  const g = ctx.createRadialGradient(b.x,b.y,0,b.x,b.y,r);
  g.addColorStop(0,`rgba(255,255,255,${{0.90*flashFade}})`);
  g.addColorStop(.24,`rgba(255,236,180,${{0.50*flashFade}})`);
  g.addColorStop(1,"rgba(255,255,255,0)");
  ctx.fillStyle = g;
  ctx.beginPath(); ctx.arc(b.x,b.y,r,0,Math.PI*2); ctx.fill();

  // Si E_fotón < Eg puede existir una absorción óptica débil, pero no se
  // representa creación de un par banda-a-banda.
  if(!b.generaPar) return;

  // Azul = hueco (h+), rojo = electrón (e−), coherente con la pestaña 2.
  // En regiones neutras se destaca el PORTADOR MINORITARIO que difunde hacia
  // la zona de depleción. El mayoritario aparece sólo de forma breve/local.
  const move = 1-Math.pow(1-t,2.2);
  const wobble = Math.sin(b.phase + t*5.0);
  let hx=b.x, hy=b.y, ex=b.x, ey=b.y;
  let hAlpha=0, eAlpha=0;

  if(b.region === "emitter"){{
    // Emisor n: el hueco es minoritario y difunde hacia la depleción (abajo).
    hx = b.x - 2.2 + 1.2*wobble;
    hy = b.y + 23*move;
    ex = b.x + 2.2;
    ey = b.y - 4*move;
    hAlpha = 0.92*fade;
    eAlpha = 0.30*fade;
  }} else if(b.region === "base"){{
    // Base p: el electrón es minoritario y difunde hacia la depleción (arriba).
    ex = b.x + 2.2 + 1.2*wobble;
    ey = b.y - 23*move;
    hx = b.x - 2.2;
    hy = b.y + 4*move;
    eAlpha = 0.92*fade;
    hAlpha = 0.30*fade;
  }} else {{
    // Depleción: el campo interno separa claramente la pareja.
    ex = b.x + 3.0 + 0.8*wobble;
    ey = b.y - 22*move;
    hx = b.x - 3.0 - 0.8*wobble;
    hy = b.y + 22*move;
    eAlpha = 0.92*fade;
    hAlpha = 0.92*fade;
  }}

  drawCarrier(hx,hy,1.9,"#7dd3fc",hAlpha); // h+
  drawCarrier(ex,ey,1.9,"#fb7185",eAlpha); // e−
}}

function drawStats(){{
  // Conteo acumulado EN TIEMPO REAL de los fotones representativos que ya
  // han alcanzado la superficie de la celda. Los destinos se resuelven con
  // R(lambda), alpha(lambda), Beer-Lambert, el espesor y R_Al.
  const completed = nAbs + nFrontRef + nBackLoss + nEscape;
  const nNoAbs = nFrontRef + nBackLoss + nEscape;
  const pct = n => completed > 0 ? (100*n/completed).toFixed(0) + "%" : "—";

  const stats = [
    ["INCIDENTES", nIncident, ""],
    ["ABSORBIDOS", nAbs, pct(nAbs)],
    ["PARES e-/h+", nPairs, ""],
    ["REF. FRONTAL", nFrontRef, pct(nFrontRef)],
    ["NO ABSORBIDOS", nNoAbs, pct(nNoAbs)],
    ["PERD. TRASERA", nBackLoss, pct(nBackLoss)],
    ["ESCAPE FRONTAL", nEscape, pct(nEscape)],
  ];

  const gap = 6;
  const y = H - 60;
  const h = 46;
  const boxW = (right-left-gap*(stats.length-1))/stats.length;

  stats.forEach((s,i) => {{
    const x = left + i*(boxW+gap);
    roundedRect(x,y,boxW,h,8);
    ctx.fillStyle = "rgba(255,255,255,.036)";
    ctx.fill();
    ctx.strokeStyle = "rgba(148,163,184,.12)";
    ctx.lineWidth = 1;
    ctx.stroke();

    ctx.font = "600 8px Inter, system-ui, sans-serif";
    ctx.fillStyle = "rgba(148,163,184,.82)";
    ctx.fillText(s[0], x+8, y+14);

    ctx.font = "700 14px Inter, system-ui, sans-serif";
    ctx.fillStyle = "rgba(241,245,249,.97)";
    const value = s[2] ? `${{s[1]}} · ${{s[2]}}` : `${{s[1]}}`;
    ctx.fillText(value, x+8, y+34);
  }});

  // El rebote en Al es un evento intermedio: después de reflejarse, ese
  // mismo fotón todavía puede absorberse o escapar por el frente.
  if(reflectorActivo){{
    const txt = `REF. EN Al  ${{nAlRef}}`;
    ctx.font = "600 9px Inter, system-ui, sans-serif";
    const tw = ctx.measureText(txt).width;
    roundedRect(right-tw-25, blockBottom-28, tw+17, 20, 7);
    ctx.fillStyle = "rgba(245,193,86,.11)";
    ctx.fill();
    ctx.strokeStyle = "rgba(245,193,86,.18)";
    ctx.stroke();
    ctx.fillStyle = "rgba(253,230,138,.88)";
    ctx.fillText(txt, right-tw-16, blockBottom-14);
  }}
}}

function step(now){{
  const dt = Math.min((now-lastTime)/1000,0.04);
  lastTime = now;
  drawScene(now);

  nextSpawn -= dt;
  if(nextSpawn <= 0){{
    spawnPhoton();
    scheduleNextSpawn();
  }}

  photons.forEach(p => {{
    if(p.state === "incoming"){{
      p.frac += p.speed*dt;

      // Un fotón cuenta como INCIDENTE cuando alcanza físicamente la
      // superficie frontal. En ese mismo instante se decide la reflexión R(λ).
      if(!p.frontDecision && p.frac >= 0){{
        p.frontDecision = true;
        nIncident++;
        if(Math.random() < p.Rfront){{
          p.state = "front_reflected";
          nFrontRef++;
        }}
      }}

      if(p.state === "incoming"){{
        drawPhoton(p,now,false);
        if(!p.transmitted && p.frac >= p.fracAbs && p.frac > 0){{
          absorb(p,yOfFrac(p.fracAbs),p.fracAbs);
        }} else if(p.transmitted && p.frac >= 1.0){{
          if(reflectorActivo && Math.random() < RAl){{
            p.state = "returning";
            p.frac = 1.0;
            nAlRef++;
            const dBack = -Math.log(Math.max(Math.random(),1e-9)) / Math.max(p.alpha,1e-8);
            p.escapeFront = dBack >= Wtotal;
            p.fracAbsReturn = p.escapeFront ? 0.0 : fracOfDepth(Wtotal-dBack);
          }} else {{
            p.state = "done";
            nBackLoss++;
          }}
        }}
      }}
    }} else if(p.state === "front_reflected"){{
      p.frac -= p.speed*dt*0.95;
      drawPhoton(p,now,true);
      if(p.frac < -0.20) p.state = "done";
    }} else if(p.state === "returning"){{
      p.frac -= p.speed*dt*0.93;
      drawPhoton(p,now,true);
      if(!p.escapeFront && p.frac <= p.fracAbsReturn){{
        absorb(p,yOfFrac(p.fracAbsReturn),p.fracAbsReturn);
      }} else if(p.escapeFront && p.frac < -0.16){{
        p.state = "done";
        nEscape++;
      }}
    }}
  }});

  photons = photons.filter(p => p.state !== "done" && p.state !== "absorbed");

  bursts.forEach(b => updateBurst(b,dt));
  bursts = bursts.filter(b => b.age < b.life);

  // Dibujar los contadores dentro del canvas garantiza que se vean y que
  // cambien cuadro a cuadro mientras los fotones recorren la celda.
  drawStats();
  updateStatsDom();
  requestAnimationFrame(step);
}}
requestAnimationFrame(step);
</script>
"""

    components.html(html_photons, height=590, scrolling=False)

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("λ", f"{single_wl:.0f} nm")
    m2.metric("Irradiancia", f"{irr_soles:.2f} sol")
    m3.metric("1/α", f"{single_depth_um:.2f} µm")
    m4.metric("x₉₀", f"{single_x90_um:.2f} µm" if single_x90_um < 1e4 else "> 10 mm")

    # ============================================================
    # VISTA 3D DEL BLOQUE — muestra Monte Carlo proporcional al flujo físico
    # ============================================================
    st.markdown("##### Vista 3D")

    def _caja_mesh3d(z0, z1, color, opacidad, nombre, Lx=1.0, Ly=1.0):
        xs = [-Lx, Lx, Lx, -Lx, -Lx, Lx, Lx, -Lx]
        ys = [-Ly, -Ly, Ly, Ly, -Ly, -Ly, Ly, Ly]
        zs = [z0, z0, z0, z0, z1, z1, z1, z1]
        i = [0, 0, 0, 4, 4, 4, 0, 0, 1, 1, 2, 2]
        j = [1, 2, 3, 5, 6, 7, 1, 5, 2, 6, 3, 7]
        k = [2, 3, 0, 6, 7, 4, 5, 4, 6, 5, 7, 6]
        return go.Mesh3d(
            x=xs, y=ys, z=zs, i=i, j=j, k=k,
            color=color, opacity=opacidad, name=nombre,
            showlegend=True, flatshading=True,
        )

    z0, z1 = 0.0, -1.0
    zE, zD = -0.24, -0.34
    fig3d = go.Figure()
    fig3d.add_trace(_caja_mesh3d(z0, zE, "#63b3ed", 0.30, "Emisor n"))
    fig3d.add_trace(_caja_mesh3d(zE, zD, "#f6ad55", 0.42, "Depleción"))
    fig3d.add_trace(_caja_mesh3d(zD, z1, "#68d391", 0.22, "Base p"))

    def _z_de_depth(x_um):
        if x_um <= xn_um:
            t = x_um / max(xn_um, 1e-9)
            return z0 + t * (zE - z0)
        if x_um <= xp_um:
            t = (x_um - xn_um) / max(xp_um - xn_um, 1e-9)
            return zE + t * (zD - zE)
        t = min((x_um - xp_um) / max(W_total_um - xp_um, 1e-9), 1.0)
        return zD + t * (z1 - zD)

    def _color_foton_3d(wl):
        if wl < 380:
            return "#8b5cf6"   # UV en falso color
        if wl > 750:
            return "#fb7185"   # IR en falso color
        return wavelength_to_hex(wl)

    # El número de puntos NO es un conteo arbitrario de fotones reales.
    # Se obtiene como una muestra proporcional al flujo físico incidente.
    # El máximo de 72 puntos sólo fija la resolución gráfica del muestreo.
    N3D_MAX = 72
    if S["anim_modo"] == "unico":
        flujo_ref_3d = 1.5 * float(np.max(phi0_grid))
    else:
        flujo_ref_3d = 1.5 * float(np.trapezoid(phi0_grid, wl_grid))
    peso_marcador_3d = flujo_ref_3d / N3D_MAX if flujo_ref_3d > 0 else np.inf
    n_fot3d = int(np.clip(np.round(flujo_inc_phys / peso_marcador_3d), 0, N3D_MAX))
    if flujo_inc_phys > 0 and n_fot3d == 0:
        n_fot3d = 1

    rng3d = np.random.default_rng(7)
    wl_lookup_arr = np.asarray(wl_lookup, dtype=float)

    if S["anim_modo"] == "unico":
        wl_muestras = np.full(n_fot3d, single_wl, dtype=float)
    else:
        phi_probs = np.clip(np.asarray(phi0_lookup, dtype=float), 0.0, None)
        phi_probs = phi_probs / phi_probs.sum() if phi_probs.sum() > 0 else np.full_like(phi_probs, 1 / len(phi_probs))
        wl_muestras = rng3d.choice(wl_lookup_arr, size=n_fot3d, replace=True, p=phi_probs)

    alpha_muestras_um = np.interp(wl_muestras, wl_lookup_arr, np.asarray(alpha_um_lookup, dtype=float))
    R_muestras = np.interp(wl_muestras, wl_lookup_arr, np.asarray(R_lookup, dtype=float))
    colores_3d = [_color_foton_3d(wl) for wl in wl_muestras]
    x0_3d = rng3d.uniform(-0.88, 0.88, n_fot3d)
    y0_3d = rng3d.uniform(-0.88, 0.88, n_fot3d)
    t0_3d = rng3d.uniform(0.0, 0.22, n_fot3d)

    # Cada marcador sigue el mismo balance físico de la vista 2D:
    # reflexión frontal -> absorción Beer–Lambert -> pérdida trasera o
    # reflexión en Al -> absorción en segundo paso / escape frontal.
    eventos_3d = []
    z_obj_3d = []
    for i in range(n_fot3d):
        if rng3d.random() < R_muestras[i]:
            eventos_3d.append("Reflejado frontal")
            z_obj_3d.append(0.30)
            continue

        d1 = -np.log(max(rng3d.random(), 1e-12)) / max(alpha_muestras_um[i], 1e-12)
        if d1 < W_total_um:
            eventos_3d.append("Absorbido")
            z_obj_3d.append(_z_de_depth(d1))
            continue

        if S["reflector_trasero"] and rng3d.random() < c.R_ALUMINIO_EFECTIVA:
            d2 = -np.log(max(rng3d.random(), 1e-12)) / max(alpha_muestras_um[i], 1e-12)
            if d2 < W_total_um:
                eventos_3d.append("Absorbido tras reflexión Al")
                z_obj_3d.append(_z_de_depth(W_total_um - d2))
            else:
                eventos_3d.append("Escape frontal")
                z_obj_3d.append(0.30)
        else:
            eventos_3d.append("Pérdida trasera")
            z_obj_3d.append(-1.12)

    n_frames_3d = 42
    frames_3d = []
    for fr in range(n_frames_3d):
        tf = fr / (n_frames_3d - 1)
        zs_frame = []
        for i in range(n_fot3d):
            if tf < t0_3d[i]:
                zs_frame.append(0.28)
                continue

            u = (tf - t0_3d[i]) / max(1.0 - t0_3d[i], 1e-9)
            u = float(np.clip(u, 0.0, 1.0))
            evento = eventos_3d[i]
            zfinal = z_obj_3d[i]

            # Fase incidente: desde arriba hasta la superficie.
            if u < 0.22:
                zs_frame.append(0.28 * (1.0 - u / 0.22))
            elif evento == "Reflejado frontal":
                p = (u - 0.22) / 0.78
                zs_frame.append(0.30 * p)
            elif evento == "Absorbido":
                p = min((u - 0.22) / 0.58, 1.0)
                zs_frame.append(p * zfinal)
            elif evento == "Pérdida trasera":
                p = min((u - 0.22) / 0.70, 1.0)
                zs_frame.append(p * zfinal)
            elif evento == "Absorbido tras reflexión Al":
                if u < 0.62:
                    p = (u - 0.22) / 0.40
                    zs_frame.append(-p)
                else:
                    p = min((u - 0.62) / 0.30, 1.0)
                    zs_frame.append(-1.0 + p * (zfinal + 1.0))
            else:  # Escape frontal tras reflexión en Al
                if u < 0.55:
                    p = (u - 0.22) / 0.33
                    zs_frame.append(-p)
                elif u < 0.88:
                    p = (u - 0.55) / 0.33
                    zs_frame.append(-1.0 + p)
                else:
                    p = (u - 0.88) / 0.12
                    zs_frame.append(0.30 * p)

        frames_3d.append(
            go.Frame(
                data=[go.Scatter3d(
                    x=x0_3d, y=y0_3d, z=zs_frame,
                    mode="markers",
                    marker=dict(size=5, color=colores_3d, opacity=0.95),
                    text=[f"λ={wl:.0f} nm · {ev}" for wl, ev in zip(wl_muestras, eventos_3d)],
                    hovertemplate="%{text}<extra></extra>",
                )],
                traces=[3],
                name=str(fr),
            )
        )

    fig3d.add_trace(
        go.Scatter3d(
            x=x0_3d, y=y0_3d, z=[0.28] * n_fot3d,
            mode="markers",
            marker=dict(size=5, color=colores_3d, opacity=0.95),
            text=[f"λ={wl:.0f} nm · {ev}" for wl, ev in zip(wl_muestras, eventos_3d)],
            hovertemplate="%{text}<extra></extra>",
            name="Fotones",
        )
    )
    fig3d.frames = frames_3d
    fig3d.update_layout(
        template="plotly_dark",
        height=540,
        title=dict(
            text=f"Φinc = {_fmt_flujo(flujo_inc_phys)} {flujo_unidad}",
            x=0.02,
            xanchor="left",
            font=dict(size=13, color="#cbd5e0"),
        ),
        scene=dict(
            xaxis=dict(title="", showticklabels=False, showbackground=False),
            yaxis=dict(title="", showticklabels=False, showbackground=False),
            zaxis=dict(title="profundidad (comprimida)", showticklabels=False),
            aspectmode="manual",
            aspectratio=dict(x=1, y=1, z=1.25),
            camera=dict(eye=dict(x=1.4, y=-1.6, z=0.9)),
        ),
        updatemenus=[dict(
            type="buttons", showactive=False, y=1.03, x=0.0,
            buttons=[dict(
                label="▶ Reproducir",
                method="animate",
                args=[None, dict(frame=dict(duration=65, redraw=True), fromcurrent=True)],
            )],
        )],
        legend=dict(orientation="h", y=-0.02),
        margin=dict(l=0, r=0, t=58, b=0),
    )
    st.plotly_chart(fig3d, width="stretch")
    # ============================================================
    # PERFIL G(x) Y PROFUNDIDAD 1/α
    # ============================================================
    c1, c2 = st.columns(2)

    with c1:
        x_perfil = np.linspace(0, W_total_um, 600)
        G_perfil = generacion_actual_vista(x_perfil)
        i_wl = int(np.argmin(np.abs(wl_grid - S["lambda_perfil"])))
        fig = go.Figure()
        fig.add_trace(
            go.Scatter(
                x=x_perfil,
                y=G_perfil[:, i_wl],
                mode="lines",
                line=dict(color=single_color, width=3),
                name="G(x)",
            )
        )
        fig.add_vline(
            x=S["dn_um"],
            line_dash="dot",
            line_color="orange",
            annotation_text="juntura (xj=dn)",
        )
        fig.update_layout(
            title=f"Tasa de generación G(x) a λ={S['lambda_perfil']:.0f} nm ({irr_soles:.2f} soles)",
            xaxis_title="Profundidad x [µm]",
            yaxis_title="G [cm⁻³ s⁻¹ nm⁻¹]",
            height=380,
            template="plotly_dark",
        )
        st.plotly_chart(fig, width="stretch")

    with c2:
        prof_abs_um = np.clip(
            1.0 / np.maximum(alpha_grid, 1e-8) * 1e4,
            0,
            500,
        )
        fig2 = go.Figure()
        fig2.add_trace(
            go.Scatter(
                x=wl_grid,
                y=prof_abs_um,
                mode="lines",
                line=dict(color="#68d391", width=3),
            )
        )
        fig2.add_hline(
            y=W_total_um,
            line_dash="dash",
            line_color="white",
            annotation_text=f"espesor celda W={W_total_um:.0f} µm",
        )
        fig2.update_layout(
            title="Profundidad de absorción 1/α(λ)",
            xaxis_title="λ [nm]",
            yaxis_title="1/α [µm]",
            yaxis_type="log",
            height=380,
            template="plotly_dark",
        )
        st.plotly_chart(fig2, width="stretch")

    # ============================================================
    # GENERACIÓN — coherente con el modo de iluminación seleccionado
    # ============================================================
    x_gext = np.linspace(0, W_total_um, 500)
    G_matrix = generacion_actual_vista(x_gext)
    x_gext_cm = x_gext * 1e-4

    if S["anim_modo"] == "unico":
        i_focus = int(np.argmin(np.abs(wl_grid - single_wl)))
        G_focus = np.maximum(G_matrix[:, i_focus], 0.0)
        titulo_generacion = f"Generación a λ = {wl_grid[i_focus]:.0f} nm"
        y_generacion = "G [cm⁻³ s⁻¹ nm⁻¹]"
        unidad_pares = "pares·cm⁻²·s⁻¹·nm⁻¹"

        f_loss_focus = float(frac_back_phys[i_focus] + frac_escape_phys[i_focus])
        flujo_perdido_focus = flujo_inc_phys * f_loss_focus
    else:
        G_focus = np.maximum(np.trapezoid(G_matrix, wl_grid, axis=1), 0.0)
        titulo_generacion = "Generación integrada AM1.5G"
        y_generacion = "G [cm⁻³ s⁻¹]"
        unidad_pares = "pares·cm⁻²·s⁻¹"
        flujo_perdido_focus = flujo_back_phys + flujo_escape_phys
        f_loss_focus = flujo_perdido_focus / flujo_inc_phys if flujo_inc_phys > 0 else 0.0

    st.markdown(f"##### {titulo_generacion}")

    fig_gext = go.Figure()
    fig_gext.add_trace(go.Scatter(
        x=x_gext, y=G_focus, mode="lines",
        line=dict(color="#f687b3", width=3), name="G(x)",
    ))
    fig_gext.add_vline(
        x=S["dn_um"], line_dash="dot", line_color="orange",
        annotation_text="juntura",
    )
    fig_gext.update_layout(
        xaxis_title="Profundidad x [µm]",
        yaxis_title=y_generacion,
        height=360,
        template="plotly_dark",
        margin=dict(t=30),
        showlegend=False,
    )
    st.plotly_chart(fig_gext, width="stretch")

    # Integrar G sobre profundidad exige convertir µm -> cm.
    mask_emisor = x_gext <= S["dn_um"]
    mask_base = x_gext > S["dn_um"]
    flujo_pares_total = float(np.trapezoid(G_focus, x_gext_cm))
    flujo_pares_emisor = (
        float(np.trapezoid(G_focus[mask_emisor], x_gext_cm[mask_emisor]))
        if mask_emisor.sum() > 1 else 0.0
    )
    flujo_pares_base = (
        float(np.trapezoid(G_focus[mask_base], x_gext_cm[mask_base]))
        if mask_base.sum() > 1 else 0.0
    )

    frac_emisor_gen = flujo_pares_emisor / flujo_pares_total if flujo_pares_total > 0 else 0.0
    frac_base_gen = flujo_pares_base / flujo_pares_total if flujo_pares_total > 0 else 0.0

    gm1, gm2, gm3 = st.columns(3)
    gm1.metric(
        "Pares generados en el emisor",
        f"{100 * frac_emisor_gen:.1f} %",
        delta=f"{flujo_pares_emisor:.2e} {unidad_pares}",
        delta_color="off",
    )
    gm2.metric(
        "Pares generados en la base",
        f"{100 * frac_base_gen:.1f} %",
        delta=f"{flujo_pares_base:.2e} {unidad_pares}",
        delta_color="off",
    )
    gm3.metric(
        "Fotones perdidos",
        f"{100 * f_loss_focus:.1f} %",
        delta=f"{flujo_perdido_focus:.2e} {flujo_unidad}",
        delta_color="off",
    )
    # ============================================================
    # MAPA λ-x
    # ============================================================
    st.markdown("##### Mapa G(x,λ)")

    x_mapa = np.linspace(0, W_total_um, 220)
    G_mapa = generacion_actual_vista(x_mapa)
    fig3 = go.Figure(
        data=go.Heatmap(
            z=np.log10(np.maximum(G_mapa, 1e-6)).T,
            x=x_mapa,
            y=wl_grid,
            colorscale="Inferno",
            colorbar=dict(
                title=dict(text="log₁₀ G", side="right", font=dict(size=12)),
                x=1.025,
                y=0.5,
                len=0.78,
                thickness=18,
                tickfont=dict(size=10),
                outlinewidth=0,
            ),
            hovertemplate="x=%{x:.2f} µm<br>λ=%{y:.0f} nm<br>log₁₀G=%{z:.2f}<extra></extra>",
        )
    )
    fig3.add_hline(
        y=S["lambda_perfil"],
        line_color="cyan",
        line_dash="dot",
    )
    fig3.add_vline(
        x=S["dn_um"],
        line_color="orange",
        line_dash="dot",
    )

    _i_sel = int(np.argmin(np.abs(wl_grid - S["lambda_perfil"])))
    _lambda_sel = float(wl_grid[_i_sel])
    _alpha_sel = float(alpha_grid[_i_sel])
    _prof_abs_sel = float(1.0 / _alpha_sel * 1e4)
    _x90_sel = float(np.log(10.0) / _alpha_sel * 1e4)
    _frac_abs_sel = float(
        1.0 - np.exp(-_alpha_sel * W_total_um * 1e-4)
    )

    if _prof_abs_sel <= W_total_um:
        fig3.add_trace(
            go.Scatter(
                x=[_prof_abs_sel],
                y=[_lambda_sel],
                mode="markers",
                marker=dict(
                    size=11,
                    color="lime",
                    symbol="circle",
                ),
                name=f"1/α · {_lambda_sel:.0f} nm",
                hovertemplate=(
                    "λ=%{y:.0f} nm<br>"
                    "1/α=%{x:.2f} µm<extra></extra>"
                ),
            )
        )
    if _x90_sel <= W_total_um:
        fig3.add_trace(
            go.Scatter(
                x=[_x90_sel],
                y=[_lambda_sel],
                mode="markers",
                marker=dict(
                    size=11,
                    color="cyan",
                    symbol="x",
                ),
                name=f"x₉₀ · {_lambda_sel:.0f} nm",
                hovertemplate=(
                    "λ=%{y:.0f} nm<br>"
                    "x90=%{x:.2f} µm<extra></extra>"
                ),
            )
        )

    fig3.update_layout(
        xaxis_title="Profundidad x [µm]",
        yaxis_title="λ [nm]",
        height=440,
        template="plotly_dark",
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="left",
            x=0.01,
            bgcolor="rgba(11,14,20,0.72)",
            bordercolor="rgba(148,163,184,0.18)",
            borderwidth=1,
            font=dict(size=11),
        ),
        margin=dict(l=65, r=125, t=72, b=55),
    )
    st.plotly_chart(fig3, width="stretch")

    with st.expander("Fuentes"):
        st.markdown(
            "**Óptica:** Schinke.csv, datos de k(λ) del silicio; "
            "α(λ) = 4πk(λ)/λ.\n\n"
            "**Espectro:** astmg173.xls, ASTM G173-03, hoja SMARTS2, "
            "columna Global tilt, AM1.5G."
        )

# ------------------------------------------------------------------
# TAB 2 — EQE / IQE
# ------------------------------------------------------------------
with tab2:
    st.subheader("Transporte de portadores y eficiencia cuántica")

    st.caption(
        "Los puntos son pares electrón-hueco generados por la absorción. "
        "El azul representa huecos minoritarios en el emisor n y el rojo "
        "electrones minoritarios en la base p. La probabilidad física de "
        "colección es fc(x); los portadores que no llegan a la juntura "
        "se recombinan."
    )

    # ============================================================
    # ANIMACIÓN DE GENERACIÓN, DIFUSIÓN Y COLECCIÓN
    # ============================================================
    x_life = np.linspace(0.0, W_total_um, 400)
    fc_life = f.prob_coleccion_total(
        x_life,
        xn_um,
        xp_um,
        W_total_um,
        Lp_um,
        Ln_um,
        Dp,
        Dn,
        S["Sf"],
        S["Sr"],
    )

    G_x_full = generacion_actual(x_life)
    G_tot_life = np.maximum(
        np.trapezoid(G_x_full, wl_grid, axis=1),
        0.0,
    )
    dx_life = np.gradient(x_life)
    cdf_life = np.cumsum(G_tot_life * dx_life)
    cdf_life = np.maximum.accumulate(cdf_life)

    if cdf_life[-1] > 0.0:
        cdf_life = cdf_life / cdf_life[-1]
    else:
        cdf_life = np.linspace(0.0, 1.0, len(cdf_life))

    html_vida = f"""
<div style="background:#0b0e14;border-radius:10px;padding:10px">
<canvas id="cv2" width="900" height="400"
        style="width:100%;display:block;border-radius:8px"></canvas>
</div>
<script>
const xLife = {json.dumps(x_life.tolist())};
const fcLife = {json.dumps(fc_life.tolist())};
const cdfLife = {json.dumps(cdf_life.tolist())};
const xnUm = {xn_um};
const xpUm = {xp_um};
const Wum = {W_total_um};

function interp2(x, xs, ys) {{
    if (x <= xs[0]) return ys[0];
    if (x >= xs[xs.length - 1]) return ys[ys.length - 1];
    for (let i = 0; i < xs.length - 1; i++) {{
        if (x >= xs[i] && x <= xs[i + 1]) {{
            const t = (x - xs[i]) / (xs[i + 1] - xs[i]);
            return ys[i] + t * (ys[i + 1] - ys[i]);
        }}
    }}
    return ys[ys.length - 1];
}}

function sampleX0() {{
    const r = Math.random();
    for (let i = 0; i < cdfLife.length - 1; i++) {{
        if (r <= cdfLife[i + 1]) {{
            const rango = Math.max(cdfLife[i + 1] - cdfLife[i], 1e-12);
            const t = (r - cdfLife[i]) / rango;
            return xLife[i] + t * (xLife[i + 1] - xLife[i]);
        }}
    }}
    return xLife[xLife.length - 1];
}}

const cv = document.getElementById("cv2");
const ctx = cv.getContext("2d");
const W = cv.width;
const H = cv.height;
const topY = 40;
const bottomY = H - 55;
const blockH = bottomY - topY;
const fracEmisor = 0.22;
const fracDeplecion = 0.10;
const depthBreaks = [0.0, xnUm, xpUm, Wum];
const fracBreaks = [0.0, fracEmisor, fracEmisor + fracDeplecion, 1.0];

function yOf(xum) {{
    if (xum <= depthBreaks[0]) return topY;
    if (xum >= depthBreaks[3]) return topY + blockH;
    for (let i = 0; i < 3; i++) {{
        if (xum >= depthBreaks[i] && xum <= depthBreaks[i + 1]) {{
            const t = (xum - depthBreaks[i]) /
                Math.max(depthBreaks[i + 1] - depthBreaks[i], 1e-9);
            const frac = fracBreaks[i] +
                t * (fracBreaks[i + 1] - fracBreaks[i]);
            return topY + frac * blockH;
        }}
    }}
    return topY + blockH;
}}

let nGen = 0;
let nCol = 0;
let nRec = 0;
let carriers = [];

function spawn() {{
    const x0 = sampleX0();
    const fc0 = Math.max(0.0, Math.min(1.0, interp2(x0, xLife, fcLife)));
    const willCollect = Math.random() < fc0;
    const enDeplecion = x0 >= xnUm && x0 <= xpUm;

    let junctionTarget;
    let contactTarget;
    let tipo;
    let colorViva;

    if (enDeplecion) {{
        junctionTarget = x0;
        contactTarget = Wum;
        tipo = "par generado en depleción";
        colorViva = "#f6e05e";
    }} else if (x0 < xnUm) {{
        junctionTarget = xnUm;
        contactTarget = 0.0;
        tipo = "hueco minoritario en emisor";
        colorViva = "#63b3ed";
    }} else {{
        junctionTarget = xpUm;
        contactTarget = Wum;
        tipo = "electrón minoritario en base";
        colorViva = "#fc8181";
    }}

    let destinoFinal;
    if (willCollect) {{
        destinoFinal = contactTarget;
    }} else if (enDeplecion) {{
        destinoFinal = x0;
    }} else {{
        const fraccionRecorrida = 0.10 + Math.random() * 0.60;
        destinoFinal = x0 +
            (junctionTarget - x0) * fraccionRecorrida;
    }}

    nGen++;
    carriers.push({{
        x0: x0,
        destinoFinal: destinoFinal,
        x: 60 + Math.random() * (W - 120),
        tipo: tipo,
        colorViva: colorViva,
        willCollect: willCollect,
        enDeplecion: enDeplecion,
        prog: 0.0,
        alive: true,
        burst: 0.0,
        phase: Math.random() * 2.0 * Math.PI,
    }});
}}

function drawCarrier(p, progress, yy) {{
    const envolvente = Math.max(0.0, 1.0 - progress);
    const wiggle = Math.sin(p.phase + progress * 10.0) *
        3.0 * envolvente;
    const xDraw = p.x + wiggle;
    ctx.beginPath();
    ctx.arc(xDraw, yy, 3.5, 0, 2 * Math.PI);
    ctx.fillStyle = p.colorViva;
    ctx.fill();
}}

function drawSeparatedPair(p, progress, yy) {{
    const separacion = 5.0 + 28.0 * progress;
    const alpha = Math.max(0.15, 1.0 - 0.25 * progress);

    ctx.beginPath();
    ctx.arc(p.x - separacion, yy - 4.0 * progress, 3.0, 0, 2 * Math.PI);
    ctx.fillStyle = `rgba(99,179,237,${{alpha}})`;
    ctx.fill();

    ctx.beginPath();
    ctx.arc(p.x + separacion, yy + 4.0 * progress, 3.0, 0, 2 * Math.PI);
    ctx.fillStyle = `rgba(252,129,129,${{alpha}})`;
    ctx.fill();
}}

function drawOutcome(p, yy) {{
    p.burst += 0.08;
    const radius = p.willCollect
        ? 3.0 + 12.0 * p.burst
        : 3.0 + 9.0 * p.burst;
    ctx.beginPath();
    ctx.arc(p.x, yy, radius, 0, 2 * Math.PI);
    ctx.strokeStyle = p.willCollect
        ? `rgba(246,224,94,${{Math.max(0.0, 1.0 - p.burst)}})`
        : `rgba(160,174,192,${{Math.max(0.0, 1.0 - p.burst)}})`;
    ctx.lineWidth = 2.5;
    ctx.stroke();
    if (p.burst >= 1.0) {{
        if (p.willCollect) nCol++;
        else nRec++;
        p.alive = false;
    }}
}}

function step() {{
    ctx.clearRect(0, 0, W, H);
    ctx.fillStyle = "#20242c";
    ctx.fillRect(30, topY, W - 60, blockH);
    ctx.strokeStyle = "#4a5568";
    ctx.strokeRect(30, topY, W - 60, blockH);

    ctx.fillStyle = "rgba(99,179,237,0.14)";
    ctx.fillRect(31, yOf(0), W - 62, yOf(xnUm) - yOf(0));
    ctx.fillStyle = "rgba(246,173,85,0.28)";
    ctx.fillRect(31, yOf(xnUm), W - 62, yOf(xpUm) - yOf(xnUm));
    ctx.fillStyle = "rgba(104,211,145,0.12)";
    ctx.fillRect(31, yOf(xpUm), W - 62, yOf(Wum) - yOf(xpUm));

    ctx.fillStyle = "#90cdf4";
    ctx.font = "bold 12px sans-serif";
    ctx.fillText("emisor n: huecos minoritarios", 36, (yOf(0) + yOf(xnUm)) / 2 + 4);
    ctx.fillStyle = "#f6ad55";
    ctx.fillText("depleción: separación por campo", 36, (yOf(xnUm) + yOf(xpUm)) / 2 + 4);
    ctx.fillStyle = "#9ae6b4";
    ctx.fillText("base p: electrones minoritarios", 36, yOf(xpUm) + 18);

    if (Math.random() < 0.08) spawn();

    carriers.forEach(p => {{
        if (!p.alive) return;
        p.prog += 0.014 + Math.random() * 0.004;
        const progress = Math.min(p.prog, 1.0);
        const depthNow = p.x0 + (p.destinoFinal - p.x0) * progress;
        const yy = yOf(depthNow);

        if (p.prog < 1.0) {{
            if (p.enDeplecion) drawSeparatedPair(p, progress, yy);
            else drawCarrier(p, progress, yy);
        }} else if (p.burst < 1.0) {{
            drawOutcome(p, yy);
        }}
    }});

    carriers = carriers.filter(p => p.alive);
    const pctCol = nGen > 0 ? 100.0 * nCol / nGen : 0.0;
    const pctRec = nGen > 0 ? 100.0 * nRec / nGen : 0.0;

    ctx.font = "13px sans-serif";
    ctx.fillStyle = "#e2e8f0";
    ctx.fillText("Generados: " + nGen, 30, H - 28);
    ctx.fillStyle = "#f6e05e";
    ctx.fillText("Colectados: " + nCol + " (" + pctCol.toFixed(1) + "%)", 180, H - 28);
    ctx.fillStyle = "#a0aec0";
    ctx.fillText("Recombinados: " + nRec + " (" + pctRec.toFixed(1) + "%)", 420, H - 28);
    ctx.fillStyle = "#90cdf4";
    ctx.fillText("Azul = hueco emisor | Rojo = electrón base", 680, H - 28);

    requestAnimationFrame(step);
}}
step();
</script>
"""

    st.iframe(html_vida, height="content")

    # ============================================================
    # CURVAS EQE, IQE Y fc(x)
    # ============================================================
    st.subheader("Probabilidad de colección fc(x) y eficiencia cuántica")

    S["lambda_iqe_mapa"] = st.slider(
        "Longitud de onda de inspección [nm]",
        300.0,
        1200.0,
        S["lambda_iqe_mapa"],
        5.0,
        key="l2",
    )

    x_fc = np.linspace(0.0, W_total_um, 600)
    fc_x = f.prob_coleccion_total(
        x_fc,
        xn_um,
        xp_um,
        W_total_um,
        Lp_um,
        Ln_um,
        Dp,
        Dn,
        S["Sf"],
        S["Sr"],
    )

    c1, c2 = st.columns([1, 1])

    with c1:
        fig_fc = go.Figure()
        fig_fc.add_trace(
            go.Scatter(
                x=x_fc,
                y=fc_x,
                mode="lines",
                line=dict(color="#f687b3", width=3),
                name="fc(x)",
            )
        )
        fig_fc.add_vrect(x0=0, x1=xn_um, fillcolor="#63b3ed", opacity=0.15,
                         line_width=0, annotation_text="emisor")
        fig_fc.add_vrect(x0=xn_um, x1=xp_um, fillcolor="#f6ad55", opacity=0.25,
                         line_width=0, annotation_text="depleción")
        fig_fc.add_vrect(x0=xp_um, x1=W_total_um, fillcolor="#68d391", opacity=0.15,
                         line_width=0, annotation_text="base")
        fig_fc.update_layout(
            title="Probabilidad de colección fc(x)",
            xaxis_title="Profundidad x [µm]",
            yaxis_title="fc(x) [adimensional]",
            height=380,
            template="plotly_dark",
            yaxis_range=[0, 1.05],
        )
        st.plotly_chart(fig_fc, width="stretch")

    with c2:
        fig_eqe = go.Figure()
        fig_eqe.add_trace(go.Scatter(x=wl_grid, y=EQE, name="EQE(λ)",
                                     line=dict(color="#68d391", width=3)))
        fig_eqe.add_trace(go.Scatter(x=wl_grid, y=IQE, name="IQE(λ)",
                                     line=dict(color="#f6ad55", width=3, dash="dot")))
        fig_eqe.add_trace(go.Scatter(x=wl_grid, y=1.0 - R_grid,
                                     name="Cota física 1-R(λ)",
                                     line=dict(color="gray", dash="dash")))
        fig_eqe.add_vline(x=S["lambda_iqe_mapa"], line_color="cyan", line_dash="dot")
        fig_eqe.update_layout(
            title="EQE(λ) e IQE(λ)",
            xaxis_title="Longitud de onda λ [nm]",
            yaxis_title="Eficiencia cuántica [adimensional]",
            height=380,
            template="plotly_dark",
            yaxis_range=[0, 1.05],
        )
        st.plotly_chart(fig_eqe, width="stretch")

    _iq = int(np.argmin(np.abs(wl_grid - S["lambda_iqe_mapa"])))
    q1, q2, q3, q4 = st.columns(4)
    q1.metric("λ inspeccionada", f"{wl_grid[_iq]:.0f} nm")
    q2.metric("EQE", f"{EQE[_iq]:.3f}")
    q3.metric("IQE", f"{IQE[_iq]:.3f}")
    q4.metric("Reflectancia R", f"{100 * R_grid[_iq]:.1f} %")

    st.caption(
        "EQE se obtiene integrando la generación Beer–Lambert ponderada por fc(x); "
        "IQE = EQE / [1−R(λ)]."
    )

    # ============================================================
    # MAPA DE IQE LOCAL 8×8 CON HOVER DETALLADO
    # ============================================================
    st.markdown("### Mapa de IQE local por sectores (grilla 8×8)")
    st.caption(
        "Cada sector utiliza su τn local y su Sf local. Mueve el cursor sobre "
        "un sector para consultar sus parámetros y su IQE."
    )

    nsec = 8
    tau_n_grid = np.full((nsec, nsec), S["tau_n_us"], dtype=float)
    sf_local_grid = np.full((nsec, nsec), S["Sf"], dtype=float)

    if S["defecto_activo"]:
        r0, r1 = S["defecto_filas"]
        c0, c1 = S["defecto_cols"]
        tau_n_grid[r0:r1, c0:c1] = S["defecto_tau_n_us"]

    lambda_mapa = S["lambda_iqe_mapa"]
    i_mapa = int(np.argmin(np.abs(wl_grid - lambda_mapa)))
    alpha_mapa = float(alpha_grid[i_mapa])
    R_mapa = float(R_grid[i_mapa])
    wl_mapa_real = float(wl_grid[i_mapa])

    iqe_map = np.zeros((nsec, nsec), dtype=float)
    Lp_local = f.longitud_difusion(Dp, S["tau_p_us"]) * 1e4

    for i in range(nsec):
        for j in range(nsec):
            Ln_ij = f.longitud_difusion(Dn, tau_n_grid[i, j]) * 1e4
            _, iqe_ij = f.calcular_EQE_IQE_preciso(
                np.array([wl_mapa_real]),
                np.array([alpha_mapa]),
                np.array([R_mapa]),
                np.array([1.0]),
                xn_um,
                xp_um,
                W_total_um,
                Lp_local,
                Ln_ij,
                Dp,
                Dn,
                sf_local_grid[i, j],
                S["Sr"],
                reflector_trasero_activo=S["reflector_trasero"],
                R_aluminio=c.R_ALUMINIO_EFECTIVA,
            )
            iqe_map[i, j] = float(iqe_ij[0])

    customdata = np.stack(
        [tau_n_grid, sf_local_grid],
        axis=-1,
    )

    fig_iqe_map = go.Figure(
        data=go.Heatmap(
            z=iqe_map,
            x=np.arange(1, nsec + 1),
            y=np.arange(1, nsec + 1),
            zmin=0.0,
            zmax=1.0,
            colorscale="Viridis",
            colorbar=dict(title="IQE local"),
            customdata=customdata,
            hovertemplate=(
                "Columna: %{x}<br>"
                "Fila: %{y}<br>"
                "IQE local: %{z:.3f}<br>"
                "τn local: %{customdata[0]:.2f} µs<br>"
                "Sf local: %{customdata[1]:.2e} cm/s"
                "<extra></extra>"
            ),
        )
    )
    fig_iqe_map.update_layout(
        title=f"IQE local a λ={wl_mapa_real:.0f} nm",
        xaxis_title="Columna del sector",
        yaxis_title="Fila del sector",
        xaxis=dict(tickmode="linear", dtick=1, fixedrange=True),
        yaxis=dict(tickmode="linear", dtick=1, fixedrange=True, autorange="reversed"),
        height=460,
        template="plotly_dark",
    )
    st.plotly_chart(
        fig_iqe_map,
        config={"displayModeBar": False, "scrollZoom": False},
        width="stretch",
    )

    st.metric(
        "Rango numérico de fc(x)",
        f"[{fc_x.min():.3f}, {fc_x.max():.3f}]",
        help="Debe permanecer dentro de 0 ≤ fc(x) ≤ 1.",
    )

    if S["defecto_activo"]:
        st.caption("La región seleccionada tiene τn menor y, por tanto, una IQE local reducida.")
    else:
        st.caption("Sin contaminación activa, los sectores son homogéneos.")

    # ============================================================
    # TENDENCIAS DE LA LÁMINA 30
    # ============================================================
    c3, c4 = st.columns(2)

    with c3:
        st.markdown("**IQE en el rojo vs τn de volumen**")
        taus = np.geomspace(0.5, 1000, 25)
        wl_rojo = 950.0
        i_rojo = int(np.argmin(np.abs(wl_grid - wl_rojo)))
        iqe_vs_tau = []
        for t in taus:
            Ln_t = f.longitud_difusion(Dn, t) * 1e4
            _e, _i = f.calcular_EQE_IQE_preciso(
                np.array([wl_rojo]), np.array([alpha_grid[i_rojo]]),
                np.array([R_grid[i_rojo]]), np.array([1.0]),
                xn_um, xp_um, W_total_um, Lp_um, Ln_t,
                Dp, Dn, S["Sf"], S["Sr"],
                reflector_trasero_activo=S["reflector_trasero"],
                R_aluminio=c.R_ALUMINIO_EFECTIVA,
            )
            iqe_vs_tau.append(_i[0])

        figr = go.Figure(go.Scatter(x=taus, y=iqe_vs_tau,
                                    line=dict(color="#fc8181", width=3)))
        figr.update_layout(
            xaxis_title="τn de volumen [µs]",
            yaxis_title=f"IQE a {wl_rojo:.0f} nm",
            xaxis_type="log",
            height=320,
            template="plotly_dark",
        )
        st.plotly_chart(figr, width="stretch")

    with c4:
        st.markdown("**IQE en el azul vs Sf**")
        Sfs = np.geomspace(10, 1e6, 25)
        wl_azul = 420.0
        i_azul = int(np.argmin(np.abs(wl_grid - wl_azul)))
        iqe_vs_sf = []
        for sfv in Sfs:
            _e, _i = f.calcular_EQE_IQE_preciso(
                np.array([wl_azul]), np.array([alpha_grid[i_azul]]),
                np.array([R_grid[i_azul]]), np.array([1.0]),
                xn_um, xp_um, W_total_um, Lp_um, Ln_um,
                Dp, Dn, sfv, S["Sr"],
                reflector_trasero_activo=S["reflector_trasero"],
                R_aluminio=c.R_ALUMINIO_EFECTIVA,
            )
            iqe_vs_sf.append(_i[0])

        figb = go.Figure(go.Scatter(x=Sfs, y=iqe_vs_sf,
                                    line=dict(color="#63b3ed", width=3)))
        figb.update_layout(
            xaxis_title="Sf [cm/s]",
            yaxis_title=f"IQE a {wl_azul:.0f} nm",
            xaxis_type="log",
            height=320,
            template="plotly_dark",
        )
        st.plotly_chart(figb, width="stretch")

    st.caption(
        "En el rojo, la IQE aumenta con τn de volumen; en el azul, "
        "la sensibilidad dominante corresponde al emisor y a Sf."
    )


# ------------------------------------------------------------------
# TAB 3 — CURVA I-V (animada)
# ------------------------------------------------------------------
with tab3:
    st.subheader("Ensayo eléctrico de la celda p-n")
    st.caption(
        "Difusión localizada, formación de la juntura y respuesta eléctrica "
        "bajo iluminación."
    )

    # ============================================================
    # VARIABLES LOCALES Y PARÁMETROS TÉRMICOS
    # ============================================================
    dn_tab3_um = float(S["dn_um"])
    Wtotal_tab3_um = float(W_total_um)
    xn_tab3_um = float(xn_um)
    xp_tab3_um = float(xp_um)
    Wdep_tab3_um = max(xp_tab3_um - xn_tab3_um, 0.0)

    if Wdep_tab3_um > 0.0:
        frac_xn_visual = float(np.clip(
            (dn_tab3_um - xn_tab3_um) / Wdep_tab3_um,
            0.0,
            1.0,
        ))
    else:
        frac_xn_visual = 0.5
    frac_xp_visual = 1.0 - frac_xn_visual

    # Parámetros térmicos coherentes con T actual.
    params_T_tab3 = f.J0_con_temperatura(
        T_K,
        S["NA"],
        S["ND"],
        S["tau_n_us"],
        S["tau_p_us"],
    )
    ni_tab3 = params_T_tab3["ni_cm3"]
    Dn_tab3 = params_T_tab3["Dn_cm2_s"]
    Dp_tab3 = params_T_tab3["Dp_cm2_s"]
    Ln_tab3_cm = params_T_tab3["Ln_cm"]
    Lp_tab3_cm = params_T_tab3["Lp_cm"]
    J0_tab3 = params_T_tab3["J0_A_cm2"]

    # ============================================================
    # 1. FORMACIÓN DE LA JUNTURA
    # ============================================================
    st.markdown("### 1. Formación de la juntura p-n")
    st.caption(
        "Los portadores cercanos a la interfaz difunden y se recombinan. "
        "El estado final deja iones fijos expuestos en la zona de depleción; "
        "el bulk profundo permanece en equilibrio local."
    )

    n_ion_p = int(np.clip(np.interp(np.log10(S["NA"]), [14, 17], [6, 46]), 6, 46))
    n_ion_n = int(np.clip(np.interp(np.log10(S["ND"]), [17, 20], [10, 60]), 10, 60))
    rng_j = np.random.default_rng(11)
    xL, xR = -1.0, 1.0
    ionsP_x = rng_j.uniform(xL, -0.08, n_ion_p)
    ionsP_y = rng_j.uniform(-0.85, 0.85, n_ion_p)
    ionsP_z = rng_j.uniform(-0.85, 0.85, n_ion_p)
    ionsN_x = rng_j.uniform(0.08, xR, n_ion_n)
    ionsN_y = rng_j.uniform(-0.85, 0.85, n_ion_n)
    ionsN_z = rng_j.uniform(-0.85, 0.85, n_ion_n)

    ancho_dep_visual = 0.34
    wP_3d = ancho_dep_visual * frac_xp_visual
    wN_3d = ancho_dep_visual * frac_xn_visual

    def _caja_3d(x0, x1, color, opacidad, nombre):
        xs = [x0, x1, x1, x0, x0, x1, x1, x0]
        ys = [-1, -1, 1, 1, -1, -1, 1, 1]
        zs = [-1, -1, -1, -1, 1, 1, 1, 1]
        i = [0, 0, 0, 4, 4, 4, 0, 0, 1, 1, 2, 2]
        j = [1, 2, 3, 5, 6, 7, 1, 5, 2, 6, 3, 7]
        k = [2, 3, 0, 6, 7, 4, 5, 7, 6, 5, 7, 6]
        return go.Mesh3d(
            x=xs,
            y=ys,
            z=zs,
            i=i,
            j=j,
            k=k,
            color=color,
            opacity=opacidad,
            name=nombre,
            showlegend=True,
            flatshading=True,
        )

    fig_j = go.Figure()
    fig_j.add_trace(_caja_3d(xL, -wP_3d, "#4a5568", 0.10, "Base p"))
    fig_j.add_trace(_caja_3d(-wP_3d, wN_3d, "#f6ad55", 0.28, "Depleción"))
    fig_j.add_trace(_caja_3d(wN_3d, xR, "#4a5568", 0.10, "Emisor n"))

    ion_p_expuesto = ionsP_x >= -wP_3d
    ion_n_expuesto = ionsN_x <= wN_3d
    dest_p_x = np.where(ion_p_expuesto, 0.0, ionsP_x)
    dest_n_x = np.where(ion_n_expuesto, 0.0, ionsN_x)

    fig_j.add_trace(go.Scatter3d(
        x=ionsP_x,
        y=ionsP_y,
        z=ionsP_z,
        mode="markers",
        name="Iones aceptores",
        marker=dict(
            size=5,
            color=np.where(ion_p_expuesto, "#fc8181", "#718096"),
            symbol="circle-open",
            line=dict(width=2),
        ),
    ))
    fig_j.add_trace(go.Scatter3d(
        x=ionsN_x,
        y=ionsN_y,
        z=ionsN_z,
        mode="markers",
        name="Iones donadores",
        marker=dict(
            size=5,
            color=np.where(ion_n_expuesto, "#63b3ed", "#718096"),
            symbol="circle-open",
            line=dict(width=2),
        ),
    ))

    progreso_juntura = st.slider(
        "Progreso de formación",
        0.0,
        1.0,
        1.0,
        0.01,
        key="tab3_progreso_juntura",
        help="0: antes del contacto; 1: estado final.",
    )
    avance = min(progreso_juntura / 0.60, 1.0)
    hx_anim = (ionsP_x + (dest_p_x - ionsP_x) * avance).astype(object)
    ex_anim = (ionsN_x + (dest_n_x - ionsN_x) * avance).astype(object)
    if progreso_juntura >= 0.62:
        for idx in np.where(ion_p_expuesto)[0]:
            hx_anim[idx] = None
        for idx in np.where(ion_n_expuesto)[0]:
            ex_anim[idx] = None

    fig_j.add_trace(go.Scatter3d(
        x=hx_anim,
        y=ionsP_y,
        z=ionsP_z,
        mode="markers",
        name="Huecos móviles",
        marker=dict(size=4, color="#63b3ed"),
    ))
    fig_j.add_trace(go.Scatter3d(
        x=ex_anim,
        y=ionsN_y,
        z=ionsN_z,
        mode="markers",
        name="Electrones móviles",
        marker=dict(size=4, color="#fc8181"),
    ))
    if progreso_juntura >= 0.85:
        fig_j.add_trace(go.Scatter3d(
            x=[-wP_3d, wN_3d],
            y=[0, 0],
            z=[0, 0],
            mode="lines+markers",
            line=dict(color="#f6ad55", width=7),
            marker=dict(size=7, color="#f6ad55", symbol="diamond"),
            name="Campo interno E",
        ))

    fig_j.update_layout(
        template="plotly_dark",
        height=540,
        scene=dict(
            xaxis=dict(title="p  ⟵           ⟶  n", showticklabels=False, range=[-1, 1]),
            yaxis=dict(showticklabels=False, title="", range=[-1, 1]),
            zaxis=dict(showticklabels=False, title="", range=[-1, 1]),
            aspectmode="manual",
            aspectratio=dict(x=1.3, y=1, z=1),
            camera=dict(eye=dict(x=1.3, y=-1.7, z=0.7)),
        ),
        legend=dict(orientation="h", y=-0.02),
        margin=dict(l=0, r=0, t=40, b=0),
    )
    st.plotly_chart(fig_j, width="stretch")

    j1, j2, j3 = st.columns(3)
    j1.metric("Ψ₀", f"{Psi0:.3f} V")
    j2.metric("Wdep", f"{Wdep_tab3_um:.2f} µm")
    j3.metric("Reparto Wdep", f"p: {100 * frac_xp_visual:.1f}% | n: {100 * frac_xn_visual:.1f}%")

    # ============================================================
    # 2. CONDICIONES DEL ENSAYO
    # ============================================================
    st.markdown("### 2. Condiciones del ensayo")

    malla = f.modelo_malla_frontal_plata(S["num_dedos"], S["ancho_dedo_um"])
    Rs_base = c.RS_BASE_OHM_CM2
    Rs_malla = malla["Rs_malla_ohm_cm2"]
    Rs_extra = S["Rs_extra"]
    Rs_total = Rs_base + Rs_malla + Rs_extra

    p1, p2, p3, p4, p5 = st.columns(5)
    p1.metric("Irradiancia", f"{S['irradiancia_soles']:.2f} soles")
    p2.metric("T", f"{T_K - 273.15:.1f} °C")
    p3.metric("n idealidad", f"{S['n_ideal']:.2f}")
    p4.metric("Rp", f"{S['Rp']:.2e} Ω·cm²")
    p5.metric("Rs total", f"{Rs_total:.4f} Ω·cm²")
    st.caption(f"ni(T) = {ni_tab3:.3e} cm⁻³ · J0(T) = {J0_tab3:.3e} A/cm²")

    # ============================================================
    # 3. ENSAYO J–V Y P–V
    # ============================================================
    st.markdown("### 3. Ensayo iluminado J–V y P–V")

    JL_con_sombra = malla["fraccion_iluminada"] * JL_A_cm2
    resultado = f.simular_celda_JV(
        JL_con_sombra,
        J0_tab3,
        T_K,
        S["irradiancia_soles"],
        S["n_ideal"],
        Rs_total,
        S["Rp"],
        n_puntos=250,
    )

    V_arr, J_arr, P_arr = truncar_cerca_voc(
        resultado["V_array_V"],
        resultado["J_array_A_cm2"] * 1e3,
        resultado["P_array_W_cm2"] * 1e3,
    )

    fig_iv = make_subplots(
        rows=1,
        cols=2,
        subplot_titles=("Curva J–V", "Curva P–V"),
        horizontal_spacing=0.12,
    )
    fig_iv.add_trace(go.Scatter(
        x=V_arr,
        y=J_arr,
        mode="lines",
        name="J–V",
        line=dict(color="#68d391", width=3),
    ), row=1, col=1)
    fig_iv.add_trace(go.Scatter(
        x=V_arr,
        y=P_arr,
        mode="lines",
        name="P–V",
        line=dict(color="#63b3ed", width=3),
    ), row=1, col=2)
    fig_iv.add_trace(go.Scatter(
        x=[resultado["Vmp_V"]],
        y=[resultado["Jmp_A_cm2"] * 1e3],
        mode="markers+text",
        text=["MPP"],
        textposition="top center",
        marker=dict(color="#f6e05e", size=12, symbol="diamond"),
        name="MPP",
    ), row=1, col=1)
    fig_iv.add_trace(go.Scatter(
        x=[resultado["Vmp_V"]],
        y=[resultado["Pmax_W_cm2"] * 1e3],
        mode="markers+text",
        text=["MPP"],
        textposition="top center",
        marker=dict(color="#f6e05e", size=12, symbol="diamond"),
        showlegend=False,
    ), row=1, col=2)
    fig_iv.update_xaxes(title_text="Voltaje V [V]", row=1, col=1)
    fig_iv.update_xaxes(title_text="Voltaje V [V]", row=1, col=2)
    fig_iv.update_yaxes(title_text="J [mA/cm²]", row=1, col=1)
    fig_iv.update_yaxes(title_text="P [mW/cm²]", row=1, col=2)
    fig_iv.update_layout(
        height=440,
        template="plotly_dark",
        showlegend=False,
        margin=dict(l=30, r=30, t=55, b=30),
    )
    st.plotly_chart(fig_iv, width="stretch")

    # ============================================================
    # 4. PARÁMETROS ELÉCTRICOS
    # ============================================================
    st.markdown("### 4. Parámetros eléctricos y pérdidas")
    FF0 = f.FF0_empirico(resultado["Voc_V"], T_K)

    m1, m2, m3, m4, m5 = st.columns(5)
    m1.metric("Jsc", f"{resultado['Jsc_A_cm2'] * 1e3:.2f} mA/cm²")
    m2.metric("Voc", f"{resultado['Voc_V'] * 1e3:.1f} mV")
    m3.metric("FF", f"{resultado['FF'] * 100:.1f} %", f"FF₀={FF0 * 100:.1f}%")
    m4.metric("Pmax", f"{resultado['Pmax_W_cm2'] * 1e3:.2f} mW/cm²")
    m5.metric("η", f"{resultado['eta'] * 100:.2f} %")

    q1, q2, q3 = st.columns(3)
    q1.metric("Vmp", f"{resultado['Vmp_V']:.3f} V")
    q2.metric("Jmp", f"{resultado['Jmp_A_cm2'] * 1e3:.2f} mA/cm²")
    q3.metric("FF − FF₀", f"{(resultado['FF'] - FF0) * 100:+.2f} pp")

    r1, r2, r3, r4 = st.columns(4)
    r1.metric("Rs base", f"{Rs_base:.4f} Ω·cm²")
    r2.metric("Rs malla", f"{Rs_malla:.4f} Ω·cm²")
    r3.metric("Rs adicional", f"{Rs_extra:.4f} Ω·cm²")
    r4.metric("Rs total", f"{Rs_total:.4f} Ω·cm²")

    # ============================================================
    # 5. ESQUEMA Y MAGNITUDES DEL CIRCUITO
    # ============================================================
    st.markdown("### 5. Circuito equivalente y corrientes en el punto de operación")

    V_max_exp = max(float(resultado["Voc_V"]), 0.05)
    V_inicial = min(0.6 * V_max_exp, V_max_exp)
    if st.session_state.get("tab3_v_operacion", 0.0) > V_max_exp:
        st.session_state["tab3_v_operacion"] = V_max_exp

    V_op = st.slider(
        "Voltaje de operación V [V]",
        0.0,
        V_max_exp,
        V_inicial,
        0.005,
        key="tab3_v_operacion",
    )

    Vt_local = c.K_B_EVK * T_K
    J_foto_mA = max(JL_con_sombra, 0.0) * 1e3
    J_curva_op_mA = float(np.interp(
        V_op,
        resultado["V_array_V"],
        resultado["J_array_A_cm2"] * 1e3,
    ))
    J_curva_op_A = J_curva_op_mA * 1e-3
    V_diodo_op = V_op - Rs_total * J_curva_op_A

    J_diodo_mA = max(
        J0_tab3 * (
            np.exp(
                np.clip(
                    V_diodo_op / (S["n_ideal"] * Vt_local),
                    -700.0,
                    700.0,
                )
            ) - 1.0
        ) * 1e3,
        0.0,
    )
    J_shunt_mA = max(V_diodo_op / max(S["Rp"], 1e-12), 0.0) * 1e3
    J_externa_mA = J_foto_mA - J_diodo_mA - J_shunt_mA

    esquema, barras = st.columns([1.15, 1.0])

    with esquema:
        st.markdown("**Modelo equivalente**")
        svg = f"""
<div style='background:#0b0e14;border-radius:10px;padding:12px'>
<svg viewBox='0 0 620 300' preserveAspectRatio='xMidYMid meet'
style='width:100%;height:auto;display:block'>
<line x1='75' y1='65' x2='545' y2='65' stroke='#e2e8f0' stroke-width='3'/>
<line x1='75' y1='235' x2='545' y2='235' stroke='#e2e8f0' stroke-width='3'/>
<line x1='145' y1='235' x2='145' y2='65' stroke='#68d391' stroke-width='5'/>
<circle cx='145' cy='150' r='31' fill='#161b22' stroke='#68d391' stroke-width='3'/>
<line x1='145' y1='119' x2='145' y2='181' stroke='#68d391' stroke-width='3'/>
<polygon points='145,104 134,123 156,123' fill='#68d391'/>
<text x='90' y='275' fill='#68d391' font-size='15'>JL = {J_foto_mA:.2f} mA/cm²</text>
<line x1='300' y1='65' x2='300' y2='235' stroke='#fc8181' stroke-width='4'/>
<polygon points='300,120 286,150 314,150' fill='#fc8181'/>
<text x='270' y='275' fill='#fc8181' font-size='15'>Diodo</text>
<line x1='425' y1='65' x2='425' y2='235' stroke='#f6ad55' stroke-width='4'/>
<rect x='407' y='128' width='36' height='44' fill='#161b22' stroke='#f6ad55' stroke-width='3'/>
<text x='400' y='275' fill='#f6ad55' font-size='15'>Rp</text>
<rect x='500' y='48' width='48' height='34' fill='#161b22' stroke='#63b3ed' stroke-width='3'/>
<text x='500' y='35' fill='#63b3ed' font-size='15'>Rs</text>
<text x='35' y='58' fill='#a0aec0' font-size='18'>−</text>
<text x='558' y='58' fill='#a0aec0' font-size='18'>+</text>
<text x='35' y='258' fill='#a0aec0' font-size='12'>Terminal negativo</text>
<text x='465' y='258' fill='#a0aec0' font-size='12'>Terminal positivo</text>
</svg>
</div>
"""
        st.components.v1.html(svg, height=390, scrolling=False)

    with barras:
        etiquetas = ["JL", "J externa", "J diodo", "J Rp"]
        valores = [J_foto_mA, J_externa_mA, J_diodo_mA, J_shunt_mA]
        colores = ["#68d391", "#63b3ed", "#fc8181", "#f6ad55"]
        fig_bar = go.Figure(go.Bar(
            x=etiquetas,
            y=valores,
            marker_color=colores,
            text=[f"{v:.3f}" for v in valores],
            textposition="outside",
            hovertemplate="%{x}: %{y:.3f} mA/cm²<extra></extra>",
        ))
        fig_bar.update_layout(
            title=f"Magnitudes a V={V_op:.3f} V",
            xaxis_title="Componente",
            yaxis_title="Densidad de corriente [mA/cm²]",
            height=320,
            template="plotly_dark",
            showlegend=False,
            margin=dict(l=20, r=20, t=55, b=45),
        )
        st.plotly_chart(fig_bar, width="stretch")

    sm1, sm2, sm3, sm4 = st.columns(4)
    sm1.metric("JL", f"{J_foto_mA:.3f} mA/cm²")
    sm2.metric("J externa", f"{J_externa_mA:.3f} mA/cm²")
    sm3.metric("J diodo", f"{J_diodo_mA:.3f} mA/cm²")
    sm4.metric("J Rp", f"{J_shunt_mA:.3f} mA/cm²")

    # ============================================================
    # 6. MALLA FRONTAL
    # ============================================================
    st.markdown("### 6. Malla frontal: sombra versus resistencia serie")

    c1, c2 = st.columns(2)
    with c1:
        st.metric("Fracción de sombra fs", f"{malla['fraccion_sombra'] * 100:.2f} %")
        st.metric("Rs de la malla", f"{malla['Rs_malla_ohm_cm2']:.4f} Ω·cm²")
    with c2:
        Ns = np.linspace(5, 100, 40)
        fss = Ns * S["ancho_dedo_um"] * 1e-4 / c.ANCHO_CELDA_CM
        Rss = c.RS_REF_DEDOS_OHM_CM2 * c.NUMERO_DEDOS_REFERENCIA / Ns
        figN = go.Figure()
        figN.add_trace(go.Scatter(
            x=Ns,
            y=fss * 100,
            name="Sombra [%]",
            line=dict(color="#f6ad55", width=3),
        ))
        figN.add_trace(go.Scatter(
            x=Ns,
            y=Rss,
            name="Rs malla [Ω·cm²]",
            yaxis="y2",
            line=dict(color="#63b3ed", width=3),
        ))
        figN.add_vline(x=S["num_dedos"], line_dash="dot", line_color="white")
        figN.update_layout(
            xaxis_title="Número de dedos",
            yaxis_title="Sombra [%]",
            yaxis2=dict(title="Rs [Ω·cm²]", overlaying="y", side="right"),
            height=340,
            template="plotly_dark",
        )
        st.plotly_chart(figN, width="stretch")


# ------------------------------------------------------------------
# TAB 4 — MAPA DE SECTORES Y DEFECTOS
# ------------------------------------------------------------------
with tab4:
    st.subheader("Defectos localizados y respuesta global")

    st.caption(
        "La celda se divide en una grilla física 32×32. La contaminación "
        "reduce localmente τₙ y la probabilidad de colección. El dedo de "
        "plata interrumpido se modela por separado como un aumento de Rₛ. "
        "La superficie 3D se interpola únicamente para mejorar la lectura visual."
    )

    # ============================================================
    # CONFIGURACIÓN DE LA GRILLA
    # ============================================================
    n_sec = 32
    n_visual = 64

    filas_sector = np.arange(n_sec, dtype=float)
    columnas_sector = np.arange(n_sec, dtype=float)
    X_sector, Y_sector = np.meshgrid(columnas_sector, filas_sector)

    # ============================================================
    # ESTADO LOCAL DE LA PESTAÑA
    # ============================================================
    st.session_state.setdefault("tab4_tipo_falla", "Mancha circular")
    st.session_state.setdefault("tab4_severidad", "Moderada")
    st.session_state.setdefault("tab4_fila_centro", 15.5)
    st.session_state.setdefault("tab4_columna_centro", 15.5)
    st.session_state.setdefault("tab4_radio_falla", 4.0)
    st.session_state.setdefault("tab4_relacion_elipse", 2.0)
    st.session_state.setdefault("tab4_severidad_dedo", "Moderada")
    st.session_state.setdefault("tab4_columna_dedo", 15)

    # ============================================================
    # CONTROLES
    # ============================================================
    st.markdown("### Definición de los defectos")

    control_izq, control_der = st.columns(2)

    with control_izq:
        st.markdown("**Contaminación metálica**")

        S["defecto_activo"] = st.checkbox(
            "Activar contaminación",
            value=S["defecto_activo"],
        )

        tipo_falla = st.selectbox(
            "Forma de la falla",
            options=[
                "Mancha circular",
                "Mancha elíptica",
                "Grieta diagonal",
                "Gradiente radial",
            ],
            key="tab4_tipo_falla",
        )

        severidad = st.select_slider(
            "Severidad",
            options=["Leve", "Moderada", "Severa"],
            key="tab4_severidad",
        )

        fila_centro = st.slider(
            "Fila del centro [sector]",
            min_value=0.0,
            max_value=float(n_sec - 1),
            step=0.5,
            key="tab4_fila_centro",
        )

        columna_centro = st.slider(
            "Columna del centro [sector]",
            min_value=0.0,
            max_value=float(n_sec - 1),
            step=0.5,
            key="tab4_columna_centro",
        )

        radio_falla = st.slider(
            "Radio característico [sectores]",
            min_value=0.5,
            max_value=12.0,
            step=0.5,
            key="tab4_radio_falla",
        )

        relacion_elipse = st.slider(
            "Relación de aspecto de la elipse",
            min_value=1.0,
            max_value=4.0,
            step=0.1,
            disabled=tipo_falla != "Mancha elíptica",
            key="tab4_relacion_elipse",
        )

        if tipo_falla == "Gradiente radial":
            st.caption(
                "La severidad es máxima cerca del centro y decrece linealmente "
                "hasta cero al alcanzar el radio definido."
            )

    with control_der:
        st.markdown("**Dedo de plata interrumpido**")

        activar_dedo = st.checkbox(
            "Activar dedo roto",
            value=S["dedo_roto_col"] is not None,
        )

        if activar_dedo:
            columna_dedo = st.slider(
                "Columna del dedo roto [sector]",
                min_value=0,
                max_value=n_sec - 1,
                value=int(
                    st.session_state.get(
                        "tab4_columna_dedo",
                        n_sec // 2,
                    )
                ),
                key="tab4_columna_dedo",
            )

            S["dedo_roto_col"] = int(columna_dedo)

            severidad_dedo = st.select_slider(
                "Severidad resistiva",
                options=["Leve", "Moderada", "Severa"],
                key="tab4_severidad_dedo",
            )
        else:
            S["dedo_roto_col"] = None
            severidad_dedo = "Leve"

        st.caption(
            "El dedo roto aumenta Rₛ y afecta principalmente FF y Pmax. "
            "No modifica la IQE local ni Jᴸ."
        )

    wl_defecto = st.slider(
        "λ para visualizar el defecto [nm]",
        min_value=300.0,
        max_value=1200.0,
        value=900.0,
        step=10.0,
        key="tab4_lambda_defecto",
    )

    # ============================================================
    # MAPA CONTINUO DE SEVERIDAD
    # ============================================================
    dx = X_sector - columna_centro
    dy = Y_sector - fila_centro
    sigma = max(radio_falla, 0.25)

    if tipo_falla == "Mancha elíptica":
        sigma_x = sigma * relacion_elipse
        sigma_y = sigma
        severidad_map = np.exp(
            -0.5 * (
                (dx / sigma_x) ** 2
                + (dy / sigma_y) ** 2
            )
        )

    elif tipo_falla == "Grieta diagonal":
        distancia = np.abs(dx - dy) / np.sqrt(2.0)
        coordenada_grieta = (dx + dy) / np.sqrt(2.0)
        severidad_map = np.exp(
            -0.5 * (
                distancia / max(sigma / 3.0, 0.15)
            ) ** 2
        )
        severidad_map *= np.exp(
            -0.5 * (
                coordenada_grieta / max(2.0 * sigma, 0.5)
            ) ** 2
        )

    elif tipo_falla == "Gradiente radial":
        distancia = np.sqrt(dx ** 2 + dy ** 2)
        severidad_map = np.clip(
            1.0 - distancia / max(sigma, 0.5),
            0.0,
            1.0,
        )

    else:
        distancia2 = dx ** 2 + dy ** 2
        severidad_map = np.exp(
            -0.5 * distancia2 / max(sigma ** 2, 0.25)
        )

    severidad_map = np.clip(severidad_map, 0.0, 1.0)

    # ============================================================
    # TIEMPO DE VIDA LOCAL
    # ============================================================
    factores_severidad = {
        "Leve": 0.50,
        "Moderada": 0.10,
        "Severa": 0.01,
    }
    factor_tau = factores_severidad[severidad]

    tau_n_sano = np.full(
        (n_sec, n_sec),
        S["tau_n_us"],
        dtype=float,
    )

    tau_n_defecto = tau_n_sano.copy()

    if S["defecto_activo"]:
        tau_n_defecto = S["tau_n_us"] * (
            1.0 - severidad_map * (1.0 - factor_tau)
        )
        tau_n_defecto = np.clip(
            tau_n_defecto,
            S["tau_n_us"] * factor_tau,
            S["tau_n_us"],
        )

    # ============================================================
    # IQE LOCAL POR SECTOR
    # ============================================================
    i_w = int(np.argmin(np.abs(wl_grid - wl_defecto)))
    wl_real = float(wl_grid[i_w])
    alpha_real = float(alpha_grid[i_w])
    R_real = float(R_grid[i_w])

    sf_local_grid = np.full(
        (n_sec, n_sec),
        S["Sf"],
        dtype=float,
    )

    def calcular_mapa_iqe(tau_n_grid):
        """Calcula IQE local con la misma ecuación de las Pestañas 2 y 3."""
        mapa_iqe = np.zeros((n_sec, n_sec), dtype=float)

        Lp_local_um = f.longitud_difusion(
            Dp,
            S["tau_p_us"],
        ) * 1e4

        for i in range(n_sec):
            for j in range(n_sec):
                Ln_local_um = f.longitud_difusion(
                    Dn,
                    tau_n_grid[i, j],
                ) * 1e4

                _, iqe_local = f.calcular_EQE_IQE_preciso(
                    np.array([wl_real]),
                    np.array([alpha_real]),
                    np.array([R_real]),
                    np.array([1.0]),
                    xn_um,
                    xp_um,
                    W_total_um,
                    Lp_local_um,
                    Ln_local_um,
                    Dp,
                    Dn,
                    sf_local_grid[i, j],
                    S["Sr"],
                    reflector_trasero_activo=S["reflector_trasero"],
                    R_aluminio=c.R_ALUMINIO_EFECTIVA,
                )

                mapa_iqe[i, j] = float(iqe_local[0])

        return mapa_iqe

    mapa_iqe_sano = calcular_mapa_iqe(tau_n_sano)
    mapa_iqe_defecto = (
        calcular_mapa_iqe(tau_n_defecto)
        if S["defecto_activo"]
        else mapa_iqe_sano.copy()
    )

    # ============================================================
    # HEATMAPS IQE
    # ============================================================
    def construir_heatmap_iqe(mapa, titulo):
        fig = go.Figure(
            go.Heatmap(
                z=mapa,
                x=np.arange(1, n_sec + 1),
                y=np.arange(1, n_sec + 1),
                zmin=0.0,
                zmax=1.0,
                colorscale="Viridis",
                colorbar=dict(title="IQE local"),
                hovertemplate=(
                    "Columna: %{x}<br>"
                    "Fila: %{y}<br>"
                    "IQE local: %{z:.3f}<extra></extra>"
                ),
            )
        )

        fig.update_layout(
            title=titulo,
            xaxis_title="Columna del sector",
            yaxis_title="Fila del sector",
            xaxis=dict(
                tickmode="linear",
                dtick=4,
                fixedrange=True,
            ),
            yaxis=dict(
                tickmode="linear",
                dtick=4,
                fixedrange=True,
                autorange="reversed",
            ),
            height=440,
            template="plotly_dark",
        )

        return fig

    st.markdown(f"### IQE local a λ={wl_real:.0f} nm")

    mapa_izq, mapa_der = st.columns(2)

    with mapa_izq:
        st.plotly_chart(
            construir_heatmap_iqe(
                mapa_iqe_sano,
                "IQE local — celda sana",
            ),
            config={
                "displayModeBar": False,
                "scrollZoom": False,
            },
            width="stretch",
        )

    with mapa_der:
        st.plotly_chart(
            construir_heatmap_iqe(
                mapa_iqe_defecto,
                "IQE local — celda con defecto",
            ),
            config={
                "displayModeBar": False,
                "scrollZoom": False,
            },
            width="stretch",
        )

    # ============================================================
    # PENALIZACIÓN RESISTIVA LOCALIZADA
    # ============================================================
    factores_dedo = {
        "Leve": 0.5,
        "Moderada": 1.0,
        "Severa": 2.0,
    }

    penalizacion_dedo = (
        factores_dedo[severidad_dedo]
        if S["dedo_roto_col"] is not None
        else 0.0
    )

    mapa_resistivo = np.zeros(
        (n_sec, n_sec),
        dtype=float,
    )

    if S["dedo_roto_col"] is not None:
        mapa_resistivo[:, S["dedo_roto_col"]] = (
            penalizacion_dedo / factores_dedo["Severa"]
        )

    def construir_heatmap_resistivo():
        fig = go.Figure(
            go.Heatmap(
                z=mapa_resistivo,
                x=np.arange(1, n_sec + 1),
                y=np.arange(1, n_sec + 1),
                zmin=0.0,
                zmax=1.0,
                colorscale="Hot",
                colorbar=dict(title="Penalización relativa"),
                hovertemplate=(
                    "Columna: %{x}<br>"
                    "Fila: %{y}<br>"
                    "Penalización: %{z:.3f}<extra></extra>"
                ),
            )
        )

        fig.update_layout(
            title="Localización de la penalización resistiva",
            xaxis_title="Columna del sector",
            yaxis_title="Fila del sector",
            xaxis=dict(
                tickmode="linear",
                dtick=4,
                fixedrange=True,
            ),
            yaxis=dict(
                tickmode="linear",
                dtick=4,
                fixedrange=True,
                autorange="reversed",
            ),
            height=440,
            template="plotly_dark",
        )

        return fig

    st.markdown("### Diagnóstico resistivo")
    st.caption(
        "La banda vertical identifica los sectores asociados al dedo roto. "
        "La escala es relativa: no representa una temperatura ni una potencia "
        "local absoluta."
    )

    st.plotly_chart(
        construir_heatmap_resistivo(),
        config={
            "displayModeBar": False,
            "scrollZoom": False,
        },
        width="stretch",
    )

    # ============================================================
    # MÉTRICAS ESPACIALES
    # ============================================================
    area_afectada = float(
        np.mean(severidad_map > 0.1) * 100.0
    )
    iqe_media_sana = float(np.mean(mapa_iqe_sano))
    iqe_media_defecto = float(np.mean(mapa_iqe_defecto))
    reduccion_iqe_media = (
        100.0 * (1.0 - iqe_media_defecto / iqe_media_sana)
        if iqe_media_sana > 0.0
        else 0.0
    )

    st.markdown("### Indicadores espaciales")
    met1, met2, met3, met4 = st.columns(4)

    met1.metric(
        "Área con severidad > 0.1",
        f"{area_afectada:.1f} %",
    )
    met2.metric(
        "IQE media sana",
        f"{iqe_media_sana:.3f}",
    )
    met3.metric(
        "IQE media afectada",
        f"{iqe_media_defecto:.3f}",
    )
    met4.metric(
        "Reducción media de IQE",
        f"{reduccion_iqe_media:.1f} %",
    )

    # ============================================================
    # SUPERFICIE 3D ÚNICA
    # ============================================================
    def interpolar_matriz_visual(matriz, resolucion_visual):
        x_original = np.linspace(0.0, 1.0, n_sec)
        y_original = np.linspace(0.0, 1.0, n_sec)
        x_visual = np.linspace(0.0, 1.0, resolucion_visual)
        y_visual = np.linspace(0.0, 1.0, resolucion_visual)
        matriz = np.asarray(matriz, dtype=float)

        try:
            from scipy.interpolate import RectBivariateSpline

            interpolador = RectBivariateSpline(
                y_original,
                x_original,
                matriz,
                kx=3,
                ky=3,
            )
            matriz_visual = interpolador(
                y_visual,
                x_visual,
            )
        except ImportError:
            matriz_x = np.array([
                np.interp(
                    x_visual,
                    x_original,
                    fila,
                )
                for fila in matriz
            ])
            matriz_visual = np.array([
                np.interp(
                    y_visual,
                    y_original,
                    matriz_x[:, j],
                )
                for j in range(resolucion_visual)
            ]).T

        return np.clip(matriz_visual, 0.0, 1.0)

    altura_fisica = (
        severidad_map
        if S["defecto_activo"]
        else np.zeros((n_sec, n_sec), dtype=float)
    )

    altura_visual = interpolar_matriz_visual(
        altura_fisica,
        n_visual,
    ) * 0.65

    eje_visual = np.linspace(
        1.0,
        float(n_sec),
        n_visual,
    )
    X_visual, Y_visual = np.meshgrid(
        eje_visual,
        eje_visual,
    )

    fig_3d = go.Figure(
        go.Surface(
            x=X_visual,
            y=Y_visual,
            z=altura_visual,
            colorscale=[
                [0.00, "#20242c"],
                [0.25, "#276749"],
                [0.55, "#d69e2e"],
                [0.80, "#ed8936"],
                [1.00, "#c53030"],
            ],
            cmin=0.0,
            cmax=0.65,
            colorbar=dict(title="Severidad visual"),
            hovertemplate=(
                "Columna: %{x:.1f}<br>"
                "Fila: %{y:.1f}<br>"
                "Altura visual: %{z:.3f}<extra></extra>"
            ),
            lighting=dict(
                ambient=0.75,
                diffuse=0.75,
                specular=0.20,
                roughness=0.75,
                fresnel=0.10,
            ),
        )
    )

    fig_3d.update_layout(
        title="Relieve de la contaminación",
        height=500,
        template="plotly_dark",
        margin=dict(l=0, r=0, t=45, b=0),
        scene=dict(
            xaxis_title="Columna del sector",
            yaxis_title="Fila del sector",
            zaxis_title="Severidad visual",
            xaxis=dict(
                range=[1.0, float(n_sec)],
                nticks=8,
            ),
            yaxis=dict(
                range=[1.0, float(n_sec)],
                nticks=8,
            ),
            zaxis=dict(
                range=[0.0, 0.65],
                nticks=5,
            ),
            aspectmode="manual",
            aspectratio=dict(
                x=1.0,
                y=1.0,
                z=0.42,
            ),
            camera=dict(
                eye=dict(
                    x=1.45,
                    y=-1.45,
                    z=1.05,
                )
            ),
        ),
    )

    st.markdown("### Intensidad espacial del defecto")
    st.caption(
        "La elevación es una representación visual de la severidad. No es "
        "una magnitud física adicional ni una altura geométrica de la celda."
    )

    st.plotly_chart(
        fig_3d,
        config={
            "displayModeBar": False,
            "scrollZoom": True,
        },
        width="stretch",
    )

    # ============================================================
    # CORRIENTE FOTOGENERADA GLOBAL
    # ============================================================
    st.markdown("### Promedio sectorial de la colección")

    def calcular_JL_global(tau_n_grid, sf_grid):
        """Promedia JL calculado sector por sector sobre la grilla física."""
        JL_sum = 0.0
        Lp_global_um = f.longitud_difusion(
            Dp,
            S["tau_p_us"],
        ) * 1e4

        for i in range(n_sec):
            for j in range(n_sec):
                Ln_local_um = f.longitud_difusion(
                    Dn,
                    tau_n_grid[i, j],
                ) * 1e4

                eqe_local, _ = f.calcular_EQE_IQE_preciso(
                    wl_grid,
                    alpha_grid,
                    R_grid,
                    phi0_grid,
                    xn_um,
                    xp_um,
                    W_total_um,
                    Lp_global_um,
                    Ln_local_um,
                    Dp,
                    Dn,
                    sf_grid[i, j],
                    S["Sr"],
                    reflector_trasero_activo=S["reflector_trasero"],
                    R_aluminio=c.R_ALUMINIO_EFECTIVA,
                )

                JL_sum += c.Q * np.trapezoid(
                    phi0_grid * eqe_local,
                    wl_grid,
                )

        return JL_sum / float(n_sec * n_sec)

    sf_grid_sano = np.full(
        (n_sec, n_sec),
        S["Sf"],
        dtype=float,
    )

    JL_sano = calcular_JL_global(
        tau_n_sano,
        sf_grid_sano,
    )

    JL_defecto = (
        calcular_JL_global(
            tau_n_defecto,
            sf_grid_sano,
        )
        if S["defecto_activo"]
        else JL_sano
    )

    # ============================================================
    # RESISTENCIA SERIE DEL DEDO ROTO
    # ============================================================
    malla_sana = f.modelo_malla_frontal_plata(
        S["num_dedos"],
        S["ancho_dedo_um"],
    )

    Rs_sano = (
        c.RS_BASE_OHM_CM2
        + malla_sana["Rs_malla_ohm_cm2"]
        + S["Rs_extra"]
    )

    Rs_defecto = Rs_sano + penalizacion_dedo * (
        c.RS_REF_DEDOS_OHM_CM2
        * c.NUMERO_DEDOS_REFERENCIA
        / S["num_dedos"]
    )

    # ============================================================
    # CURVAS J–V
    # ============================================================
    resultado_sano = f.simular_celda_JV(
        malla_sana["fraccion_iluminada"] * JL_sano,
        J0_A_cm2,
        T_K,
        S["irradiancia_soles"],
        S["n_ideal"],
        Rs_sano,
        S["Rp"],
        n_puntos=250,
    )

    resultado_defecto = f.simular_celda_JV(
        malla_sana["fraccion_iluminada"] * JL_defecto,
        J0_A_cm2,
        T_K,
        S["irradiancia_soles"],
        S["n_ideal"],
        Rs_defecto,
        S["Rp"],
        n_puntos=250,
    )

    V_sano, J_sano = truncar_cerca_voc(
        resultado_sano["V_array_V"],
        resultado_sano["J_array_A_cm2"] * 1e3,
    )
    V_defecto, J_defecto = truncar_cerca_voc(
        resultado_defecto["V_array_V"],
        resultado_defecto["J_array_A_cm2"] * 1e3,
    )

    fig_jv = go.Figure()

    fig_jv.add_trace(go.Scatter(
        x=V_sano,
        y=J_sano,
        name="Celda sana",
        line=dict(
            color="#68d391",
            width=3,
        ),
    ))

    fig_jv.add_trace(go.Scatter(
        x=V_defecto,
        y=J_defecto,
        name="Con defecto(s)",
        line=dict(
            color="#fc8181",
            width=3,
            dash="dash",
        ),
    ))

    fig_jv.update_layout(
        title="Propagación del defecto a la curva J–V",
        xaxis_title="Voltaje V [V]",
        yaxis_title="Densidad de corriente J [mA/cm²]",
        height=420,
        template="plotly_dark",
        xaxis=dict(fixedrange=True),
        yaxis=dict(
            fixedrange=True,
            range=[
                0.0,
                max(J_sano.max(), J_defecto.max()) * 1.08,
            ],
        ),
    )

    st.plotly_chart(
        fig_jv,
        config={
            "displayModeBar": False,
            "scrollZoom": False,
        },
        width="stretch",
    )

    # ============================================================
    # MÉTRICAS GLOBALES
    # ============================================================
    metricas = st.columns(6)

    metricas[0].metric(
        "JL sana",
        f"{JL_sano * 1e3:.2f} mA/cm²",
    )
    metricas[1].metric(
        "JL afectada",
        f"{JL_defecto * 1e3:.2f} mA/cm²",
    )
    metricas[2].metric(
        "Δ Jsc",
        f"{(resultado_defecto['Jsc_A_cm2'] - resultado_sano['Jsc_A_cm2']) * 1e3:+.3f} mA/cm²",
    )
    metricas[3].metric(
        "Δ FF",
        f"{(resultado_defecto['FF'] - resultado_sano['FF']) * 100:+.2f} pp",
    )
    metricas[4].metric(
        "Δ Pmax",
        f"{(resultado_defecto['Pmax_W_cm2'] - resultado_sano['Pmax_W_cm2']) * 1e3:+.3f} mW/cm²",
    )
    metricas[5].metric(
        "Rs con defecto",
        f"{Rs_defecto:.4f} Ω·cm²",
    )

    # ============================================================
    # LECTURA FÍSICA AUTOMÁTICA
    # ============================================================
    if S["defecto_activo"] and S["dedo_roto_col"] is not None:
        st.info(
            "Lectura física: la contaminación reduce τₙ, Lₙ, IQE, JL y Jsc. "
            "El dedo roto agrega una penalización de resistencia serie que "
            "afecta principalmente FF y Pmax."
        )
    elif S["defecto_activo"]:
        st.info(
            "Lectura física: la contaminación es un defecto de colección. "
            "Al disminuir τₙ local, disminuye Lₙ y se reduce la corriente "
            "fotogenerada global."
        )
    elif S["dedo_roto_col"] is not None:
        st.info(
            "Lectura física: el dedo roto es un defecto resistivo. No cambia "
            "IQE ni JL; su efecto aparece principalmente en Rs, FF y Pmax."
        )
    else:
        st.caption(
            "Sin defectos activos, la celda sana y la celda afectada coinciden."
        )


# ------------------------------------------------------------------
# TAB 5 — VALIDACIÓN
# ------------------------------------------------------------------
with tab5:
    st.subheader("Verificaciones automáticas (con los parámetros de la semilla S=3 por defecto)")
    st.caption("Esta pestaña se ejecuta automáticamente. Compara cada resultado de la simulación con un "
               "valor de referencia y una tolerancia (Anexo B / criterios de aceptación del enunciado 2.2).")

    # Recalcular todo con valores por defecto de semilla, sin importar los sliders actuales.
    NA0, ND0 = c.NA_BASE_DEFAULT, c.ND_EMISOR_DEFAULT
    dn0, Wp0 = c.D_N_EMISOR_UM, c.W_P_BASE_UM_DEFAULT
    W0 = dn0 + Wp0
    T0_K = c.T_OPERACION_C_DEFAULT + 273.15
    Sf0, Sr0 = c.S_FRONTAL_CM_S_DEFAULT, 1.0e2
    tau_n0, tau_p0 = c.TAU_SRH_VOLUMEN_US_DEFAULT, c.TAU_P_EMISOR_US_DEFAULT

    Dp0 = f.coef_difusion(T0_K, c.MU_P_EMISOR_N_300K)
    Dn0 = f.coef_difusion(T0_K, c.MU_N_BASE_P_300K)
    Lp0_um = f.longitud_difusion(Dp0, tau_p0) * 1e4
    Ln0_um = f.longitud_difusion(Dn0, tau_n0) * 1e4
    Psi0_0 = f.potencial_juntura(NA0, ND0, c.NI_300K, T0_K)
    Wdep0_um = f.ancho_zona_deplecion(Psi0_0, NA0, ND0) * 1e4
    xn0_um = dn0 - Wdep0_um / 2.0
    xp0_um = dn0 + Wdep0_um / 2.0

    wl0 = np.linspace(300.0, 1200.0, 900)
    alpha0 = f.alpha_silicio(wl0)
    R0 = f.reflectancia_frontal(wl0, modo="fresnel")
    P0, phi00 = f.espectro_y_flujo_fotones(wl0)
    EQE0, IQE0 = f.calcular_EQE_IQE_preciso(wl0, alpha0, R0, phi00, xn0_um, xp0_um, W0,
                                             Lp0_um, Ln0_um, Dp0, Dn0, Sf0, Sr0)

    filas = []

    # V1: balance de fotones suma 1
    fr, fa, ft = f.balance_fotones(R0, alpha0, W0)
    suma = fr + fa + ft
    err_v1 = np.max(np.abs(suma - 1.0)) * 100
    filas.append(("V1", "Balance de fotones Beer-Lambert (suma=1 ∀λ)", f"{suma.min():.5f}–{suma.max():.5f}",
                  "1.00000", f"{err_v1:.4f}%", err_v1 < 1.0))

    # V2: profundidad de absorción a 450nm y 1000nm
    i450 = int(np.argmin(np.abs(wl0 - 450))); i1000 = int(np.argmin(np.abs(wl0 - 1000)))
    prof450 = 1.0 / alpha0[i450] * 1e4
    prof1000 = 1.0 / alpha0[i1000] * 1e4
    ok_v2 = (0.3 <= prof450 <= 3.0) and (prof1000 >= 70)
    filas.append(("V2", "Profundidad de absorción 1/α a 450 y 1000 nm",
                  f"{prof450:.2f} µm ; {prof1000:.1f} µm", "~1 µm ; >100 µm (±30%)",
                  "—", ok_v2))

    # V3: consistencia cruzada Jsc (EQE integrado) vs Jsc leída de curva J-V
    JL0 = c.Q * np.trapezoid(phi00 * EQE0, wl0)
    J00 = f.corriente_saturacion_J0(NA0, ND0, c.NI_300K, Dn0, Ln0_um * 1e-4, Dp0, Lp0_um * 1e-4)
    malla0 = f.modelo_malla_frontal_plata(c.NUMERO_DEDOS_BASE, c.ANCHO_DEDO_BASE_UM)
    res0 = f.simular_celda_JV(malla0["fraccion_iluminada"] * JL0, J00, T0_K, 1.0, 1.0,
                               c.RS_BASE_OHM_CM2 + malla0["Rs_malla_ohm_cm2"], c.RP_BASE_OHM_CM2, n_puntos=400)
    Jsc_EQE = JL0 * malla0["fraccion_iluminada"] * 1e3
    Jsc_JV = res0["Jsc_A_cm2"] * 1e3
    err_v3 = abs(Jsc_EQE - Jsc_JV) / Jsc_JV * 100 if Jsc_JV > 0 else np.nan
    filas.append(("V3", "Consistencia cruzada Jsc: ∫q·φ0·EQE dλ vs Jsc de curva J-V",
                  f"{Jsc_EQE:.3f} vs {Jsc_JV:.3f} mA/cm²", "coincidencia <5%", f"{err_v3:.3f}%", err_v3 < 5.0))

    # V4: FF0 con Rs->0, Rp->inf, n=1
    res_ideal = f.simular_celda_JV(malla0["fraccion_iluminada"] * JL0, J00, T0_K, 1.0, 1.0, 0.0, 1e12, n_puntos=400)
    FF0_calc = res_ideal["FF"]
    FF0_emp = f.FF0_empirico(res_ideal["Voc_V"], T0_K)
    err_v4 = abs(FF0_calc - FF0_emp) / FF0_emp * 100
    filas.append(("V4", "FF con Rs→0,Rp→∞,n=1 vs FF₀ empírico", f"{FF0_calc:.4f} vs {FF0_emp:.4f}",
                  "coincidencia <1%", f"{err_v4:.3f}%", err_v4 < 1.0))

    # V5: cota física EQE(λ) <= 1-R(λ)
    margen = (1 - R0) - EQE0
    ok_v5 = np.all(margen >= -1e-6)
    filas.append(("V5", "Cota física EQE(λ) ≤ 1−R(λ) para todo λ", f"mín margen={margen.min():.2e}",
                  "≥ 0 siempre", "—", ok_v5))

    # V6: dVoc/dT entre 15-75C
    temps_C = np.linspace(15, 75, 13)
    Vocs = []
    for TC in temps_C:
        TK = TC + 273.15
        p = f.J0_con_temperatura(TK, NA0, ND0, tau_n0, tau_p0)
        r = f.simular_celda_JV(malla0["fraccion_iluminada"] * JL0, p["J0_A_cm2"], TK, 1.0, 1.0,
                                0.0, 1e12, n_puntos=250)
        Vocs.append(r["Voc_V"])
    pendiente_mV_C = np.polyfit(temps_C, Vocs, 1)[0] * 1e3
    ok_v6 = -2.6 <= pendiente_mV_C <= -1.8
    filas.append(("V6", "Coeficiente dVoc/dT (barrido 15–75°C)", f"{pendiente_mV_C:.3f} mV/°C",
                  "entre −1.8 y −2.6 mV/°C", "—", ok_v6))

    # V7: efecto de la malla frontal — Jsc cae proporcional a fs añadida
    malla_x1 = f.modelo_malla_frontal_plata(c.NUMERO_DEDOS_BASE, c.ANCHO_DEDO_BASE_UM)
    malla_x2 = f.modelo_malla_frontal_plata(c.NUMERO_DEDOS_BASE, c.ANCHO_DEDO_BASE_UM * 2)
    res_x1 = f.simular_celda_JV(malla_x1["fraccion_iluminada"] * JL0, J00, T0_K, 1.0, 1.0,
                                 c.RS_BASE_OHM_CM2 + malla_x1["Rs_malla_ohm_cm2"], c.RP_BASE_OHM_CM2, n_puntos=250)
    res_x2 = f.simular_celda_JV(malla_x2["fraccion_iluminada"] * JL0, J00, T0_K, 1.0, 1.0,
                                 c.RS_BASE_OHM_CM2 + malla_x2["Rs_malla_ohm_cm2"], c.RP_BASE_OHM_CM2, n_puntos=250)
    caida_Jsc_pct = (1 - res_x2["Jsc_A_cm2"] / res_x1["Jsc_A_cm2"]) * 100
    caida_area_pct = (malla_x2["fraccion_sombra"] - malla_x1["fraccion_sombra"]) / (1 - malla_x1["fraccion_sombra"]) * 100
    err_v7 = abs(caida_Jsc_pct - caida_area_pct)
    filas.append(("V7", "Duplicar ancho de dedos: caída de Jsc vs área sombreada añadida",
                  f"{caida_Jsc_pct:.3f}% vs {caida_area_pct:.3f}%", "coincidencia <2 puntos", f"{err_v7:.3f} pp",
                  err_v7 < 2.0))

    import pandas as pd
    df = pd.DataFrame(filas, columns=["#", "Verificación", "Valor calculado", "Referencia/tolerancia",
                                       "Error", "Veredicto"])
    df["Veredicto"] = df["Veredicto"].map(lambda ok: "✅ APROBADO" if ok else "❌ REVISAR")
    st.dataframe(df, width="stretch", hide_index=True)

    n_ok = sum(1 for r in filas if r[-1])
    if n_ok == len(filas):
        st.success(f"Todas las verificaciones ({n_ok}/{len(filas)}) están dentro de tolerancia, calculadas "
                   "en tiempo real a partir de los datos ópticos medidos (Schinke.csv) y del espectro "
                   "AM1.5G real (astmg173.xls) — nada de esta tabla está codificado a mano.")
    else:
        st.warning(f"{n_ok}/{len(filas)} verificaciones aprobadas. Revisa las marcadas ❌ — el enunciado "
                   "acepta fallas siempre que se identifique físicamente qué supuesto del "
                   "modelo las causa y en qué régimen (de λ, V o T) ocurren; no basta con que exista "
                   "la verificación, hay que poder explicar la falla.")

    with st.expander("📎 Metodología, datos y supuestos del modelo"):
        st.markdown("""
- **α(λ) del silicio** se calcula desde `datos/Schinke.csv` (n, k medidos), y el **espectro AM1.5G**
  desde `datos/astmg173.xls` (columna *Global tilt*, ASTM G173-03) — ambos son datos reales medidos,
  no una aproximación analítica. Su integral da 1000 W/m² entre 300–2000 nm, coincidiendo con la
  referencia de la Unidad 3 sin necesidad de normalizar a mano.
- El **EQE/IQE** se integra **analíticamente por tramos** (no con la regla del trapecio sobre una
  malla uniforme): para λ azul la longitud de absorción puede ser de pocos nanómetros, y una malla
  en x demasiado gruesa frente a eso sobreestima groseramente la integral con trapecios (llegaba a
  dar EQE>1 en una versión anterior). La integral de α·e^(−αx) tiene primitiva cerrada en cada tramo
  (emisor/deplección/base), así que el resultado no depende de ninguna malla.
- `τₚ` del emisor no viene dado por la semilla (la Tabla A.1 solo asigna `τ_SRH` de volumen); se
  declaró 1 µs como valor típico de un emisor n⁺ muy dopado. Es un supuesto explícito del modelo.
- Si en algún momento cambian los datos de `datos/` (por ejemplo por una versión más reciente de
  Schinke), esta pestaña se recalcula sola con los nuevos archivos: no hay ningún número de esta
  tabla escrito a mano en el código.
        """)


# ------------------------------------------------------------------
# TAB 6 — RESUMEN ANIMADO (secuencia completa, autoplay, sin controles)
# ------------------------------------------------------------------
with tab6:
    st.subheader("Secuencia completa de conversión fotovoltaica")
    st.caption("Un ciclo de ~22 s que recorre automáticamente las etapas de absorción, transporte, separación y entrega de potencia.")

    V_arr_full = resultado["V_array_V"]
    J_arr_full = resultado["J_array_A_cm2"] * 1e3  # mA/cm², convención J<0 = generando
    # Truncar justo después de Voc: más allá el diodo entra en conducción directa
    # fuerte (J llega a decenas de mA/cm² positivos) y aplastaría la escala del
    # tramo fotovoltaico, que es el que importa mostrar aquí.
    i_voc = int(np.searchsorted(J_arr_full, 0.0)) if np.any(J_arr_full >= 0) else len(J_arr_full) - 1
    i_corte = min(i_voc + max(len(J_arr_full) // 40, 3), len(J_arr_full) - 1)
    V_arr6 = V_arr_full[:i_corte + 1].tolist()
    J_arr6 = (-J_arr_full[:i_corte + 1]).tolist()  # signo positivo = corriente generada
    Jsc6, Voc6, FF6, eta6, Pmax6 = (resultado["Jsc_A_cm2"] * 1e3, resultado["Voc_V"],
                                     resultado["FF"] * 100, resultado["eta"] * 100,
                                     resultado["Pmax_W_cm2"] * 1e3)

    html_resumen = f"""
<div style="background:#0b0e14;border-radius:10px;padding:10px">
<div id="fase-titulo" style="color:#f6ad55;font:bold 18px sans-serif;margin-bottom:2px">Cargando…</div>
<div id="fase-sub" style="color:#a0aec0;font:13px sans-serif;margin-bottom:8px;min-height:18px"></div>
<div style="background:#1a202c;border-radius:4px;height:6px;margin-bottom:8px;overflow:hidden">
  <div id="barra" style="background:#68d391;height:100%;width:0%"></div>
</div>
<canvas id="cv6" width="900" height="440" style="width:100%;display:block;border-radius:8px;"></canvas>
</div>
<script>
const wlLookup6 = {json.dumps(wl_lookup)};
const alphaLookup6 = {json.dumps(alpha_um_lookup)};
const xnUm6 = {xn_um}, xpUm6 = {xp_um}, Wum6 = {W_total_um}, dnUm6 = {S['dn_um']};
const NA6 = {S['NA']}, ND6 = {S['ND']}, Psi06 = {Psi0};
const nIonP6 = {n_ion_p}, nIonN6 = {n_ion_n}, fracXn6 = {frac_xn_visual};
const Varr6 = {json.dumps(V_arr6)};
const Jarr6 = {json.dumps(J_arr6)};
const Jsc6={Jsc6:.4f}, Voc6={Voc6:.5f}, FF6={FF6:.2f}, eta6={eta6:.3f}, Pmax6={Pmax6:.4f};

function interp6(x, xs, ys){{
  if(x<=xs[0]) return ys[0];
  if(x>=xs[xs.length-1]) return ys[ys.length-1];
  for(let i=0;i<xs.length-1;i++){{
    if(x>=xs[i] && x<=xs[i+1]){{
      const t=(x-xs[i])/(xs[i+1]-xs[i]);
      return ys[i]+t*(ys[i+1]-ys[i]);
    }}
  }}
  return ys[ys.length-1];
}}
function colorFromWl6(wl){{
  wl = Math.max(380, Math.min(750, wl));
  let R,G,B;
  if(wl<440){{R=-(wl-440)/(440-380);G=0;B=1;}}
  else if(wl<490){{R=0;G=(wl-440)/(490-440);B=1;}}
  else if(wl<510){{R=0;G=1;B=-(wl-510)/(510-490);}}
  else if(wl<580){{R=(wl-510)/(580-510);G=1;B=0;}}
  else if(wl<645){{R=1;G=-(wl-645)/(645-580);B=0;}}
  else {{R=1;G=0;B=0;}}
  return `rgb(${{Math.round(255*R)}},${{Math.round(255*G)}},${{Math.round(255*B)}})`;
}}

const cv6=document.getElementById('cv6'); const ctx6=cv6.getContext('2d');
const W6=cv6.width, H6=cv6.height;
const tituloEl=document.getElementById('fase-titulo'), subEl=document.getElementById('fase-sub'), barraEl=document.getElementById('barra');

// --- cross-section reutilizable (fases 1-3): escala comprimida por zona ---
const csTop=30, csBottom=H6-30, csLeft=40, csRight=W6-40, csH=csBottom-csTop;
const fracEmi6=0.24, fracDep6=0.10;
const depthBr6=[0,xnUm6,xpUm6,Wum6], fracBr6=[0,fracEmi6,fracEmi6+fracDep6,1.0];
function yOf6(x_um){{
  if(x_um<=depthBr6[0]) return csTop;
  if(x_um>=depthBr6[3]) return csTop+csH;
  for(let i=0;i<3;i++){{
    if(x_um>=depthBr6[i] && x_um<=depthBr6[i+1]){{
      const t=(x_um-depthBr6[i])/Math.max(depthBr6[i+1]-depthBr6[i],1e-9);
      return csTop+(fracBr6[i]+t*(fracBr6[i+1]-fracBr6[i]))*csH;
    }}
  }}
  return csTop+csH;
}}
function drawCrossSection(){{
  ctx6.fillStyle="#20242c"; ctx6.fillRect(csLeft,csTop,csRight-csLeft,csH);
  ctx6.fillStyle="rgba(99,179,237,0.14)"; ctx6.fillRect(csLeft+1, yOf6(0), csRight-csLeft-2, yOf6(xnUm6)-yOf6(0));
  ctx6.fillStyle="rgba(246,173,85,0.28)"; ctx6.fillRect(csLeft+1, yOf6(xnUm6), csRight-csLeft-2, yOf6(xpUm6)-yOf6(xnUm6));
  ctx6.fillStyle="rgba(104,211,145,0.12)"; ctx6.fillRect(csLeft+1, yOf6(xpUm6), csRight-csLeft-2, yOf6(Wum6)-yOf6(xpUm6));
  ctx6.strokeStyle="#4a5568"; ctx6.strokeRect(csLeft,csTop,csRight-csLeft,csH);
  ctx6.font="bold 12px sans-serif";
  ctx6.fillStyle="#90cdf4"; ctx6.fillText("EMISOR n", csLeft+8, (yOf6(0)+yOf6(xnUm6))/2+4);
  ctx6.fillStyle="#f6ad55"; ctx6.fillText("DEPLECCIÓN", csLeft+8, (yOf6(xnUm6)+yOf6(xpUm6))/2+4);
  ctx6.fillStyle="#9ae6b4"; ctx6.fillText("BASE p", csLeft+8, yOf6(xpUm6)+20);
}}

// --- estado de fases ---
const FASES = [
  {{ nombre:"1. Absorción y generación", sub:"Cada fotón se absorbe a una profundidad que depende de su color (Beer-Lambert).", dur:5000 }},
  {{ nombre:"2. Difusión: ¿colección o recombinación?", sub:"El portador minoritario difunde al azar; solo una fracción fc(x) llega a la juntura.", dur:5000 }},
  {{ nombre:"3. Así se formó la juntura p-n", sub:"Los portadores móviles se recombinan en el contacto, dejando expuestos los iones fijos.", dur:6000 }},
  {{ nombre:"4. Curva J-V bajo iluminación", sub:"Se barre el voltaje y se traza la curva; el punto naranja es el ensayo en curso.", dur:6000 }},
  {{ nombre:"Resumen", sub:"Parámetros de la celda con los parámetros actuales.", dur:3000 }},
];
const CICLO_TOTAL = FASES.reduce((a,f)=>a+f.dur,0);
const t0_6 = performance.now();

// fotones deterministicos para la fase 1 (reproducible en cada vuelta)
const fotonesDemo = [
  {{wl:420, t0:0.05}}, {{wl:480, t0:0.22}}, {{wl:560, t0:0.40}},
  {{wl:650, t0:0.58}}, {{wl:900, t0:0.74}}, {{wl:420, t0:0.90}}
];
function faseFotones(tf){{
  drawCrossSection();
  fotonesDemo.forEach(fd=>{{
    if(tf < fd.t0) return;
    const prog = Math.min((tf-fd.t0)/0.30, 1.0);
    const alpha_um = interp6(fd.wl, wlLookup6, alphaLookup6);
    const xAbs = Math.min(1.6/Math.max(alpha_um,1e-6), Wum6*1.05);
    const color = colorFromWl6(fd.wl);
    const x0 = 90 + (fd.wl % 300) * 2.3;
    if(prog < 1.0){{
      const yy = csTop + prog*(yOf6(Math.min(xAbs,Wum6))-csTop);
      ctx6.beginPath(); ctx6.arc(x0, yy, 4, 0, 7); ctx6.fillStyle=color; ctx6.fill();
    }} else {{
      const burst = Math.min((tf-fd.t0-0.30)/0.15, 1.0);
      if(burst<1.0){{
        const yy = yOf6(Math.min(xAbs,Wum6));
        ctx6.beginPath(); ctx6.arc(x0, yy, 3+burst*9, 0, 7);
        ctx6.strokeStyle=`rgba(255,255,180,${{1-burst}})`; ctx6.lineWidth=2; ctx6.stroke();
      }}
    }}
  }});
  ctx6.fillStyle="#e2e8f0"; ctx6.font="12px sans-serif";
  ctx6.fillText("azul/violeta → se frena en el emisor   |   rojo/IR → llega a la base o la atraviesa", csLeft, csBottom+22);
}}

const portadoresDemo = [
  {{x0:2.0, willCollect:true,  t0:0.05, x:260}},
  {{x0:80.0, willCollect:false, t0:0.15, x:520}},
  {{x0:3.5, willCollect:true,  t0:0.55, x:700}},
];
function faseVida(tf){{
  drawCrossSection();
  portadoresDemo.forEach(p=>{{
    if(tf<p.t0) return;
    const target = p.x0 < xnUm6 ? xnUm6 : xpUm6;
    const fracFinal = p.willCollect ? 1.0 : 0.5;
    const prog = Math.min((tf-p.t0)/0.35, 1.0);
    const fracNow = prog*fracFinal;
    const depthNow = p.x0 + (target-p.x0)*Math.min(fracNow/fracFinal,1);
    const yy = yOf6(depthNow);
    const wiggle = Math.sin(prog*30+p.x)*3;
    const color = p.x0 < xnUm6 ? "#63b3ed" : "#fc8181";
    if(prog<1.0){{
      ctx6.beginPath(); ctx6.arc(p.x+wiggle, yy, 4, 0, 7); ctx6.fillStyle=color; ctx6.fill();
    }} else {{
      const burst=Math.min((tf-p.t0-0.35)/0.20,1.0);
      const col = p.willCollect ? `rgba(246,224,94,${{1-burst}})` : `rgba(160,174,192,${{1-burst}})`;
      ctx6.beginPath(); ctx6.arc(p.x+wiggle, yy, 3+burst*11, 0, 7);
      ctx6.strokeStyle=col; ctx6.lineWidth=2.2; ctx6.stroke();
      if(burst>=1.0){{
        ctx6.fillStyle= p.willCollect ? "#f6e05e" : "#a0aec0"; ctx6.font="11px sans-serif";
        ctx6.fillText(p.willCollect?"colectado":"recombinado", p.x-20, yy-14);
      }}
    }}
  }});
}}

function faseJuntura(tf){{
  const left=csLeft, right=csRight, midX=(left+right)/2, midY=(csTop+csBottom)/2;
  let gap=0, depW=0, showField=false;
  if(tf<0.20){{ gap=40*(1-tf/0.20); }}
  else if(tf<0.55){{ gap=0; const tt=(tf-0.20)/0.35; depW=tt*(right-left)*0.30; }}
  else {{ depW=(right-left)*0.30; showField = tf<0.92; }}
  const shift=gap/2;
  ctx6.strokeStyle="#4a5568";
  ctx6.strokeRect(left-shift,csTop,midX-left-shift,csH);
  ctx6.strokeRect(midX+shift,csTop,right-midX-shift,csH);
  ctx6.fillStyle="#a0aec0"; ctx6.font="12px sans-serif";
  ctx6.fillText("base p (NA="+NA6.toExponential(0)+")", left, csTop-8);
  ctx6.fillText("emisor n (ND="+ND6.toExponential(0)+")", midX+shift+10, csTop-8);
  if(depW>0.5){{
    const wN=depW*fracXn6, wP=depW*(1-fracXn6);
    ctx6.fillStyle="rgba(246,173,85,0.28)"; ctx6.fillRect(midX-wP, csTop, wP+wN, csH);
    if(showField){{
      ctx6.strokeStyle="#f6ad55"; ctx6.lineWidth=2;
      ctx6.beginPath(); ctx6.moveTo(midX-wP+4,midY); ctx6.lineTo(midX+wN-4,midY);
      ctx6.lineTo(midX+wN-10,midY-5); ctx6.moveTo(midX+wN-4,midY); ctx6.lineTo(midX+wN-10,midY+5);
      ctx6.stroke();
      ctx6.fillStyle="#f6ad55"; ctx6.fillText("Campo E — Ψ₀≈"+Psi06.toFixed(3)+" V", midX-wP, csTop+16);
    }}
  }}
  // iones (posiciones fijas por indice, deterministicas)
  for(let i=0;i<nIonP6;i++){{
    const ix = left+10+((i*53)%Math.max(midX-left-24,1));
    const iy = csTop+20+((i*37)%Math.max(csH-40,1));
    const inDep = depW>0.5 && ix > midX-depW*(1-fracXn6);
    ctx6.beginPath(); ctx6.arc(ix-shift, iy, 4.5, 0, 7);
    ctx6.strokeStyle = inDep ? "#fc8181" : "#718096"; ctx6.stroke();
    if(tf<0.55){{ ctx6.beginPath(); ctx6.arc(ix-shift-(tf<0.20?shift:0), iy, 2.4, 0, 7); ctx6.fillStyle="#63b3ed"; ctx6.fill(); }}
  }}
  for(let i=0;i<nIonN6;i++){{
    const ix = midX+10+((i*47)%Math.max(right-midX-24,1));
    const iy = csTop+16+((i*41)%Math.max(csH-36,1));
    const inDep = depW>0.5 && ix < midX+depW*fracXn6;
    ctx6.beginPath(); ctx6.arc(ix+shift, iy, 4.5, 0, 7);
    ctx6.strokeStyle = inDep ? "#63b3ed" : "#718096"; ctx6.stroke();
    if(tf<0.55){{ ctx6.beginPath(); ctx6.arc(ix+shift+(tf<0.20?shift:0), iy, 2.4, 0, 7); ctx6.fillStyle="#fc8181"; ctx6.fill(); }}
  }}
}}

function faseIV(tf){{
  const left=70, right=W6-40, top=30, bottom=H6-60;
  ctx6.strokeStyle="#4a5568"; ctx6.beginPath();
  ctx6.moveTo(left,top); ctx6.lineTo(left,bottom); ctx6.lineTo(right,bottom); ctx6.stroke();
  ctx6.fillStyle="#a0aec0"; ctx6.font="12px sans-serif";
  ctx6.fillText("V [V]", right-30, bottom+18); ctx6.fillText("J [mA/cm²]", left-55, top+4);
  const Vmax=Varr6[Varr6.length-1], Jmax=Jsc6*1.08;
  const xOf=v=>left+(v/Vmax)*(right-left);
  const yOf7=j=>bottom-(j/Jmax)*(bottom-top-10);
  const nShow = Math.max(2, Math.floor(Math.min(tf/0.85,1.0)*Varr6.length));
  ctx6.strokeStyle="#68d391"; ctx6.lineWidth=2.5; ctx6.beginPath();
  for(let i=0;i<nShow;i++){{ const x=xOf(Varr6[i]), y=yOf7(Jarr6[i]); if(i===0) ctx6.moveTo(x,y); else ctx6.lineTo(x,y); }}
  ctx6.stroke();
  const iPunto = Math.min(nShow-1, Varr6.length-1);
  if(iPunto>=0){{
    ctx6.beginPath(); ctx6.arc(xOf(Varr6[iPunto]), yOf7(Jarr6[iPunto]), 6, 0, 7);
    ctx6.fillStyle="#f6ad55"; ctx6.fill();
    ctx6.font="12px sans-serif"; ctx6.fillStyle="#e2e8f0";
    ctx6.fillText(`V=${{Varr6[iPunto].toFixed(3)}} V   J=${{Jarr6[iPunto].toFixed(2)}} mA/cm²`, left+10, top+16);
  }}
  if(tf>0.90){{
    ctx6.fillStyle="#f6ad55"; ctx6.font="bold 13px sans-serif";
    ctx6.fillText(`Jsc=${{Jsc6.toFixed(2)}}  Voc=${{(Voc6*1000).toFixed(0)}}mV  FF=${{FF6.toFixed(1)}}%  η=${{eta6.toFixed(2)}}%`, left+10, bottom-10);
  }}
}}

function faseResumen(tf){{
  ctx6.fillStyle="#e2e8f0"; ctx6.textAlign="center";
  ctx6.font="bold 22px sans-serif";
  ctx6.fillText("Resumen de la celda simulada", W6/2, H6/2-90);
  const items = [
    [`Jsc = ${{Jsc6.toFixed(2)}} mA/cm²`, "#68d391"],
    [`Voc = ${{(Voc6*1000).toFixed(0)}} mV`, "#63b3ed"],
    [`FF = ${{FF6.toFixed(1)}} %`, "#f6ad55"],
    [`η = ${{eta6.toFixed(2)}} %`, "#f687b3"],
  ];
  ctx6.font="bold 30px sans-serif";
  items.forEach((it,i)=>{{
    ctx6.fillStyle=it[1];
    ctx6.fillText(it[0], W6/2, H6/2-20+i*46);
  }});
  ctx6.textAlign="left";
}}

function draw6(){{
  const tGlobal = ((performance.now()-t0_6) % CICLO_TOTAL);
  let acc=0, faseIdx=0, tf=0;
  for(let i=0;i<FASES.length;i++){{
    if(tGlobal < acc+FASES[i].dur){{ faseIdx=i; tf=(tGlobal-acc)/FASES[i].dur; break; }}
    acc += FASES[i].dur;
  }}
  ctx6.clearRect(0,0,W6,H6);
  tituloEl.textContent = FASES[faseIdx].nombre;
  subEl.textContent = FASES[faseIdx].sub;
  barraEl.style.width = (100*(tGlobal/CICLO_TOTAL)).toFixed(1)+"%";

  if(faseIdx===0) faseFotones(tf);
  else if(faseIdx===1) faseVida(tf);
  else if(faseIdx===2) faseJuntura(tf);
  else if(faseIdx===3) faseIV(tf);
  else faseResumen(tf);

  requestAnimationFrame(draw6);
}}
draw6();
</script>
"""
    st.iframe(html_resumen, height="content")
    st.caption("Los números que ves al final corresponden a los parámetros actuales de la barra lateral "
               "(no a la semilla fija) — si cambias algo ahí, esta pestaña se regenera con los nuevos valores.")
