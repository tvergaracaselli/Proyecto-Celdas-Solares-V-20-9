# -*- coding: utf-8 -*-
"""
constantes.py
Único módulo de constantes físicas y parámetros del curso.
Cada constante declara su unidad y su fuente (CODATA o Anexo B del
enunciado "Proyecto 1 - Celdas Solares Fotovoltaicas", UAI 2026-2).
No se aceptan números arbitrarios dispersos en el código: todo lo que
aparece en fisica.py o app.py que sea una constante física vive aquí.
"""

# ---------------- CONSTANTES FISICAS UNIVERSALES (CODATA) ----------------
Q = 1.602176634e-19          # Carga del electrón [C]
K_B_JK = 1.380649e-23        # Constante de Boltzmann [J/K]
K_B_EVK = 8.6173e-5          # Constante de Boltzmann [eV/K]  (Anexo B, U2)
H_PLANCK = 6.62607015e-34    # Constante de Planck [J*s]
C_LUZ = 2.99792458e8         # Velocidad de la luz en el vacío [m/s]
EPS0 = 8.854e-14             # Permitividad del vacío [F/cm]
EPS_R_SI = 11.7              # Permitividad relativa del silicio [adimensional]
EPS_SI = EPS_R_SI * EPS0     # Permitividad del silicio [F/cm]

# ---------------- VALORES DE REFERENCIA DEL CURSO (Anexo B) ----------------
NI_300K = 1.0e10             # Concentración intrínseca del Si a 300 K [cm^-3] (U2)
EG_SI_300K = 1.12            # Banda prohibida del Si a 300 K [eV] (U4, valor canónico)
CN_PLUS_CP = 4.0e-31         # Coeficiente Auger cn+cp [cm^6/s] (U4)
B_RADIATIVO = 4.73e-15       # Coeficiente radiativo del Si [cm^3/s] (U4)
IRRADIANCIA_AM15G = 100e-3   # Irradiancia AM1.5G de referencia [W/cm^2] = 100 mW/cm^2 (U3)
JSC_MAX_SI = 43.5            # Densidad de corriente máxima teórica para Si [mA/cm^2] (U4)
VOC_LIMITE_AUGER_100UM = 0.785  # VOC límite por Auger, W=100 um [V] (U4)
FF0_IDEAL = 0.86             # Factor de forma ideal de referencia (U4)
EFICIENCIA_LIMITE_SI = 0.293    # Eficiencia límite teórica del Si (U4)
COEF_TEMP_VOC_SI_MV = -2.3   # Coeficiente de temperatura de VOC de referencia [mV/°C] (U4)
R_FRONTAL_SI_DESNUDO = 0.30  # Reflectancia media de Si desnudo bajo AM1.5G (U2)
R_ALUMINIO_EFECTIVA = 0.85 # Reflectancia efectiva del contacto trasero de Al [-]; aproximación declarada para una reflexión trasera

# ---------------- GEOMETRÍA DE LA CELDA (fija por el enunciado 2.2) ----------------
D_N_EMISOR_UM = 5.0          # Espesor del emisor tipo n [um] (enunciado 2.2, fijo)
W_P_BASE_UM_DEFAULT = 100.0  # Espesor por defecto de la base tipo p [um]
W_P_BASE_MIN_UM = 20.0       # Límite inferior del control de espesor de base [um]
W_P_BASE_MAX_UM = 300.0      # Límite superior del control de espesor de base [um]
ANCHO_CELDA_CM = 5.0         # Ancho lateral de la celda, perpendicular a los dedos [cm]

# ---------------- MOVILIDADES DE REFERENCIA (Anexo B, U3) ----------------
MU_N_BASE_P_300K = 1200.0    # Movilidad electrones en base tipo p, NA~1e16 cm^-3 [cm^2/V*s] (U3)
MU_P_EMISOR_N_300K = 60.0    # Movilidad huecos en emisor tipo n+, ND~1e19-1e20 cm^-3 [cm^2/V*s] (U3)
EXPONENTE_MOVILIDAD_T = -2.2 # Exponente de la ley mu(T) = mu(300K)*(T/300)^exp (aprox. dispersión por fonones)

# ---------------- PARÁMETROS ASIGNADOS POR SEMILLA (Anexo A, Tabla A.1, fila S=3) ----------------
# S = (suma últimos 3 dígitos RUT sin DV, de ambos integrantes) mod 10 = 3
SEMILLA_S = 3
NA_BASE_DEFAULT = 1.0e15     # Concentración de aceptores en la base tipo p [cm^-3]
ND_EMISOR_DEFAULT = 2.0e19   # Concentración de donores en el emisor tipo n [cm^-3]
TAU_SRH_VOLUMEN_US_DEFAULT = 500.0   # Vida media SRH de volumen asignada por semilla [us]
S_FRONTAL_CM_S_DEFAULT = 1.0e2       # Velocidad de recombinación superficial frontal [cm/s]
T_OPERACION_C_DEFAULT = 25.0         # Temperatura de operación asignada por semilla [°C]

# Vida media de portador minoritario en el emisor (no fijada por la semilla,
# se declara un valor típico de emisor fuertemente dopado, más corto que el de volumen)
TAU_P_EMISOR_US_DEFAULT = 1.0  # [us], típico de emisores n+ muy dopados (orden de magnitud U3/U4)

# ---------------- MALLA FRONTAL DE DEDOS DE PLATA (valores base) ----------------
NUMERO_DEDOS_BASE = 40
ANCHO_DEDO_BASE_UM = 80.0
RS_BASE_OHM_CM2 = 0.05
RS_REF_DEDOS_OHM_CM2 = 0.50
NUMERO_DEDOS_REFERENCIA = 40
RP_BASE_OHM_CM2 = 1.0e4
