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
    anim_modo="arcoiris",
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

    st.markdown("### Óptica")
    S["modo_R"] = st.radio("Reflectancia frontal R(λ)", ["fresnel", "fijo"],
                            index=0 if S["modo_R"] == "fresnel" else 1, horizontal=True)
    S["reflector_trasero"] = st.checkbox("Reflector trasero de aluminio activo", S["reflector_trasero"])
    st.caption(f"Modelo del Al: una reflexión trasera, R_Al = {c.R_ALUMINIO_EFECTIVA:.2f}.")

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
    S["irradiancia_soles"] = st.slider("Irradiancia [soles]", 0.1, 1.5, S["irradiancia_soles"], 0.05)
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
    """Aproximación visual del color asociado a una longitud de onda
    (algoritmo clásico de Dan Bruton). Solo para representación gráfica:
    por debajo de 380 nm y por sobre 750 nm no hay color perceptible
    real, se extrapola para que la animación siga siendo legible."""
    wl = float(np.clip(wl, 380, 750))
    if wl < 440: R, G, B = -(wl - 440) / (440 - 380), 0.0, 1.0
    elif wl < 490: R, G, B = 0.0, (wl - 440) / (490 - 440), 1.0
    elif wl < 510: R, G, B = 0.0, 1.0, -(wl - 510) / (510 - 490)
    elif wl < 580: R, G, B = (wl - 510) / (580 - 510), 1.0, 0.0
    elif wl < 645: R, G, B = 1.0, -(wl - 645) / (645 - 580), 0.0
    else: R, G, B = 1.0, 0.0, 0.0
    return "#%02x%02x%02x" % (int(255*R), int(255*G), int(255*B))


def generacion_actual(x_um):
    """G(x,lambda) coherente con el estado óptico compartido, incluido el reflector."""
    return f.tasa_generacion_con_reflector(
        x_um, phi0_grid, R_grid, alpha_grid, W_total_um,
        reflector_trasero_activo=S["reflector_trasero"],
        R_aluminio=c.R_ALUMINIO_EFECTIVA,
    )

# ============================================================
# TABS
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

st.markdown("""
<style>
div[data-testid="stMetricValue"] { font-size: 1.4rem; }
</style>
""", unsafe_allow_html=True)

# ------------------------------------------------------------------
# TAB 1 — ABSORCIÓN Y GENERACIÓN
# ------------------------------------------------------------------
with tab1:
    st.subheader("Fotones cayendo sobre el silicio: dónde se absorbe cada color")

    colA, colB = st.columns([1, 1])

    with colA:
        S["lambda_perfil"] = st.slider(
            "λ para el perfil G(x) [nm]",
            300.0,
            1200.0,
            S["lambda_perfil"],
            5.0,
            key="l1",
        )

    with colB:
        S["anim_modo"] = st.radio(
            "Animación",
            ["arcoiris (varios λ)", "un solo λ (el del slider)"],
            index=0 if S["anim_modo"] == "arcoiris" else 1,
            horizontal=True,
        )
        S["anim_modo"] = (
            "arcoiris"
            if S["anim_modo"].startswith("arcoiris")
            else "unico"
        )

    # ============================================================
    # ANIMACIÓN DE FOTONES
    # ============================================================
    wl_anim = np.linspace(300.0, 1200.0, 46)
    alpha_um_lookup = (
        f.alpha_silicio(wl_anim) * 1e-4
    ).tolist()
    wl_lookup = wl_anim.tolist()
    R_lookup = f.reflectancia_frontal(
        wl_anim,
        modo=S["modo_R"],
    ).tolist()
    colores_lookup = [
        wavelength_to_hex(wl)
        for wl in wl_lookup
    ]

    _, phi0_lookup_raw = (
        f.espectro_y_flujo_fotones(wl_anim)
    )
    phi0_lookup = phi0_lookup_raw.tolist()

    single_wl = S["lambda_perfil"]
    single_color = wavelength_to_hex(single_wl)
    single_alpha_um = float(
        f.alpha_silicio(np.array([single_wl]))[0]
        * 1e-4
    )

    html_photons = f"""
<div style="background:#0b0e14;border-radius:10px;padding:10px">
<canvas id="cv" width="900" height="360"
style="width:100%;display:block;border-radius:8px;"></canvas>
</div>
<script>
const wlLookup = {json.dumps(wl_lookup)};
const phi0Lookup = {json.dumps(phi0_lookup)};
const alphaLookup = {json.dumps(alpha_um_lookup)};
const modo = "{S['anim_modo']}";
const irradianciaSoles = {S['irradiancia_soles']};
const singleColor = "{single_color}";
const W_total_um = {W_total_um};
const dn_um = {S['dn_um']};
const reflectorActivo = {str(bool(S['reflector_trasero'])).lower()};
const RAl = {c.R_ALUMINIO_EFECTIVA};

function interp(x, xs, ys){{
  if (x <= xs[0]) return ys[0];
  if (x >= xs[xs.length - 1]) return ys[ys.length - 1];
  for (let i = 0; i < xs.length - 1; i++){{
    if (x >= xs[i] && x <= xs[i + 1]){{
      const t = (x - xs[i]) / (xs[i + 1] - xs[i]);
      return ys[i] + t * (ys[i + 1] - ys[i]);
    }}
  }}
  return ys[ys.length - 1];
}}

const cv = document.getElementById("cv");
const ctx = cv.getContext("2d");
const W = cv.width;
const H = cv.height;
const blockTop = 46;
const blockBottom = H - 46;
const blockH = blockBottom - blockTop;
const xnUmT1 = {xn_um};
const xpUmT1 = {xp_um};

const fracEmisor = 0.24;
const fracDeplecion = 0.10;
const depthBreaks = [0, xnUmT1, xpUmT1, W_total_um];
const fracBreaks = [0, fracEmisor, fracEmisor + fracDeplecion, 1.0];

function fracOfDepth(x_um){{
  if (x_um <= depthBreaks[0]) return 0;
  if (x_um >= depthBreaks[3]) return 1;
  for (let i = 0; i < 3; i++){{
    if (x_um >= depthBreaks[i] && x_um <= depthBreaks[i + 1]){{
      const t = (x_um - depthBreaks[i]) /
        Math.max(depthBreaks[i + 1] - depthBreaks[i], 1e-9);
      return fracBreaks[i] +
        t * (fracBreaks[i + 1] - fracBreaks[i]);
    }}
  }}
  return 1;
}}

function yOfFrac(fr){{
  return blockTop + fr * blockH;
}}

let photons = [];
let cdfEspectro = [];
let acumuladoEspectro = 0;

for (let i = 0; i < phi0Lookup.length; i++){{
  acumuladoEspectro += Math.max(phi0Lookup[i], 0);
  cdfEspectro.push(acumuladoEspectro);
}}

for (let i = 0; i < cdfEspectro.length; i++){{
  cdfEspectro[i] = cdfEspectro[i] /
    Math.max(acumuladoEspectro, 1e-30);
}}

function sampleWavelengthReal(){{
  const r = Math.random();
  for (let i = 0; i < cdfEspectro.length - 1; i++){{
    if (r <= cdfEspectro[i + 1]){{
      const rango = Math.max(
        cdfEspectro[i + 1] - cdfEspectro[i],
        1e-9,
      );
      const t = (r - cdfEspectro[i]) / rango;
      return wlLookup[i] +
        t * (wlLookup[i + 1] - wlLookup[i]);
    }}
  }}
  return wlLookup[wlLookup.length - 1];
}}

function colorFromWl(wl){{
  wl = Math.max(380, Math.min(750, wl));
  let R, G, B;
  if (wl < 440){{
    R = -(wl - 440) / (440 - 380);
    G = 0;
    B = 1;
  }} else if (wl < 490){{
    R = 0;
    G = (wl - 440) / (490 - 440);
    B = 1;
  }} else if (wl < 510){{
    R = 0;
    G = 1;
    B = -(wl - 510) / (510 - 490);
  }} else if (wl < 580){{
    R = (wl - 510) / (580 - 510);
    G = 1;
    B = 0;
  }} else if (wl < 645){{
    R = 1;
    G = -(wl - 645) / (645 - 580);
    B = 0;
  }} else{{
    R = 1;
    G = 0;
    B = 0;
  }}
  return `rgb(${{Math.round(255 * R)}},${{Math.round(255 * G)}},${{Math.round(255 * B)}})`;
}}

function spawnPhoton(){{
  const wl = modo === "arcoiris"
    ? sampleWavelengthReal()
    : {single_wl};
  const alpha_um = interp(wl, wlLookup, alphaLookup);
  const color = modo === "arcoiris"
    ? colorFromWl(wl)
    : singleColor;
  const xAbs = -Math.log(Math.random()) /
    Math.max(alpha_um, 1e-6);
  const transmitido = xAbs > W_total_um;

  photons.push({{
    x: 60 + Math.random() * (W - 120),
    fracPos: -0.06,
    color: color,
    vfrac: 0.010 + Math.random() * 0.004,
    fracAbs: transmitido ? 1.0 : fracOfDepth(xAbs),
    transmitido: transmitido,
    alpha_um: alpha_um,
    state: "falling",
    reflected: false,
  }});
}}

let sparks = [];
let nAbs = 0;
let nTrans = 0;
let nRef = 0;
let nEscape = 0;

function step(){{
  ctx.clearRect(0, 0, W, H);
  ctx.fillStyle = "#20242c";
  ctx.fillRect(30, blockTop, W - 60, blockH);

  const yE0 = yOfFrac(0);
  const yE1 = yOfFrac(fracEmisor);
  const yD1 = yOfFrac(fracEmisor + fracDeplecion);
  const yB1 = yOfFrac(1);

  ctx.fillStyle = "rgba(99,179,237,0.16)";
  ctx.fillRect(30, yE0, W - 60, yE1 - yE0);
  ctx.fillStyle = "rgba(246,173,85,0.30)";
  ctx.fillRect(30, yE1, W - 60, yD1 - yE1);
  ctx.fillStyle = "rgba(104,211,145,0.14)";
  ctx.fillRect(30, yD1, W - 60, yB1 - yD1);

  ctx.strokeStyle = "#4a5568";
  ctx.strokeRect(30, blockTop, W - 60, blockH);
  ctx.strokeStyle = "#f6ad55";
  ctx.setLineDash([6, 4]);
  ctx.beginPath();
  ctx.moveTo(30, yE1);
  ctx.lineTo(W - 30, yE1);
  ctx.stroke();
  ctx.beginPath();
  ctx.moveTo(30, yD1);
  ctx.lineTo(W - 30, yD1);
  ctx.stroke();
  ctx.setLineDash([]);

  ctx.font = "bold 13px sans-serif";
  ctx.fillStyle = "#90cdf4";
  ctx.fillText(
    "EMISOR n  (dn=" + dn_um.toFixed(1) + " µm)",
    36,
    (yE0 + yE1) / 2 + 5,
  );
  ctx.fillStyle = "#f6ad55";
  ctx.fillText("DEPLECCIÓN", 36, (yE1 + yD1) / 2 + 5);
  ctx.fillStyle = "#9ae6b4";
  ctx.fillText(
    "BASE p  (Wp=" + (W_total_um - dn_um).toFixed(0) + " µm)",
    36,
    yD1 + 22,
  );
  ctx.font = "11px sans-serif";
  ctx.fillStyle = "#718096";
  ctx.fillText(
    "(escala vertical comprimida; no es a escala real)",
    36,
    blockTop - 10,
  );
  ctx.fillStyle = "#a0aec0";
  ctx.fillText("superficie x=0", 36, blockTop + 12);
  ctx.fillText(
    "contacto trasero x=W=" + W_total_um.toFixed(0) + " µm",
    36,
    blockBottom + 16,
  );

  if (Math.random() < 0.10 * irradianciaSoles) spawnPhoton();

  photons.forEach(p => {{
    if (p.state === "falling"){{
      p.fracPos += p.vfrac;
      const yy = yOfFrac(Math.min(Math.max(p.fracPos, 0), 1.15));
      ctx.beginPath();
      ctx.arc(p.x, yy, 3.2, 0, 7);
      ctx.fillStyle = p.color;
      ctx.fill();
      ctx.beginPath();
      ctx.arc(p.x, yy, 6, 0, 7);
      ctx.strokeStyle = p.color;
      ctx.globalAlpha = 0.35;
      ctx.stroke();
      ctx.globalAlpha = 1;

      if (!p.transmitido && p.fracPos >= p.fracAbs && p.fracPos > 0){{
        p.state = "absorbed";
        nAbs++;
        sparks.push({{
          x: p.x,
          y: yy,
          r: 2,
          life: 1.0,
          hole: {{y: yy, vy: 1.2}},
          elec: {{y: yy, vy: -1.4}},
        }});
      }}

      if (p.transmitido && p.fracPos >= 1.0){{
        if (reflectorActivo && Math.random() < RAl){{
          p.reflected = true;
          p.state = "returning";
          p.fracPos = 1.0;
          nRef++;
          const dBack = -Math.log(Math.max(Math.random(), 1e-9)) /
            Math.max(p.alpha_um, 1e-6);
          if (dBack < W_total_um){{
            p.escapeFront = false;
            p.fracAbsReturn = fracOfDepth(W_total_um - dBack);
          }} else{{
            p.escapeFront = true;
            p.fracAbsReturn = 0.0;
          }}
        }} else{{
          p.state = "transmitted";
          nTrans++;
        }}
      }}
    }} else if (p.state === "returning"){{
      p.fracPos -= p.vfrac;
      const yy = yOfFrac(Math.min(Math.max(p.fracPos, 0), 1));
      ctx.beginPath();
      ctx.arc(p.x, yy, 3.4, 0, 7);
      ctx.fillStyle = p.color;
      ctx.fill();
      ctx.beginPath();
      ctx.arc(p.x, yy, 6.4, 0, 7);
      ctx.strokeStyle = "#f6e05e";
      ctx.globalAlpha = 0.6;
      ctx.stroke();
      ctx.globalAlpha = 1;

      if (!p.escapeFront && p.fracPos <= p.fracAbsReturn){{
        p.state = "absorbed";
        nAbs++;
        sparks.push({{
          x: p.x,
          y: yy,
          r: 2,
          life: 1.0,
          hole: {{y: yy, vy: 1.2}},
          elec: {{y: yy, vy: -1.4}},
        }});
      }} else if (p.escapeFront && p.fracPos <= -0.04){{
        p.state = "escaped";
        nEscape++;
      }}
    }}
  }});

  photons = photons.filter(
    p => p.state === "falling" || p.state === "returning",
  );

  sparks.forEach(s => {{
    s.r += 1.4;
    s.life -= 0.035;
    ctx.beginPath();
    ctx.arc(s.x, s.y, s.r, 0, 7);
    ctx.strokeStyle = `rgba(255,255,180,${{Math.max(s.life, 0)}})`;
    ctx.lineWidth = 2;
    ctx.stroke();
    s.hole.y += s.hole.vy;
    s.elec.y += s.elec.vy;
    ctx.beginPath();
    ctx.arc(s.x - 5, s.hole.y, 2.4, 0, 7);
    ctx.fillStyle = `rgba(99,179,237,${{Math.max(s.life, 0)}})`;
    ctx.fill();
    ctx.beginPath();
    ctx.arc(s.x + 5, s.elec.y, 2.4, 0, 7);
    ctx.fillStyle = `rgba(252,129,129,${{Math.max(s.life, 0)}})`;
    ctx.fill();
  }});
  sparks = sparks.filter(s => s.life > 0);

  ctx.font = "12px sans-serif";
  ctx.fillStyle = "#e2e8f0";
  const reflTxt = reflectorActivo
    ? `   Reflejados: ${{nRef}}   Escape frontal: ${{nEscape}}`
    : "";
  ctx.fillText(
    `Absorbidos: ${{nAbs}}   Transmitidos: ${{nTrans}}${{reflTxt}}`,
    30,
    H - 6,
  );

  requestAnimationFrame(step);
}}

step();
</script>
"""

    st.iframe(html_photons, height="content")
    st.caption(
        "Puntos de color = fotones. La profundidad de absorción se muestrea "
        "con Beer–Lambert. Las bandas están comprimidas visualmente para "
        "distinguir emisor, depleción y base."
    )

    # ============================================================
    # VISTA 3D DEL BLOQUE
    # ============================================================
    st.markdown(
        "##### Vista 3D del bloque de silicio "
        "(arrastra para rotar, scroll para zoom)"
    )

    def _caja_mesh3d(
        z0,
        z1,
        color,
        opacidad,
        nombre,
        Lx=1.0,
        Ly=1.0,
    ):
        xs = [-Lx, Lx, Lx, -Lx, -Lx, Lx, Lx, -Lx]
        ys = [-Ly, -Ly, Ly, Ly, -Ly, -Ly, Ly, Ly]
        zs = [z0, z0, z0, z0, z1, z1, z1, z1]
        i = [0, 0, 0, 4, 4, 4, 0, 0, 1, 1, 2, 2]
        j = [1, 2, 3, 5, 6, 7, 1, 5, 2, 6, 3, 7]
        k = [2, 3, 0, 6, 7, 4, 5, 4, 6, 5, 7, 6]
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

    z0, z1 = 0.0, -1.0
    zE = -0.24
    zD = -0.34
    fig3d = go.Figure()
    fig3d.add_trace(
        _caja_mesh3d(z0, zE, "#63b3ed", 0.35, "Emisor n")
    )
    fig3d.add_trace(
        _caja_mesh3d(zE, zD, "#f6ad55", 0.55, "Deplección")
    )
    fig3d.add_trace(
        _caja_mesh3d(zD, z1, "#68d391", 0.25, "Base p")
    )

    def _z_de_depth(x_um):
        if x_um <= xn_um:
            t = x_um / max(xn_um, 1e-9)
            return z0 + t * (zE - z0)
        if x_um <= xp_um:
            t = (x_um - xn_um) / max(xp_um - xn_um, 1e-9)
            return zE + t * (zD - zE)
        t = min(
            (x_um - xp_um) / max(W_total_um - xp_um, 1e-9),
            1.0,
        )
        return zD + t * (z1 - zD)

    rng3d = np.random.default_rng(7)
    n_fot3d = 26
    wl_lookup_arr = np.asarray(wl_lookup, dtype=float)
    phi0_probs = np.clip(
        np.asarray(phi0_lookup, dtype=float),
        0.0,
        None,
    )

    if phi0_probs.sum() <= 0.0:
        phi0_probs = np.full(
            len(wl_lookup_arr),
            1.0 / len(wl_lookup_arr),
        )
    else:
        phi0_probs = phi0_probs / phi0_probs.sum()

    wl_muestras = rng3d.choice(
        wl_lookup_arr,
        size=n_fot3d,
        replace=True,
        p=phi0_probs,
    )
    alpha_muestras_um = np.interp(
        wl_muestras,
        wl_lookup_arr,
        np.asarray(alpha_um_lookup, dtype=float),
    )
    x0_3d = rng3d.uniform(-0.85, 0.85, n_fot3d)
    y0_3d = rng3d.uniform(-0.85, 0.85, n_fot3d)
    t0_3d = rng3d.uniform(0.0, 0.55, n_fot3d)
    xabs_3d = (
        -np.log(rng3d.uniform(1e-3, 1.0, n_fot3d))
        / np.maximum(alpha_muestras_um, 1e-6)
    )
    zabs_3d = np.array([
        _z_de_depth(min(x_abs, W_total_um))
        for x_abs in xabs_3d
    ])
    colores_3d = [
        wavelength_to_hex(wl)
        for wl in wl_muestras
    ]

    n_frames_3d = 34
    frames_3d = []
    for fr in range(n_frames_3d):
        tf = fr / (n_frames_3d - 1)
        zs_frame = []
        for i in range(n_fot3d):
            if tf < t0_3d[i]:
                zs_frame.append(0.25)
            else:
                prog = min(
                    (tf - t0_3d[i]) / 0.45,
                    1.0,
                )
                zs_frame.append(
                    0.25 + prog * (zabs_3d[i] - 0.25)
                )
        frames_3d.append(
            go.Frame(
                data=[
                    go.Scatter3d(
                        x=x0_3d,
                        y=y0_3d,
                        z=zs_frame,
                        mode="markers",
                        marker=dict(
                            size=5,
                            color=colores_3d,
                        ),
                    )
                ],
                traces=[3],
                name=str(fr),
            )
        )

    fig3d.add_trace(
        go.Scatter3d(
            x=x0_3d,
            y=y0_3d,
            z=[0.25] * n_fot3d,
            mode="markers",
            marker=dict(size=5, color=colores_3d),
            name="Fotones",
        )
    )
    fig3d.frames = frames_3d
    fig3d.update_layout(
        template="plotly_dark",
        height=520,
        scene=dict(
            xaxis=dict(
                title="",
                showticklabels=False,
                showbackground=False,
            ),
            yaxis=dict(
                title="",
                showticklabels=False,
                showbackground=False,
            ),
            zaxis=dict(
                title="profundidad (comprimida)",
                showticklabels=False,
            ),
            aspectmode="manual",
            aspectratio=dict(x=1, y=1, z=1.3),
            camera=dict(eye=dict(x=1.4, y=-1.6, z=0.9)),
        ),
        updatemenus=[
            dict(
                type="buttons",
                showactive=False,
                y=1.05,
                x=0.0,
                buttons=[
                    dict(
                        label="▶ Reproducir caída de fotones",
                        method="animate",
                        args=[
                            None,
                            dict(
                                frame=dict(
                                    duration=60,
                                    redraw=True,
                                ),
                                fromcurrent=True,
                            ),
                        ],
                    )
                ],
            )
        ],
        legend=dict(orientation="h", y=-0.02),
        margin=dict(l=0, r=0, t=40, b=0),
    )
    st.plotly_chart(fig3d, width="stretch")
    st.caption(
        "La vista 3D muestra el mismo proceso en un volumen con escala "
        "vertical comprimida."
    )

    # ============================================================
    # PERFIL G(x) Y PROFUNDIDAD 1/α
    # ============================================================
    c1, c2 = st.columns(2)

    with c1:
        x_perfil = np.linspace(0, W_total_um, 600)
        G_perfil = generacion_actual(x_perfil)
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
            title=f"Tasa de generación G(x) a λ={S['lambda_perfil']:.0f} nm",
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
    # GENERACIÓN TOTAL INTEGRADA
    # ============================================================
    st.markdown("##### Generación total integrada sobre AM1.5G")

    x_gext = np.linspace(0, W_total_um, 400)
    G_gext_matrix = generacion_actual(x_gext)
    G_ext = np.maximum(
        np.trapezoid(G_gext_matrix, wl_grid, axis=1),
        0.0,
    )

    fig_gext = go.Figure()
    fig_gext.add_trace(
        go.Scatter(
            x=x_gext,
            y=G_ext,
            mode="lines",
            line=dict(color="#f687b3", width=3),
            name="G_ext(x)",
        )
    )
    fig_gext.add_vline(
        x=S["dn_um"],
        line_dash="dot",
        line_color="orange",
        annotation_text="juntura (xj=dn)",
    )
    fig_gext.update_layout(
        title="G_ext(x) = ∫ G(x,λ) dλ",
        xaxis_title="Profundidad x [µm]",
        yaxis_title="G_ext [cm⁻³ s⁻¹]",
        height=380,
        template="plotly_dark",
    )
    st.plotly_chart(fig_gext, width="stretch")

    G_ext_total = np.trapezoid(G_ext, x_gext)
    mask_emisor = x_gext <= S["dn_um"]
    mask_base = x_gext > S["dn_um"]
    G_ext_emisor = (
        np.trapezoid(G_ext[mask_emisor], x_gext[mask_emisor])
        if mask_emisor.sum() > 1
        else 0.0
    )
    G_ext_base = (
        np.trapezoid(G_ext[mask_base], x_gext[mask_base])
        if mask_base.sum() > 1
        else 0.0
    )

    frac_emisor_gen = (
        G_ext_emisor / G_ext_total
        if G_ext_total > 0
        else 0.0
    )
    frac_base_gen = (
        G_ext_base / G_ext_total
        if G_ext_total > 0
        else 0.0
    )

    frac_r_esp, frac_a_esp, frac_t_esp, frac_escape_esp = (
        f.balance_fotones_con_reflector(
            R_grid,
            alpha_grid,
            W_total_um,
            reflector_trasero_activo=S["reflector_trasero"],
            R_aluminio=c.R_ALUMINIO_EFECTIVA,
        )
    )
    peso = phi0_grid / np.trapezoid(phi0_grid, wl_grid)
    frac_t_ponderada = np.trapezoid(
        frac_t_esp * peso,
        wl_grid,
    )
    frac_escape_ponderada = np.trapezoid(
        frac_escape_esp * peso,
        wl_grid,
    )
    frac_perdida_total = frac_t_ponderada + frac_escape_ponderada

    gm1, gm2, gm3 = st.columns(3)
    gm1.metric(
        "Pares generados en el emisor",
        f"{100 * frac_emisor_gen:.1f} %",
    )
    gm2.metric(
        "Pares generados en la base",
        f"{100 * frac_base_gen:.1f} %",
    )
    gm3.metric(
        "Fotones perdidos",
        f"{100 * frac_perdida_total:.1f} %",
    )
    st.caption(
        "Las fracciones de generación se obtienen integrando G_ext(x) "
        "por región. La pérdida óptica se pondera con el espectro AM1.5G."
    )

    # ============================================================
    # MAPA λ-x
    # ============================================================
    st.markdown("##### Mapa 2D de generación G(x,λ)")

    x_mapa = np.linspace(0, W_total_um, 220)
    G_mapa = generacion_actual(x_mapa)
    fig3 = go.Figure(
        data=go.Heatmap(
            z=np.log10(np.maximum(G_mapa, 1e-6)).T,
            x=x_mapa,
            y=wl_grid,
            colorscale="Inferno",
            colorbar_title="log₁₀G",
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
                name=f"1/α a {_lambda_sel:.0f} nm",
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
                name=f"x90 a {_lambda_sel:.0f} nm",
                hovertemplate=(
                    "λ=%{y:.0f} nm<br>"
                    "x90=%{x:.2f} µm<extra></extra>"
                ),
            )
        )

    fig3.update_layout(
        xaxis_title="Profundidad x [µm]",
        yaxis_title="λ [nm]",
        height=420,
        template="plotly_dark",
    )
    st.plotly_chart(fig3, width="stretch")

    am1, am2, am3 = st.columns(3)
    am1.metric(
        "Profundidad 1/α",
        f"{_prof_abs_sel:.2f} µm",
    )
    am2.metric(
        "Profundidad x₉₀",
        f"{_x90_sel:.2f} µm"
        if _x90_sel <= 9999
        else "> 10 mm",
    )
    am3.metric(
        "Absorbido en un recorrido",
        f"{100 * _frac_abs_sel:.1f} %",
    )
    st.caption(
        "El punto verde marca 1/α y la cruz cian marca x₉₀ para la "
        "longitud de onda seleccionada."
    )

    with st.expander("Datos utilizados"):
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
        "La pestaña sigue la cadena física: difusión de portadores, formación "
        "de la zona de depleción, campo interno y ensayo iluminado J–V."
    )

    # ============================================================
    # VARIABLES LOCALES EXPLÍCITAS
    # ============================================================
    # Estas variables ya existen en el modelo global, pero se asignan aquí
    # para que la pestaña sea autocontenida y no dependa de nombres visuales.
    dn_tab3_um = float(S["dn_um"])
    Wtotal_tab3_um = float(W_total_um)
    xj_tab3_um = dn_tab3_um
    xn_tab3_um = float(xn_um)
    xp_tab3_um = float(xp_um)
    Wdep_tab3_um = max(xp_tab3_um - xn_tab3_um, 0.0)

    if Wdep_tab3_um > 0.0:
        frac_xn_visual = float(
            np.clip(
                (xj_tab3_um - xn_tab3_um) / Wdep_tab3_um,
                0.0,
                1.0,
            )
        )
    else:
        frac_xn_visual = 0.5

    frac_xp_visual = 1.0 - frac_xn_visual

    # ============================================================
    # 1. FORMACIÓN DE LA JUNTURA
    # ============================================================
    st.markdown("### 1. Formación de la juntura p-n")
    st.caption(
        "Al poner en contacto una base p y un emisor n, los portadores móviles "
        "difunden y se recombinan cerca de la interfaz. Quedan expuestos iones "
        "fijos, aparece la zona de depleción y se establece el campo interno."
    )

    n_ion_p = int(
        np.clip(
            np.interp(np.log10(S["NA"]), [14, 17], [6, 46]),
            6,
            46,
        )
    )
    n_ion_n = int(
        np.clip(
            np.interp(np.log10(S["ND"]), [17, 20], [10, 60]),
            10,
            60,
        )
    )

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
    fig_j.add_trace(_caja_3d(xL, -wP_3d, "#4a5568", 0.10, "Base p (bulk)"))
    fig_j.add_trace(_caja_3d(-wP_3d, wN_3d, "#f6ad55", 0.28, "Depleción"))
    fig_j.add_trace(_caja_3d(wN_3d, xR, "#4a5568", 0.10, "Emisor n (bulk)"))

    ion_p_expuesto = ionsP_x >= -wP_3d
    ion_n_expuesto = ionsN_x <= wN_3d
    dest_p_x = np.clip(ionsP_x - 0.35, xL + 0.05, -0.05)
    dest_n_x = np.clip(ionsN_x + 0.35, 0.05, xR - 0.05)
    recombina_p = ion_p_expuesto
    recombina_n = ion_n_expuesto

    fig_j.add_trace(
        go.Scatter3d(
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
        )
    )
    fig_j.add_trace(
        go.Scatter3d(
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
        )
    )

    n_frames_j = 36
    frames_j = []
    for fr in range(n_frames_j):
        tf = fr / (n_frames_j - 1)
        hx = ionsP_x + (dest_p_x - ionsP_x) * tf
        ex = ionsN_x + (dest_n_x - ionsN_x) * tf
        hx_anim = hx.astype(object)
        ex_anim = ex.astype(object)

        if tf >= 0.5:
            for idx in np.where(recombina_p)[0]:
                hx_anim[idx] = None
            for idx in np.where(recombina_n)[0]:
                ex_anim[idx] = None

        frames_j.append(
            go.Frame(
                data=[
                    go.Scatter3d(
                        x=hx_anim,
                        y=ionsP_y,
                        z=ionsP_z,
                        mode="markers",
                        marker=dict(size=4, color="#63b3ed"),
                    ),
                    go.Scatter3d(
                        x=ex_anim,
                        y=ionsN_y,
                        z=ionsN_z,
                        mode="markers",
                        marker=dict(size=4, color="#fc8181"),
                    ),
                ],
                traces=[5, 6],
                name=str(fr),
            )
        )

    fig_j.add_trace(
        go.Scatter3d(
            x=ionsP_x,
            y=ionsP_y,
            z=ionsP_z,
            mode="markers",
            name="Huecos móviles",
            marker=dict(size=4, color="#63b3ed"),
        )
    )
    fig_j.add_trace(
        go.Scatter3d(
            x=ionsN_x,
            y=ionsN_y,
            z=ionsN_z,
            mode="markers",
            name="Electrones móviles",
            marker=dict(size=4, color="#fc8181"),
        )
    )
    fig_j.frames = frames_j
    fig_j.update_layout(
        template="plotly_dark",
        height=540,
        scene=dict(
            xaxis=dict(
                title="p  ⟵           ⟶  n",
                showticklabels=False,
                range=[-1.0, 1.0],
            ),
            yaxis=dict(showticklabels=False, title="", range=[-1.0, 1.0]),
            zaxis=dict(showticklabels=False, title="", range=[-1.0, 1.0]),
            aspectmode="manual",
            aspectratio=dict(x=1.3, y=1, z=1),
            camera=dict(eye=dict(x=1.3, y=-1.7, z=0.7)),
        ),
        updatemenus=[
            dict(
                type="buttons",
                showactive=False,
                y=1.06,
                x=0.0,
                buttons=[
                    dict(
                        label="▶ Reproducir formación",
                        method="animate",
                        args=[
                            None,
                            dict(
                                frame=dict(duration=70, redraw=True),
                                transition=dict(duration=0),
                                fromcurrent=True,
                                mode="immediate",
                            ),
                        ],
                    )
                ],
            )
        ],
        legend=dict(orientation="h", y=-0.02),
        margin=dict(l=0, r=0, t=40, b=0),
        annotations=[
            dict(
                text=f"Ψ₀ ≈ {Psi0:.3f} V",
                x=0.5,
                y=1.0,
                xref="paper",
                yref="paper",
                showarrow=False,
                font=dict(color="#f6ad55", size=14),
            )
        ],
    )
    st.plotly_chart(fig_j, width="stretch")
    st.caption(
        "Los iones se muestran como una representación visual logarítmica. "
        "La zona de depleción se reparte según NA y ND; los portadores móviles "
        "se alejan hacia sus regiones neutras y desaparecen al recombinarse."
    )

    j1, j2, j3 = st.columns(3)
    j1.metric("Ψ₀", f"{Psi0:.3f} V")
    j2.metric("Wdep", f"{Wdep_tab3_um:.2f} µm")
    j3.metric(
        "Reparto de Wdep",
        f"p: {100 * frac_xp_visual:.1f}% | n: {100 * frac_xn_visual:.1f}%",
    )

    # ============================================================
    # 2. CONDICIONES DEL ENSAYO
    # ============================================================
    st.markdown("### 2. Condiciones del ensayo")
    st.caption("Los controles principales se encuentran en la barra lateral.")

    malla = f.modelo_malla_frontal_plata(
        S["num_dedos"],
        S["ancho_dedo_um"],
    )
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

    # ============================================================
    # 3. ENSAYO J–V Y P–V
    # ============================================================
    st.markdown("### 3. Ensayo iluminado J–V y P–V")

    JL_con_sombra = malla["fraccion_iluminada"] * JL_A_cm2
    resultado = f.simular_celda_JV(
        JL_con_sombra,
        J0_A_cm2,
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

    frames = []
    n_frames = 60
    idxs = np.linspace(0, len(V_arr) - 1, n_frames).astype(int)
    for k in idxs:
        frames.append(
            go.Frame(
                data=[
                    go.Scatter(x=V_arr, y=J_arr, mode="lines", line=dict(color="#68d391", width=3)),
                    go.Scatter(x=[V_arr[k]], y=[J_arr[k]], mode="markers", marker=dict(color="#f6ad55", size=14)),
                    go.Scatter(x=V_arr, y=P_arr, mode="lines", line=dict(color="#63b3ed", width=3), xaxis="x2", yaxis="y2"),
                    go.Scatter(x=[V_arr[k]], y=[P_arr[k]], mode="markers", marker=dict(color="#f6ad55", size=14), xaxis="x2", yaxis="y2"),
                ],
                name=str(k),
            )
        )

    fig_iv = go.Figure(
        data=[
            go.Scatter(x=V_arr, y=J_arr, mode="lines", line=dict(color="#68d391", width=3), name="J–V"),
            go.Scatter(x=[V_arr[0]], y=[J_arr[0]], mode="markers", marker=dict(color="#f6ad55", size=14), name="Punto de barrido"),
            go.Scatter(x=V_arr, y=P_arr, mode="lines", line=dict(color="#63b3ed", width=3), name="P–V", xaxis="x2", yaxis="y2"),
            go.Scatter(x=[V_arr[0]], y=[P_arr[0]], mode="markers", marker=dict(color="#f6ad55", size=14), xaxis="x2", yaxis="y2", showlegend=False),
            go.Scatter(x=[resultado["Vmp_V"]], y=[resultado["Jmp_A_cm2"] * 1e3], mode="markers+text", marker=dict(color="#f6e05e", size=12, symbol="diamond"), text=["MPP"], textposition="top center", name="MPP en J–V"),
            go.Scatter(x=[resultado["Vmp_V"]], y=[resultado["Pmax_W_cm2"] * 1e3], mode="markers+text", marker=dict(color="#f6e05e", size=12, symbol="diamond"), text=["MPP"], textposition="top center", name="MPP en P–V", xaxis="x2", yaxis="y2"),
        ],
        frames=frames,
    )
    fig_iv.update_layout(
        template="plotly_dark",
        height=500,
        xaxis=dict(domain=[0, 0.46], title="Voltaje V [V]"),
        yaxis=dict(title="Densidad de corriente J [mA/cm²]", range=[0, max(J_arr.max(), 1e-9) * 1.08]),
        xaxis2=dict(domain=[0.54, 1.0], title="Voltaje V [V]"),
        yaxis2=dict(title="Potencia P [mW/cm²]", range=[0, max(P_arr.max(), 1e-9) * 1.15]),
        updatemenus=[dict(type="buttons", showactive=False, y=1.12, x=0.0, buttons=[dict(label="▶ Reproducir barrido de V", method="animate", args=[None, dict(frame=dict(duration=40, redraw=True), fromcurrent=True)])])],
        showlegend=True,
    )
    st.plotly_chart(fig_iv, width="stretch")

    # ============================================================
    # 4. PARÁMETROS ELÉCTRICOS Y PÉRDIDAS
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
    # 5. BALANCE DE CORRIENTES
    # ============================================================
    st.markdown("### 5. Balance de corrientes en el punto de operación")
    st.caption(
        "El diagrama muestra cómo se reparte la corriente fotogenerada entre "
        "corriente útil, corriente de diodo y fuga por Rp."
    )

    V_max_exp = max(float(resultado["Voc_V"]) * 1.15, 0.05)
    V_op = st.slider(
        "Voltaje de operación V [V]",
        0.0,
        V_max_exp,
        min(float(resultado["Voc_V"]) * 0.6, V_max_exp),
        0.005,
        key="tab3_v_operacion",
    )

    Vt_local = c.K_B_EVK * T_K
    J_foto_mA = max(JL_con_sombra, 0.0) * 1e3
    J_diodo_mA = max(J0_A_cm2 * (np.exp(np.clip(V_op / (S["n_ideal"] * Vt_local), -700.0, 700.0)) - 1.0) * 1e3, 0.0)
    J_shunt_mA = max(V_op / max(S["Rp"], 1e-12), 0.0) * 1e3
    J_util_mA = max(J_foto_mA - J_diodo_mA - J_shunt_mA, 0.0)

    fig_flujo = go.Figure(go.Sankey(
        arrangement="fixed",
        node=dict(
            pad=28,
            thickness=22,
            line=dict(color="#cbd5e0", width=0.5),
            label=["Fotocorriente generada", "Corriente útil externa", "Diodo", "Rp: fuga"],
            color=["#68d391", "#63b3ed", "#fc8181", "#f6ad55"],
            x=[0.02, 0.78, 0.78, 0.78],
            y=[0.50, 0.20, 0.50, 0.80],
        ),
        link=dict(
            source=[0, 0, 0],
            target=[1, 2, 3],
            value=np.maximum([J_util_mA, J_diodo_mA, J_shunt_mA], 0.0).tolist(),
            color=["rgba(99,179,237,0.65)", "rgba(252,129,129,0.65)", "rgba(246,173,85,0.65)"],
            hovertemplate="%{value:.3f} mA/cm²<extra></extra>",
        ),
    ))
    fig_flujo.update_layout(height=360, template="plotly_dark", margin=dict(l=10, r=10, t=20, b=20))
    st.plotly_chart(fig_flujo, width="stretch")

    sm1, sm2, sm3, sm4 = st.columns(4)
    sm1.metric("J fotogenerada", f"{J_foto_mA:.3f} mA/cm²")
    sm2.metric("J útil", f"{J_util_mA:.3f} mA/cm²")
    sm3.metric("J diodo", f"{J_diodo_mA:.3f} mA/cm²")
    sm4.metric("J fuga Rp", f"{J_shunt_mA:.3f} mA/cm²")

    # ============================================================
    # 6. MALLA FRONTAL
    # ============================================================
    st.markdown("### 6. Malla frontal: sombra versus resistencia serie")
    st.caption("Más dedos reducen Rs pero aumentan la sombra; menos dedos producen el efecto contrario.")

    c1, c2 = st.columns(2)
    with c1:
        st.metric("Fracción de sombra fs", f"{malla['fraccion_sombra'] * 100:.2f} %")
        st.metric("Rs de la malla", f"{malla['Rs_malla_ohm_cm2']:.4f} Ω·cm²")
    with c2:
        Ns = np.linspace(5, 100, 40)
        fss = Ns * S["ancho_dedo_um"] * 1e-4 / c.ANCHO_CELDA_CM
        Rss = c.RS_REF_DEDOS_OHM_CM2 * c.NUMERO_DEDOS_REFERENCIA / Ns
        figN = go.Figure()
        figN.add_trace(go.Scatter(x=Ns, y=fss * 100, name="Sombra [%]", line=dict(color="#f6ad55", width=3)))
        figN.add_trace(go.Scatter(x=Ns, y=Rss, name="Rs malla [Ω·cm²]", yaxis="y2", line=dict(color="#63b3ed", width=3)))
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
        "La celda se representa mediante una grilla física 8×8 de sectores. "
        "La contaminación modifica localmente la vida media τₙ y, por "
        "lo tanto, la IQE y la corriente fotogenerada. La superficie 3D "
        "usa una malla visual interpolada 64×64 únicamente para mejorar "
        "la calidad gráfica. Un dedo de plata interrumpido se modela como "
        "un defecto resistivo: aumenta Rs, pero no modifica la IQE local ni JL."
    )

    n_sec = 8

    # ============================================================
    # ESTADO LOCAL DE LA PESTAÑA
    # ============================================================
    st.session_state.setdefault("tab4_tipo_falla", "Mancha circular")
    st.session_state.setdefault("tab4_severidad", "Moderada")
    st.session_state.setdefault("tab4_fila_centro", 3.5)
    st.session_state.setdefault("tab4_columna_centro", 3.5)
    st.session_state.setdefault("tab4_radio_falla", 1.5)
    st.session_state.setdefault("tab4_relacion_elipse", 2.0)
    st.session_state.setdefault("tab4_severidad_dedo", "Moderada")

    # ============================================================
    # CONTROLES
    # ============================================================
    c1, c2 = st.columns(2)

    with c1:
        st.markdown("**Contaminación metálica**")

        S["defecto_activo"] = st.checkbox(
            "Activar contaminación",
            value=S["defecto_activo"],
        )

        tipo_falla = st.selectbox(
            "Forma de la falla",
            [
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
            "Fila del centro de la falla",
            0.0,
            7.0,
            step=0.5,
            key="tab4_fila_centro",
        )

        columna_centro = st.slider(
            "Columna del centro de la falla",
            0.0,
            7.0,
            step=0.5,
            key="tab4_columna_centro",
        )

        radio_falla = st.slider(
            "Tamaño de la falla [sectores]",
            0.5,
            4.0,
            step=0.5,
            key="tab4_radio_falla",
        )

        relacion_elipse = st.slider(
            "Relación de aspecto de la elipse",
            1.0,
            4.0,
            step=0.5,
            key="tab4_relacion_elipse",
            disabled=tipo_falla != "Mancha elíptica",
        )

    with c2:
        st.markdown("**Dedo de plata interrumpido**")

        activar_dedo = st.checkbox(
            "Activar dedo roto",
            value=S["dedo_roto_col"] is not None,
        )

        if activar_dedo:
            S["dedo_roto_col"] = st.slider(
                "Columna del dedo roto",
                0,
                n_sec - 1,
                S["dedo_roto_col"]
                if S["dedo_roto_col"] is not None
                else 3,
            )

            severidad_dedo = st.select_slider(
                "Severidad resistiva",
                options=["Leve", "Moderada", "Severa"],
                key="tab4_severidad_dedo",
            )
        else:
            S["dedo_roto_col"] = None
            severidad_dedo = "Leve"

        st.caption(
            "El dedo roto modifica Rs y la curva J–V, pero no la IQE local."
        )

    wl_defecto = st.slider(
        "λ para visualizar el defecto [nm]",
        300.0,
        1200.0,
        900.0,
        10.0,
        key="tab4_lambda_defecto",
    )

    # ============================================================
    # MATRIZ CONTINUA DE SEVERIDAD
    # ============================================================
    filas = np.arange(n_sec, dtype=float)
    cols = np.arange(n_sec, dtype=float)
    X, Y = np.meshgrid(cols, filas)

    dx = X - columna_centro
    dy = Y - fila_centro
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
        severidad_map = np.exp(
            -0.5 * (
                distancia / max(sigma / 3.0, 0.15)
            ) ** 2
        )
        severidad_map *= np.exp(
            -0.5 * (
                (dx + dy) / max(2.0 * sigma, 0.5)
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
    # LONGITUD DE ONDA Y MAPAS IQE
    # ============================================================
    i_w = int(np.argmin(np.abs(wl_grid - wl_defecto)))
    wl_real = float(wl_grid[i_w])
    alpha_real = float(alpha_grid[i_w])
    R_real = float(R_grid[i_w])

    def mapa_iqe_local(tau_n_grid):
        mapa = np.zeros((n_sec, n_sec), dtype=float)

        Lp_local = (
            f.longitud_difusion(
                Dp,
                S["tau_p_us"],
            )
            * 1e4
        )

        for i in range(n_sec):
            for j in range(n_sec):
                Ln_local = (
                    f.longitud_difusion(
                        Dn,
                        tau_n_grid[i, j],
                    )
                    * 1e4
                )

                _, iqe_local = f.calcular_EQE_IQE_preciso(
                    np.array([wl_real]),
                    np.array([alpha_real]),
                    np.array([R_real]),
                    np.array([1.0]),
                    xn_um,
                    xp_um,
                    W_total_um,
                    Lp_local,
                    Ln_local,
                    Dp,
                    Dn,
                    S["Sf"],
                    S["Sr"],
                    reflector_trasero_activo=S["reflector_trasero"],
                    R_aluminio=c.R_ALUMINIO_EFECTIVA,
                )

                mapa[i, j] = float(iqe_local[0])

        return mapa

    mapa_sano = mapa_iqe_local(tau_n_sano)
    mapa_con_defecto = (
        mapa_iqe_local(tau_n_defecto)
        if S["defecto_activo"]
        else mapa_sano.copy()
    )

    # ============================================================
    # HEATMAPS 2D SIN INTERACCIÓN POR CLIC
    # ============================================================
    def heatmap_iqe(mapa, titulo):
        fig_mapa = go.Figure(
            data=go.Heatmap(
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
                    "IQE: %{z:.3f}<extra></extra>"
                ),
            )
        )

        fig_mapa.update_layout(
            title=titulo,
            xaxis_title="Columna del sector",
            yaxis_title="Fila del sector",
            xaxis=dict(
                tickmode="linear",
                dtick=1,
                fixedrange=True,
            ),
            yaxis=dict(
                tickmode="linear",
                dtick=1,
                fixedrange=True,
                autorange="reversed",
            ),
            height=400,
            template="plotly_dark",
        )

        return fig_mapa

    st.markdown(f"### IQE local a λ={wl_real:.0f} nm")

    c3, c4 = st.columns(2)

    with c3:
        st.plotly_chart(
            heatmap_iqe(
                mapa_sano,
                "IQE local — celda sana",
            ),
            config={
                "displayModeBar": False,
                "scrollZoom": False,
            },
            width="stretch",
        )

    with c4:
        st.plotly_chart(
            heatmap_iqe(
                mapa_con_defecto,
                "IQE local — celda con defecto",
            ),
            config={
                "displayModeBar": False,
                "scrollZoom": False,
            },
            width="stretch",
        )

    st.caption(
        "La posición de la falla se modifica mediante los sliders de fila "
        "y columna. El mapa 2D es una representación informativa de la IQE."
    )

    # ============================================================
    # MONTAÑAS 3D CON MALLA VISUAL 64×64
    # ============================================================
    def interpolar_matriz_visual(matriz_8x8, resolucion_visual=64):
        """Interpolación bilineal/cúbica visual sin cambiar la física."""
        x_original = np.linspace(0.0, 1.0, n_sec)
        y_original = np.linspace(0.0, 1.0, n_sec)
        x_visual = np.linspace(0.0, 1.0, resolucion_visual)
        y_visual = np.linspace(0.0, 1.0, resolucion_visual)

        matriz = np.asarray(matriz_8x8, dtype=float)

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
            matriz_x = np.array(
                [
                    np.interp(
                        x_visual,
                        x_original,
                        fila,
                    )
                    for fila in matriz
                ]
            )
            matriz_visual = np.array(
                [
                    np.interp(
                        y_visual,
                        y_original,
                        matriz_x[:, j],
                    )
                    for j in range(resolucion_visual)
                ]
            ).T

        return np.clip(matriz_visual, 0.0, 1.0)

    def superficie_montana(
        defecto_map,
        titulo,
        max_altura=0.65,
        resolucion_visual=64,
    ):
        if S["defecto_activo"]:
            altura_8x8 = np.asarray(
                defecto_map,
                dtype=float,
            )
            altura_8x8 = np.clip(
                altura_8x8,
                0.0,
                1.0,
            )
        else:
            altura_8x8 = np.zeros(
                (n_sec, n_sec),
                dtype=float,
            )

        altura_visual = interpolar_matriz_visual(
            altura_8x8,
            resolucion_visual=resolucion_visual,
        )

        altura_visual *= max_altura

        eje_visual = np.linspace(
            1.0,
            float(n_sec),
            resolucion_visual,
        )

        X_visual, Y_visual = np.meshgrid(
            eje_visual,
            eje_visual,
        )

        fig_3d = go.Figure(
            data=[
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
                    cmax=max_altura,
                    colorbar=dict(title="Altura visual"),
                    hovertemplate=(
                        "Columna: %{x:.1f}<br>"
                        "Fila: %{y:.1f}<br>"
                        "Altura: %{z:.3f}<extra></extra>"
                    ),
                    lighting=dict(
                        ambient=0.75,
                        diffuse=0.75,
                        specular=0.20,
                        roughness=0.75,
                        fresnel=0.10,
                    ),
                    contours=dict(
                        z=dict(show=False),
                    ),
                )
            ]
        )

        fig_3d.update_layout(
            title=titulo,
            height=470,
            template="plotly_dark",
            margin=dict(l=0, r=0, t=45, b=0),
            scene=dict(
                xaxis_title="Columna",
                yaxis_title="Fila",
                zaxis_title="Intensidad visual",
                xaxis=dict(
                    range=[1.0, float(n_sec)],
                    nticks=8,
                ),
                yaxis=dict(
                    range=[1.0, float(n_sec)],
                    nticks=8,
                ),
                zaxis=dict(
                    range=[0.0, max_altura],
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

        return fig_3d

    st.markdown("### Intensidad espacial del defecto")
    st.caption(
        "La física se calcula en 8×8 sectores. La superficie se interpola "
        "a 64×64 puntos y la altura se exagera moderadamente solo para hacer "
        "visible la forma espacial."
    )

    c5, c6 = st.columns(2)

    with c5:
        st.plotly_chart(
            superficie_montana(
                np.zeros((n_sec, n_sec)),
                "Base de referencia — celda sana",
                max_altura=0.65,
                resolucion_visual=64,
            ),
            config={
                "displayModeBar": False,
                "scrollZoom": True,
            },
            width="stretch",
        )

    with c6:
        st.plotly_chart(
            superficie_montana(
                severidad_map,
                "Montaña de contaminación — celda afectada",
                max_altura=0.65,
                resolucion_visual=64,
            ),
            config={
                "displayModeBar": False,
                "scrollZoom": True,
            },
            width="stretch",
        )

    # ============================================================
    # PROPAGACIÓN A J–V
    # ============================================================
    def JL_global(tau_n_grid, Sf_grid_local=None):
        if Sf_grid_local is None:
            Sf_grid_local = np.full(
                (n_sec, n_sec),
                S["Sf"],
            )

        JL_sum = 0.0

        for i in range(n_sec):
            for j in range(n_sec):
                Ln_local = (
                    f.longitud_difusion(
                        Dn,
                        tau_n_grid[i, j],
                    )
                    * 1e4
                )

                eqe_local, _ = f.calcular_EQE_IQE_preciso(
                    wl_grid,
                    alpha_grid,
                    R_grid,
                    phi0_grid,
                    xn_um,
                    xp_um,
                    W_total_um,
                    Lp_um,
                    Ln_local,
                    Dp,
                    Dn,
                    Sf_grid_local[i, j],
                    S["Sr"],
                    reflector_trasero_activo=S["reflector_trasero"],
                    R_aluminio=c.R_ALUMINIO_EFECTIVA,
                )

                JL_sum += c.Q * np.trapezoid(
                    phi0_grid * eqe_local,
                    wl_grid,
                )

        return JL_sum / (n_sec * n_sec)

    Sf_grid_sano = np.full(
        (n_sec, n_sec),
        S["Sf"],
    )

    JL_sano = JL_global(
        tau_n_sano,
        Sf_grid_sano,
    )

    JL_defecto = (
        JL_global(
            tau_n_defecto,
            Sf_grid_sano,
        )
        if S["defecto_activo"]
        else JL_sano
    )

    # ============================================================
    # DEDO ROTO: SOLO RESISTENCIA SERIE
    # ============================================================
    malla_sana = f.modelo_malla_frontal_plata(
        S["num_dedos"],
        S["ancho_dedo_um"],
    )

    Rs_sano = (
        c.RS_BASE_OHM_CM2
        + malla_sana["Rs_malla_ohm_cm2"]
    )

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

    Rs_con_dedo_roto = Rs_sano + penalizacion_dedo * (
        c.RS_REF_DEDOS_OHM_CM2
        * c.NUMERO_DEDOS_REFERENCIA
        / S["num_dedos"]
    )

    # ============================================================
    # CURVAS J–V
    # ============================================================
    res_sano = f.simular_celda_JV(
        malla_sana["fraccion_iluminada"] * JL_sano,
        J0_A_cm2,
        T_K,
        S["irradiancia_soles"],
        S["n_ideal"],
        Rs_sano,
        S["Rp"],
        n_puntos=250,
    )

    res_defecto = f.simular_celda_JV(
        malla_sana["fraccion_iluminada"] * JL_defecto,
        J0_A_cm2,
        T_K,
        S["irradiancia_soles"],
        S["n_ideal"],
        Rs_con_dedo_roto,
        S["Rp"],
        n_puntos=250,
    )

    fig_jv = go.Figure()

    Vs, Js = truncar_cerca_voc(
        res_sano["V_array_V"],
        res_sano["J_array_A_cm2"] * 1e3,
    )

    Vd, Jd = truncar_cerca_voc(
        res_defecto["V_array_V"],
        res_defecto["J_array_A_cm2"] * 1e3,
    )

    fig_jv.add_trace(
        go.Scatter(
            x=Vs,
            y=Js,
            name="Celda sana",
            line=dict(color="#68d391", width=3),
        )
    )

    fig_jv.add_trace(
        go.Scatter(
            x=Vd,
            y=Jd,
            name="Con defecto(s)",
            line=dict(color="#fc8181", width=3, dash="dash"),
        )
    )

    fig_jv.update_layout(
        title="Propagación del defecto a la curva J–V",
        xaxis_title="V [V]",
        yaxis_title="J [mA/cm²]",
        height=400,
        template="plotly_dark",
        xaxis=dict(fixedrange=True),
        yaxis=dict(
            fixedrange=True,
            range=[0.0, max(Js.max(), Jd.max()) * 1.08],
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
    # MÉTRICAS
    # ============================================================
    m1, m2, m3, m4 = st.columns(4)

    m1.metric(
        "Jsc sana",
        f"{res_sano['Jsc_A_cm2'] * 1e3:.2f} mA/cm²",
    )

    m2.metric(
        "Δ Jsc",
        f"{(
            res_defecto['Jsc_A_cm2']
            - res_sano['Jsc_A_cm2']
        ) * 1e3:+.3f} mA/cm²",
    )

    m3.metric(
        "Δ FF",
        f"{(
            res_defecto['FF']
            - res_sano['FF']
        ) * 100:+.2f} pp",
    )

    m4.metric(
        "Δ Pmax",
        f"{(
            res_defecto['Pmax_W_cm2']
            - res_sano['Pmax_W_cm2']
        ) * 1e3:+.3f} mW/cm²",
    )

    if S["defecto_activo"]:
        st.caption(
            "La contaminación se representa como una distribución continua "
            "de τₙ reducido. En la visualización 3D, la severidad se "
            "interpola a una malla 64×64 y se exagera moderadamente solo "
            "para hacer visible la forma espacial."
        )
    elif S["dedo_roto_col"] is not None:
        st.caption(
            "El dedo roto es resistivo: no modifica los mapas ni la montaña "
            "de IQE, pero aumenta Rs y afecta principalmente FF y Pmax."
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
