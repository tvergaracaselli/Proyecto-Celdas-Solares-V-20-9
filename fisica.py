# -*- coding: utf-8 -*-
"""
fisica.py
Modelo físico completo del Problema 2.2 (Laboratorio virtual de
caracterización de una celda p-n de silicio). Las funciones de esta
biblioteca implementan las ecuaciones del enunciado 2.2 y conservan
la física validada por el grupo: Beer-Lambert, probabilidad de colección
fc(x), EQE/IQE, diodo implícito con Rs/Rp, malla frontal de dedos de plata,
reflector trasero opcional, y dependencia con temperatura.

Ninguna curva se codifica a mano: todo se calcula en tiempo real a
partir de constantes.py y de los parámetros que el usuario mueve en
la barra lateral de Streamlit.
"""
import numpy as np
from scipy.optimize import brentq
import constantes as c
from pathlib import Path
import pandas as pd

# ============================================================
# 1) ÓPTICA: n(λ), k(λ), α(λ), espectro AM1.5G
# ============================================================




# Carpeta donde vive fisica.py.
# Así funciona tanto localmente como en Streamlit Cloud.
CARPETA_PROYECTO = Path(__file__).resolve().parent
CARPETA_DATOS = CARPETA_PROYECTO / "datos"

RUTA_SCHINKE = CARPETA_DATOS / "Schinke.csv"
RUTA_AM15G = CARPETA_DATOS / "astmg173.xls"


# Caché simple: evita leer los archivos en cada actualización
# de un slider de Streamlit.
_DATOS_NK_CACHE = None
_DATOS_AM15G_CACHE = None


def cargar_datos_nk_reales(ruta_csv=RUTA_SCHINKE):
    """
    Carga n(lambda) y k(lambda) del silicio desde Schinke.csv.

    El archivo tiene dos bloques:
        wl,n
        wl,k

    La longitud de onda del archivo está en micrómetros y se
    convierte a nanómetros.

    Retorna
    -------
    wavelength_nm : ndarray
        Longitudes de onda [nm].
    n : ndarray
        Índice de refracción real.
    k : ndarray
        Coeficiente de extinción.
    """
    ruta_csv = Path(ruta_csv)

    if not ruta_csv.exists():
        raise FileNotFoundError(
            f"No se encontró el archivo óptico: {ruta_csv}"
        )

    with ruta_csv.open("r", encoding="utf-8") as archivo:
        lineas = [
            linea.strip()
            for linea in archivo
            if linea.strip()
        ]

    if "wl,k" not in lineas:
        raise ValueError(
            "Schinke.csv no tiene el formato esperado: "
            "falta el separador 'wl,k'."
        )

    indice_k = lineas.index("wl,k")

    bloque_n = lineas[1:indice_k]
    bloque_k = lineas[indice_k + 1:]

    datos_n = pd.DataFrame(
        [linea.split(",") for linea in bloque_n],
        columns=["wavelength_um", "n"]
    ).astype(float)

    datos_k = pd.DataFrame(
        [linea.split(",") for linea in bloque_k],
        columns=["wavelength_um", "k"]
    ).astype(float)

    tabla_nk = pd.merge(
        datos_n,
        datos_k,
        on="wavelength_um",
        how="inner"
    )

    tabla_nk = tabla_nk.sort_values(
        "wavelength_um"
    ).reset_index(drop=True)

    wavelength_nm = (
        tabla_nk["wavelength_um"].to_numpy()
        * 1000.0
    )

    n = tabla_nk["n"].to_numpy()
    k = tabla_nk["k"].to_numpy()

    return wavelength_nm, n, k


def obtener_datos_nk():
    """
    Devuelve los datos n(lambda), k(lambda) usando caché.
    """
    global _DATOS_NK_CACHE

    if _DATOS_NK_CACHE is None:
        _DATOS_NK_CACHE = cargar_datos_nk_reales()

    return _DATOS_NK_CACHE


def cargar_espectro_am15g_real(ruta_xls=RUTA_AM15G):
    """
    Carga el espectro solar ASTM G173-03 desde astmg173.xls.

    Usa la hoja SMARTS2 y la columna Global tilt,
    correspondiente al espectro AM1.5G Global.

    Retorna
    -------
    wavelength_nm : ndarray
        Longitudes de onda [nm].
    P_lambda : ndarray
        Irradiancia espectral [W/m^2/nm].
    """
    ruta_xls = Path(ruta_xls)

    if not ruta_xls.exists():
        raise FileNotFoundError(
            f"No se encontró el espectro AM1.5G: {ruta_xls}"
        )

    df = pd.read_excel(
        ruta_xls,
        sheet_name="SMARTS2",
        header=1,
        engine="xlrd"
    )

    df.columns = [
        "wavelength_nm",
        "etr",
        "global_tilt",
        "direct_circumsolar"
    ]

    df = df.dropna().reset_index(drop=True)

    wavelength_nm = df["wavelength_nm"].to_numpy(
        dtype=float
    )

    P_lambda = df["global_tilt"].to_numpy(
        dtype=float
    )

    return wavelength_nm, P_lambda


def obtener_espectro_am15g():
    """
    Devuelve los datos AM1.5G usando caché.
    """
    global _DATOS_AM15G_CACHE

    if _DATOS_AM15G_CACHE is None:
        _DATOS_AM15G_CACHE = cargar_espectro_am15g_real()

    return _DATOS_AM15G_CACHE


def k_a_alpha(wavelength_nm, k):
    """
    Convierte k(lambda) a alpha(lambda):

        alpha(lambda) = 4*pi*k(lambda)/lambda.

    Parámetros
    ----------
    wavelength_nm : ndarray
        Longitud de onda [nm].
    k : ndarray
        Índice de extinción [adimensional].

    Retorna
    -------
    alpha_cm : ndarray
        Coeficiente de absorción [cm^-1].
    """
    wavelength_cm = (
        np.asarray(wavelength_nm, dtype=float)
        * 1e-7
    )

    k = np.asarray(k, dtype=float)

    if np.any(wavelength_cm <= 0.0):
        raise ValueError(
            "Las longitudes de onda deben ser positivas."
        )

    return 4.0 * np.pi * k / wavelength_cm


def alpha_silicio(wavelength_nm):
    """
    Coeficiente de absorción medido del silicio [cm^-1].

    Interpola k(lambda) de Schinke.csv y aplica:
        alpha = 4*pi*k/lambda.
    """
    wl_datos, _, k_datos = obtener_datos_nk()

    k_interp = np.interp(
        wavelength_nm,
        wl_datos,
        k_datos
    )

    return k_a_alpha(
        wavelength_nm,
        k_interp
    )


def reflectancia_frontal(wavelength_nm, modo="fresnel"):
    """
    Reflectancia frontal aire-silicio.

    modo='fresnel':
        R = [((n-1)^2 + k^2)] / [((n+1)^2 + k^2)].

    modo='fijo':
        Usa R_FRONTAL_SI_DESNUDO de constantes.py.
    """
    wl = np.asarray(wavelength_nm, dtype=float)

    if modo == "fijo":
        return np.full_like(
            wl,
            c.R_FRONTAL_SI_DESNUDO,
            dtype=float
        )

    if modo != "fresnel":
        raise ValueError(
            "modo debe ser 'fresnel' o 'fijo'."
        )

    wl_datos, n_datos, k_datos = obtener_datos_nk()

    n_si = np.interp(
        wl,
        wl_datos,
        n_datos
    )

    k_si = np.interp(
        wl,
        wl_datos,
        k_datos
    )

    numerador = (
        (n_si - 1.0)**2
        + k_si**2
    )

    denominador = (
        (n_si + 1.0)**2
        + k_si**2
    )

    return np.clip(
        numerador / denominador,
        0.0,
        1.0
    )


def irradiancia_a_flujo_fotones(wavelength_nm, P_lambda):
    """
    Convierte irradiancia espectral a flujo de fotones.

    Entrada:
        P_lambda [W/m^2/nm].

    Salida:
        phi0(lambda) [cm^-2 s^-1 nm^-1].

    Usa:
        E(eV) = 1.24 / lambda(um).
    """
    wavelength_um = (
        np.asarray(wavelength_nm, dtype=float)
        * 1e-3
    )

    P_lambda = np.asarray(
        P_lambda,
        dtype=float
    )

    flujo_m2 = (
        P_lambda
        * wavelength_um
        / (1.24 * c.Q)
    )

    return flujo_m2 * 1e-4


def espectro_y_flujo_fotones(wavelength_nm):
    """
    Interpola el espectro AM1.5G real sobre wavelength_nm
    y lo convierte a flujo fotónico incidente.

    Retorna
    -------
    P_lambda : ndarray
        Irradiancia espectral AM1.5G [W/m^2/nm].
    phi0 : ndarray
        Flujo fotónico [cm^-2 s^-1 nm^-1].
    """
    wl_datos, P_datos = obtener_espectro_am15g()

    P_lambda = np.interp(
        wavelength_nm,
        wl_datos,
        P_datos
    )

    phi0 = irradiancia_a_flujo_fotones(
        wavelength_nm,
        P_lambda
    )

    return P_lambda, phi0

# ============================================================
# 2) GENERACIÓN DE PARES: Beer-Lambert
# ============================================================

def flujo_fotones(x_um, phi0, R, alpha_cm):
    """Φ(x,λ) = φ0(λ)[1-R(λ)] exp(-α(λ) x)"""
    x_cm = np.asarray(x_um) * 1e-4
    X, ALPHA = np.meshgrid(x_cm, alpha_cm, indexing="ij")
    _, PHI0 = np.meshgrid(x_cm, phi0, indexing="ij")
    _, R2 = np.meshgrid(x_cm, R, indexing="ij")
    return PHI0 * (1.0 - R2) * np.exp(-ALPHA * X)


def tasa_generacion(x_um, phi0, R, alpha_cm):
    """G(x,λ) = α(λ) φ0(λ) [1-R(λ)] exp(-α(λ) x)  [cm^-3 s^-1 nm^-1]"""
    x_cm = np.asarray(x_um) * 1e-4
    X, ALPHA = np.meshgrid(x_cm, alpha_cm, indexing="ij")
    _, PHI0 = np.meshgrid(x_cm, phi0, indexing="ij")
    _, R2 = np.meshgrid(x_cm, R, indexing="ij")
    return ALPHA * PHI0 * (1.0 - R2) * np.exp(-ALPHA * X)


def balance_fotones(R, alpha_cm, W_total_um):
    """Fracción reflejada, absorbida y transmitida (V1: debe sumar 1)."""
    W_cm = W_total_um * 1e-4
    frac_reflejada = np.asarray(R)
    frac_transmitida = (1.0 - R) * np.exp(-alpha_cm * W_cm)
    frac_absorbida = (1.0 - R) - frac_transmitida
    return frac_reflejada, frac_absorbida, frac_transmitida


def tasa_generacion_con_reflector(x_um, phi0, R, alpha_cm, W_total_um,
                                  reflector_trasero_activo=False,
                                  R_aluminio=c.R_ALUMINIO_EFECTIVA):
    """Tasa de generación con una reflexión trasera opcional de aluminio.

    El primer término es Beer-Lambert en el recorrido frontal. Si el
    reflector está activo, se suma un segundo recorrido desde el contacto
    trasero hacia la superficie frontal. Se considera UNA reflexión trasera;
    no se modela una cavidad de reflexiones múltiples.
    """
    G_ida = tasa_generacion(x_um, phi0, R, alpha_cm)
    if not reflector_trasero_activo or R_aluminio <= 0:
        return G_ida

    x_cm = np.asarray(x_um, dtype=float) * 1e-4
    W_cm = float(W_total_um) * 1e-4
    alpha = np.asarray(alpha_cm, dtype=float)
    phi0 = np.asarray(phi0, dtype=float)
    R = np.asarray(R, dtype=float)

    # Flujo que llega al dorso y es reflejado por el Al.
    phi_dorso_reflejado = phi0 * (1.0 - R) * np.exp(-alpha * W_cm) * R_aluminio
    X, ALPHA = np.meshgrid(x_cm, alpha, indexing="ij")
    _, PHI_BACK = np.meshgrid(x_cm, phi_dorso_reflejado, indexing="ij")
    distancia_retorno = W_cm - X
    G_retorno = ALPHA * PHI_BACK * np.exp(-ALPHA * distancia_retorno)
    return G_ida + G_retorno


def balance_fotones_con_reflector(R, alpha_cm, W_total_um,
                                  reflector_trasero_activo=False,
                                  R_aluminio=c.R_ALUMINIO_EFECTIVA):
    """Balance óptico con una reflexión trasera opcional.

    Retorna cuatro fracciones respecto al flujo incidente:
      R_frontal, A_total_en_Si, perdida_en_Al_o_transmitida, escape_frontal.
    Su suma es 1 para cada longitud de onda.
    """
    R = np.asarray(R, dtype=float)
    alpha = np.asarray(alpha_cm, dtype=float)
    W_cm = float(W_total_um) * 1e-4
    trans_una_pasada = np.exp(-alpha * W_cm)

    frac_reflejada = R
    A_ida = (1.0 - R) * (1.0 - trans_una_pasada)

    if not reflector_trasero_activo:
        perdida_trasera = (1.0 - R) * trans_una_pasada
        escape_frontal = np.zeros_like(perdida_trasera)
        return frac_reflejada, A_ida, perdida_trasera, escape_frontal

    flujo_dorso = (1.0 - R) * trans_una_pasada
    perdida_en_Al = flujo_dorso * (1.0 - R_aluminio)
    flujo_reflejado = flujo_dorso * R_aluminio
    A_retorno = flujo_reflejado * (1.0 - trans_una_pasada)
    escape_frontal = flujo_reflejado * trans_una_pasada
    return frac_reflejada, A_ida + A_retorno, perdida_en_Al, escape_frontal


# ============================================================
# 3) TRANSPORTE Y PROBABILIDAD DE COLECCIÓN fc(x)
# ============================================================

def coef_difusion(T_K, mu_cm2_Vs):
    """Relación de Einstein: D = (kB T/q) * mu  [cm^2/s]"""
    return (c.K_B_EVK * T_K) * mu_cm2_Vs


def longitud_difusion(D, tau_us):
    """L = sqrt(D * tau)  [cm]"""
    return np.sqrt(D * tau_us * 1e-6)


def potencial_juntura(NA, ND, ni, T_K):
    """Psi0 = (kB T/q) ln(NA ND / ni^2)  [V]"""
    return (c.K_B_EVK * T_K) * np.log((NA * ND) / (ni ** 2))


def ancho_zona_deplecion(Psi0, NA, ND):
    """W_dep = sqrt(2 eps_Si Psi0/q (1/NA+1/ND))  [cm]"""
    return np.sqrt(2.0 * c.EPS_SI * Psi0 / c.Q * (1.0 / NA + 1.0 / ND))


# Nota de modelamiento: aunque una juntura abrupta real reparte Wdep de forma
# asimétrica según los dopajes, el Problema 2.2 entrega explícitamente
# xn=xj-Wdep/2 y xp=xj+Wdep/2. La app usa esa definición de la pauta.

def fc_emisor(x_cm, xn_cm, Lp_cm, Dp, Sf):
    num = np.cosh(x_cm / Lp_cm) + (Sf * Lp_cm / Dp) * np.sinh(x_cm / Lp_cm)
    den = np.cosh(xn_cm / Lp_cm) + (Sf * Lp_cm / Dp) * np.sinh(xn_cm / Lp_cm)
    return num / den


def fc_base(x_cm, xp_cm, W_cm, Ln_cm, Dn, Sr):
    u = x_cm - xp_cm
    Wb = W_cm - xp_cm
    num = np.cosh((Wb - u) / Ln_cm) + (Sr * Ln_cm / Dn) * np.sinh((Wb - u) / Ln_cm)
    den = np.cosh(Wb / Ln_cm) + (Sr * Ln_cm / Dn) * np.sinh(Wb / Ln_cm)
    return num / den


def prob_coleccion_total(x_um, xn_um, xp_um, W_um, Lp_um, Ln_um, Dp, Dn, Sf, Sr):
    """fc(x) por tramos: emisor / zona de deplección (=1) / base."""
    x_cm = np.asarray(x_um, dtype=float) * 1e-4
    xn_cm, xp_cm, W_cm = xn_um * 1e-4, xp_um * 1e-4, W_um * 1e-4
    Lp_cm, Ln_cm = Lp_um * 1e-4, Ln_um * 1e-4

    fc = np.zeros_like(x_cm)
    m_e = (x_cm >= 0.0) & (x_cm < xn_cm)
    if np.any(m_e):
        fc[m_e] = fc_emisor(x_cm[m_e], xn_cm, Lp_cm, Dp, Sf)
    m_d = (x_cm >= xn_cm) & (x_cm <= xp_cm)
    fc[m_d] = 1.0
    m_b = (x_cm > xp_cm) & (x_cm <= W_cm)
    if np.any(m_b):
        fc[m_b] = fc_base(x_cm[m_b], xp_cm, W_cm, Ln_cm, Dn, Sr)
    return np.clip(fc, 0.0, 1.0)


def calcular_EQE_IQE(G_x_lambda, fc_x, x_um, phi0, R):
    """EQE(λ)=∫fc(x)G(x,λ)dx / φ0(λ) ;  IQE(λ)=EQE(λ)/(1-R(λ))

    ADVERTENCIA NUMÉRICA: esta versión integra con trapecios sobre una
    malla x_um fija. Para el azul, la longitud de absorción 1/α puede
    ser de solo unos pocos nanómetros, mucho más fina que cualquier
    malla razonable en x. Usar esta función para el mapa 2D de
    generación (solo visual) — para EQE/IQE/JL cuantitativos usar
    SIEMPRE `calcular_EQE_IQE_preciso`, que integra analíticamente por
    tramos y no sufre este problema de resolución."""
    x_cm = x_um * 1e-4
    integrando = fc_x[:, np.newaxis] * G_x_lambda
    integral = np.trapezoid(integrando, x_cm, axis=0)
    EQE = integral / phi0
    IQE = EQE / (1.0 - R)
    return EQE, IQE


def calcular_EQE_IQE_preciso(wavelength_nm, alpha_cm, R, phi0,
                              xn_um, xp_um, W_um, Lp_um, Ln_um, Dp, Dn, Sf, Sr,
                              reflector_trasero_activo=False,
                              R_aluminio=c.R_ALUMINIO_EFECTIVA):
    """EQE(λ) e IQE(λ) integrando analíticamente ∫ fc(x)·α·e^{-αx} dx
    por tramos (emisor / zona de deplección / base), en vez de
    trapecios sobre una malla uniforme. Esto es necesario porque para
    λ azul la longitud de absorción 1/α puede ser de pocos nanómetros:
    una malla en x demasiado gruesa frente a 1/α sobreestima
    groseramente la integral con la regla del trapecio (el valor podía
    superar 1 en la versión ingenua). La integral de exp(-αx) en un
    tramo [a,b] tiene primitiva cerrada, por lo que aquí no hay
    ningún error de discretización."""
    alpha_cm = np.asarray(alpha_cm, dtype=float)
    xn_cm, xp_cm, W_cm = xn_um * 1e-4, xp_um * 1e-4, W_um * 1e-4
    Lp_cm, Ln_cm = Lp_um * 1e-4, Ln_um * 1e-4

    # --- Tramo emisor [0, xn]: fc,n(x) = A cosh(x/Lp) + B sinh(x/Lp) ---
    den_e = np.cosh(xn_cm / Lp_cm) + (Sf * Lp_cm / Dp) * np.sinh(xn_cm / Lp_cm)
    A_e, B_e = 1.0 / den_e, (Sf * Lp_cm / Dp) / den_e

    def integral_cosh_exp(a, alpha, L):
        # ∫ cosh(x/L) e^{-alpha x} dx  entre 0 y a
        k = 1.0 / L
        return 0.5 * (
            (1 - np.exp(-(alpha - k) * a)) / (alpha - k)
            + (1 - np.exp(-(alpha + k) * a)) / (alpha + k)
        )

    def integral_sinh_exp(a, alpha, L):
        k = 1.0 / L
        return 0.5 * (
            (1 - np.exp(-(alpha - k) * a)) / (alpha - k)
            - (1 - np.exp(-(alpha + k) * a)) / (alpha + k)
        )

    I_emisor = A_e * integral_cosh_exp(xn_cm, alpha_cm, Lp_cm) \
        + B_e * integral_sinh_exp(xn_cm, alpha_cm, Lp_cm)
    aporte_emisor = alpha_cm * I_emisor

    # --- Tramo deplección [xn, xp]: fc = 1 ---
    aporte_deplecion = np.exp(-alpha_cm * xn_cm) - np.exp(-alpha_cm * xp_cm)

    # --- Tramo base [xp, W], u = x - xp, fc,p(u) = C cosh(u/Ln) + D sinh(u/Ln) ---
    # (expandiendo cosh/sinh(Wb-u) por identidades de suma de ángulos)
    Wb_cm = W_cm - xp_cm
    den_b = np.cosh(Wb_cm / Ln_cm) + (Sr * Ln_cm / Dn) * np.sinh(Wb_cm / Ln_cm)
    ch_Wb, sh_Wb = np.cosh(Wb_cm / Ln_cm), np.sinh(Wb_cm / Ln_cm)
    Sr_term = Sr * Ln_cm / Dn
    C_b = (ch_Wb + Sr_term * sh_Wb) / den_b
    D_b = -(sh_Wb + Sr_term * ch_Wb) / den_b
    I_base_cosh = integral_cosh_exp(Wb_cm, alpha_cm, Ln_cm)
    I_base_sinh = integral_sinh_exp(Wb_cm, alpha_cm, Ln_cm)
    aporte_base = np.exp(-alpha_cm * xp_cm) * alpha_cm * (C_b * I_base_cosh + D_b * I_base_sinh)

    integral_total = aporte_emisor + aporte_deplecion + aporte_base
    EQE = (1.0 - R) * integral_total

    # Segundo recorrido óptico opcional por reflexión trasera. Para mantener
    # robustez numérica, este término (relevante sobre todo en rojo/IR, donde
    # la absorción es suave) se integra sobre una malla refinada cerca de ambas
    # superficies. El recorrido frontal principal conserva la integral analítica.
    if reflector_trasero_activo and R_aluminio > 0:
        W_um_f = float(W_um)
        x_ref_um = np.unique(np.concatenate([
            np.linspace(0.0, W_um_f, 900),
            np.linspace(0.0, min(5.0, W_um_f), 250),
            np.linspace(max(0.0, W_um_f - 20.0), W_um_f, 450),
        ]))
        fc_ref = prob_coleccion_total(
            x_ref_um, xn_um, xp_um, W_um, Lp_um, Ln_um, Dp, Dn, Sf, Sr
        )
        x_ref_cm = x_ref_um * 1e-4
        distancia_desde_dorso_cm = (W_um_f - x_ref_um) * 1e-4
        # G_retorno/phi0 = alpha*(1-R)*R_Al*exp(-alpha*W)*exp[-alpha*(W-x)]
        kernel = (
            alpha_cm[np.newaxis, :]
            * (1.0 - R)[np.newaxis, :]
            * R_aluminio
            * np.exp(-alpha_cm[np.newaxis, :] * (W_um_f * 1e-4))
            * np.exp(-distancia_desde_dorso_cm[:, np.newaxis] * alpha_cm[np.newaxis, :])
        )
        aporte_reflejado = np.trapezoid(fc_ref[:, np.newaxis] * kernel, x_ref_cm, axis=0)
        EQE = EQE + aporte_reflejado

    # Aunque exista reflector, cada fotón incidente que supera la interfaz
    # frontal puede generar como máximo un par útil: la cota sigue siendo
    # EQE <= 1-R e IQE <= 1. El segundo recorrido solo recupera parte de los
    # fotones que habrían escapado por transmisión en el primer paso.
    EQE = np.clip(EQE, 0.0, 1.0 - R)
    IQE = EQE / np.maximum(1.0 - R, 1e-15)
    return EQE, np.clip(IQE, 0.0, 1.0)


# ============================================================
# 4) DIODO IMPLÍCITO CON Rs, Rp
# ============================================================

def corriente_saturacion_J0(NA, ND, ni, Dn, Ln, Dp, Lp):
    """J0 = q ni^2 [Dn/(NA Ln) + Dp/(ND Lp)]  [A/cm^2]"""
    return c.Q * ni ** 2 * (Dn / (NA * Ln) + Dp / (ND * Lp))


def _residuo_diodo(J, V, J0, n_ideal, T_K, Rs, Rp, JL):
    Vt = c.K_B_EVK * T_K
    V_diodo = V - Rs * J
    arg = np.clip(V_diodo / (n_ideal * Vt), -700.0, 700.0)
    J_diodo = J0 * (np.exp(arg) - 1.0)
    J_shunt = V_diodo / Rp
    return J - (J_diodo + J_shunt - JL)


def resolver_curva_JV(V_array, J0, n_ideal, T_K, Rs, Rp, JL):
    """Resuelve la ecuación implícita J = J0[exp((V-RsJ)/nVt)-1] + (V-RsJ)/Rp - JL
    punto a punto con búsqueda de raíces (brentq)."""
    V_array = np.asarray(V_array, dtype=float)
    J_array = np.zeros_like(V_array)
    J_min = -2.0 * max(JL, 1e-12)
    J_max = 10.0 + 10.0 * max(JL, 1e-12)
    for i, V in enumerate(V_array):
        f = lambda J: _residuo_diodo(J, V, J0, n_ideal, T_K, Rs, Rp, JL)
        fmin, fmax = f(J_min), f(J_max)
        intentos = 0
        while fmin * fmax > 0 and intentos < 20:
            J_min *= 2.0
            J_max *= 2.0
            fmin, fmax = f(J_min), f(J_max)
            intentos += 1
        J_array[i] = brentq(f, J_min, J_max, xtol=1e-14, rtol=1e-12, maxiter=200)
    return J_array


def calcular_parametros_celda(V_array, J_array, irradiancia_soles=1.0):
    """Jsc, Voc, Vmp, Jmp, Pmax, FF, eta a partir de la curva J-V."""
    Jsc = np.abs(np.interp(0.0, V_array, J_array))
    orden = np.argsort(J_array)
    Voc = np.interp(0.0, J_array[orden], V_array[orden])
    P_array = np.maximum(-V_array * J_array, 0.0)
    i_mpp = np.argmax(P_array)
    Pmax, Vmp, Jmp = P_array[i_mpp], V_array[i_mpp], np.abs(J_array[i_mpp])
    FF = Pmax / (Voc * Jsc) if (Voc > 0 and Jsc > 0) else 0.0
    Pin = irradiancia_soles * c.IRRADIANCIA_AM15G
    eta = Pmax / Pin if Pin > 0 else 0.0
    return dict(Jsc_A_cm2=Jsc, Voc_V=Voc, Vmp_V=Vmp, Jmp_A_cm2=Jmp, Pmax_W_cm2=Pmax,
                FF=FF, eta=eta, P_array_W_cm2=P_array, i_mpp=i_mpp)


def FF0_empirico(Voc, T_K):
    """FF0 = [v0-ln(v0+0.72)]/(v0+1), v0=Voc/Vt (Unidad 4)."""
    if Voc <= 0:
        return 0.0
    v0 = Voc / (c.K_B_EVK * T_K)
    return (v0 - np.log(v0 + 0.72)) / (v0 + 1.0)


def modelo_malla_frontal_plata(numero_dedos, ancho_dedo_um,
                                ancho_celda_cm=c.ANCHO_CELDA_CM,
                                Rs_base=c.RS_BASE_OHM_CM2,
                                Rs_ref=c.RS_REF_DEDOS_OHM_CM2,
                                n_ref=c.NUMERO_DEDOS_REFERENCIA):
    """f_s = N w_dedo/ancho_celda (sombra);  Rs_malla = Rs_ref*n_ref/N."""
    ancho_dedo_cm = ancho_dedo_um * 1e-4
    fs = np.clip(numero_dedos * ancho_dedo_cm / ancho_celda_cm, 0.0, 0.95)
    Rs_malla = Rs_ref * n_ref / numero_dedos
    Rs_total = Rs_base + Rs_malla
    return dict(fraccion_sombra=fs, fraccion_iluminada=1 - fs,
                Rs_malla_ohm_cm2=Rs_malla, Rs_total_ohm_cm2=Rs_total)


def simular_celda_JV(JL_base_A_cm2, J0, T_K, irradiancia_soles=1.0, n_ideal=1.0,
                      Rs_ohm_cm2=0.0, Rp_ohm_cm2=1e12, n_puntos=400):
    JL_local = irradiancia_soles * JL_base_A_cm2
    Vt = c.K_B_EVK * T_K
    Voc_est = n_ideal * Vt * np.log1p(JL_local / J0)
    V_max = max(1.10 * Voc_est, 0.10)
    V_array = np.linspace(0.0, V_max, n_puntos)
    J_array = resolver_curva_JV(V_array, J0, n_ideal, T_K, Rs_ohm_cm2, Rp_ohm_cm2, JL_local)
    res = calcular_parametros_celda(V_array, J_array, irradiancia_soles)
    res.update(V_array_V=V_array, J_array_A_cm2=J_array, JL_A_cm2=JL_local, J0_A_cm2=J0,
               n_ideal=n_ideal, Rs_ohm_cm2=Rs_ohm_cm2, Rp_ohm_cm2=Rp_ohm_cm2,
               irradiancia_soles=irradiancia_soles)
    return res


def simular_celda_con_malla_frontal(JL_base_A_cm2, J0, T_K, numero_dedos, ancho_dedo_um,
                                     irradiancia_soles=1.0, n_ideal=1.0, Rp_ohm_cm2=c.RP_BASE_OHM_CM2,
                                     n_puntos=400):
    malla = modelo_malla_frontal_plata(numero_dedos, ancho_dedo_um)
    JL_con_sombra = malla["fraccion_iluminada"] * JL_base_A_cm2
    res = simular_celda_JV(JL_con_sombra, J0, T_K, irradiancia_soles, n_ideal,
                            malla["Rs_total_ohm_cm2"], Rp_ohm_cm2, n_puntos)
    res.update(malla)
    res["JL_sin_sombra_A_cm2"] = irradiancia_soles * JL_base_A_cm2
    return res


# ============================================================
# 5) TEMPERATURA
# ============================================================

def Eg_silicio_T(T_K):
    """Eg(T) = 1.206 - 0.000273 T  [eV] (Unidad 4)."""
    return 1.206 - 0.000273 * T_K


def ni_silicio_T(T_K, ni_300K=c.NI_300K):
    Eg_T, Eg_300 = Eg_silicio_T(T_K), Eg_silicio_T(300.0)
    term = -Eg_T / (2.0 * c.K_B_EVK * T_K) + Eg_300 / (2.0 * c.K_B_EVK * 300.0)
    return ni_300K * (T_K / 300.0) ** 1.5 * np.exp(term)


def movilidad_escalada_T(mu_300K, T_K, exponente=c.EXPONENTE_MOVILIDAD_T):
    return mu_300K * (T_K / 300.0) ** exponente


def J0_con_temperatura(T_K, NA, ND, tau_n_us, tau_p_us):
    ni_T = ni_silicio_T(T_K)
    mu_n_T = movilidad_escalada_T(c.MU_N_BASE_P_300K, T_K)
    mu_p_T = movilidad_escalada_T(c.MU_P_EMISOR_N_300K, T_K)
    Dn_T, Dp_T = coef_difusion(T_K, mu_n_T), coef_difusion(T_K, mu_p_T)
    Ln_T, Lp_T = longitud_difusion(Dn_T, tau_n_us), longitud_difusion(Dp_T, tau_p_us)
    J0_T = corriente_saturacion_J0(NA, ND, ni_T, Dn_T, Ln_T, Dp_T, Lp_T)
    return dict(Eg_eV=Eg_silicio_T(T_K), ni_cm3=ni_T, Dn_cm2_s=Dn_T, Dp_cm2_s=Dp_T,
                Ln_cm=Ln_T, Lp_cm=Lp_T, J0_A_cm2=J0_T)


def Voc_analitico_desde_J0(T_K, JL_A_cm2, J0_A_cm2, n_ideal=1.0):
    """Voc = n Vt ln(1+JL/J0)  (diodo ideal iluminado)."""
    Vt = c.K_B_EVK * T_K
    return n_ideal * Vt * np.log1p(JL_A_cm2 / J0_A_cm2)


# ============================================================
# 6) IDENTIFICACIÓN INVERSA / CALIBRACIÓN VIRTUAL
# ============================================================

def ajustar_Sf_tau_n_desde_EQE(wavelength_nm, alpha_cm, R, phi0, EQE_objetivo,
                                xn_um, xp_um, W_um, tau_p_us, Dp, Dn, Sr,
                                Sf_inicial=1e3, tau_n_inicial_us=100.0,
                                reflector_trasero_activo=False,
                                R_aluminio=c.R_ALUMINIO_EFECTIVA):
    """Estima Sf y tau_n a partir de una curva EQE objetivo.

    Es una identificación inversa didáctica: usa regiones azul (380-520 nm)
    y rojo/IR (850-1050 nm), donde esos parámetros dejan firmas distintas.
    Los parámetros se optimizan en escala logarítmica para cubrir varios
    órdenes de magnitud sin sesgo numérico.
    """
    from scipy.optimize import least_squares

    wl = np.asarray(wavelength_nm, dtype=float)
    alpha = np.asarray(alpha_cm, dtype=float)
    R = np.asarray(R, dtype=float)
    phi0 = np.asarray(phi0, dtype=float)
    target = np.asarray(EQE_objetivo, dtype=float)
    mask = ((wl >= 380) & (wl <= 520)) | ((wl >= 850) & (wl <= 1050))
    idx = np.where(mask)[0][::4]
    if len(idx) < 8:
        idx = np.arange(0, len(wl), max(len(wl)//30, 1))

    wl_s, a_s, R_s, p_s, t_s = wl[idx], alpha[idx], R[idx], phi0[idx], target[idx]
    Lp_um = longitud_difusion(Dp, tau_p_us) * 1e4

    def residual(z):
        Sf = 10.0 ** z[0]
        tau_n = 10.0 ** z[1]
        Ln_um = longitud_difusion(Dn, tau_n) * 1e4
        mod, _ = calcular_EQE_IQE_preciso(
            wl_s, a_s, R_s, p_s, xn_um, xp_um, W_um,
            Lp_um, Ln_um, Dp, Dn, Sf, Sr,
            reflector_trasero_activo=reflector_trasero_activo,
            R_aluminio=R_aluminio,
        )
        return (mod - t_s) * 100.0

    x0 = [np.log10(max(Sf_inicial, 10.0)), np.log10(max(tau_n_inicial_us, 0.1))]
    sol = least_squares(residual, x0=x0, bounds=([1.0, -1.0], [6.0, 3.0]), max_nfev=80)
    Sf_fit, tau_fit = 10.0 ** sol.x[0], 10.0 ** sol.x[1]
    Ln_fit_um = longitud_difusion(Dn, tau_fit) * 1e4
    EQE_fit, IQE_fit = calcular_EQE_IQE_preciso(
        wl, alpha, R, phi0, xn_um, xp_um, W_um,
        Lp_um, Ln_fit_um, Dp, Dn, Sf_fit, Sr,
        reflector_trasero_activo=reflector_trasero_activo,
        R_aluminio=R_aluminio,
    )
    rmse = float(np.sqrt(np.mean((EQE_fit - target) ** 2)))
    return dict(Sf_cm_s=Sf_fit, tau_n_us=tau_fit, EQE_fit=EQE_fit, IQE_fit=IQE_fit,
                rmse=rmse, success=bool(sol.success), nfev=int(sol.nfev))


def ajustar_Rs_Rp_n_desde_JV(V_medida, J_medida_A_cm2, J0, T_K, JL_A_cm2,
                              Rs_inicial=0.5, Rp_inicial=1e4, n_inicial=1.1):
    """Estima Rs, Rp y n desde una curva J-V objetivo con JL y J0 fijos.

    JL NO se calibra: proviene de Pestañas 1-2. J0 tampoco es libre: proviene
    de los parámetros del material. Esto reproduce la lógica física del
    enunciado y evita que el ajuste oculte errores ópticos con un JL arbitrario.
    """
    from scipy.optimize import least_squares

    V = np.asarray(V_medida, dtype=float)
    Jt = np.asarray(J_medida_A_cm2, dtype=float)

    def residual(z):
        Rs = 10.0 ** z[0]
        Rp = 10.0 ** z[1]
        n = z[2]
        Jm = resolver_curva_JV(V, J0, n, T_K, Rs, Rp, JL_A_cm2)
        return (Jm - Jt) * 1e3  # residual en mA/cm2

    x0 = [np.log10(max(Rs_inicial, 1e-4)), np.log10(max(Rp_inicial, 10.0)), n_inicial]
    sol = least_squares(residual, x0=x0,
                        bounds=([-4.0, 1.0, 1.0], [1.0, 7.0, 2.0]),
                        max_nfev=70)
    Rs_fit, Rp_fit, n_fit = 10.0 ** sol.x[0], 10.0 ** sol.x[1], sol.x[2]
    J_fit = resolver_curva_JV(V, J0, n_fit, T_K, Rs_fit, Rp_fit, JL_A_cm2)
    rmse_mA = float(np.sqrt(np.mean(((J_fit - Jt) * 1e3) ** 2)))
    return dict(Rs_ohm_cm2=Rs_fit, Rp_ohm_cm2=Rp_fit, n_ideal=n_fit,
                J_fit_A_cm2=J_fit, rmse_mA_cm2=rmse_mA,
                success=bool(sol.success), nfev=int(sol.nfev))
