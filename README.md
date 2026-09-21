# Laboratorio virtual — Celda p-n de silicio (Problema 2.2)

Proyecto 1, **Celdas Solares Fotovoltaicas**, UAI 2026-2. Semilla **S = 3**.

## Objetivo de la interfaz

La aplicación está diseñada como un **instrumento de exploración física**: el usuario modifica parámetros de la celda y observa, en tiempo real, cómo cambian la absorción, la colección de portadores, la eficiencia cuántica y la respuesta eléctrica.

No contiene cuestionarios ni respuestas preparadas. Las animaciones, gráficos y métricas están conectados al mismo estado físico compartido.

## Cómo correrla

```bash
python -m pip install -r requirements.txt
python -m streamlit run app.py
```

## Arquitectura

- `constantes.py`: constantes físicas, parámetros de semilla y valores base.
- `fisica.py`: modelo físico: Beer–Lambert, reflector trasero, transporte, colección, EQE/IQE, diodo implícito, malla frontal y temperatura.
- `app.py`: interfaz Streamlit, estado compartido, gráficos y animaciones.
- `datos/Schinke.csv`: datos medidos n(λ), k(λ) para silicio.
- `datos/astmg173.xls`: espectro ASTM G173 AM1.5G.

## Pestañas

1. **Absorción y Generación** — animación de fotones, G(x,λ), profundidad de absorción, mapa λ–x y balance óptico.
2. **Eficiencia Cuántica** — transporte animado, fc(x), EQE/IQE, inspector espectral y mapa 8×8.
3. **Curva I-V** — formación de la juntura, barrido J-V/P-V animado, flujos de corriente y malla frontal.
4. **Sectores y Defectos** — contaminación y dedo interrumpido con propagación a la respuesta global.
5. **Validación** — verificaciones V1–V7 automáticas.
6. **Resumen animado** — secuencia automática del proceso fotovoltaico completo.

## Modelo físico

- El reflector trasero de Al está conectado a G(x,λ), EQE/IQE, JL y la curva I-V mediante una reflexión trasera.
- La zona de depleción sigue la definición del enunciado: `xn = xj - Wdep/2`, `xp = xj + Wdep/2`.
- La contaminación reduce τn local y afecta la colección; un dedo roto se modela como defecto resistivo y aumenta Rs, sin convertir artificialmente el sector en una zona de baja IQE.
- La ecuación I-V se resuelve numéricamente de forma implícita.

## Librerías

| Librería | Uso |
|---|---|
| NumPy | mallas, integrales y cálculo numérico |
| SciPy | búsqueda de raíces para la ecuación implícita I-V |
| Pandas | lectura de datos ópticos y espectrales |
| Plotly | gráficos interactivos 2D/3D y animaciones |
| Streamlit | interfaz web y `session_state` |
| HTML5 Canvas / JavaScript | animaciones continuas de fotones y portadores |
